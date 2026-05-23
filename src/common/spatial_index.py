"""AABB 与静态 BVH 空间索引。

该模块用于 L1 broad phase：保守枚举 expanded AABB 相交的跨 Part face pair。
它只负责候选生成，不做接触类型判断。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations, product
from typing import Iterable


@dataclass(frozen=True, slots=True)
class AABB:
    """轴对齐包围盒。

    Args:
        xmin: X 方向最小值。
        xmax: X 方向最大值。
        ymin: Y 方向最小值。
        ymax: Y 方向最大值。
        zmin: Z 方向最小值。
        zmax: Z 方向最大值。
    """

    xmin: float
    xmax: float
    ymin: float
    ymax: float
    zmin: float
    zmax: float

    def expanded(self, radius: float) -> "AABB":
        """向六个方向膨胀 AABB。"""
        r = float(radius)
        return AABB(self.xmin - r, self.xmax + r, self.ymin - r, self.ymax + r, self.zmin - r, self.zmax + r)

    def intersects(self, other: "AABB") -> bool:
        """判断两个 AABB 是否相交或接触。"""
        return not (
            self.xmax < other.xmin
            or other.xmax < self.xmin
            or self.ymax < other.ymin
            or other.ymax < self.ymin
            or self.zmax < other.zmin
            or other.zmax < self.zmin
        )

    def union(self, other: "AABB") -> "AABB":
        """返回覆盖两个 AABB 的 union box。"""
        return AABB(
            xmin=min(self.xmin, other.xmin),
            xmax=max(self.xmax, other.xmax),
            ymin=min(self.ymin, other.ymin),
            ymax=max(self.ymax, other.ymax),
            zmin=min(self.zmin, other.zmin),
            zmax=max(self.zmax, other.zmax),
        )

    @property
    def center(self) -> tuple[float, float, float]:
        """返回 AABB 中心点。"""
        return ((self.xmin + self.xmax) / 2.0, (self.ymin + self.ymax) / 2.0, (self.zmin + self.zmax) / 2.0)

    @property
    def extent(self) -> tuple[float, float, float]:
        """返回 AABB 在三个轴上的长度。"""
        return (self.xmax - self.xmin, self.ymax - self.ymin, self.zmax - self.zmin)

    def to_tuple(self) -> tuple[float, float, float, float, float, float]:
        """转换为元组，顺序与 FaceFingerprint.bbox 一致。"""
        return (self.xmin, self.xmax, self.ymin, self.ymax, self.zmin, self.zmax)

    @classmethod
    def from_tuple(cls, values: Iterable[float]) -> "AABB":
        """从六元组创建 AABB。"""
        xmin, xmax, ymin, ymax, zmin, zmax = [float(v) for v in values]
        return cls(xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax, zmin=zmin, zmax=zmax)

    @classmethod
    def union_all(cls, boxes: list["AABB"]) -> "AABB":
        """计算一组 AABB 的 union。"""
        if not boxes:
            raise ValueError("无法对空 AABB 列表求 union")
        result = boxes[0]
        for box in boxes[1:]:
            result = result.union(box)
        return result


@dataclass(frozen=True, slots=True)
class AABBItem:
    """BVH 叶节点中的 face 条目。"""

    face_uid: str
    part_uid: str
    geom_type: str
    bbox: AABB


@dataclass(slots=True)
class BVHNode:
    """静态二叉 BVH 节点。"""

    bbox: AABB
    left: "BVHNode | None" = None
    right: "BVHNode | None" = None
    items: list[AABBItem] | None = None

    @property
    def is_leaf(self) -> bool:
        """叶节点判断。"""
        return self.items is not None


def _auto_max_depth(num_items: int, leaf_size: int) -> int:
    """根据条目数量估算默认 BVH 最大深度。"""
    if num_items <= leaf_size:
        return 1
    return max(2, math.ceil(math.log2(max(1, num_items / max(1, leaf_size)))) * 2)


def build_bvh(items: list[AABBItem], leaf_size: int = 8, max_depth: int | None = None) -> BVHNode:
    """构建静态二叉 AABB Tree/BVH。

    Args:
        items: AABB 条目列表。
        leaf_size: 叶节点最大条目数。
        max_depth: 最大深度，None 时自动估算。

    Returns:
        BVHNode: 根节点。
    """
    if not items:
        raise ValueError("BVH 至少需要一个 AABBItem")
    if leaf_size <= 0:
        raise ValueError("leaf_size 必须大于 0")
    depth_limit = max_depth if max_depth is not None else _auto_max_depth(len(items), leaf_size)
    return _build_bvh_recursive(list(items), leaf_size, depth_limit, depth=0)


def _build_bvh_recursive(items: list[AABBItem], leaf_size: int, max_depth: int, depth: int) -> BVHNode:
    """递归构建 BVH 节点。"""
    bbox = AABB.union_all([item.bbox for item in items])
    if len(items) <= leaf_size or depth >= max_depth:
        return BVHNode(bbox=bbox, items=items)

    centers = [item.bbox.center for item in items]
    spans = []
    for axis in range(3):
        values = [center[axis] for center in centers]
        spans.append(max(values) - min(values))
    split_axis = max(range(3), key=lambda axis: spans[axis])

    ordered = sorted(items, key=lambda item: (item.bbox.center[split_axis], item.face_uid))
    midpoint = len(ordered) // 2
    if midpoint <= 0 or midpoint >= len(ordered):
        return BVHNode(bbox=bbox, items=items)

    left = _build_bvh_recursive(ordered[:midpoint], leaf_size, max_depth, depth + 1)
    right = _build_bvh_recursive(ordered[midpoint:], leaf_size, max_depth, depth + 1)
    return BVHNode(bbox=bbox, left=left, right=right)


def query_intersecting_pairs(root: BVHNode) -> list[tuple[AABBItem, AABBItem]]:
    """枚举 BVH 中所有 expanded AABB 相交的跨 Part face pair。

    Args:
        root: BVH 根节点。

    Returns:
        list[tuple[AABBItem, AABBItem]]: 去重后的无序 pair 列表。
    """
    seen: set[tuple[str, str]] = set()
    pairs: list[tuple[AABBItem, AABBItem]] = []

    def emit(a: AABBItem, b: AABBItem) -> None:
        if a.part_uid == b.part_uid or not a.bbox.intersects(b.bbox):
            return
        key = tuple(sorted((a.face_uid, b.face_uid)))
        if key in seen:
            return
        seen.add(key)
        pairs.append((a, b))

    def query_leaf_items(a_items: list[AABBItem], b_items: list[AABBItem], same_leaf: bool) -> None:
        iterator = combinations(a_items, 2) if same_leaf else product(a_items, b_items)
        for first, second in iterator:
            emit(first, second)

    def query_pair(a: BVHNode, b: BVHNode) -> None:
        if not a.bbox.intersects(b.bbox):
            return
        if a.is_leaf and b.is_leaf:
            query_leaf_items(a.items or [], b.items or [], same_leaf=a is b)
            return
        if a.is_leaf:
            if b.left:
                query_pair(a, b.left)
            if b.right:
                query_pair(a, b.right)
            return
        if b.is_leaf:
            if a.left:
                query_pair(a.left, b)
            if a.right:
                query_pair(a.right, b)
            return
        if a.left and b.left:
            query_pair(a.left, b.left)
        if a.left and b.right:
            query_pair(a.left, b.right)
        if a.right and b.left:
            query_pair(a.right, b.left)
        if a.right and b.right:
            query_pair(a.right, b.right)

    def query_self(node: BVHNode) -> None:
        if node.is_leaf:
            query_leaf_items(node.items or [], node.items or [], same_leaf=True)
            return
        if node.left:
            query_self(node.left)
        if node.left and node.right:
            query_pair(node.left, node.right)
        if node.right:
            query_self(node.right)

    query_self(root)
    return pairs

