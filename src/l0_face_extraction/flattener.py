"""CadQuery Assembly 扁平化。

本模块只处理 L0 的 Part manifest 和运行期 shape 映射：递归展开装配树，
把每个带几何的 leaf component 转换为一个独立 Part 实例，并记录其根坐标系
变换矩阵。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cadquery as cq
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from src.common.data_models import ImportStrategy, Part
from src.common.geometry import Matrix4x4
from src.common.uid_manager import UIDManager

from .encoding_recovery import recover_part_name


@dataclass(slots=True)
class ImportedStep:
    """STEP 导入后的运行期数据。

    Args:
        source_file: STEP 文件路径。
        parts: 扁平化后的 Part manifest。
        part_shapes: `part_uid -> cq.Shape` 的运行期几何映射，shape 已位于根坐标系。
        import_strategy: 实际使用的导入策略。
        part_boundary_reliable: Part 边界是否可靠，可否执行 L1 跨 Part 检测。
        diagnostics: 导入过程中的辅助诊断信息。
    """

    source_file: Path
    parts: list[Part]
    part_shapes: dict[str, Any]
    import_strategy: ImportStrategy
    part_boundary_reliable: bool
    diagnostics: dict[str, Any] = field(default_factory=dict)


def count_faces(shape: Any) -> int:
    """用 TopExp_Explorer 统计 shape 中的拓扑 face 数量。

    Args:
        shape: CadQuery Shape/Solid/Compound，需提供 `.wrapped`。
    """
    explorer = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    count = 0
    while explorer.More():
        count += 1
        explorer.Next()
    return count


def location_to_matrix(location: cq.Location) -> Matrix4x4:
    """将 CadQuery Location 转为 4x4 齐次矩阵。

    Args:
        location: CadQuery Location 对象。
    """
    trsf = location.wrapped.Transformation()
    return [
        [float(trsf.Value(1, 1)), float(trsf.Value(1, 2)), float(trsf.Value(1, 3)), float(trsf.Value(1, 4))],
        [float(trsf.Value(2, 1)), float(trsf.Value(2, 2)), float(trsf.Value(2, 3)), float(trsf.Value(2, 4))],
        [float(trsf.Value(3, 1)), float(trsf.Value(3, 2)), float(trsf.Value(3, 3)), float(trsf.Value(3, 4))],
        [0.0, 0.0, 0.0, 1.0],
    ]


def flatten_assembly(assembly: cq.Assembly, uid_manager: UIDManager | None = None) -> tuple[list[Part], dict[str, Any]]:
    """递归展开 CadQuery Assembly 为扁平 Part 列表。

    Args:
        assembly: `cq.Assembly.load()` 返回的装配体。
        uid_manager: 可选 UID 管理器；为空时创建新的管理器。

    Returns:
        tuple[list[Part], dict[str, Any]]: Part manifest 和运行期 `part_uid -> shape` 映射。
    """
    uids = uid_manager or UIDManager()
    parts: list[Part] = []
    part_shapes: dict[str, Any] = {}
    definition_uids: dict[tuple[str, int], str] = {}

    def walk(node: cq.Assembly, parent_path: str, parent_loc: cq.Location) -> None:
        for child_index, child in enumerate(getattr(node, "children", []) or [], start=1):
            raw_name = getattr(child, "name", "") or ""
            child_path_name = raw_name or f"child_{child_index}"
            assembly_path = f"{parent_path}/{child_index}:{child_path_name}"
            child_loc = parent_loc * getattr(child, "loc", cq.Location())
            child_obj = getattr(child, "obj", None)
            child_children = getattr(child, "children", []) or []

            if child_obj is not None and not child_children:
                face_count = count_faces(child_obj)
                if face_count > 0:
                    part_uid = uids.next_part_uid()
                    part_seq = int(part_uid.split("-")[1])
                    recovered_name = recover_part_name(raw_name, part_seq)
                    definition_key = (recovered_name, face_count)
                    source_definition_uid = definition_uids.setdefault(
                        definition_key,
                        f"def-{len(definition_uids) + 1:04d}",
                    )
                    located_shape = child_obj.located(child_loc)
                    part = Part(
                        part_uid=part_uid,
                        name=recovered_name,
                        assembly_path=assembly_path,
                        source_definition_uid=source_definition_uid,
                        root_transform=location_to_matrix(child_loc),
                        part_face_count=face_count,
                        part_boundary_reliable=True,
                    )
                    parts.append(part)
                    part_shapes[part_uid] = located_shape

            walk(child, assembly_path, child_loc)

    root_loc = getattr(assembly, "loc", cq.Location())
    walk(assembly, "root", root_loc)
    return parts, part_shapes


def build_synthetic_import(
    source_file: str | Path,
    shape: Any,
    uid_manager: UIDManager | None = None,
) -> ImportedStep:
    """为 importStep fallback 构建单个 synthetic Part。

    Args:
        source_file: STEP 文件路径。
        shape: importStep 读取出的整体几何 shape。
        uid_manager: 可选 UID 管理器。
    """
    uids = uid_manager or UIDManager()
    part_uid = uids.next_part_uid()
    face_count = count_faces(shape)
    part = Part(
        part_uid=part_uid,
        name=Path(source_file).stem or "synthetic_part",
        assembly_path="import_step_fallback/synthetic_part",
        source_definition_uid="def-synthetic-0001",
        root_transform=location_to_matrix(cq.Location()),
        part_face_count=face_count,
        part_boundary_reliable=False,
    )
    return ImportedStep(
        source_file=Path(source_file),
        parts=[part],
        part_shapes={part_uid: shape},
        import_strategy=ImportStrategy.IMPORT_STEP_FALLBACK,
        part_boundary_reliable=False,
        diagnostics={"synthetic_part": True, "face_count": face_count},
    )
