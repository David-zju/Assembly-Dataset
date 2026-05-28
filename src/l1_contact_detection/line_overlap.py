"""二维直线与凸多边形、一维区间 overlap 工具。

Tangency Contact 会把理论切线投影到 PlaneFrame 中，再用本模块求切线
在有限平面 trimmed domain 内的参数区间。
"""

from __future__ import annotations

from dataclasses import dataclass

from .planar_overlap import Point2D


@dataclass(frozen=True, slots=True)
class LineIntervalResult:
    """直线与多边形相交得到的一维参数区间。"""

    intervals: list[tuple[float, float]]
    supported: bool
    method: str = "line_convex_polygon"
    reason: str | None = None


def line_polygon_intervals(line_point: Point2D, line_dir: Point2D, polygon: list[Point2D]) -> LineIntervalResult:
    """计算无限直线与凸多边形交集在线参数 t 上的区间。

    Args:
        line_point: 直线上一点。
        line_dir: 直线方向，长度不必为 1，但不能为零。
        polygon: 逆时针凸多边形顶点。
    """
    dx, dy = line_dir
    if abs(dx) + abs(dy) <= 1e-12:
        return LineIntervalResult([], False, reason="zero_line_dir")
    if len(polygon) < 3:
        return LineIntervalResult([], False, reason="degenerate_polygon")

    t_min = float("-inf")
    t_max = float("inf")
    px, py = line_point
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        ex = end[0] - start[0]
        ey = end[1] - start[1]
        # 逆时针多边形内部在每条边左侧，约束 cross(edge, point-start) >= 0。
        numerator = ex * (py - start[1]) - ey * (px - start[0])
        denominator = ey * dx - ex * dy
        if abs(denominator) <= 1e-12:
            if numerator < -1e-9:
                return LineIntervalResult([], True)
            continue
        bound = -numerator / denominator
        if denominator > 0.0:
            t_min = max(t_min, bound)
        else:
            t_max = min(t_max, bound)
        if t_min - t_max > 1e-9:
            return LineIntervalResult([], True)

    if t_min == float("-inf") or t_max == float("inf"):
        return LineIntervalResult([], False, reason="unbounded_interval")
    if t_max - t_min <= 1e-9:
        return LineIntervalResult([], True)
    return LineIntervalResult([(float(t_min), float(t_max))], True)


def intersect_1d_intervals(
    intervals_a: list[tuple[float, float]],
    intervals_b: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    """计算两组一维区间的交集。"""
    result: list[tuple[float, float]] = []
    for start_a, end_a in intervals_a:
        for start_b, end_b in intervals_b:
            start = max(start_a, start_b)
            end = min(end_a, end_b)
            if end - start > 1e-9:
                result.append((float(start), float(end)))
    return result


def segment_overlap_length(intervals: list[tuple[float, float]]) -> float:
    """计算一组不要求预合并的一维区间总长度。"""
    if not intervals:
        return 0.0
    ordered = sorted(intervals)
    merged: list[tuple[float, float]] = []
    for start, end in ordered:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return float(sum(end - start for start, end in merged))
