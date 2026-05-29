"""L1 几何属性提取辅助函数。

本模块统一封装 CadQuery/OCP face 到 L1 判定所需几何参数的转换。
调用方只需要传入 L0 保留的 `cq.Face`，无需关心 STEP 中曲面是否被
`Geom_RectangularTrimmedSurface` 等 wrapper 包裹。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.gp import gp_Ax1, gp_Pln

from src.common.geometry import Vector3, dot, gp_dir_to_tuple, gp_pnt_to_tuple, normalize
from src.common.spatial_index import AABB


@dataclass(frozen=True, slots=True)
class PlaneGeometry:
    """平面 face 的必要几何属性。"""

    plane: gp_Pln
    normal: Vector3
    center: Vector3


@dataclass(frozen=True, slots=True)
class CylinderGeometry:
    """圆柱 face 的必要几何属性。"""

    axis: gp_Ax1
    axis_dir: Vector3
    axis_location: Vector3
    radius: float
    center: Vector3
    kind: str


def uv_mid(face: cq.Face) -> tuple[float, float]:
    """返回 face UV 参数范围的中点。"""
    umin, umax, vmin, vmax = face.uvBounds()
    return (float(umin + umax) / 2.0, float(vmin + vmax) / 2.0)


def normal_at_mid(face: cq.Face) -> Vector3:
    """获取 face UV 中点处的材料外法向量。"""
    u_mid, v_mid = uv_mid(face)
    normal = face.normalAt(u_mid, v_mid)[0].toTuple()
    return normalize(normal)


def center_of_face(face: cq.Face) -> Vector3:
    """获取 CadQuery face 中心点。"""
    return tuple(float(v) for v in face.Center().toTuple())  # type: ignore[return-value]


def face_aabb(face: cq.Face) -> AABB:
    """从 CadQuery face 构造 AABB。"""
    bbox = face.BoundingBox()
    return AABB(float(bbox.xmin), float(bbox.xmax), float(bbox.ymin), float(bbox.ymax), float(bbox.zmin), float(bbox.zmax))


def unwrapped_surface(face: cq.Face) -> Any:
    """返回 face 的底层几何曲面，剥离 STEP 中常见的 trimmed/offset wrapper。

    Args:
        face: CadQuery face。

    Returns:
        Any: OCP `Geom_Surface` 子类。对 `Geom_RectangularTrimmedSurface`，
        返回其 `BasisSurface()`；若后续遇到多层 wrapper，会继续向内解包。

    Example:
        `surface = unwrapped_surface(face)` 后，可对 PLANE 调用 `surface.Pln()`，
        对 CYLINDER 调用 `surface.Axis()` / `surface.Radius()`。
    """
    surface = BRep_Tool.Surface_s(face.wrapped)
    seen_ids: set[int] = set()
    while hasattr(surface, "BasisSurface"):
        current_id = id(surface)
        if current_id in seen_ids:
            break
        seen_ids.add(current_id)
        basis = surface.BasisSurface()
        if basis is None or basis is surface:
            break
        surface = basis
    return surface


def plane_geometry(face: cq.Face) -> PlaneGeometry:
    """提取平面 face 的 gp_Pln、材料外法向量和中心点。"""
    surface = unwrapped_surface(face)
    return PlaneGeometry(plane=surface.Pln(), normal=normal_at_mid(face), center=center_of_face(face))


def cylinder_kind(face: cq.Face, axis: gp_Ax1) -> str:
    """判断圆柱面是 shaft、hole 还是 unknown。"""
    u_mid, v_mid = uv_mid(face)
    normal = face.normalAt(u_mid, v_mid)[0].toTuple()
    point = face.positionAt(u_mid, v_mid).toTuple()
    axis_loc = axis.Location()
    to_surface = (point[0] - axis_loc.X(), point[1] - axis_loc.Y(), point[2] - axis_loc.Z())
    value = dot(normal, to_surface)
    if value > 1e-9:
        return "shaft"
    if value < -1e-9:
        return "hole"
    return "unknown"


def cylinder_geometry(face: cq.Face) -> CylinderGeometry:
    """提取圆柱 face 的轴线、半径、中心点和内外分类。"""
    surface = unwrapped_surface(face)
    axis = surface.Axis()
    return CylinderGeometry(
        axis=axis,
        axis_dir=gp_dir_to_tuple(axis.Direction()),
        axis_location=gp_pnt_to_tuple(axis.Location()),
        radius=float(surface.Radius()),
        center=center_of_face(face),
        kind=cylinder_kind(face, axis),
    )


def angle_between_vectors_deg(a: Vector3, b: Vector3, *, unsigned: bool = False) -> float:
    """计算两个向量夹角，单位度。"""
    a_norm = normalize(a)
    b_norm = normalize(b)
    value = dot(a_norm, b_norm)
    if unsigned:
        value = abs(value)
    value = max(-1.0, min(1.0, value))
    return math.degrees(math.acos(value))


def projected_bbox_overlap_ratio(face_a: cq.Face, face_b: cq.Face, normal: Vector3) -> float:
    """在主投影平面上用 2D bbox 近似计算重叠比例。

    Args:
        face_a: 第一个平面 face。
        face_b: 第二个平面 face。
        normal: 平面法向量，用于选择被丢弃的主轴。
    """
    drop_axis = max(range(3), key=lambda index: abs(normal[index]))
    keep_axes = [axis for axis in range(3) if axis != drop_axis]

    def intervals(face: cq.Face) -> tuple[tuple[float, float], tuple[float, float]]:
        box = face_aabb(face)
        bounds = [(box.xmin, box.xmax), (box.ymin, box.ymax), (box.zmin, box.zmax)]
        return bounds[keep_axes[0]], bounds[keep_axes[1]]

    (a0, a1), (a2, a3) = intervals(face_a)
    (b0, b1), (b2, b3) = intervals(face_b)
    overlap_x = max(0.0, min(a1, b1) - max(a0, b0))
    overlap_y = max(0.0, min(a3, b3) - max(a2, b2))
    overlap_area = overlap_x * overlap_y
    area_a = max(0.0, a1 - a0) * max(0.0, a3 - a2)
    area_b = max(0.0, b1 - b0) * max(0.0, b3 - b2)
    denom = min(area_a, area_b)
    if denom <= 1e-12:
        return 1.0 if overlap_x > 0.0 or overlap_y > 0.0 else 0.0
    return overlap_area / denom


def axis_bbox_interval(face: cq.Face, axis: gp_Ax1) -> tuple[float, float]:
    """用 face AABB 的 8 个角点估算其在轴线方向上的投影区间。"""
    box = face_aabb(face)
    origin = gp_pnt_to_tuple(axis.Location())
    direction = gp_dir_to_tuple(axis.Direction())
    points = [
        (x, y, z)
        for x in (box.xmin, box.xmax)
        for y in (box.ymin, box.ymax)
        for z in (box.zmin, box.zmax)
    ]
    values = [dot((point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]), direction) for point in points]
    return min(values), max(values)


def interval_overlap_ratio(a: tuple[float, float], b: tuple[float, float]) -> tuple[float, float]:
    """计算两个一维区间的重叠长度和相对重叠比例。"""
    overlap = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    len_a = max(0.0, a[1] - a[0])
    len_b = max(0.0, b[1] - b[0])
    denom = min(len_a, len_b)
    ratio = 0.0 if denom <= 1e-12 else overlap / denom
    return overlap, ratio


def expanded_aabb_intersects(face_a: cq.Face, face_b: cq.Face, radius: float) -> bool:
    """判断两个 face 的 AABB 在膨胀后是否相交。"""
    return face_aabb(face_a).expanded(radius).intersects(face_aabb(face_b).expanded(radius))
