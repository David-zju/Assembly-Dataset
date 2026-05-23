"""STEP 文件导入入口。

正式装配体导入使用 `cq.Assembly.load()` 保留 Part 边界；`cq.importers.importStep()`
只作为几何诊断兜底，兜底结果必须标记为 Part 边界不可靠。
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

import cadquery as cq

from src.common.data_models import ImportStrategy
from src.common.exceptions import StepImportError
from src.common.logging import get_logger
from src.common.uid_manager import UIDManager

from .flattener import ImportedStep, build_synthetic_import, count_faces, flatten_assembly

logger = get_logger("l0.step_importer")


def _combine_import_step_shapes(values: list[Any]) -> Any:
    """把 importStep 返回的顶层 shape 合并为一个诊断 shape。"""
    if not values:
        raise StepImportError("importStep 未返回任何 shape")
    if len(values) == 1:
        return values[0]
    return cq.Compound.makeCompound(values)


def import_step_file(
    step_file: str | Path,
    *,
    allow_import_step_fallback: bool = True,
    uid_manager: UIDManager | None = None,
) -> ImportedStep:
    """导入 STEP 文件并生成 L0 可用的 Part 运行期数据。

    Args:
        step_file: `.step` / `.stp` 文件路径。
        allow_import_step_fallback: Assembly.load 失败时是否允许 importStep 诊断兜底。
        uid_manager: 可选 UID 管理器，用于生成 Part UID。

    Raises:
        StepImportError: 文件不存在、后缀非法或两种导入方式均无法提取 face。
    """
    path = Path(step_file)
    if not path.is_file():
        raise StepImportError(f"STEP 文件不存在: {path}")
    if path.suffix.lower() not in {".step", ".stp"}:
        raise StepImportError(f"不支持的 STEP 文件后缀: {path}")

    uids = uid_manager or UIDManager()
    diagnostics: dict[str, Any] = {}

    try:
        started_at = perf_counter()
        assembly = cq.Assembly.load(str(path))
        diagnostics["assembly_load_seconds"] = perf_counter() - started_at
        parts, part_shapes = flatten_assembly(assembly, uids)
        face_count = sum(part.part_face_count for part in parts)
        diagnostics["assembly_leaf_parts"] = len(parts)
        diagnostics["assembly_face_count"] = face_count
        if parts and face_count > 0:
            logger.info("Assembly.load 成功: %s parts, %s faces", len(parts), face_count)
            return ImportedStep(
                source_file=path,
                parts=parts,
                part_shapes=part_shapes,
                import_strategy=ImportStrategy.ASSEMBLY_LOAD,
                part_boundary_reliable=True,
                diagnostics=diagnostics,
            )
        diagnostics["assembly_error"] = "Assembly.load 未提取到带 face 的 leaf Part"
    except Exception as exc:  # CadQuery/OCP 会抛多种底层异常，统一降级处理。
        diagnostics["assembly_error"] = repr(exc)
        logger.warning("Assembly.load 失败，将尝试 importStep fallback: %s", exc)

    if not allow_import_step_fallback:
        raise StepImportError(f"Assembly.load 无法从 {path} 提取可靠 Part")

    try:
        started_at = perf_counter()
        imported = cq.importers.importStep(str(path))
        diagnostics["import_step_seconds"] = perf_counter() - started_at
        values = imported.vals()
        shape = _combine_import_step_shapes(values)
        face_count = count_faces(shape)
        diagnostics["import_step_top_shapes"] = len(values)
        diagnostics["import_step_face_count"] = face_count
        if face_count <= 0:
            raise StepImportError(f"importStep 从 {path} 提取到 0 个 face")
        synthetic = build_synthetic_import(path, shape, uids)
        synthetic.diagnostics.update(diagnostics)
        logger.warning("importStep fallback 仅生成 synthetic Part，Part 边界不可靠: %s faces", face_count)
        return synthetic
    except StepImportError:
        raise
    except Exception as exc:
        raise StepImportError(f"STEP 导入失败: {path}; diagnostics={diagnostics}; error={exc!r}") from exc
