"""L0 B-rep face 遍历、UID 分配与指纹生成。

所有拓扑 face 都必须保留在 L0 输出中；不支持的几何类型只标记
`supported=false`，不得从 face_uid 序列或运行期映射中删除。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cadquery as cq
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from src.common.data_models import FaceMetadata
from src.common.fingerprint import compute_face_fingerprint
from src.common.logging import get_logger
from src.common.uid_manager import UIDManager

from .flattener import ImportedStep

logger = get_logger("l0.face_traversal")

SUPPORTED_GEOM_TYPES = {"PLANE", "CYLINDER", "CONE", "SPHERE", "TORUS"}
UNSUPPORTED_GEOM_TYPES = {"BEZIER", "BSPLINE", "OTHER"}


@dataclass(slots=True)
class TraversalResult:
    """L0 face 遍历结果。

    Args:
        faces: 可序列化 face 元数据，覆盖所有拓扑 face。
        face_map: 运行期 `face_uid -> cq.Face` 映射，覆盖所有拓扑 face。
        type_distribution: 几何类型分布统计。
        skipped_face_count: unsupported face 数量。
    """

    faces: list[FaceMetadata]
    face_map: dict[str, cq.Face]
    type_distribution: dict[str, int]
    skipped_face_count: int


def iter_topology_faces(shape: Any) -> list[cq.Face]:
    """使用 TopExp_Explorer 遍历 shape 的所有拓扑 face。

    Args:
        shape: CadQuery Shape/Solid/Compound，需提供 `.wrapped`。
    """
    faces: list[cq.Face] = []
    explorer = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    while explorer.More():
        faces.append(cq.Face(explorer.Current()))
        explorer.Next()
    return faces


def normalize_geom_type(face: cq.Face) -> str:
    """读取并规范化 CadQuery face 几何类型。"""
    try:
        geom_type = str(face.geomType()).upper()
    except Exception:
        geom_type = "OTHER"
    return geom_type if geom_type else "OTHER"


def is_supported_geom_type(geom_type: str) -> bool:
    """判断 face 类型是否进入 L1 接触检测候选集合。"""
    return geom_type in SUPPORTED_GEOM_TYPES and geom_type not in UNSUPPORTED_GEOM_TYPES


def traverse_imported_faces(imported: ImportedStep, uid_manager: UIDManager | None = None) -> TraversalResult:
    """遍历 ImportedStep 中每个 Part 的所有 face，并分配 face_uid。

    Args:
        imported: STEP 导入后的 Part 与 shape 映射。
        uid_manager: 可选 UID 管理器；应与导入阶段使用同一个实例或全新实例。
    """
    uids = uid_manager or UIDManager()
    faces: list[FaceMetadata] = []
    face_map: dict[str, cq.Face] = {}
    type_distribution: dict[str, int] = {}
    skipped_face_count = 0
    global_index = 0

    for part in imported.parts:
        shape = imported.part_shapes[part.part_uid]
        part_seq = int(part.part_uid.split("-")[1])
        topology_faces = iter_topology_faces(shape)
        part.part_face_count = len(topology_faces)
        for part_face_index, face in enumerate(topology_faces):
            geom_type = normalize_geom_type(face)
            supported = is_supported_geom_type(geom_type)
            skip_reason = None if supported else "unsupported_geom_type"
            if not supported:
                skipped_face_count += 1
                logger.debug("跳过 unsupported face: part=%s index=%s geom=%s", part.part_uid, part_face_index, geom_type)

            face_uid = uids.next_face_uid(part_seq, part_face_index + 1)
            metadata = FaceMetadata(
                face_uid=face_uid,
                part_uid=part.part_uid,
                global_face_index=global_index,
                part_face_index=part_face_index,
                geom_type=geom_type,
                supported=supported,
                skip_reason=skip_reason,
                fingerprint=compute_face_fingerprint(face),
            )
            faces.append(metadata)
            face_map[face_uid] = face
            type_distribution[geom_type] = type_distribution.get(geom_type, 0) + 1
            global_index += 1

    return TraversalResult(
        faces=faces,
        face_map=face_map,
        type_distribution=type_distribution,
        skipped_face_count=skipped_face_count,
    )
