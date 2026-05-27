# face-contact-detection

跨零件几何接触检测的能力规格。本变更修改 Planar Contact 与 Tangency Contact 的有限 trimmed face overlap 判定。

## MODIFIED Requirements

### Requirement: 系统能够检测 Planar Contact

系统 SHALL 检测两个不同 Part 上的 PLANE 类型 face 是否构成平面接触。判定条件：法向量反向（180° ± max_angle_deg）、共面（距离 < max_distance_mm）、两个 trimmed face 在同一平面局部 2D 坐标系中的有限面域具有足够重叠。系统 MUST NOT 仅依赖 2D bbox overlap 作为 Planar Contact 的主判定依据。

#### Scenario: 两平面共面反向且有限面域重叠

- **WHEN** 两个 PLANE face 的法向量夹角为 180° ± max_angle_deg、面间距离 < max_distance_mm，且两个 trimmed face 在同一 PlaneFrame 中的投影多边形有面积重叠
- **THEN** 系统判定为 Planar Contact
- **AND** 输出 normal_angle_deg、plane_distance、overlap_area、overlap_ratio、overlap_method 和 confidence
- **AND** overlap_method SHALL 表明 overlap 由平面局部 2D trimmed domain 判定得到

#### Scenario: 两平面共面但距离超容差

- **WHEN** 两个 PLANE face 法向量反向但面间距离 > max_distance_mm
- **THEN** 系统判定为不接触

#### Scenario: 两平面法向量不反向

- **WHEN** 两个 PLANE face 的法向量夹角偏离 180° 超过 max_angle_deg
- **THEN** 系统判定为不接触

#### Scenario: 同 Part 内平面

- **WHEN** 两个 PLANE face 属于同一个 Part（part_uid 相同）
- **THEN** 直接跳过，不进入判定（INV-07）

#### Scenario: bbox 相交但有限面域不重叠

- **WHEN** 两个 PLANE face 法向量反向、共面距离在容差内，且二者 2D bbox 有重叠
- **AND** 两个 face 的真实 trimmed domain 在 PlaneFrame 中没有面积重叠，或 overlap_area <= min_planar_overlap_area_mm2
- **THEN** 系统判定为不接触
- **AND** 不得仅因为 bbox 投影相交而输出 Planar Contact

#### Scenario: 平面边界含曲线且可离散化

- **WHEN** 两个 PLANE face 的边界包含 CIRCLE/ARC 等可离散化 edge，且离散化后的 PlaneTrimDomain 有足够面积重叠
- **THEN** 系统 SHALL 判定为 Planar Contact
- **AND** 输出 overlap_method = "plane_polygon_sampled" 或等价方法标识
- **AND** 输出 needs_exact_overlap = true

#### Scenario: 平面边界复杂或含孔洞

- **WHEN** 系统无法将 PLANE face 提取为受支持的 PlaneTrimDomain，例如存在孔洞、多 outer、非闭合 wire、BSPLINE/ELLIPSE 或超过 max_plane_polygon_vertices 的复杂边界
- **THEN** 系统 SHALL 使用 bbox fallback 作为低置信度诊断
- **AND** 输出 overlap_method = "bbox_fallback" 或等价方法标识
- **AND** 输出 needs_exact_overlap = true
- **AND** 不得将 fallback 结果标记为精确有限面 overlap

### Requirement: 系统能够检测 Tangency Contact

系统 SHALL 检测一个 CYLINDER face 和一个 PLANE face 是否构成切向接触。判定条件：圆柱轴线平行于平面（axis ⟂ normal，在容差内）；圆柱轴线到平面的距离 ≈ 半径；圆柱-平面的理论切线在 PLANE face 的有限 PlaneTrimDomain 内有有效线段，并且该线段落在 CYLINDER face 的有限轴向范围与周向覆盖范围内。系统 MUST NOT 仅依赖 3D expanded AABB 相交作为 Tangency Contact 的有限面主判定。

#### Scenario: 圆柱与平面相切且有限切线重叠

- **WHEN** 圆柱轴线平行于平面、|dist(axis, plane) - radius| < max_distance_mm
- **AND** 理论切线与 PLANE face 的 PlaneTrimDomain 相交得到有效线段
- **AND** 该切线线段与 CYLINDER face 的轴向 interval 和周向 coverage 有足够 overlap
- **THEN** 系统判定为 Tangency Contact
- **AND** 输出 axis_plane_angle_deg、axis_plane_distance、radius、distance_error、tangent_overlap_length、overlap_method 和 confidence
- **AND** overlap_method SHALL 表明有限切线 overlap 由 trimmed domain 判定得到

#### Scenario: 圆柱轴线不平行于平面

- **WHEN** CYLINDER face 的轴线与 PLANE face 法向量夹角偏离 90° 超过 max_axis_angle_deg
- **THEN** 系统判定为不接触

#### Scenario: 圆柱轴线到平面距离不等于半径

- **WHEN** CYLINDER face 的轴线到 PLANE face 所在平面的距离与圆柱半径之差 > max_distance_mm
- **THEN** 系统判定为不接触

#### Scenario: 同 Part 内圆柱与平面

- **WHEN** CYLINDER face 和 PLANE face 属于同一个 Part（part_uid 相同）
- **THEN** 直接跳过，不进入判定（INV-07）

#### Scenario: 理论切线落在平面有限边界之外

- **WHEN** 圆柱与平面的无限几何相切关系成立
- **AND** 理论切线与 PLANE face 的 PlaneTrimDomain 没有有效线段，或线段长度 <= min_tangency_overlap_length_mm
- **THEN** 系统判定为不接触
- **AND** 不得仅因为 CYLINDER face 与 PLANE face 的 expanded AABB 相交而输出 Tangency Contact

#### Scenario: 理论切线不落在圆柱有限范围内

- **WHEN** 圆柱与平面的无限几何相切关系成立，且理论切线与 PLANE face 的有限边界有交集
- **AND** 该切线对应的轴向区间不在 CYLINDER face 的有限轴向范围内，或对应周向角不在 CYLINDER face 的周向 coverage 内
- **THEN** 系统判定为不接触

#### Scenario: Tangency 有限 overlap 降级

- **WHEN** 系统无法提取受支持的 PlaneTrimDomain 或 CylinderTrimDomain，但 AABB fallback 可给出诊断性结果
- **THEN** 系统 SHALL 使用 fallback 作为低置信度诊断
- **AND** 输出 overlap_method = "bbox_fallback" 或等价方法标识
- **AND** 输出 needs_exact_overlap = true
- **AND** 不得将 fallback 结果标记为精确有限切线 overlap
