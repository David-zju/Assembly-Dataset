"""可视化检查默认配色与透明度。"""

from __future__ import annotations

from dataclasses import dataclass


Color = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class VisualStyle:
    """viewer 对象样式。"""

    color: Color
    alpha: float


L0_FACE = VisualStyle((255, 59, 48), 1.0)
L0_PART = VisualStyle((47, 128, 237), 0.45)
L0_UNSUPPORTED = VisualStyle((255, 149, 0), 0.9)
CONTEXT_PART = VisualStyle((160, 160, 160), 0.18)
CONTEXT_ALL = VisualStyle((180, 180, 180), 0.08)
L1_FACE_A = VisualStyle((255, 59, 48), 1.0)
L1_FACE_B = VisualStyle((0, 188, 212), 1.0)
NEEDS_EXACT = VisualStyle((255, 214, 10), 1.0)


def style_for_l0_face(*, supported: bool = True) -> VisualStyle:
    """返回 L0 face 高亮样式。"""
    return L0_FACE if supported else L0_UNSUPPORTED


def style_for_l1_face(index: int, *, needs_exact: bool = False) -> VisualStyle:
    """返回 L1 contact 中第 index 个 face 的高亮样式。"""
    if needs_exact and index == 0:
        return NEEDS_EXACT
    return L1_FACE_A if index == 0 else L1_FACE_B
