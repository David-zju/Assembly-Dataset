"""平面有限 domain overlap 单元测试。"""

from __future__ import annotations

import math

import cadquery as cq

from src.common.tolerances import load_tolerances
from src.l1_contact_detection.line_overlap import intersect_1d_intervals, line_polygon_intervals, segment_overlap_length
from src.l1_contact_detection.planar_overlap import (
    build_plane_frame,
    compute_planar_overlap,
    extract_plane_trim_domain,
)


def _top_face_box(x: float, y: float, z: float = 1.0, translate: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> cq.Face:
    """构造 box 顶面。"""
    return cq.Workplane("XY").box(x, y, z).translate(translate).faces(">Z").val()


def test_planar_overlap_full_partial_and_no_overlap() -> None:
    """验证完全重叠、部分重叠和 bbox 相交但实际无面积重叠。"""
    tol = load_tolerances()
    face_a = _top_face_box(10, 10)
    frame = build_plane_frame(face_a)
    domain_a = extract_plane_trim_domain(face_a, frame, tol)
    domain_same = extract_plane_trim_domain(_top_face_box(10, 10), frame, tol)
    domain_partial = extract_plane_trim_domain(_top_face_box(10, 10, translate=(4, 0, 0)), frame, tol)
    domain_touch = extract_plane_trim_domain(_top_face_box(10, 10, translate=(10, 0, 0)), frame, tol)

    full = compute_planar_overlap(domain_a, domain_same, tol)
    partial = compute_planar_overlap(domain_a, domain_partial, tol)
    touch = compute_planar_overlap(domain_a, domain_touch, tol)

    assert math.isclose(full.overlap_ratio, 1.0, rel_tol=1e-9)
    assert 0.0 < partial.overlap_ratio < 1.0
    assert math.isclose(touch.overlap_area, 0.0, abs_tol=1e-9)


def test_planar_overlap_sampled_arc_boundary_supported() -> None:
    """验证 CIRCLE edge 可被采样为平面多边形。"""
    tol = load_tolerances()
    face = cq.Workplane("XY").box(20, 20, 2).edges("|Z").fillet(2).faces(">Z").val()
    frame = build_plane_frame(face)
    domain = extract_plane_trim_domain(face, frame, tol)
    overlap = compute_planar_overlap(domain, domain, tol)

    assert domain.is_supported
    assert domain.method == "plane_polygon_sampled"
    assert overlap.needs_exact_overlap
    assert overlap.overlap_area > 0.0


def test_line_polygon_intervals_and_1d_overlap() -> None:
    """验证直线与凸多边形 interval 以及一维区间交集。"""
    polygon = [(-5.0, -2.0), (5.0, -2.0), (5.0, 2.0), (-5.0, 2.0)]
    result = line_polygon_intervals((0.0, 0.0), (1.0, 0.0), polygon)
    assert result.supported
    assert result.intervals == [(-5.0, 5.0)]
    overlap = intersect_1d_intervals(result.intervals, [(-2.0, 3.0)])
    assert overlap == [(-2.0, 3.0)]
    assert math.isclose(segment_overlap_length(overlap), 5.0)
