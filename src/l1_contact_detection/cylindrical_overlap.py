"""圆柱 trimmed face 有限域提取与 overlap 计算。

本模块把 CadQuery/OCP 圆柱 face 的 UV 参数域采样到公共圆柱坐标系中，
用于 L1 Cylindrical Contact 判断轴向重叠和周向覆盖。它不做精确 pcurve
布尔运算；采样失败或复杂退化场景应由调用方降级为 bbox fallback。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq
from OCP.gp import gp_Ax1

from src.common.geometry import Vector3, cross, dot, gp_dir_to_tuple, gp_pnt_to_tuple, normalize
from src.common.tolerances import Tolerances

TAU = math.tau


@dataclass(frozen=True, slots=True)
class CylinderFrame:
    """公共圆柱坐标系。

    Args:
        origin: 圆柱轴线上的参考点。
        x_axis: 径向角度 0 的参考方向。
        y_axis: 与 x_axis/z_axis 构成右手系的径向方向。
        z_axis: 圆柱轴线方向。
    """

    origin: Vector3
    x_axis: Vector3
    y_axis: Vector3
    z_axis: Vector3


@dataclass(frozen=True, slots=True)
class CylinderFramePoint:
    """三维点投影到公共圆柱坐标系后的坐标。"""

    axial: float
    angle: float
    radial_distance: float


@dataclass(frozen=True, slots=True)
class CylinderTrimDomain:
    """圆柱 trimmed face 在公共圆柱坐标系下的有限域。

    Args:
        axial_interval: face 在轴线方向上的投影区间。
        angular_intervals: face 的周向覆盖区间，均为 `[0, 2π]` 内普通区间。
        is_full_circle: 是否覆盖完整 360° 周向。
        sample_count: 提取 domain 使用的 U 方向采样数量。
        method: domain 提取方法标识。
    """

    axial_interval: tuple[float, float]
    angular_intervals: list[tuple[float, float]]
    is_full_circle: bool
    sample_count: int
    method: str = "uv_sampled"


@dataclass(frozen=True, slots=True)
class DomainExtractionError:
    """圆柱有限域提取失败的可诊断错误。"""

    reason: str
    detail: str


@dataclass(frozen=True, slots=True)
class DomainExtractionResult:
    """圆柱有限域提取结果，成功时 domain 非空，失败时 error 非空。"""

    domain: CylinderTrimDomain | None
    error: DomainExtractionError | None = None

    @property
    def ok(self) -> bool:
        """返回 domain 是否成功提取。"""
        return self.domain is not None


@dataclass(frozen=True, slots=True)
class IntervalOverlap:
    """一维区间或角度区间的 overlap 结果。"""

    length: float
    ratio: float
    method: str


def build_cylinder_frame(axis: gp_Ax1) -> CylinderFrame:
    """基于圆柱轴线构造稳定的公共圆柱坐标系。

    Args:
        axis: OCP 圆柱轴线。

    Returns:
        CylinderFrame: 以轴线为 z 轴的右手正交坐标系。
    """
    origin = gp_pnt_to_tuple(axis.Location())
    z_axis = normalize(gp_dir_to_tuple(axis.Direction()))
    reference: Vector3 = (0.0, 0.0, 1.0)
    if abs(dot(reference, z_axis)) > 0.95:
        reference = (1.0, 0.0, 0.0)
    x_axis = normalize(cross(reference, z_axis))
    y_axis = normalize(cross(z_axis, x_axis))
    return CylinderFrame(origin=origin, x_axis=x_axis, y_axis=y_axis, z_axis=z_axis)


def project_point_to_cylinder_frame(point: Vector3, frame: CylinderFrame) -> CylinderFramePoint:
    """将三维点转换为公共圆柱坐标系中的轴向、角度和径向距离。

    Args:
        point: 三维点坐标。
        frame: 公共圆柱坐标系。
    """
    delta = (
        float(point[0] - frame.origin[0]),
        float(point[1] - frame.origin[1]),
        float(point[2] - frame.origin[2]),
    )
    axial = dot(delta, frame.z_axis)
    radial = (
        delta[0] - axial * frame.z_axis[0],
        delta[1] - axial * frame.z_axis[1],
        delta[2] - axial * frame.z_axis[2],
    )
    radial_x = dot(radial, frame.x_axis)
    radial_y = dot(radial, frame.y_axis)
    angle = math.atan2(radial_y, radial_x) % TAU
    radial_distance = math.sqrt(radial_x * radial_x + radial_y * radial_y)
    return CylinderFramePoint(axial=float(axial), angle=float(angle), radial_distance=float(radial_distance))


def _linspace(start: float, end: float, count: int) -> list[float]:
    """生成包含起止点的均匀采样序列。"""
    if count <= 1:
        return [float((start + end) / 2.0)]
    step = (end - start) / float(count - 1)
    return [float(start + step * index) for index in range(count)]


def _normalize_angle(angle: float) -> float:
    """将角度归一化到 `[0, 2π)`。"""
    return float(angle % TAU)


def angular_coverage_from_samples(angles: list[float]) -> list[tuple[float, float]]:
    """用最大空隙补集算法把采样角度归一化为普通角度区间。

    Args:
        angles: 已采样得到的角度，单位弧度。

    Returns:
        list[tuple[float, float]]: 若覆盖跨 0/2π，则拆成两个普通区间。
    """
    normalized = sorted(_normalize_angle(angle) for angle in angles)
    if not normalized:
        return []
    unique: list[float] = []
    for angle in normalized:
        if not unique or abs(angle - unique[-1]) > 1e-12:
            unique.append(angle)
    if len(unique) == 1:
        return [(unique[0], unique[0])]

    gaps: list[tuple[float, int]] = []
    for index in range(len(unique)):
        current = unique[index]
        nxt = unique[(index + 1) % len(unique)]
        if index == len(unique) - 1:
            gap = nxt + TAU - current
        else:
            gap = nxt - current
        gaps.append((gap, index))

    _, gap_index = max(gaps, key=lambda item: item[0])
    start = unique[(gap_index + 1) % len(unique)]
    end = unique[gap_index]
    if start <= end:
        return [(start, end)]
    return [(start, TAU), (0.0, end)]


def extract_cylinder_trim_domain(
    face: cq.Face,
    frame: CylinderFrame,
    tolerances: Tolerances,
) -> DomainExtractionResult:
    """基于 UV bounds 与 positionAt 采样提取圆柱有限域。

    Args:
        face: 待提取的 CadQuery 圆柱 face。
        frame: 公共圆柱坐标系。
        tolerances: 几何容差配置。
    """
    try:
        umin, umax, vmin, vmax = (float(value) for value in face.uvBounds())
    except Exception as exc:  # pragma: no cover - 真实 STEP 异常保护
        return DomainExtractionResult(None, DomainExtractionError("uv_bounds_failed", repr(exc)))

    sample_count = max(2, int(tolerances.cylinder_domain_sample_count))
    u_samples = _linspace(umin, umax, sample_count)
    axial_values: list[float] = []
    angular_values: list[float] = []
    v_mid = float((vmin + vmax) / 2.0)

    try:
        for u_value in u_samples:
            for v_value in (vmin, vmax):
                point = face.positionAt(u_value, v_value).toTuple()
                frame_point = project_point_to_cylinder_frame(
                    (float(point[0]), float(point[1]), float(point[2])),
                    frame,
                )
                axial_values.append(frame_point.axial)

            point = face.positionAt(u_value, v_mid).toTuple()
            frame_point = project_point_to_cylinder_frame(
                (float(point[0]), float(point[1]), float(point[2])),
                frame,
            )
            angular_values.append(frame_point.angle)
    except Exception as exc:  # pragma: no cover - 真实 STEP 异常保护
        return DomainExtractionResult(None, DomainExtractionError("position_at_failed", repr(exc)))

    if not axial_values or not angular_values:
        return DomainExtractionResult(None, DomainExtractionError("empty_samples", "未得到有效圆柱 domain 采样点"))

    full_circle_tol = math.radians(float(tolerances.full_circle_angle_tol_deg))
    u_span = abs(umax - umin)
    is_full_circle = u_span >= TAU - full_circle_tol
    angular_intervals = [(0.0, TAU)] if is_full_circle else angular_coverage_from_samples(angular_values)
    domain = CylinderTrimDomain(
        axial_interval=(min(axial_values), max(axial_values)),
        angular_intervals=angular_intervals,
        is_full_circle=is_full_circle,
        sample_count=sample_count,
    )
    return DomainExtractionResult(domain=domain)


def interval_overlap(a: tuple[float, float], b: tuple[float, float], *, method: str) -> IntervalOverlap:
    """计算两个一维区间的重叠长度与比例。

    ratio 使用较短区间长度作为分母，用于判断较短 face 是否被充分覆盖。
    """
    overlap = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    len_a = max(0.0, a[1] - a[0])
    len_b = max(0.0, b[1] - b[0])
    denom = min(len_a, len_b)
    ratio = 0.0 if denom <= 1e-12 else overlap / denom
    return IntervalOverlap(length=float(overlap), ratio=float(ratio), method=method)


def angular_coverage_length(domain: CylinderTrimDomain) -> float:
    """计算圆柱 domain 的周向覆盖长度，单位弧度。"""
    if domain.is_full_circle:
        return TAU
    return float(sum(max(0.0, end - start) for start, end in domain.angular_intervals))


def angular_overlap(domain_a: CylinderTrimDomain, domain_b: CylinderTrimDomain) -> IntervalOverlap:
    """计算两个圆柱有限域的周向 overlap。

    Args:
        domain_a: 第一个圆柱有限域。
        domain_b: 第二个圆柱有限域。
    """
    intervals_a = [(0.0, TAU)] if domain_a.is_full_circle else domain_a.angular_intervals
    intervals_b = [(0.0, TAU)] if domain_b.is_full_circle else domain_b.angular_intervals
    overlap = 0.0
    for start_a, end_a in intervals_a:
        for start_b, end_b in intervals_b:
            overlap += max(0.0, min(end_a, end_b) - max(start_a, start_b))
    coverage_a = angular_coverage_length(domain_a)
    coverage_b = angular_coverage_length(domain_b)
    denom = min(coverage_a, coverage_b)
    ratio = 0.0 if denom <= 1e-12 else overlap / denom
    return IntervalOverlap(length=float(overlap), ratio=float(ratio), method="uv_sampled_common_frame")


def angular_overlap_passes(overlap: IntervalOverlap, tolerances: Tolerances) -> bool:
    """判断周向 overlap 是否同时满足角度和比例阈值。"""
    min_angle = math.radians(float(tolerances.min_circumferential_overlap_deg))
    return overlap.length >= min_angle and overlap.ratio >= tolerances.min_circumferential_overlap_ratio


def cylinder_domain_contains_angle(domain: CylinderTrimDomain, angle: float, *, tol: float = 1e-9) -> bool:
    """判断 fixed angle 是否落入圆柱有限域的周向覆盖内。

    Args:
        domain: 圆柱有限域。
        angle: 公共圆柱坐标系下的角度，单位弧度。
        tol: 角度边界容差，单位弧度。
    """
    if domain.is_full_circle:
        return True
    normalized = _normalize_angle(angle)
    for start, end in domain.angular_intervals:
        if start - tol <= normalized <= end + tol:
            return True
        if abs(end - TAU) <= tol and normalized <= tol:
            return True
        if start <= tol and abs(normalized - TAU) <= tol:
            return True
    return False
