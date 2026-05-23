"""核心数据模型。

这些模型只保存 UID、元数据和轻量几何摘要，不复制 CadQuery/OCP 几何体。
真正的几何对象通过运行期 `face_uid -> cq.Face` 映射访问。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class ContactType(StrEnum):
    """L1 支持的 face contact 类型。"""

    PLANAR = "planar"
    CYLINDRICAL = "cylindrical"
    TANGENCY = "tangency"


class ImportStrategy(StrEnum):
    """STEP 导入策略。"""

    ASSEMBLY_LOAD = "assembly_load"
    IMPORT_STEP_FALLBACK = "import_step_fallback"


@dataclass(slots=True)
class FaceFingerprint:
    """face 几何指纹，用于跨进程身份校验。

    Args:
        geom_type: CadQuery Face.geomType() 返回的几何类型。
        area: face 面积。
        center: face 几何中心。
        bbox: AABB，顺序为 xmin, xmax, ymin, ymax, zmin, zmax。
    """

    geom_type: str
    area: float
    center: tuple[float, float, float]
    bbox: tuple[float, float, float, float, float, float]

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 友好的字典。"""
        return {
            "geom_type": self.geom_type,
            "area": self.area,
            "center": list(self.center),
            "bbox": list(self.bbox),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FaceFingerprint":
        """从字典恢复 FaceFingerprint。"""
        return cls(
            geom_type=str(data["geom_type"]),
            area=float(data["area"]),
            center=tuple(float(v) for v in data["center"]),  # type: ignore[arg-type]
            bbox=tuple(float(v) for v in data["bbox"]),  # type: ignore[arg-type]
        )


@dataclass(slots=True)
class Part:
    """装配体扁平化后的 Part 实例。

    Args:
        part_uid: 全局唯一 Part UID。
        name: 零件实例名称。
        assembly_path: Assembly 树中的稳定路径。
        source_definition_uid: 同一零件定义的共享 UID。
        root_transform: Part 到装配根坐标系的 4x4 齐次矩阵。
        part_face_count: Part 内拓扑 face 数量。
        part_boundary_reliable: Part 边界是否来自可靠 Assembly 语义。
    """

    part_uid: str
    name: str
    assembly_path: str
    source_definition_uid: str
    root_transform: list[list[float]]
    part_face_count: int = 0
    part_boundary_reliable: bool = True

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "part_uid": self.part_uid,
            "name": self.name,
            "assembly_path": self.assembly_path,
            "source_definition_uid": self.source_definition_uid,
            "root_transform": self.root_transform,
            "part_face_count": self.part_face_count,
            "part_boundary_reliable": self.part_boundary_reliable,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Part":
        """从字典恢复 Part。"""
        return cls(
            part_uid=str(data["part_uid"]),
            name=str(data.get("name", "")),
            assembly_path=str(data.get("assembly_path", "")),
            source_definition_uid=str(data.get("source_definition_uid", "")),
            root_transform=[[float(v) for v in row] for row in data.get("root_transform", identity_matrix())],
            part_face_count=int(data.get("part_face_count", 0)),
            part_boundary_reliable=bool(data.get("part_boundary_reliable", True)),
        )


@dataclass(slots=True)
class FaceMetadata:
    """L0 输出的 face 标识与支持状态。

    Args:
        face_uid: 全局唯一 face UID。
        part_uid: 所属 Part UID。
        global_face_index: 全局拓扑遍历序号，从 0 开始。
        part_face_index: Part 内拓扑遍历序号，从 0 开始。
        geom_type: face 几何类型。
        supported: 是否参与 L1 接触检测。
        skip_reason: 不参与 L1 的原因。
        fingerprint: 几何指纹。
    """

    face_uid: str
    part_uid: str
    global_face_index: int
    part_face_index: int
    geom_type: str
    supported: bool
    skip_reason: str | None
    fingerprint: FaceFingerprint

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "face_uid": self.face_uid,
            "part_uid": self.part_uid,
            "global_face_index": self.global_face_index,
            "part_face_index": self.part_face_index,
            "geom_type": self.geom_type,
            "supported": self.supported,
            "skip_reason": self.skip_reason,
            "fingerprint": self.fingerprint.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FaceMetadata":
        """从字典恢复 FaceMetadata。"""
        return cls(
            face_uid=str(data["face_uid"]),
            part_uid=str(data["part_uid"]),
            global_face_index=int(data["global_face_index"]),
            part_face_index=int(data["part_face_index"]),
            geom_type=str(data["geom_type"]),
            supported=bool(data["supported"]),
            skip_reason=data.get("skip_reason"),
            fingerprint=FaceFingerprint.from_dict(data["fingerprint"]),
        )


@dataclass(slots=True)
class FaceContact:
    """L1 输出的跨 Part face 接触实体。"""

    contact_uid: str
    face_uid_pair: tuple[str, str]
    contact_type: ContactType
    confidence: float
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        return {
            "contact_uid": self.contact_uid,
            "face_uid_pair": list(self.face_uid_pair),
            "contact_type": self.contact_type.value,
            "confidence": self.confidence,
            "parameters": self.parameters,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FaceContact":
        """从字典恢复 FaceContact。"""
        pair = tuple(str(v) for v in data["face_uid_pair"])
        if len(pair) != 2:
            raise ValueError("face_uid_pair 必须包含两个 face_uid")
        return cls(
            contact_uid=str(data["contact_uid"]),
            face_uid_pair=pair,  # type: ignore[arg-type]
            contact_type=ContactType(str(data["contact_type"])),
            confidence=float(data["confidence"]),
            parameters=dict(data.get("parameters", {})),
        )


def identity_matrix() -> list[list[float]]:
    """返回 4x4 单位矩阵。

    Returns:
        list[list[float]]: 用于 Part.root_transform 的默认矩阵。
    """
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]

