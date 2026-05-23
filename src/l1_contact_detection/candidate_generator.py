"""L1 broad phase 候选 face pair 生成。"""

from __future__ import annotations

from dataclasses import dataclass

from src.common.data_models import FaceMetadata
from src.common.spatial_index import AABB, AABBItem, build_bvh, query_intersecting_pairs
from src.common.tolerances import Tolerances, load_tolerances


@dataclass(frozen=True, slots=True)
class CandidatePair:
    """BVH 生成的无序候选 face pair。"""

    face_uid_a: str
    face_uid_b: str


def _item_from_face(face: FaceMetadata, search_radius: float) -> AABBItem:
    """将 FaceMetadata 转为 expanded AABB 条目。"""
    bbox = AABB.from_tuple(face.fingerprint.bbox).expanded(search_radius)
    return AABBItem(face_uid=face.face_uid, part_uid=face.part_uid, geom_type=face.geom_type, bbox=bbox)


def generate_candidate_pairs(
    faces: list[FaceMetadata],
    tolerances: Tolerances | None = None,
) -> list[CandidatePair]:
    """基于 expanded AABB + BVH 保守生成跨 Part 候选 face pair。

    Args:
        faces: L0 face 元数据列表，只有 supported face 会进入索引。
        tolerances: 几何容差和 BVH 参数；为空时读取默认配置。
    """
    tol = tolerances or load_tolerances()
    items = [_item_from_face(face, tol.search_radius) for face in faces if face.supported]
    if len(items) < 2:
        return []

    root = build_bvh(items, leaf_size=tol.bvh_leaf_size, max_depth=tol.bvh_max_depth)
    raw_pairs = query_intersecting_pairs(root)
    return [CandidatePair(a.face_uid, b.face_uid) for a, b in raw_pairs]
