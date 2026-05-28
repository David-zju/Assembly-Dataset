"""几何容差配置访问接口。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_THRESHOLDS_PATH = Path(__file__).resolve().parents[2] / "configs" / "thresholds.yaml"


@dataclass(frozen=True, slots=True)
class Tolerances:
    """L1 几何判定和空间索引使用的容差集合。

    Args:
        max_angle_deg: 平面法向量角度容差，单位度。
        max_distance_mm: 点面/轴面距离容差，单位 mm。
        max_axis_angle_deg: 圆柱轴线夹角容差，单位度。
        max_radius_ratio: 圆柱半径相对差阈值。
        min_overlap_length_ratio: 圆柱轴向重叠比例阈值。
        min_circumferential_overlap_ratio: 圆柱周向重叠比例阈值。
        min_circumferential_overlap_deg: 圆柱周向重叠最小角度，单位度。
        full_circle_angle_tol_deg: 判断完整 360° 圆柱面的角度容差，单位度。
        cylinder_domain_sample_count: 圆柱 UV domain 边界采样数量。
        search_radius: AABB 膨胀半径，单位与模型一致。
        overlap_min_ratio: 面重叠比例阈值。
        bbox_overlap_min_ratio: bbox 近似重叠比例阈值。
        fingerprint_abs_tol: 几何指纹浮点比较绝对容差。
        bvh_leaf_size: BVH 叶节点条目数量。
        bvh_max_depth: BVH 最大深度，None 表示自动估算。
    """

    max_angle_deg: float
    max_distance_mm: float
    max_axis_angle_deg: float
    max_radius_ratio: float
    min_overlap_length_ratio: float
    min_circumferential_overlap_ratio: float
    min_circumferential_overlap_deg: float
    full_circle_angle_tol_deg: float
    cylinder_domain_sample_count: int
    search_radius: float
    overlap_min_ratio: float
    bbox_overlap_min_ratio: float
    fingerprint_abs_tol: float
    bvh_leaf_size: int
    bvh_max_depth: int | None


def load_tolerances(config_path: str | Path | None = None) -> Tolerances:
    """从 YAML 加载几何容差。

    Args:
        config_path: 可选配置路径；为 None 时读取 configs/thresholds.yaml。

    Returns:
        Tolerances: 不可变容差对象。
    """
    path = Path(config_path) if config_path else _DEFAULT_THRESHOLDS_PATH
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    geometry = data.get("geometry", {})
    spatial = data.get("spatial_index", {})
    return Tolerances(
        max_angle_deg=float(geometry.get("max_angle_deg", 0.05)),
        max_distance_mm=float(geometry.get("max_distance_mm", 0.005)),
        max_axis_angle_deg=float(geometry.get("max_axis_angle_deg", 0.05)),
        max_radius_ratio=float(geometry.get("max_radius_ratio", 0.01)),
        min_overlap_length_ratio=float(geometry.get("min_overlap_length_ratio", 0.05)),
        min_circumferential_overlap_ratio=float(geometry.get("min_circumferential_overlap_ratio", 0.01)),
        min_circumferential_overlap_deg=float(geometry.get("min_circumferential_overlap_deg", 1.0)),
        full_circle_angle_tol_deg=float(geometry.get("full_circle_angle_tol_deg", 0.1)),
        cylinder_domain_sample_count=int(geometry.get("cylinder_domain_sample_count", 16)),
        search_radius=float(geometry.get("search_radius", 0.01)),
        overlap_min_ratio=float(geometry.get("overlap_min_ratio", 0.0)),
        bbox_overlap_min_ratio=float(geometry.get("bbox_overlap_min_ratio", 0.0)),
        fingerprint_abs_tol=float(geometry.get("fingerprint_abs_tol", 1e-4)),
        bvh_leaf_size=int(spatial.get("bvh_leaf_size", 8)),
        bvh_max_depth=spatial.get("bvh_max_depth"),
    )
