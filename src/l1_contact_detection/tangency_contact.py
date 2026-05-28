"""圆柱面与平面相切接触判定。"""

from __future__ import annotations

import math

import cadquery as cq

from src.common.data_models import ContactType, FaceMetadata
from src.common.geometry import dot, gp_pnt_to_tuple, point_plane_distance
from src.common.tolerances import Tolerances

from .cylindrical_overlap import (
    build_cylinder_frame,
    cylinder_domain_contains_angle,
    extract_cylinder_trim_domain,
    interval_overlap,
    project_point_to_cylinder_frame,
)
from .geometry_extractors import angle_between_vectors_deg, cylinder_geometry, expanded_aabb_intersects, plane_geometry
from .line_overlap import intersect_1d_intervals, line_polygon_intervals, segment_overlap_length
from .planar_overlap import build_plane_frame, extract_plane_trim_domain, project_point_to_plane_frame
from .planar_contact import ContactDetection


def detect_tangency_contact(
    cyl_meta: FaceMetadata,
    cyl_face: cq.Face,
    plane_meta: FaceMetadata,
    plane_face: cq.Face,
    tolerances: Tolerances,
) -> ContactDetection | None:
    """判断 CYLINDER face 与 PLANE face 是否构成切向接触。

    Args:
        cyl_meta: 圆柱 face 元数据。
        cyl_face: 圆柱 CadQuery Face。
        plane_meta: 平面 face 元数据。
        plane_face: 平面 CadQuery Face。
        tolerances: 几何判定容差。
    """
    if cyl_meta.part_uid == plane_meta.part_uid:
        return None

    cyl = cylinder_geometry(cyl_face)
    plane = plane_geometry(plane_face)
    tangent_angle_deg = angle_between_vectors_deg(cyl.axis_dir, plane.normal, unsigned=True)
    if abs(90.0 - tangent_angle_deg) > tolerances.max_axis_angle_deg:
        return None

    distance = point_plane_distance(plane.plane, cyl.axis_location)
    distance_error = abs(distance - cyl.radius)
    if distance_error > tolerances.max_distance_mm:
        return None

    plane_origin = gp_pnt_to_tuple(plane.plane.Location())
    signed_distance = dot(
        (
            cyl.axis_location[0] - plane_origin[0],
            cyl.axis_location[1] - plane_origin[1],
            cyl.axis_location[2] - plane_origin[2],
        ),
        plane.normal,
    )
    tangent_point = (
        cyl.axis_location[0] - signed_distance * plane.normal[0],
        cyl.axis_location[1] - signed_distance * plane.normal[1],
        cyl.axis_location[2] - signed_distance * plane.normal[2],
    )

    plane_frame = build_plane_frame(plane_face)
    plane_domain = extract_plane_trim_domain(plane_face, plane_frame, tolerances)
    cylinder_frame = build_cylinder_frame(cyl.axis)
    cylinder_domain_result = extract_cylinder_trim_domain(cyl_face, cylinder_frame, tolerances)

    if plane_domain.is_supported and cylinder_domain_result.ok:
        cylinder_domain = cylinder_domain_result.domain
        assert cylinder_domain is not None

        plane_line_point = project_point_to_plane_frame(tangent_point, plane_frame).point
        plane_line_end = project_point_to_plane_frame(
            (
                tangent_point[0] + cyl.axis_dir[0],
                tangent_point[1] + cyl.axis_dir[1],
                tangent_point[2] + cyl.axis_dir[2],
            ),
            plane_frame,
        ).point
        plane_line_dir = (plane_line_end[0] - plane_line_point[0], plane_line_end[1] - plane_line_point[1])
        plane_intervals = line_polygon_intervals(plane_line_point, plane_line_dir, plane_domain.outer_polygon)
        if not plane_intervals.supported:
            return None
        if not plane_intervals.intervals:
            return None

        tangent_frame_point = project_point_to_cylinder_frame(tangent_point, cylinder_frame)
        cylinder_angle_supported = cylinder_domain_contains_angle(cylinder_domain, tangent_frame_point.angle)
        if not cylinder_angle_supported:
            return None

        cylinder_interval = cylinder_domain.axial_interval
        finite_intervals = intersect_1d_intervals(plane_intervals.intervals, [cylinder_interval])
        overlap_length = segment_overlap_length(finite_intervals)
        plane_length = segment_overlap_length(plane_intervals.intervals)
        cylinder_length = max(0.0, cylinder_interval[1] - cylinder_interval[0])
        denom = min(plane_length, cylinder_length)
        overlap_ratio = 0.0 if denom <= 1e-12 else overlap_length / denom
        if overlap_length <= tolerances.min_tangency_overlap_length_mm:
            return None
        if overlap_ratio <= tolerances.min_tangency_overlap_ratio:
            return None

        return ContactDetection(
            contact_type=ContactType.TANGENCY,
            confidence=0.9 if not plane_domain.method.endswith("sampled") else 0.85,
            parameters={
                "axis_plane_angle_deg": tangent_angle_deg,
                "axis_plane_distance": distance,
                "radius": cyl.radius,
                "distance_error": distance_error,
                "tangent_overlap_length": overlap_length,
                "tangent_overlap_ratio": overlap_ratio,
                "plane_tangent_interval": list(plane_intervals.intervals[0]),
                "cylinder_axial_interval": list(cylinder_interval),
                "cylinder_tangent_angle_deg": math.degrees(tangent_frame_point.angle),
                "cylinder_angle_supported": cylinder_angle_supported,
                "overlap_method": "trimmed_domain_line_overlap",
                "plane_overlap_method": plane_domain.method,
                "cylinder_overlap_method": cylinder_domain.method,
                "needs_exact_overlap": plane_domain.method != "plane_polygon_clip" or not cylinder_domain.is_full_circle,
            },
        )

    if not expanded_aabb_intersects(cyl_face, plane_face, tolerances.max_distance_mm):
        return None

    return ContactDetection(
        contact_type=ContactType.TANGENCY,
        confidence=0.65,
        parameters={
            "axis_plane_angle_deg": tangent_angle_deg,
            "axis_plane_distance": distance,
            "radius": cyl.radius,
            "distance_error": distance_error,
            "tangent_overlap_length": 0.0,
            "overlap_method": "bbox_fallback",
            "plane_domain_supported": plane_domain.is_supported,
            "plane_domain_error": plane_domain.unsupported_reason,
            "cylinder_domain_error": None if cylinder_domain_result.error is None else cylinder_domain_result.error.reason,
            "needs_exact_overlap": True,
        },
    )
