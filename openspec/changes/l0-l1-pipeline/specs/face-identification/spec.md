# face-identification

B-rep 面遍历与 UID 分配的能力规格。

## ADDED Requirements

### Requirement: 系统能够遍历 B-rep 面并判定几何类型

系统 SHALL 对每个 Part 的 shape 遍历其所有 B-rep face，并判定每个 face 的几何类型。遍历 SHALL 使用 `TopExp_Explorer` 确保在真实 STEP 文件上的兼容性。

#### Scenario: 遍历面并统计类型分布

- **WHEN** 处理含有 19759 个面的 STEP 装配体
- **THEN** 系统输出所有 face 的几何类型（PLANE / CYLINDER / CONE / SPHERE / TORUS / BSPLINE / BEZIER / OTHER）
- **AND** 类型分布统计可用于验证导入正确性

#### Scenario: 跳过不支持的几何类型

- **WHEN** face 的 geomType 为 BEZIER 或 OTHER
- **THEN** 系统记录 DEBUG 日志并跳过该 face
- **AND** 管道统计中记录 skipped_face_count

### Requirement: 系统能够为 Part 和 Face 分配全局唯一 UID

系统 SHALL 为每个 Part 分配 `part_uid`（格式 `p-{seq:04d}`），为每个 Face 分配 `face_uid`（格式 `f-{part_seq:04d}-{face_seq:04d}`）。UID 在同一管道运行中全局唯一，分配后不可修改。

#### Scenario: UID 格式正确性

- **WHEN** 处理包含 3 个 Part、Part 1 有 100 个面、Part 2 有 50 个面的装配体
- **THEN** part_uid 为 `p-0001`, `p-0002`, `p-0003`
- **AND** Part 1 的 face_uid 范围为 `f-0001-00001` 至 `f-0001-00100`
- **AND** Part 2 的 face_uid 范围为 `f-0002-00001` 至 `f-0002-00050`

#### Scenario: UID 全局唯一

- **WHEN** 分配任意数量的 Part 和 Face UID
- **THEN** 所有 part_uid 之间互不相同
- **AND** 所有 face_uid 之间互不相同
- **AND** 无任何 face_uid 与任何 part_uid 重复

### Requirement: 系统能够构建 face_uid 到 Face 对象的内存映射

系统 SHALL 维护 `face_uid → cq.Face` 的映射关系，供 L1 按需查询几何属性。映射基于 TopExp_Explorer 遍历顺序（已验证确定性）。

#### Scenario: 通过 face_uid 获取 Face 对象

- **WHEN** 已知 face_uid `f-0001-00005`
- **THEN** 可通过映射获取到对应的 cq.Face 对象
- **AND** 该 Face 对象的 geomType() 与 L0 记录一致

### Requirement: 系统能够生成面的几何指纹用于跨进程校验

系统 SHALL 为每个 face 计算几何指纹（geomType + area + center + bbox），序列化到 L0 输出中，供 L1 跨进程加载时做身份校验。

#### Scenario: 指纹一致性校验

- **WHEN** L1 重新导入同一 STEP 文件并遍历 face
- **THEN** 第 0 个 face 的几何指纹与 L0 输出中的 fingerint 匹配（容差 1e-4）
- **AND** 最后一个 face 的指纹同样匹配
