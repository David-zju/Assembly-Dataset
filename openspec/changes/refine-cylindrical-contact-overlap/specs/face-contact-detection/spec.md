# face-contact-detection

跨零件几何接触检测的能力规格。本变更修改 Cylindrical Contact 的有限圆柱面 overlap 判定。

## MODIFIED Requirements

### Requirement: 系统能够检测 Cylindrical Contact

系统 SHALL 检测两个不同 Part 上的 CYLINDER 类型 face 是否构成圆柱面接触。判定条件：一个 shaft（外圆柱）一个 hole（内圆柱）、共轴（轴线夹角 < max_axis_angle_deg 且径向距离 < max_distance_mm）、半径匹配（半径差比 < max_radius_ratio）、两个 trimmed cylinder face 在公共圆柱坐标系下具有足够的轴向 overlap 和周向 overlap。系统 MUST NOT 仅依赖 3D AABB 投影作为 cylindrical 有限面 overlap 的主判定。

#### Scenario: 完整孔轴配合成功检测

- **WHEN** 一个 shaft（dot(normal, to_surface) > 0）和一个 hole（dot < 0）共轴、半径差 < max_radius_ratio、轴向有充分重叠，且至少一个 face 为完整 360° 圆柱面
- **THEN** 系统判定为 Cylindrical Contact
- **AND** 输出 radius_diff_ratio、axis_angle_deg、axis_distance、axial_overlap_length、axial_overlap_ratio
- **AND** 输出 circumferential_overlap_angle_deg、circumferential_overlap_ratio、is_full_circle_a、is_full_circle_b
- **AND** overlap_method 或子方法字段 SHALL 表明轴向/周向 overlap 由公共圆柱坐标系下的 UV sampled 方法得到

#### Scenario: 两 shaft 或两 hole

- **WHEN** 两个 CYLINDER face 都是 shaft（或都是 hole）
- **THEN** 系统判定为不接触

#### Scenario: 共轴但半径不匹配

- **WHEN** shaft 和 hole 共轴但半径差比 > max_radius_ratio
- **THEN** 系统判定为不接触

#### Scenario: 共轴且半径匹配但轴向不重叠

- **WHEN** shaft 和 hole 共轴、半径匹配，但两个 trimmed cylinder face 在公共圆柱坐标系下的轴向 overlap_length <= 0 或 overlap_ratio <= min_overlap_length_ratio
- **THEN** 系统判定为不接触
- **AND** 不得因为两个 face 的 3D AABB 投影区间相交而输出 Cylindrical Contact

#### Scenario: 局部圆柱片周向重叠

- **WHEN** shaft 和 hole 共轴、半径匹配、轴向充分重叠，且两个局部 cylinder face 的公共周向角度区间有 overlap
- **AND** circumferential_overlap_angle_deg >= min_circumferential_overlap_deg
- **AND** circumferential_overlap_ratio >= min_circumferential_overlap_ratio
- **THEN** 系统判定为 Cylindrical Contact
- **AND** 输出 circumferential_overlap_method = "uv_sampled_common_frame" 或等价方法标识

#### Scenario: 局部圆柱片周向错开

- **WHEN** shaft 和 hole 共轴、半径匹配、轴向充分重叠，但两个局部 cylinder face 的公共周向角度区间没有足够 overlap
- **THEN** 系统判定为不接触
- **AND** 不得仅因为轴向区间重叠而输出 Cylindrical Contact

#### Scenario: 周向区间跨零点

- **WHEN** 一个局部 cylinder face 的周向覆盖跨越 0/2π 边界，例如 350° 至 10°
- **AND** 另一个局部 cylinder face 的周向覆盖与其在公共圆柱坐标系中真实重叠
- **THEN** 系统 SHALL 正确计算周向 overlap
- **AND** 不得把短跨零弧段误判为接近完整圆或完全不重叠

#### Scenario: 非全局 Z 轴圆柱

- **WHEN** 两个 CYLINDER face 的轴线不平行于全局 Z 轴，但彼此共轴、半径匹配、轴向和周向均充分重叠
- **THEN** 系统判定为 Cylindrical Contact
- **AND** 公共圆柱坐标系 SHALL 基于圆柱轴线构造，而不得依赖固定全局轴向

#### Scenario: UV sampled overlap 失败时降级

- **WHEN** 系统无法通过 uvBounds/positionAt 提取有效 CylinderTrimDomain，但 AABB fallback 可给出诊断性 overlap
- **THEN** 系统 MAY 使用 AABB interval fallback 作为低置信度诊断
- **AND** 输出 axial_overlap_method = "axis_interval_bbox_fallback" 或等价方法标识
- **AND** 输出 needs_exact_overlap = true
- **AND** 不得将 fallback 结果标记为精确有限圆柱面 overlap
