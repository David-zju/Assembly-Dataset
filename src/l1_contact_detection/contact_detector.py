"""L1 接触检测统一入口。"""

from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq

from src.common.data_models import FaceMetadata
from src.common.tolerances import Tolerances, load_tolerances

from .candidate_generator import CandidatePair, generate_candidate_pairs
from .cylindrical_contact import detect_cylindrical_contact
from .face_classifier import FaceClassification, classify_faces
from .planar_contact import ContactDetection, detect_planar_contact
from .tangency_contact import detect_tangency_contact


@dataclass(slots=True)
class DetectionRun:
    """L1 几何判定阶段的运行结果。"""

    contacts: list[tuple[CandidatePair, ContactDetection]]
    candidates: list[CandidatePair]
    classification: FaceClassification


def detect_contact_for_pair(
    meta_a: FaceMetadata,
    face_a: cq.Face,
    meta_b: FaceMetadata,
    face_b: cq.Face,
    tolerances: Tolerances,
) -> ContactDetection | None:
    """按 geom_type 组合路由到具体接触判定器。"""
    type_a = meta_a.geom_type.upper()
    type_b = meta_b.geom_type.upper()
    if type_a == "PLANE" and type_b == "PLANE":
        return detect_planar_contact(meta_a, face_a, meta_b, face_b, tolerances)
    if type_a == "CYLINDER" and type_b == "CYLINDER":
        return detect_cylindrical_contact(meta_a, face_a, meta_b, face_b, tolerances)
    if type_a == "CYLINDER" and type_b == "PLANE":
        return detect_tangency_contact(meta_a, face_a, meta_b, face_b, tolerances)
    if type_a == "PLANE" and type_b == "CYLINDER":
        return detect_tangency_contact(meta_b, face_b, meta_a, face_a, tolerances)
    return None


def run_l1_detection(
    faces: list[FaceMetadata],
    face_map: dict[str, cq.Face],
    tolerances: Tolerances | None = None,
) -> DetectionRun:
    """执行 L1 面分类、候选生成和几何接触判定。

    Args:
        faces: L0 face 元数据列表。
        face_map: `face_uid -> cq.Face` 运行期映射。
        tolerances: 可选几何容差。
    """
    tol = tolerances or load_tolerances()
    classification = classify_faces(faces)
    candidates = generate_candidate_pairs(faces, tol)
    by_uid = {face.face_uid: face for face in faces}
    contacts: list[tuple[CandidatePair, ContactDetection]] = []
    for candidate in candidates:
        meta_a = by_uid[candidate.face_uid_a]
        meta_b = by_uid[candidate.face_uid_b]
        detection = detect_contact_for_pair(
            meta_a,
            face_map[candidate.face_uid_a],
            meta_b,
            face_map[candidate.face_uid_b],
            tol,
        )
        if detection is not None:
            contacts.append((candidate, detection))
    return DetectionRun(contacts=contacts, candidates=candidates, classification=classification)
