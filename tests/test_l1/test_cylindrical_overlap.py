"""圆柱有限域 overlap 单元测试。"""

from __future__ import annotations

import math

import cadquery as cq
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.Geom import Geom_CylindricalSurface
from OCP.gp import gp_Ax1, gp_Ax3, gp_Dir, gp_Pnt

from src.common.tolerances import load_tolerances
from src.l1_contact_detection.cylindrical_overlap import (
    angular_coverage_from_samples,
    angular_overlap,
    angular_overlap_passes,
    build_cylinder_frame,
    extract_cylinder_trim_domain,
    interval_overlap,
    project_point_to_cylinder_frame,
)


def _partial_cylinder_face(
    start_deg: float,
    end_deg: float,
    *,
    vmin: float = -5.0,
    vmax: float = 5.0,
    axis_dir: tuple[float, float, float] = (0.0, 0.0, 1.0),
    reversed_orientation: bool = False,
) -> cq.Face:
    """构造测试用局部圆柱 face。"""
    surf = Geom_CylindricalSurface(
        gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(*axis_dir)),
        2.5,
    )
    face = cq.Face(
        BRepBuilderAPI_MakeFace(
            surf,
            math.radians(start_deg),
            math.radians(end_deg),
            vmin,
            vmax,
            1e-7,
        ).Face(),
    )
    if reversed_orientation:
        return cq.Face(face.wrapped.Reversed())
    return face


def test_cylinder_frame_projection_global_and_x_axis() -> None:
    """验证全局 Z 轴和 X 轴圆柱 frame 投影稳定。"""
    z_frame = build_cylinder_frame(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)))
    z_point = project_point_to_cylinder_frame((0.0, -2.5, 4.0), z_frame)
    assert math.isclose(z_point.axial, 4.0, abs_tol=1e-9)
    assert math.isclose(z_point.radial_distance, 2.5, abs_tol=1e-9)
    assert 0.0 <= z_point.angle < math.tau

    x_frame = build_cylinder_frame(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(1, 0, 0)))
    x_point = project_point_to_cylinder_frame((6.0, 0.0, 2.5), x_frame)
    assert math.isclose(x_point.axial, 6.0, abs_tol=1e-9)
    assert math.isclose(x_point.radial_distance, 2.5, abs_tol=1e-9)


def test_extract_domain_full_circle_and_partial_cross_zero() -> None:
    """验证完整圆、U 跨界和公共 frame 跨零局部圆柱片 domain 提取。"""
    tol = load_tolerances()
    full_face = next(face for face in cq.Workplane("XY").circle(2.5).extrude(10).faces().vals() if face.geomType() == "CYLINDER")
    frame = build_cylinder_frame(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)))

    full = extract_cylinder_trim_domain(full_face, frame, tol)
    assert full.ok
    assert full.domain is not None
    assert full.domain.is_full_circle
    assert math.isclose(full.domain.axial_interval[1] - full.domain.axial_interval[0], 10.0, rel_tol=1e-6)

    u_crossing_partial = extract_cylinder_trim_domain(_partial_cylinder_face(350, 370), frame, tol)
    assert u_crossing_partial.ok
    assert u_crossing_partial.domain is not None
    assert not u_crossing_partial.domain.is_full_circle

    frame_crossing_partial = extract_cylinder_trim_domain(_partial_cylinder_face(260, 280), frame, tol)
    assert frame_crossing_partial.ok
    assert frame_crossing_partial.domain is not None
    assert len(frame_crossing_partial.domain.angular_intervals) == 2


def test_angular_coverage_and_overlap_variants() -> None:
    """验证周向覆盖区间、跨零点和完整圆 overlap 计算。"""
    tol = load_tolerances()
    frame = build_cylinder_frame(gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)))
    a = extract_cylinder_trim_domain(_partial_cylinder_face(350, 370), frame, tol).domain
    b = extract_cylinder_trim_domain(_partial_cylinder_face(355, 365), frame, tol).domain
    c = extract_cylinder_trim_domain(_partial_cylinder_face(90, 110), frame, tol).domain
    full_face = next(face for face in cq.Workplane("XY").circle(2.5).extrude(10).faces().vals() if face.geomType() == "CYLINDER")
    full = extract_cylinder_trim_domain(full_face, frame, tol).domain

    assert a is not None and b is not None and c is not None and full is not None
    assert angular_overlap_passes(angular_overlap(a, b), tol)
    assert not angular_overlap_passes(angular_overlap(a, c), tol)
    assert angular_overlap_passes(angular_overlap(full, b), tol)

    intervals = angular_coverage_from_samples([math.radians(350), math.radians(0), math.radians(10)])
    assert len(intervals) == 2


def test_interval_overlap_uses_shorter_interval_denominator() -> None:
    """验证轴向 overlap ratio 使用较短区间作为分母。"""
    overlap = interval_overlap((0.0, 10.0), (2.0, 4.0), method="unit")
    assert math.isclose(overlap.length, 2.0)
    assert math.isclose(overlap.ratio, 1.0)
