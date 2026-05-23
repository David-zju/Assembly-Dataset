"""Cylindrical face contact 判定。"""

from __future__ import annotations

from typing import Any

import cadquery as cq

from src.common.data_models import ContactType, FaceMetadata
from src.common.geometry import axis_angle_deg, axis_distance
from src.common.tolerances import Tolerances

from .geometry_extractors import axis_bbox_interval, cylinder_geometry, interval_overlap_ratio
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

    interval_a = axis_bbox_interval(face_a, cyl_a.axis)
    interval_b = axis_bbox_interval(face_b, cyl_a.axis)
    overlap_length, overlap_ratio = interval_overlap_ratio(interval_a, interval_b)
    if overlap_ratio <= tolerances.min_overlap_length_ratio:
        return None

    parameters: dict[str, Any] = {
        "axis_angle_deg": angle_deg,
        "axis_distance": radial_distance,
        "radius_a": cyl_a.radius,
        "radius_b": cyl_b.radius,
        "radius_diff_ratio": radius_diff_ratio,
        "kind_a": cyl_a.kind,
        "kind_b": cyl_b.kind,
        "axial_overlap_length": overlap_length,
        "axial_overlap_ratio": overlap_ratio,
        "overlap_method": "axis_interval_bbox",
        "needs_circumferential_check": True,
    }
    return ContactDetection(contact_type=ContactType.CYLINDRICAL, confidence=0.95, parameters=parameters)
