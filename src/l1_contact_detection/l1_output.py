"""L1 输出结构与 FaceContact 组装。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.common.data_models import FaceContact, FaceMetadata
from src.common.exceptions import StepImportError
from src.common.tolerances import Tolerances, load_tolerances
from src.common.uid_manager import UIDManager
from src.l0_face_extraction.l0_output import L0Output

from .contact_detector import run_l1_detection


@dataclass(slots=True)
class L1Output:
    """L1 可序列化输出。"""

    metadata: dict[str, Any]
    contacts: list[FaceContact]
    per_part_contact_index: dict[str, list[str]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 友好的字典。"""
        return {
            "metadata": self.metadata,
            "contacts": [contact.to_dict() for contact in self.contacts],
            "per_part_contact_index": self.per_part_contact_index,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "L1Output":
        """从字典恢复 L1Output。"""
        return cls(
            metadata=dict(data.get("metadata", {})),
            contacts=[FaceContact.from_dict(item) for item in data.get("contacts", [])],
            per_part_contact_index={str(k): [str(v) for v in values] for k, values in data.get("per_part_contact_index", {}).items()},
        )


def build_per_part_contact_index(
    contacts: list[FaceContact],
    faces_by_uid: dict[str, FaceMetadata],
) -> dict[str, list[str]]:
    """构建 `part_uid -> contact_uid[]` 快速索引。"""
    index: dict[str, list[str]] = {}
    for contact in contacts:
        part_uids = [faces_by_uid[face_uid].part_uid for face_uid in contact.face_uid_pair]
        for part_uid in part_uids:
            index.setdefault(part_uid, []).append(contact.contact_uid)
    return index


def build_l1_output(
    l0_output: L0Output,
    *,
    uid_manager: UIDManager | None = None,
    tolerances: Tolerances | None = None,
) -> L1Output:
    """从 L0Output 构建 L1 FaceContact 输出。

    Args:
        l0_output: L0 输出，必须包含运行期 face_map。
        uid_manager: 可选 UID 管理器，用于 contact_uid 分配。
        tolerances: 可选几何容差。
    """
    if not bool(l0_output.metadata.get("part_boundary_reliable", False)):
        raise StepImportError("L0 Part 边界不可靠，拒绝执行 L1 跨 Part 接触检测")
    if not l0_output.face_map:
        raise StepImportError("L1 需要 face_uid -> cq.Face 运行期映射")

    tol = tolerances or load_tolerances()
    uids = uid_manager or UIDManager()
    detection_run = run_l1_detection(l0_output.faces, l0_output.face_map, tol)
    contacts: list[FaceContact] = []
    for candidate, detection in detection_run.contacts:
        pair = tuple(sorted((candidate.face_uid_a, candidate.face_uid_b)))
        contacts.append(
            FaceContact(
                contact_uid=uids.next_contact_uid(),
                face_uid_pair=pair,  # type: ignore[arg-type]
                contact_type=detection.contact_type,
                confidence=detection.confidence,
                parameters=detection.parameters,
            )
        )

    faces_by_uid = {face.face_uid: face for face in l0_output.faces}
    index = build_per_part_contact_index(contacts, faces_by_uid)
    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "num_candidates": len(detection_run.candidates),
        "num_contacts": len(contacts),
        "supported_face_count": detection_run.classification.supported_count,
        "unsupported_face_count": detection_run.classification.unsupported_count,
        "type_distribution": detection_run.classification.type_distribution,
    }
    return L1Output(metadata=metadata, contacts=contacts, per_part_contact_index=index)
