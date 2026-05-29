"""L1 兼容入口：跨进程恢复 `face_uid -> cq.Face` 映射。

真实恢复逻辑位于 `src.common.face_reloader`，本模块保留历史导入路径，
避免已有 L1 集成测试和外部脚本失效。
"""

from __future__ import annotations

from pathlib import Path

from src.common.face_reloader import restore_face_map_from_step
from src.common.tolerances import Tolerances
from src.l0_face_extraction.l0_output import L0Output


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

    Returns:
        L0Output: 原对象本身，已填充 `face_map`。
    """
    l0_output.face_map = restore_face_map_from_step(
        step_file,
        l0_output.parts,
        l0_output.faces,
        l0_output.metadata,
        tolerances=tolerances,
    )
    return l0_output
