"""Cylindrical face contact 判定。"""

from __future__ import annotations

import math
from typing import Any

import cadquery as cq

from src.common.data_models import ContactType, FaceMetadata
from src.common.geometry import axis_angle_deg, axis_distance
from src.common.tolerances import Tolerances

from .geometry_extractors import axis_bbox_interval, cylinder_geometry, interval_overlap_ratio
from .cylindrical_overlap import (
    angular_overlap,
    angular_overlap_passes,
    build_cylinder_frame,
    extract_cylinder_trim_domain,
    interval_overlap,
)
from .planar_contact import ContactDetection


def detect_cylindrical_contact(
    meta_a: FaceMetadata,
    face_a: cq.Face,
    meta_b: FaceMetadata,
    face_b: cq.Face,
    tolerances: Tolerances,
) -> ContactDetection | None:
    """判断两个 CYLINDER face 是否构成孔轴圆柱接触。

    Args:
        meta_a: 第一个 face 元数据。
        face_a: 第一个 CadQuery Face。
        meta_b: 第二个 face 元数据。
        face_b: 第二个 CadQuery Face。
        tolerances: 几何判定容差。
    """
    if meta_a.part_uid == meta_b.part_uid:
        return None

    cyl_a = cylinder_geometry(face_a)
    cyl_b = cylinder_geometry(face_b)
    if cyl_a.kind == "unknown" or cyl_b.kind == "unknown" or cyl_a.kind == cyl_b.kind:
        return None

    angle_deg = axis_angle_deg(cyl_a.axis, cyl_b.axis)
    if angle_deg > tolerances.max_axis_angle_deg:
        return None

    radial_distance = axis_distance(cyl_a.axis, cyl_b.axis)
    if radial_distance > tolerances.max_distance_mm:
        return None

    radius_diff_ratio = abs(cyl_a.radius - cyl_b.radius) / max(cyl_a.radius, cyl_b.radius, 1e-12)
    if radius_diff_ratio > tolerances.max_radius_ratio:
        return None

    base_parameters: dict[str, Any] = {
        "axis_angle_deg": angle_deg,
        "axis_distance": radial_distance,
        "radius_a": cyl_a.radius,
        "radius_b": cyl_b.radius,
        "radius_diff_ratio": radius_diff_ratio,
        "kind_a": cyl_a.kind,
        "kind_b": cyl_b.kind,
    }

    frame = build_cylinder_frame(cyl_a.axis)
    domain_a_result = extract_cylinder_trim_domain(face_a, frame, tolerances)
    domain_b_result = extract_cylinder_trim_domain(face_b, frame, tolerances)
    if domain_a_result.ok and domain_b_result.ok:
        domain_a = domain_a_result.domain
        domain_b = domain_b_result.domain
        assert domain_a is not None
        assert domain_b is not None

        axial = interval_overlap(domain_a.axial_interval, domain_b.axial_interval, method="uv_sampled")
        if axial.length <= 0.0 or axial.ratio <= tolerances.min_overlap_length_ratio:
            return None

        circumferential = angular_overlap(domain_a, domain_b)
        if not angular_overlap_passes(circumferential, tolerances):
            return None

        has_local_face = not (domain_a.is_full_circle and domain_b.is_full_circle)
        parameters = {
            **base_parameters,
            "axial_overlap_length": axial.length,
            "axial_overlap_ratio": axial.ratio,
            "axial_overlap_method": axial.method,
            "circumferential_overlap_angle_deg": math.degrees(circumferential.length),
            "circumferential_overlap_ratio": circumferential.ratio,
            "circumferential_overlap_method": circumferential.method,
            "is_full_circle_a": domain_a.is_full_circle,
            "is_full_circle_b": domain_b.is_full_circle,
            "overlap_method": "uv_sampled_common_frame",
            "needs_exact_overlap": has_local_face,
        }
        confidence = 0.95 if not has_local_face else 0.9
        return ContactDetection(contact_type=ContactType.CYLINDRICAL, confidence=confidence, parameters=parameters)

    interval_a = axis_bbox_interval(face_a, cyl_a.axis)
    interval_b = axis_bbox_interval(face_b, cyl_a.axis)
    overlap_length, overlap_ratio = interval_overlap_ratio(interval_a, interval_b)
    if overlap_ratio <= tolerances.min_overlap_length_ratio:
        return None

    parameters = {
        **base_parameters,
        "axial_overlap_length": overlap_length,
        "axial_overlap_ratio": overlap_ratio,
        "axial_overlap_method": "axis_interval_bbox_fallback",
        "circumferential_overlap_angle_deg": 0.0,
        "circumferential_overlap_ratio": 0.0,
        "circumferential_overlap_method": "not_evaluated_fallback",
        "is_full_circle_a": False,
        "is_full_circle_b": False,
        "overlap_method": "axis_interval_bbox_fallback",
        "needs_exact_overlap": True,
        "domain_error_a": None if domain_a_result.error is None else domain_a_result.error.reason,
        "domain_error_b": None if domain_b_result.error is None else domain_b_result.error.reason,
    }
    return ContactDetection(contact_type=ContactType.CYLINDRICAL, confidence=0.65, parameters=parameters)
