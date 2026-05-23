"""common 模块单元测试。"""

from __future__ import annotations

import math

from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt

from src.common.geometry import axis_angle_deg, axis_distance
from src.common.spatial_index import AABB, AABBItem, build_bvh, query_intersecting_pairs
from src.common.tolerances import load_tolerances
from src.common.uid_manager import UIDManager


def test_uid_manager_formats_and_uniqueness() -> None:
    """验证 UID 格式和唯一性。"""
    uids = UIDManager()
    assert uids.next_part_uid() == "p-0001"
    assert uids.next_part_uid() == "p-0002"
    assert uids.next_face_uid(1, 1) == "f-0001-00001"
    assert uids.next_contact_uid() == "c-000001"


def test_tolerances_load_defaults() -> None:
    """验证默认容差配置可以加载。"""
    tolerances = load_tolerances()
    assert tolerances.max_angle_deg > 0.0
    assert tolerances.bvh_leaf_size == 8


def test_axis_geometry_matches_manual_expectation() -> None:
    """验证轴线夹角和距离计算。"""
    ax1 = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
    ax2 = gp_Ax1(gp_Pnt(0.1, 0, 5), gp_Dir(0, 0.001, 1))
    assert math.isclose(axis_angle_deg(ax1, ax2), 0.0572957, rel_tol=1e-4)
    assert math.isclose(axis_distance(ax1, ax2), 0.1, rel_tol=1e-4)


def test_bvh_intersections_filter_same_part_and_deduplicate() -> None:
    """验证 BVH 只输出跨 Part 去重候选。"""
    items = [
        AABBItem("f1", "p1", "PLANE", AABB(0, 1, 0, 1, 0, 1)),
        AABBItem("f2", "p2", "PLANE", AABB(0.5, 1.5, 0, 1, 0, 1)),
        AABBItem("f3", "p1", "PLANE", AABB(0.2, 0.8, 0, 1, 0, 1)),
        AABBItem("f4", "p2", "PLANE", AABB(3, 4, 0, 1, 0, 1)),
    ]
    pairs = query_intersecting_pairs(build_bvh(items, leaf_size=2))
    keys = {tuple(sorted((a.face_uid, b.face_uid))) for a, b in pairs}
    assert keys == {("f1", "f2"), ("f2", "f3")}


def test_bvh_degenerate_centers_and_long_thin_boxes() -> None:
    """验证 center 退化和长窄 AABB 端部相交场景。"""
    items = [
        AABBItem("a", "p1", "PLANE", AABB(0, 10, 0, 0.1, 0, 0.1)),
        AABBItem("b", "p2", "PLANE", AABB(9.9, 20, 0, 0.1, 0, 0.1)),
        AABBItem("c", "p3", "PLANE", AABB(30, 40, 0, 0.1, 0, 0.1)),
        AABBItem("d", "p4", "PLANE", AABB(30, 40, 0, 0.1, 0, 0.1)),
    ]
    pairs = query_intersecting_pairs(build_bvh(items, leaf_size=1))
    keys = {tuple(sorted((a.face_uid, b.face_uid))) for a, b in pairs}
    assert ("a", "b") in keys
    assert ("c", "d") in keys
