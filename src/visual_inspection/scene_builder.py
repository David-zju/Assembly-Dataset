"""把 L0/L1 选择结果转换为 viewer 场景对象。

本模块不直接调用 ocp_vscode，只构造包含对象、名称、颜色、透明度和角色的
`SceneObject` 列表，便于自动测试和替换 viewer。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import cadquery as cq

from src.common.data_models import FaceContact, FaceMetadata

from .data_loader import L0InspectionData, L1InspectionData, VisualInspectionError, contact_needs_exact_overlap
from .palettes import CONTEXT_ALL, CONTEXT_PART, L0_PART, VisualStyle, style_for_l0_face, style_for_l1_face
from .selectors import require_contact, require_face, require_part, select_part_faces

ContextMode = Literal["none", "part", "all"]


@dataclass(frozen=True, slots=True)
class SceneObject:
    """viewer 可渲染对象描述。

    Args:
        obj: CadQuery/OCP 可渲染对象。
        name: viewer 对象树显示名称。
        role: 语义角色，如 `l1_face_a`。
        color: RGB 颜色。
        alpha: 透明度。
        metadata: 诊断字段，供测试或日志使用。
    """

    obj: Any
    name: str
    role: str
    color: tuple[int, int, int]
    alpha: float
    metadata: dict[str, Any] = field(default_factory=dict)


def _runtime_face(data: L0InspectionData, face_uid: str) -> Any:
    """取得运行期 face 对象。"""
    try:
        return data.l0.face_map[face_uid]
    except KeyError as exc:
        raise VisualInspectionError(f"face_map 中缺少 face_uid，请确认已恢复几何: {face_uid}") from exc


def _style_object(obj: Any, *, name: str, role: str, style: VisualStyle, metadata: dict[str, Any]) -> SceneObject:
    """用样式构造 SceneObject。"""
    return SceneObject(obj=obj, name=name, role=role, color=style.color, alpha=style.alpha, metadata=metadata)


def build_l0_face_scene(data: L0InspectionData, faces: list[FaceMetadata], *, context: ContextMode = "none") -> list[SceneObject]:
    """构建 L0 face 高亮场景。

    Args:
        data: L0 检查数据，必须已恢复 face_map。
        faces: 待高亮 face 元数据。
        context: 上下文模式，`part` 会额外显示相关 Part。
    """
    objects: list[SceneObject] = []
    if context == "part":
        for part_uid in sorted({face.part_uid for face in faces}):
            part = require_part(data, part_uid)
            shape = _part_shape_from_faces(data, part_uid)
            objects.append(
                _style_object(
                    shape,
                    name=f"context {part.part_uid} {part.name}",
                    role="context_part",
                    style=CONTEXT_PART,
                    metadata={"part_uid": part.part_uid},
                )
            )

    for face in faces:
        style = style_for_l0_face(supported=face.supported)
        label = f"{face.face_uid} {face.part_uid} {face.geom_type}"
        if not face.supported:
            label += f" unsupported={face.skip_reason}"
        objects.append(
            _style_object(
                _runtime_face(data, face.face_uid),
                name=label,
                role="l0_face",
                style=style,
                metadata={
                    "face_uid": face.face_uid,
                    "part_uid": face.part_uid,
                    "geom_type": face.geom_type,
                    "supported": face.supported,
                    "skip_reason": face.skip_reason,
                },
            )
        )
    return objects


def build_l0_part_scene(data: L0InspectionData, part_uid: str) -> list[SceneObject]:
    """构建 L0 Part 高亮场景。"""
    part = require_part(data, part_uid)
    shape = _part_shape_from_faces(data, part_uid)
    return [
        _style_object(
            shape,
            name=f"{part.part_uid} {part.name} faces={part.part_face_count}",
            role="l0_part",
            style=L0_PART,
            metadata={"part_uid": part.part_uid, "part_name": part.name, "part_face_count": part.part_face_count},
        )
    ]


def build_l1_contact_scene(data: L1InspectionData, contact_uid: str, *, context: ContextMode = "part") -> list[SceneObject]:
    """构建 L1 contact 高亮场景。

    Args:
        data: L1 检查数据，L0 部分必须已恢复 face_map。
        contact_uid: 待检查 contact UID。
        context: `none` 仅显示两个 face；`part` 显示 parent part；`all` 显示所有 Part 上下文。
    """
    contact = require_contact(data, contact_uid)
    l0_data = data.l0_data
    face_a = require_face(l0_data, contact.face_uid_pair[0])
    face_b = require_face(l0_data, contact.face_uid_pair[1])
    needs_exact = contact_needs_exact_overlap(contact)
    objects: list[SceneObject] = []

    if context == "part":
        for part_uid in sorted({face_a.part_uid, face_b.part_uid}):
            part = require_part(l0_data, part_uid)
            objects.append(
                _style_object(
                    _part_shape_from_faces(l0_data, part_uid),
                    name=f"context {part.part_uid} {part.name}",
                    role="context_part",
                    style=CONTEXT_PART,
                    metadata={"part_uid": part.part_uid, "contact_uid": contact.contact_uid},
                )
            )
    elif context == "all":
        for part_uid, part in l0_data.parts_by_uid.items():
            objects.append(
                _style_object(
                    _part_shape_from_faces(l0_data, part_uid),
                    name=f"context-all {part.part_uid} {part.name}",
                    role="context_all",
                    style=CONTEXT_ALL,
                    metadata={"part_uid": part.part_uid, "contact_uid": contact.contact_uid},
                )
            )

    for index, face in enumerate((face_a, face_b)):
        role = "l1_face_a" if index == 0 else "l1_face_b"
        objects.append(
            _style_object(
                _runtime_face(l0_data, face.face_uid),
                name=_contact_face_label(contact, face, index=index),
                role=role,
                style=style_for_l1_face(index, needs_exact=needs_exact),
                metadata={
                    "contact_uid": contact.contact_uid,
                    "face_uid": face.face_uid,
                    "part_uid": face.part_uid,
                    "contact_type": contact.contact_type.value,
                    "confidence": contact.confidence,
                    "needs_exact_overlap": needs_exact,
                },
            )
        )
    return objects


def _contact_face_label(contact: FaceContact, face: FaceMetadata, *, index: int) -> str:
    """生成 contact face 在对象树中的名称。"""
    side = "A" if index == 0 else "B"
    exact = " needs_exact" if contact_needs_exact_overlap(contact) else ""
    return f"{contact.contact_uid} {contact.contact_type.value} face-{side} {face.face_uid} {face.part_uid} conf={contact.confidence:.2f}{exact}"


def _part_shape_from_faces(data: L0InspectionData, part_uid: str) -> Any:
    """用 Part 下 face 合成可渲染上下文对象。

    当前恢复流程只持有 face_map，不额外保存原始 Part shape。这里把同一 Part
    的 face 合成 Compound，作为上下文对象渲染。
    """
    faces = select_part_faces(data, part_uid)
    if not faces:
        raise VisualInspectionError(f"Part 下没有可显示 face: {part_uid}")
    return cq.Compound.makeCompound([_runtime_face(data, face.face_uid) for face in faces])
