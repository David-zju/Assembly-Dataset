# face-contact-detection

跨零件几何接触检测的能力规格。包含 Planar（面-面共面反向）、Cylindrical（圆柱面共轴匹配）、Tangency（圆柱面与平面相切）三类接触判定。

## ADDED Requirements

### Requirement: 系统能够对面进行类型分类与空间索引

系统 SHALL 在接触检测前，将 supported = true 的 face 按 geomType 分类，并为这些候选 face 构建基于 expanded AABB 的 AABB Tree/BVH 空间索引，以保守且高效地生成可能接触的跨 Part face pair。

#### Scenario: 面分类

- **WHEN** 管道处理包含 PLANE / CYLINDER / CONE / SPHERE / TORUS / BSPLINE 等类型面的装配体
- **THEN** 面被分组为 planes[], cylinders[], cones[], spheres[], tori[] 等
- **AND** supported = false 的 face 不进入 L1 分类、空间索引和接触判定

#### Scenario: AABB Tree/BVH 保守候选生成

- **WHEN** 两个 face 的 AABB 在膨胀 search_radius 后不相交
- **THEN** 该对直接跳过，不进入几何接触判定
- **AND** 任何 expanded AABB 相交的跨 Part face pair 均作为候选输出

#### Scenario: BVH 候选对不重复且过滤同 Part

- **WHEN** 多个 face 的 expanded AABB 相交，且其中部分 face 属于同一 Part
- **THEN** 系统仅输出跨 Part 的候选 face pair
- **AND** 同一个无序 face pair 最多输出一次

### Requirement: 系统能够检测 Planar Contact

系统 SHALL 检测两个不同 Part 上的 PLANE 类型 face 是否构成平面接触。判定条件：法向量反向（180° ± max_angle_deg）、共面（距离 < max_distance_mm）、两个 trimmed face 在平面局部 2D 坐标中的投影重叠（bbox 近似或后续精确判定）。

#### Scenario: 两平面共面反向接触

- **WHEN** 两个 PLANE face 的法向量夹角为 180° ± 0.05°、面间距离 < 0.005mm、bbox 投影有重叠
- **THEN** 系统判定为 Planar Contact
- **AND** 输出 overlap_method 和 confidence
- **AND** 若仅通过 bbox 近似判定重叠，则 confidence < 1.0 且 needs_exact_overlap = true

#### Scenario: 两平面共面但距离超容差

- **WHEN** 两个 PLANE face 法向量反向但面间距离 > max_distance_mm
- **THEN** 系统判定为不接触

#### Scenario: 两平面法向量不反向

- **WHEN** 两个 PLANE face 的法向量夹角偏离 180° 超过 max_angle_deg
- **THEN** 系统判定为不接触

#### Scenario: 同 Part 内平面

- **WHEN** 两个 PLANE face 属于同一个 Part（part_uid 相同）
- **THEN** 直接跳过，不进入判定（INV-07）

### Requirement: 系统能够检测 Cylindrical Contact

系统 SHALL 检测两个不同 Part 上的 CYLINDER 类型 face 是否构成圆柱面接触。判定条件：一个 shaft（外圆柱）一个 hole（内圆柱）、共轴（轴线夹角 < max_axis_angle_deg + 径向距离 < 容差）、半径匹配（半径差比 < max_radius_ratio）、两个 trimmed face 的轴向区间重叠（重叠长度比 > min_overlap_length_ratio），并保留周向覆盖验证接口。

#### Scenario: 孔轴配合成功检测

- **WHEN** 一个 shaft（dot(normal, to_surface) > 0）和一个 hole（dot < 0）共轴、半径差 < 1%、轴向有充分重叠
- **THEN** 系统判定为 Cylindrical Contact
- **AND** 输出 radius_diff_ratio、axis_angle_deg、axial_overlap_length、overlap_method

#### Scenario: 两 shaft 或两 hole

- **WHEN** 两个 CYLINDER face 都是 shaft（或都是 hole）
- **THEN** 系统判定为不接触

#### Scenario: 共轴但半径不匹配

- **WHEN** shaft 和 hole 共轴但半径差比 > max_radius_ratio
- **THEN** 系统判定为不接触

### Requirement: 系统能够检测 Tangency Contact

系统 SHALL 检测一个 CYLINDER face 和一个 PLANE face 是否构成切向接触。判定条件：圆柱轴线平行于平面，即圆柱轴线垂直于平面法向量（axis ⟂ normal，在容差内）；圆柱轴线到平面的距离 ≈ 半径；切线落在 PLANE face 的有限边界内，并落在 CYLINDER face 的 V 参数范围内。

#### Scenario: 圆柱与平面相切

- **WHEN** 圆柱轴线平行于平面（即垂直于平面法向量）、|dist(axis, plane) - radius| < max_distance_mm，且切线落在两个 trimmed face 的有效范围内
- **THEN** 系统判定为 Tangency Contact
- **AND** 输出 distance、tangent_angle_deg、overlap_method

### Requirement: 系统能够为检测到的接触分配 UID

系统 SHALL 为每个检测到的 FaceContact 分配全局唯一的 contact_uid（格式 `c-{seq:06d}`）。

#### Scenario: Contact UID 连续分配

- **WHEN** 检测到 N 个 FaceContact
- **THEN** contact_uid 范围为 `c-000001` 至 `c-{N:06d}`
- **AND** 所有 contact_uid 互不相同

### Requirement: 系统能够构建 PerPartContactIndex

系统 SHALL 构建 `Dict[part_uid, List[contact_uid]]` 索引，支持按 Part 快速查询其参与的所有接触。

#### Scenario: 按 Part 查询接触

- **WHEN** 已知 part_uid `p-0001`
- **THEN** 可通过 PerPartContactIndex 获取该 Part 参与的所有 contact_uid 列表
