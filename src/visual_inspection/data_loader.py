"""可视化检查的数据加载与索引构建。

本模块读取已有 L0/L1 JSON 输出，恢复 dataclass 数据结构，并建立
`part_uid`、`face_uid`、`contact_uid` 查询索引。它不导入 ocp_vscode，
因此可在自动测试和无 GUI 环境中安全使用。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.data_models import FaceContact, FaceMetadata, Part
from src.common.exceptions import SerializationError, StepImportError
from src.common.face_reloader import restore_face_map_from_step
from src.common.serialization import read_json_dict, read_l0_json
from src.common.tolerances import Tolerances
from src.l0_face_extraction.l0_output import L0Output
from src.l1_contact_detection.l1_output import L1Output


class VisualInspectionError(ValueError):
    """可视化检查输入或选择无效时抛出。

    Args:
        message: 面向用户的中文错误说明。
    """


@dataclass(slots=True)
class L0InspectionData:
    """L0 可视化检查数据。

    Args:
        l0: 从 L0 JSON 恢复的输出对象。
        parts_by_uid: `part_uid -> Part` 索引。
        faces_by_uid: `face_uid -> FaceMetadata` 索引。
        faces_by_part: `part_uid -> FaceMetadata[]` 索引。
    """

    l0: L0Output
    parts_by_uid: dict[str, Part]
    faces_by_uid: dict[str, FaceMetadata]
    faces_by_part: dict[str, list[FaceMetadata]]


@dataclass(slots=True)
class L1InspectionData:
    """L1 可视化检查数据。

    Args:
        l0_data: L0 检查数据。
        l1: 从 L1 JSON 恢复的输出对象。
        contacts_by_uid: `contact_uid -> FaceContact` 索引。
    """

    l0_data: L0InspectionData
    l1: L1Output
    contacts_by_uid: dict[str, FaceContact]


def _require_file(path: str | Path, *, label: str) -> Path:
    """校验输入文件存在并返回 Path。"""
    resolved = Path(path)
    if not resolved.is_file():
        raise VisualInspectionError(f"{label} 不存在: {resolved}")
    return resolved


def build_l0_inspection_data(l0: L0Output) -> L0InspectionData:
    """从 L0Output 构建查询索引。

    Args:
        l0: 从 JSON 或管道运行期得到的 L0Output。
    """
    parts_by_uid = {part.part_uid: part for part in l0.parts}
    faces_by_uid = {face.face_uid: face for face in l0.faces}
    faces_by_part: dict[str, list[FaceMetadata]] = {}
    for face in l0.faces:
        faces_by_part.setdefault(face.part_uid, []).append(face)
    for values in faces_by_part.values():
        values.sort(key=lambda face: face.part_face_index)
    return L0InspectionData(l0=l0, parts_by_uid=parts_by_uid, faces_by_uid=faces_by_uid, faces_by_part=faces_by_part)


def load_l0_inspection_data(
    l0_json: str | Path,
    *,
    step_file: str | Path | None = None,
    restore_faces: bool = False,
    tolerances: Tolerances | None = None,
) -> L0InspectionData:
    """读取 L0 JSON，并可选恢复运行期 face_map。

    Args:
        l0_json: L0 输出 JSON 路径。
        step_file: 可覆盖 L0 metadata.source_file 的原始 STEP 路径。
        restore_faces: 是否恢复 `face_uid -> cq.Face`。
        tolerances: 可选指纹容差。
    """
    path = _require_file(l0_json, label="L0 JSON")
    try:
        l0 = L0Output.from_dict(read_l0_json(path))
    except SerializationError:
        raise
    except Exception as exc:
        raise VisualInspectionError(f"L0 JSON 解析失败: {path}; error={exc!r}") from exc

    if restore_faces:
        try:
            l0.face_map = restore_face_map_from_step(step_file, l0.parts, l0.faces, l0.metadata, tolerances=tolerances)
        except StepImportError as exc:
            raise VisualInspectionError(str(exc)) from exc
    return build_l0_inspection_data(l0)


def build_l1_inspection_data(l0_data: L0InspectionData, l1: L1Output) -> L1InspectionData:
    """从 L0 检查数据与 L1Output 构建 contact 索引。"""
    contacts_by_uid = {contact.contact_uid: contact for contact in l1.contacts}
    return L1InspectionData(l0_data=l0_data, l1=l1, contacts_by_uid=contacts_by_uid)


def load_l1_inspection_data(
    l0_json: str | Path,
    l1_json: str | Path,
    *,
    step_file: str | Path | None = None,
    restore_faces: bool = False,
    tolerances: Tolerances | None = None,
) -> L1InspectionData:
    """读取 L0/L1 JSON，并可选恢复运行期 face_map。

    Args:
        l0_json: L0 输出 JSON 路径。
        l1_json: L1 输出 JSON 路径。
        step_file: 可覆盖 L0 metadata.source_file 的原始 STEP 路径。
        restore_faces: 是否恢复 `face_uid -> cq.Face`。
        tolerances: 可选指纹容差。
    """
    l0_data = load_l0_inspection_data(l0_json, step_file=step_file, restore_faces=restore_faces, tolerances=tolerances)
    path = _require_file(l1_json, label="L1 JSON")
    try:
        l1 = L1Output.from_dict(read_json_dict(path))
    except SerializationError:
        raise
    except Exception as exc:
        raise VisualInspectionError(f"L1 JSON 解析失败: {path}; error={exc!r}") from exc
    return build_l1_inspection_data(l0_data, l1)


def contact_needs_exact_overlap(contact: FaceContact) -> bool:
    """读取 contact 参数中的 `needs_exact_overlap` 标记。"""
    return bool(contact.parameters.get("needs_exact_overlap", False))


def contact_part_uids(contact: FaceContact, faces_by_uid: dict[str, FaceMetadata]) -> tuple[str, str]:
    """返回 contact 两个 face 对应的 part_uid。

    Args:
        contact: L1 contact。
        faces_by_uid: L0 face 索引。
    """
    try:
        face_a, face_b = contact.face_uid_pair
        return faces_by_uid[face_a].part_uid, faces_by_uid[face_b].part_uid
    except KeyError as exc:
        raise VisualInspectionError(f"L1 contact 引用了 L0 中不存在的 face_uid: {exc.args[0]}") from exc


def contact_summary(contact: FaceContact, faces_by_uid: dict[str, FaceMetadata]) -> dict[str, Any]:
    """构建用于列表显示和测试断言的 contact 摘要。"""
    part_a, part_b = contact_part_uids(contact, faces_by_uid)
    face_a, face_b = contact.face_uid_pair
    return {
        "contact_uid": contact.contact_uid,
        "contact_type": contact.contact_type.value,
        "confidence": contact.confidence,
        "face_uid_pair": list(contact.face_uid_pair),
        "part_uid_pair": [part_a, part_b],
        "geom_type_pair": [faces_by_uid[face_a].geom_type, faces_by_uid[face_b].geom_type],
        "needs_exact_overlap": contact_needs_exact_overlap(contact),
    }
