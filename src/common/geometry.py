"""常用空间几何计算工具。

本模块封装 L1 接触判定会复用的纯数值计算，避免在多个判定器中重复编写
向量点积、叉积、轴线距离和坐标变换逻辑。
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from OCP.gp import gp_Ax1, gp_Dir, gp_Pln, gp_Pnt

Vector3 = tuple[float, float, float]
Matrix4x4 = list[list[float]]


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    """将浮点数限制到指定区间。

    Args:
        value: 输入浮点数。
        low: 下界。
        high: 上界。
    """
    return max(low, min(high, value))


def dot(a: Sequence[float], b: Sequence[float]) -> float:
    """计算三维向量点积。"""
    return float(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])


def cross(a: Sequence[float], b: Sequence[float]) -> Vector3:
    """计算三维向量叉积。"""
    return (
        float(a[1] * b[2] - a[2] * b[1]),
        float(a[2] * b[0] - a[0] * b[2]),
        float(a[0] * b[1] - a[1] * b[0]),
    )


def norm(v: Sequence[float]) -> float:
    """计算三维向量长度。"""
    return math.sqrt(dot(v, v))


def normalize(v: Sequence[float]) -> Vector3:
    """归一化三维向量。

    Args:
        v: 三维向量。

    Raises:
        ValueError: 输入向量长度接近 0。
    """
    length = norm(v)
    if length < 1e-12:
        raise ValueError("无法归一化零长度向量")
    return (float(v[0] / length), float(v[1] / length), float(v[2] / length))


def gp_dir_to_tuple(direction: gp_Dir) -> Vector3:
    """将 gp_Dir 转为 Python tuple。"""
    return (float(direction.X()), float(direction.Y()), float(direction.Z()))


def gp_pnt_to_tuple(point: gp_Pnt) -> Vector3:
    """将 gp_Pnt 转为 Python tuple。"""
    return (float(point.X()), float(point.Y()), float(point.Z()))


def gp_dir_angle_deg(a: gp_Dir, b: gp_Dir, *, unsigned: bool = True) -> float:
    """计算两个 gp_Dir 的夹角，单位为度。

    Args:
        a: 第一个方向。
        b: 第二个方向。
        unsigned: 为 True 时忽略方向正负，适合圆柱轴线比较。
    """
    va, vb = gp_dir_to_tuple(a), gp_dir_to_tuple(b)
    value = dot(va, vb)
    if unsigned:
        value = abs(value)
    return math.degrees(math.acos(clamp(value)))


def axis_angle_deg(a: gp_Ax1, b: gp_Ax1) -> float:
    """计算两条轴线方向夹角，忽略正负方向。"""
    return gp_dir_angle_deg(a.Direction(), b.Direction(), unsigned=True)


def axis_distance(a: gp_Ax1, b: gp_Ax1) -> float:
    """计算两条三维轴线的最短距离。

    Args:
        a: 第一条轴线。
        b: 第二条轴线。

    Returns:
        float: 两轴线最短距离。
    """
    p1, d1 = gp_pnt_to_tuple(a.Location()), gp_dir_to_tuple(a.Direction())
    p2, d2 = gp_pnt_to_tuple(b.Location()), gp_dir_to_tuple(b.Direction())
    delta = (p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2])
    cross_dir = cross(d1, d2)
    cross_len = norm(cross_dir)
    if cross_len < 1e-10:
        return norm(cross(delta, d1))
    return abs(dot(delta, cross_dir)) / cross_len


def point_plane_distance(plane: gp_Pln, point: Sequence[float] | gp_Pnt) -> float:
    """计算点到平面的距离。

    Args:
        plane: OCP gp_Pln 平面。
        point: gp_Pnt 或三元坐标。
    """
    pnt = point if isinstance(point, gp_Pnt) else gp_Pnt(float(point[0]), float(point[1]), float(point[2]))
    return float(abs(plane.Distance(pnt)))


def identity_matrix() -> Matrix4x4:
    """返回 4x4 单位矩阵。"""
    return [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def apply_transform(matrix: Sequence[Sequence[float]], point: Sequence[float]) -> Vector3:
    """用 4x4 齐次矩阵变换三维点。

    Args:
        matrix: 4x4 齐次矩阵。
        point: 三维点。
    """
    x, y, z = float(point[0]), float(point[1]), float(point[2])
    return (
        float(matrix[0][0] * x + matrix[0][1] * y + matrix[0][2] * z + matrix[0][3]),
        float(matrix[1][0] * x + matrix[1][1] * y + matrix[1][2] * z + matrix[1][3]),
        float(matrix[2][0] * x + matrix[2][1] * y + matrix[2][2] * z + matrix[2][3]),
    )

