# face-contact-detection

跨零件几何接触检测的能力规格。包含 Planar（面-面共面反向）、Cylindrical（圆柱面共轴匹配）、Tangency（圆柱面与平面相切）三类接触判定。

## ADDED Requirements

### Requirement: 系统能够对面进行类型分类与空间索引

系统 SHALL 在接触检测前，将所有 face 按 geomType 分类，并为所有 face 构建空间索引（AABB 粗筛 + KD-Tree）以高效搜索邻近面。

#### Scenario: 面分类

- **WHEN** 管道处理包含 PLANE / CYLINDER / CONE / SPHERE / TORUS / BSPLINE 等类型面的装配体
- **THEN** 面被分组为 planes[], cylinders[], cones[], spheres[], tori[] 等
- **AND** BEZIER / BSPLINE / OTHER 类型被跳过并记录 DEBUG 日志

#### Scenario: AABB 粗筛

- **WHEN** 两个 face 的 AABB 在膨胀 search_radius 后不相交
- **THEN** 该对直接跳过，不进入 KD-Tree 精细搜索

### Requirement: 系统能够检测 Planar Contact

系统 SHALL 检测两个不同 Part 上的 PLANE 类型 face 是否构成平面接触。判定条件：法向量反向（180° ± max_angle_deg）、共面（距离 < max_distance_mm）、投影重叠（bbox 近似或后序精确判定）。

#### Scenario: 两平面共面反向接触

- **WHEN** 两个 PLANE face 的法向量夹角为 180° ± 0.05°、面间距离 < 0.005mm、bbox 投影有重叠
- **THEN** 系统判定为 Planar Contact
- **AND** 输出 confidence = 1.0

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

系统 SHALL 检测两个不同 Part 上的 CYLINDER 类型 face 是否构成圆柱面接触。判定条件：一个 shaft（外圆柱）一个 hole（内圆柱）、共轴（轴线夹角 < max_axis_angle_deg + 径向距离 < 容差）、半径匹配（半径差比 < max_radius_ratio）、轴向重叠（重叠长度比 > min_overlap_length_ratio）。

#### Scenario: 孔轴配合成功检测

- **WHEN** 一个 shaft（dot(normal, to_surface) > 0）和一个 hole（dot < 0）共轴、半径差 < 1%、轴向有充分重叠
- **THEN** 系统判定为 Cylindrical Contact
- **AND** 输出 radius_diff_ratio、axis_angle_deg、overlap_length

#### Scenario: 两 shaft 或两 hole

- **WHEN** 两个 CYLINDER face 都是 shaft（或都是 hole）
- **THEN** 系统判定为不接触

#### Scenario: 共轴但半径不匹配

- **WHEN** shaft 和 hole 共轴但半径差比 > max_radius_ratio
- **THEN** 系统判定为不接触

### Requirement: 系统能够检测 Tangency Contact

系统 SHALL 检测一个 CYLINDER face 和一个 PLANE face 是否构成切向接触。判定条件：圆柱轴线平行于平面（axis ⟂ normal，在容差内）、圆柱表面到平面的最短距离 ≈ 半径。

#### Scenario: 圆柱与平面相切

- **WHEN** 圆柱轴线平行于平面法向量、|dist(axis, plane) - radius| < max_distance_mm
- **THEN** 系统判定为 Tangency Contact
- **AND** 输出 distance 和 tangent_angle_deg

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
