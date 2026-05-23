"""Planar face contact 判定。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cadquery as cq

from src.common.data_models import ContactType, FaceMetadata
from src.common.geometry import point_plane_distance
from src.common.tolerances import Tolerances

from .geometry_extractors import angle_between_vectors_deg, plane_geometry, projected_bbox_overlap_ratio


@dataclass(frozen=True, slots=True)
class ContactDetection:
    """单个候选 pair 的几何判定结果。"""

    contact_type: ContactType
    confidence: float
    parameters: dict[str, Any]


def detect_planar_contact(
    meta_a: FaceMetadata,
    face_a: cq.Face,
    meta_b: FaceMetadata,
    face_b: cq.Face,
    tolerances: Tolerances,
) -> ContactDetection | None:
    """判断两个 PLANE face 是否构成平面接触。

    Args:
        meta_a: 第一个 face 的 L0 元数据。
        face_a: 第一个 CadQuery Face。
        meta_b: 第二个 face 的 L0 元数据。
        face_b: 第二个 CadQuery Face。
        tolerances: 几何判定容差。
    """
    if meta_a.part_uid == meta_b.part_uid:
        return None

    geom_a = plane_geometry(face_a)
    geom_b = plane_geometry(face_b)
    normal_angle_deg = angle_between_vectors_deg(geom_a.normal, geom_b.normal)
    if abs(180.0 - normal_angle_deg) > tolerances.max_angle_deg:
        return None

    distance = point_plane_distance(geom_a.plane, geom_b.center)
    if distance > tolerances.max_distance_mm:
        return None

    overlap_ratio = projected_bbox_overlap_ratio(face_a, face_b, geom_a.normal)
    if overlap_ratio <= tolerances.bbox_overlap_min_ratio:
        return None

    return ContactDetection(
        contact_type=ContactType.PLANAR,
        confidence=0.9,
        parameters={
            "normal_angle_deg": normal_angle_deg,
            "plane_distance": distance,
            "overlap_ratio": overlap_ratio,
            "overlap_method": "bbox_approx",
            "needs_exact_overlap": True,
        },
    )
