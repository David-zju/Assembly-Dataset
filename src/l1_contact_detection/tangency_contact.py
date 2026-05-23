"""圆柱面与平面相切接触判定。"""

from __future__ import annotations

import cadquery as cq

from src.common.data_models import ContactType, FaceMetadata
from src.common.geometry import point_plane_distance
from src.common.tolerances import Tolerances

from .geometry_extractors import angle_between_vectors_deg, cylinder_geometry, expanded_aabb_intersects, plane_geometry
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

    if not expanded_aabb_intersects(cyl_face, plane_face, tolerances.max_distance_mm):
        return None

    return ContactDetection(
        contact_type=ContactType.TANGENCY,
        confidence=0.85,
        parameters={
            "axis_plane_angle_deg": tangent_angle_deg,
            "axis_plane_distance": distance,
            "radius": cyl.radius,
            "distance_error": distance_error,
            "overlap_method": "bbox_approx",
            "needs_exact_overlap": True,
        },
    )
