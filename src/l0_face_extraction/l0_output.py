"""L0 输出结构与构建入口。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import cadquery as cq

from src.common.data_models import FaceMetadata, Part
from src.common.uid_manager import UIDManager

if TYPE_CHECKING:
    from .flattener import ImportedStep


@dataclass(slots=True)
class L0Output:
    """L0 可序列化输出和运行期 face 映射。

    Args:
        metadata: 源文件、导入策略、统计信息等元数据。
        parts: Part manifest。
        faces: 所有拓扑 face 的元数据。
        face_map: 运行期 `face_uid -> cq.Face` 映射，不写入 JSON。
    """

    metadata: dict[str, Any]
    parts: list[Part]
    faces: list[FaceMetadata]
    face_map: dict[str, cq.Face] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """序列化为 JSON 友好的字典。"""
        return {
            "metadata": self.metadata,
            "parts": [part.to_dict() for part in self.parts],
            "faces": [face.to_dict() for face in self.faces],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "L0Output":
        """从字典恢复 L0Output；运行期 face_map 为空。"""
        return cls(
            metadata=dict(data.get("metadata", {})),
            parts=[Part.from_dict(item) for item in data.get("parts", [])],
            faces=[FaceMetadata.from_dict(item) for item in data.get("faces", [])],
        )


def build_l0_output(
    imported: ImportedStep,
    *,
    uid_manager: UIDManager | None = None,
    pipeline_version: str = "0.1.0",
) -> L0Output:
    """从 ImportedStep 构建完整 L0 输出。

    Args:
        imported: STEP 导入和扁平化结果。
        uid_manager: 可选 UID 管理器，用于 face_uid 分配。
        pipeline_version: 写入 metadata 的管道版本。
    """
    from .face_traversal import traverse_imported_faces

    traversal = traverse_imported_faces(imported, uid_manager=uid_manager)
    supported_count = sum(1 for face in traversal.faces if face.supported)
    unsupported_count = len(traversal.faces) - supported_count
    metadata = {
        "source_file": str(imported.source_file),
        "pipeline_version": pipeline_version,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "num_parts": len(imported.parts),
        "num_faces": len(traversal.faces),
        "supported_face_count": supported_count,
        "unsupported_face_count": unsupported_count,
        "skipped_face_count": traversal.skipped_face_count,
        "type_distribution": traversal.type_distribution,
        "import_strategy": imported.import_strategy.value,
        "part_boundary_reliable": imported.part_boundary_reliable,
        "diagnostics": imported.diagnostics,
    }
    return L0Output(
        metadata=metadata,
        parts=imported.parts,
        faces=traversal.faces,
        face_map=traversal.face_map,
    )
