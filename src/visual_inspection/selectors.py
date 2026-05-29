"""L0/L1 可视化检查选择与过滤函数。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

from src.common.data_models import FaceContact, FaceMetadata, Part

from .data_loader import L0InspectionData, L1InspectionData, VisualInspectionError, contact_needs_exact_overlap, contact_part_uids

SortKey = Literal["contact_uid", "confidence", "contact_type"]


@dataclass(frozen=True, slots=True)
class ContactFilter:
    """L1 contact 列表过滤条件。

    Args:
        contact_type: 可选 contact 类型，如 `planar`。
        needs_exact: 可选 `needs_exact_overlap` 状态。
        part_uid: 可选参与 contact 的 Part UID。
        face_uid: 可选参与 contact 的 face UID。
        min_confidence: 可选最小置信度。
        query: 可选文本查询，匹配 contact_uid / part_uid / face_uid。
    """

    contact_type: str | None = None
    needs_exact: bool | None = None
    part_uid: str | None = None
    face_uid: str | None = None
    min_confidence: float | None = None
    query: str | None = None


def require_face(data: L0InspectionData, face_uid: str) -> FaceMetadata:
    """按 face_uid 取得 L0 face 元数据，不存在时抛中文错误。"""
    try:
        return data.faces_by_uid[face_uid]
    except KeyError as exc:
        raise VisualInspectionError(f"未找到 face_uid: {face_uid}") from exc


def require_part(data: L0InspectionData, part_uid: str) -> Part:
    """按 part_uid 取得 Part 元数据，不存在时抛中文错误。"""
    try:
        return data.parts_by_uid[part_uid]
    except KeyError as exc:
        raise VisualInspectionError(f"未找到 part_uid: {part_uid}") from exc


def require_contact(data: L1InspectionData, contact_uid: str) -> FaceContact:
    """按 contact_uid 取得 L1 contact，不存在时抛中文错误。"""
    try:
        return data.contacts_by_uid[contact_uid]
    except KeyError as exc:
        raise VisualInspectionError(f"未找到 contact_uid: {contact_uid}") from exc


def select_faces(data: L0InspectionData, face_uids: Iterable[str]) -> list[FaceMetadata]:
    """按多个 face_uid 选择 face 元数据。"""
    return [require_face(data, face_uid) for face_uid in face_uids]


def select_part_faces(data: L0InspectionData, part_uid: str) -> list[FaceMetadata]:
    """选择某个 Part 下的全部 face。"""
    require_part(data, part_uid)
    return list(data.faces_by_part.get(part_uid, []))


def select_geom_type_faces(data: L0InspectionData, geom_type: str) -> list[FaceMetadata]:
    """选择指定几何类型的 face。"""
    target = geom_type.upper()
    return [face for face in data.l0.faces if face.geom_type.upper() == target]


def select_unsupported_faces(data: L0InspectionData) -> list[FaceMetadata]:
    """选择所有 unsupported face。"""
    return [face for face in data.l0.faces if not face.supported]


def filter_contacts(data: L1InspectionData, criteria: ContactFilter) -> list[FaceContact]:
    """按条件过滤 L1 contacts。

    Args:
        data: L1 检查数据。
        criteria: 过滤条件。
    """
    contacts = list(data.l1.contacts)
    faces_by_uid = data.l0_data.faces_by_uid
    if criteria.contact_type is not None:
        target = criteria.contact_type.lower()
        contacts = [contact for contact in contacts if contact.contact_type.value == target]
    if criteria.needs_exact is not None:
        contacts = [contact for contact in contacts if contact_needs_exact_overlap(contact) is criteria.needs_exact]
    if criteria.face_uid is not None:
        contacts = [contact for contact in contacts if criteria.face_uid in contact.face_uid_pair]
    if criteria.part_uid is not None:
        contacts = [contact for contact in contacts if criteria.part_uid in contact_part_uids(contact, faces_by_uid)]
    if criteria.min_confidence is not None:
        contacts = [contact for contact in contacts if contact.confidence >= criteria.min_confidence]
    if criteria.query:
        query = criteria.query.lower()
        filtered: list[FaceContact] = []
        for contact in contacts:
            part_uids = contact_part_uids(contact, faces_by_uid)
            values = [contact.contact_uid, *contact.face_uid_pair, *part_uids, contact.contact_type.value]
            if any(query in value.lower() for value in values):
                filtered.append(contact)
        contacts = filtered
    return contacts


def sort_contacts(contacts: list[FaceContact], *, sort_key: SortKey = "contact_uid", descending: bool = False) -> list[FaceContact]:
    """排序 L1 contacts。"""
    if sort_key == "confidence":
        key = lambda contact: (contact.confidence, contact.contact_uid)
    elif sort_key == "contact_type":
        key = lambda contact: (contact.contact_type.value, contact.contact_uid)
    else:
        key = lambda contact: contact.contact_uid
    return sorted(contacts, key=key, reverse=descending)
