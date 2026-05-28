"""平面 trimmed face 的局部 2D domain 提取与 overlap 计算。

本模块将 CadQuery/OCP 平面 face 的 wire/edge 边界投影到局部二维坐标系，
并对简单无孔凸多边形计算面积 overlap。复杂边界会返回 unsupported，
由调用方降级为 bbox fallback。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import cadquery as cq
from OCP.BRepTools import BRepTools_WireExplorer
from OCP.TopAbs import TopAbs_EDGE, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer

from src.common.geometry import Vector3, cross, dot, normalize
from src.common.tolerances import Tolerances

from .geometry_extractors import normal_at_mid

Point2D = tuple[float, float]


@dataclass(frozen=True, slots=True)
class PlaneFrame:
    """平面局部二维坐标系。

    Args:
        origin: 投影原点，通常取 face center。
        x_axis: 局部 U 方向单位向量。
        y_axis: 局部 V 方向单位向量。
        normal: 材料外法向单位向量。
    """

    origin: Vector3
    x_axis: Vector3
    y_axis: Vector3
    normal: Vector3


@dataclass(frozen=True, slots=True)
class PlaneProjection:
    """三维点投影到 PlaneFrame 后的二维坐标和残差。"""

    point: Point2D
    residual: float


@dataclass(frozen=True, slots=True)
class PlaneTrimDomain:
    """平面 face 在局部 2D 坐标中的有限边界。"""

    outer_polygon: list[Point2D]
    holes: list[list[Point2D]] = field(default_factory=list)
    source_edge_types: list[str] = field(default_factory=list)
    method: str = "plane_polygon_clip"
    is_supported: bool = True
    unsupported_reason: str | None = None


@dataclass(frozen=True, slots=True)
class PlanarOverlapResult:
    """两个平面有限域 overlap 计算结果。"""

    overlap_area: float
    overlap_ratio: float
    method: str
    needs_exact_overlap: bool
    supported: bool


def build_plane_frame(face: cq.Face) -> PlaneFrame:
    """使用材料外法向和 face center 构造稳定 PlaneFrame。

    Args:
        face: CadQuery 平面 face。
    """
    origin = tuple(float(value) for value in face.Center().toTuple())
    normal = normal_at_mid(face)
    reference: Vector3 = (1.0, 0.0, 0.0)
    if abs(dot(reference, normal)) > 0.95:
        reference = (0.0, 1.0, 0.0)
    x_axis = normalize(cross(reference, normal))
    y_axis = normalize(cross(normal, x_axis))
    return PlaneFrame(origin=origin, x_axis=x_axis, y_axis=y_axis, normal=normal)


def project_point_to_plane_frame(point: Vector3, frame: PlaneFrame) -> PlaneProjection:
    """将三维点投影到 PlaneFrame 的二维坐标。

    Args:
        point: 三维点坐标。
        frame: 平面局部坐标系。
    """
    delta = (
        float(point[0] - frame.origin[0]),
        float(point[1] - frame.origin[1]),
        float(point[2] - frame.origin[2]),
    )
    return PlaneProjection(
        point=(dot(delta, frame.x_axis), dot(delta, frame.y_axis)),
        residual=abs(dot(delta, frame.normal)),
    )


def polygon_area(points: list[Point2D]) -> float:
    """使用 shoelace formula 计算多边形有向面积。"""
    if len(points) < 3:
        return 0.0
    total = 0.0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        total += point[0] * nxt[1] - nxt[0] * point[1]
    return float(total / 2.0)


def _dedupe_consecutive(points: list[Point2D], *, tol: float = 1e-9) -> list[Point2D]:
    """删除连续重复点，并去掉首尾重复点。"""
    result: list[Point2D] = []
    for point in points:
        if not result or abs(point[0] - result[-1][0]) > tol or abs(point[1] - result[-1][1]) > tol:
            result.append(point)
    if len(result) > 1 and abs(result[0][0] - result[-1][0]) <= tol and abs(result[0][1] - result[-1][1]) <= tol:
        result.pop()
    return result


def _dedupe_all(points: list[Point2D], *, tol: float = 1e-9) -> list[Point2D]:
    """删除全局重复点，保留首次出现的近似坐标。"""
    result: list[Point2D] = []
    for point in points:
        if not any(abs(point[0] - existing[0]) <= tol and abs(point[1] - existing[1]) <= tol for existing in result):
            result.append(point)
    return result


def _sort_points_around_centroid(points: list[Point2D]) -> list[Point2D]:
    """按点集中心的极角排序，适用于凸边界采样点。"""
    unique = _dedupe_all(points)
    if len(unique) < 3:
        return unique
    cx = sum(point[0] for point in unique) / len(unique)
    cy = sum(point[1] for point in unique) / len(unique)
    return sorted(unique, key=lambda point: math.atan2(point[1] - cy, point[0] - cx))


def _is_convex_polygon(points: list[Point2D]) -> bool:
    """检查多边形是否为凸多边形。"""
    if len(points) < 3:
        return False
    sign = 0
    for index, point in enumerate(points):
        nxt = points[(index + 1) % len(points)]
        after = points[(index + 2) % len(points)]
        cross_value = (nxt[0] - point[0]) * (after[1] - nxt[1]) - (nxt[1] - point[1]) * (after[0] - nxt[0])
        if abs(cross_value) <= 1e-9:
            continue
        current_sign = 1 if cross_value > 0.0 else -1
        if sign == 0:
            sign = current_sign
        elif sign != current_sign:
            return False
    return True


def normalize_polygon(points: list[Point2D]) -> list[Point2D]:
    """将多边形顶点顺序规范为逆时针。"""
    polygon = _dedupe_consecutive(points)
    if polygon_area(polygon) < 0.0:
        polygon = list(reversed(polygon))
    return polygon


def _edge_points(edge: cq.Edge, frame: PlaneFrame, tolerances: Tolerances) -> tuple[list[Point2D], str, bool]:
    """将一条 edge 离散化为局部 2D 点列。

    Returns:
        tuple: `(points, edge_type, sampled)`。
    """
    edge_type = str(edge.geomType()).upper()
    if edge_type == "LINE":
        start = edge.startPoint().toTuple()
        end = edge.endPoint().toTuple()
        return (
            [
                project_point_to_plane_frame((float(start[0]), float(start[1]), float(start[2])), frame).point,
                project_point_to_plane_frame((float(end[0]), float(end[1]), float(end[2])), frame).point,
            ],
            edge_type,
            False,
        )
    if edge_type == "CIRCLE":
        count = max(3, int(tolerances.plane_edge_sample_count))
        points: list[Point2D] = []
        for index in range(count + 1):
            parameter = index / float(count)
            point = edge.positionAt(parameter).toTuple()
            points.append(project_point_to_plane_frame((float(point[0]), float(point[1]), float(point[2])), frame).point)
        return points, edge_type, True
    return [], edge_type, False


def extract_plane_trim_domain(face: cq.Face, frame: PlaneFrame, tolerances: Tolerances) -> PlaneTrimDomain:
    """提取平面 face 的局部 2D trimmed domain。

    初始版本支持无孔 LINE 多边形和 CIRCLE edge 采样；复杂边界返回
    `is_supported=False`，由调用方 fallback。
    """
    rings: list[list[Point2D]] = []
    edge_types: list[str] = []
    sampled = False

    exp_w = TopExp_Explorer(face.wrapped, TopAbs_WIRE)
    while exp_w.More():
        wire = cq.Wire(exp_w.Current())
        if not wire.Closed():
            return PlaneTrimDomain([], source_edge_types=edge_types, is_supported=False, unsupported_reason="open_wire")

        ring_points: list[Point2D] = []
        exp_e = BRepTools_WireExplorer(wire.wrapped)
        while exp_e.More():
            edge = cq.Edge(exp_e.Current())
            points, edge_type, edge_sampled = _edge_points(edge, frame, tolerances)
            edge_types.append(edge_type)
            if not points:
                return PlaneTrimDomain([], source_edge_types=edge_types, is_supported=False, unsupported_reason=f"unsupported_edge_{edge_type}")
            sampled = sampled or edge_sampled
            ring_points.extend(points)
            exp_e.Next()

        ring = normalize_polygon(_sort_points_around_centroid(ring_points))
        if len(ring) < 3 or abs(polygon_area(ring)) <= 1e-12:
            return PlaneTrimDomain([], source_edge_types=edge_types, is_supported=False, unsupported_reason="degenerate_ring")
        if not _is_convex_polygon(ring):
            return PlaneTrimDomain(ring, source_edge_types=edge_types, is_supported=False, unsupported_reason="non_convex_polygon")
        rings.append(ring)
        exp_w.Next()

    if not rings:
        return PlaneTrimDomain([], source_edge_types=edge_types, is_supported=False, unsupported_reason="no_wire")

    rings.sort(key=lambda item: abs(polygon_area(item)), reverse=True)
    outer = rings[0]
    holes = rings[1:]
    if holes:
        return PlaneTrimDomain(outer, holes=holes, source_edge_types=edge_types, is_supported=False, unsupported_reason="holes")
    if len(outer) > tolerances.max_plane_polygon_vertices:
        return PlaneTrimDomain(outer, source_edge_types=edge_types, is_supported=False, unsupported_reason="too_many_vertices")

    method = "plane_polygon_sampled" if sampled else "plane_polygon_clip"
    return PlaneTrimDomain(outer, holes=[], source_edge_types=edge_types, method=method, is_supported=True)


def polygon_bbox(points: list[Point2D]) -> tuple[float, float, float, float]:
    """返回二维多边形 bbox: xmin, xmax, ymin, ymax。"""
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), max(xs), min(ys), max(ys)


def _bbox_intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    """判断两个二维 bbox 是否相交。"""
    return not (a[1] < b[0] or b[1] < a[0] or a[3] < b[2] or b[3] < a[2])


def _inside(point: Point2D, edge_start: Point2D, edge_end: Point2D) -> bool:
    """判断点是否在有向边左侧。"""
    return (edge_end[0] - edge_start[0]) * (point[1] - edge_start[1]) - (edge_end[1] - edge_start[1]) * (point[0] - edge_start[0]) >= -1e-9


def _line_intersection(a1: Point2D, a2: Point2D, b1: Point2D, b2: Point2D) -> Point2D:
    """计算两条二维直线交点；近似平行时返回 a2 作为保守兜底。"""
    x1, y1 = a1
    x2, y2 = a2
    x3, y3 = b1
    x4, y4 = b2
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return a2
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return float(px), float(py)


def clip_convex_polygon(subject: list[Point2D], clipper: list[Point2D]) -> list[Point2D]:
    """使用 Sutherland-Hodgman 算法裁剪两个凸多边形。"""
    output = normalize_polygon(subject)
    clip = normalize_polygon(clipper)
    for index, edge_start in enumerate(clip):
        edge_end = clip[(index + 1) % len(clip)]
        input_points = output
        output = []
        if not input_points:
            break
        previous = input_points[-1]
        for current in input_points:
            current_inside = _inside(current, edge_start, edge_end)
            previous_inside = _inside(previous, edge_start, edge_end)
            if current_inside:
                if not previous_inside:
                    output.append(_line_intersection(previous, current, edge_start, edge_end))
                output.append(current)
            elif previous_inside:
                output.append(_line_intersection(previous, current, edge_start, edge_end))
            previous = current
        output = _dedupe_consecutive(output)
    return normalize_polygon(output)


def compute_planar_overlap(
    domain_a: PlaneTrimDomain,
    domain_b: PlaneTrimDomain,
    tolerances: Tolerances,
) -> PlanarOverlapResult:
    """计算两个受支持 PlaneTrimDomain 的面积 overlap。"""
    if not domain_a.is_supported or not domain_b.is_supported:
        return PlanarOverlapResult(0.0, 0.0, "unsupported", True, False)
    if not _bbox_intersects(polygon_bbox(domain_a.outer_polygon), polygon_bbox(domain_b.outer_polygon)):
        return PlanarOverlapResult(0.0, 0.0, domain_a.method if domain_a.method == domain_b.method else "plane_polygon_mixed", False, True)

    intersection = clip_convex_polygon(domain_a.outer_polygon, domain_b.outer_polygon)
    overlap_area = abs(polygon_area(intersection))
    area_a = abs(polygon_area(domain_a.outer_polygon))
    area_b = abs(polygon_area(domain_b.outer_polygon))
    denom = min(area_a, area_b)
    ratio = 0.0 if denom <= 1e-12 else overlap_area / denom
    method = domain_a.method if domain_a.method == domain_b.method else "plane_polygon_mixed"
    needs_exact = method != "plane_polygon_clip"
    return PlanarOverlapResult(overlap_area, ratio, method, needs_exact, True)
