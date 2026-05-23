"""L1 跨进程 face_uid 映射恢复。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cadquery as cq
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer

from src.common.data_models import FaceMetadata
from src.common.exceptions import FingerprintMismatchError, StepImportError
from src.common.fingerprint import compute_face_fingerprint, fingerprints_match
from src.common.tolerances import Tolerances, load_tolerances
from src.l0_face_extraction.l0_output import L0Output


def _iter_faces(shape: Any) -> list[cq.Face]:
    """用 TopExp_Explorer 遍历 shape 的所有 face。"""
    faces: list[cq.Face] = []
    explorer = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    while explorer.More():
        faces.append(cq.Face(explorer.Current()))
        explorer.Next()
    return faces


def _collect_assembly_shapes(assembly: cq.Assembly) -> dict[str, Any]:
    """按 L0 assembly_path 规则收集 leaf Part shape。"""
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


def _faces_by_part(l0_output: L0Output) -> dict[str, list[FaceMetadata]]:
    """按 Part 和 part_face_index 排序 face 元数据。"""
    result: dict[str, list[FaceMetadata]] = {}
    for face in l0_output.faces:
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


def restore_l0_face_map_from_step(
    l0_output: L0Output,
    step_file: str | Path | None = None,
    *,
    tolerances: Tolerances | None = None,
) -> L0Output:
    """重新导入 STEP，并为 L0Output 恢复 `face_uid -> cq.Face` 映射。

    Args:
        l0_output: 从 L0 JSON 恢复的数据结构。
        step_file: 可覆盖 metadata.source_file 的 STEP 路径。
        tolerances: 指纹校验容差。
    """
    if not bool(l0_output.metadata.get("part_boundary_reliable", False)):
        raise StepImportError("L0 Part 边界不可靠，拒绝恢复 L1 跨 Part face 映射")
    if str(l0_output.metadata.get("import_strategy", "")) != "assembly_load":
        raise StepImportError("L1 独立加载仅支持 assembly_load 产生的 L0 输出")

    tol = tolerances or load_tolerances()
    source_file = Path(step_file or l0_output.metadata.get("source_file", ""))
    assembly = cq.Assembly.load(str(source_file))
    shapes_by_path = _collect_assembly_shapes(assembly)
    l0_faces_by_part = _faces_by_part(l0_output)
    face_map: dict[str, cq.Face] = {}

    for part in l0_output.parts:
        shape = shapes_by_path.get(part.assembly_path)
        if shape is None:
            raise StepImportError(f"无法按 assembly_path 恢复 Part: {part.assembly_path}")
        runtime_faces = _iter_faces(shape)
        part_faces = l0_faces_by_part.get(part.part_uid, [])
        if _fingerprint_endpoints_match(part_faces, runtime_faces, tol.fingerprint_abs_tol):
            for meta, runtime_face in zip(part_faces, runtime_faces, strict=True):
                face_map[meta.face_uid] = runtime_face
        else:
            face_map.update(_fallback_fingerprint_match(part_faces, runtime_faces, tol.fingerprint_abs_tol))

    l0_output.face_map = face_map
    return l0_output
