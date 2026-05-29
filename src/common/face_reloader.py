"""跨进程恢复 `face_uid -> cq.Face` 运行期映射。

L0/L1 JSON 只保存 UID、Part/Face 元数据和几何指纹，不保存 CadQuery/OCP
对象。本模块根据原始 STEP 文件重新导入装配体，并利用 L0 的 assembly_path、
part_face_index 与几何指纹恢复可用于可视化和后续诊断的运行期 face 映射。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cadquery as cq
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from src.common.data_models import FaceMetadata, Part
from src.common.exceptions import FingerprintMismatchError, StepImportError
from src.common.fingerprint import compute_face_fingerprint, fingerprints_match
from src.common.tolerances import Tolerances, load_tolerances


def iter_faces(shape: Any) -> list[cq.Face]:
    """用 `TopExp_Explorer` 遍历 shape 的所有 face。

    Args:
        shape: CadQuery Shape/Solid/Compound，需提供 `.wrapped`。

    Returns:
        list[cq.Face]: 按 OCP 拓扑遍历顺序返回的 CadQuery face 列表。
    """
    faces: list[cq.Face] = []
    explorer = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    while explorer.More():
        faces.append(cq.Face(explorer.Current()))
        explorer.Next()
    return faces


def collect_assembly_shapes(assembly: cq.Assembly) -> dict[str, Any]:
    """按 L0 assembly_path 规则收集 leaf Part shape。

    Args:
        assembly: `cq.Assembly.load()` 返回的装配体。

    Returns:
        dict[str, Any]: `assembly_path -> located shape` 映射，shape 已位于根坐标系。
    """
    shapes: dict[str, Any] = {}

    def walk(node: cq.Assembly, parent_path: str, parent_loc: cq.Location) -> None:
        for child_index, child in enumerate(getattr(node, "children", []) or [], start=1):
            raw_name = getattr(child, "name", "") or ""
            child_path_name = raw_name or f"child_{child_index}"
            assembly_path = f"{parent_path}/{child_index}:{child_path_name}"
            child_loc = parent_loc * getattr(child, "loc", cq.Location())
            child_obj = getattr(child, "obj", None)
            child_children = getattr(child, "children", []) or []
            if child_obj is not None and not child_children:
                shapes[assembly_path] = child_obj.located(child_loc)
            walk(child, assembly_path, child_loc)

    walk(assembly, "root", getattr(assembly, "loc", cq.Location()))
    return shapes


def faces_by_part(faces: list[FaceMetadata]) -> dict[str, list[FaceMetadata]]:
    """按 Part 和 part_face_index 排序 face 元数据。

    Args:
        faces: L0 face 元数据。
    """
    result: dict[str, list[FaceMetadata]] = {}
    for face in faces:
        result.setdefault(face.part_uid, []).append(face)
    for values in result.values():
        values.sort(key=lambda face: face.part_face_index)
    return result


def _fingerprint_endpoints_match(l0_faces: list[FaceMetadata], runtime_faces: list[cq.Face], abs_tol: float) -> bool:
    """用首尾指纹快速校验遍历顺序是否一致。"""
    if len(l0_faces) != len(runtime_faces):
        return False
    if not l0_faces:
        return True
    indices = [0] if len(l0_faces) == 1 else [0, len(l0_faces) - 1]
    for index in indices:
        comparison = fingerprints_match(l0_faces[index].fingerprint, compute_face_fingerprint(runtime_faces[index]), abs_tol)
        if not comparison.matches:
            return False
    return True


def _fallback_fingerprint_match(
    l0_faces: list[FaceMetadata],
    runtime_faces: list[cq.Face],
    abs_tol: float,
) -> dict[str, cq.Face]:
    """在单个 Part 内用全量指纹回退匹配 face_uid。"""
    unmatched = list(enumerate(runtime_faces))
    mapping: dict[str, cq.Face] = {}
    for meta in l0_faces:
        matched_index = None
        for list_index, (_runtime_index, runtime_face) in enumerate(unmatched):
            comparison = fingerprints_match(meta.fingerprint, compute_face_fingerprint(runtime_face), abs_tol)
            if comparison.matches:
                matched_index = list_index
                mapping[meta.face_uid] = runtime_face
                break
        if matched_index is None:
            raise FingerprintMismatchError(f"无法通过指纹恢复 face_uid: {meta.face_uid}")
        unmatched.pop(matched_index)
    return mapping


def restore_face_map_from_step(
    step_file: str | Path | None,
    parts: list[Part],
    faces: list[FaceMetadata],
    metadata: dict[str, Any],
    *,
    tolerances: Tolerances | None = None,
) -> dict[str, cq.Face]:
    """重新导入 STEP 并恢复 `face_uid -> cq.Face` 映射。

    Args:
        step_file: 原始 STEP 文件路径；为空时使用 metadata.source_file。
        parts: L0 Part manifest。
        faces: L0 face 元数据列表。
        metadata: L0 metadata，需包含 `part_boundary_reliable` 与 `import_strategy`。
        tolerances: 可选指纹比较容差。

    Returns:
        dict[str, cq.Face]: 可用于可视化和几何诊断的运行期 face 映射。

    Raises:
        StepImportError: STEP/L0 不匹配、Part 边界不可靠或无法恢复 Part。
        FingerprintMismatchError: 指纹无法匹配时抛出。
    """
    if not bool(metadata.get("part_boundary_reliable", False)):
        raise StepImportError("L0 Part 边界不可靠，无法恢复跨 Part 可视化上下文")
    if str(metadata.get("import_strategy", "")) != "assembly_load":
        raise StepImportError("可视化几何恢复仅支持 assembly_load 产生的 L0 输出")

    source_file = Path(step_file or metadata.get("source_file", ""))
    if not source_file.is_file():
        raise StepImportError(f"STEP 文件不存在，无法恢复可视化几何: {source_file}")

    tol = tolerances or load_tolerances()
    assembly = cq.Assembly.load(str(source_file))
    shapes_by_path = collect_assembly_shapes(assembly)
    l0_faces_by_part = faces_by_part(faces)
    face_map: dict[str, cq.Face] = {}

    for part in parts:
        shape = shapes_by_path.get(part.assembly_path)
        if shape is None:
            raise StepImportError(f"无法按 assembly_path 恢复 Part: {part.assembly_path}")
        runtime_faces = iter_faces(shape)
        part_faces = l0_faces_by_part.get(part.part_uid, [])
        if _fingerprint_endpoints_match(part_faces, runtime_faces, tol.fingerprint_abs_tol):
            for meta, runtime_face in zip(part_faces, runtime_faces, strict=True):
                face_map[meta.face_uid] = runtime_face
        else:
            face_map.update(_fallback_fingerprint_match(part_faces, runtime_faces, tol.fingerprint_abs_tol))

    return face_map
