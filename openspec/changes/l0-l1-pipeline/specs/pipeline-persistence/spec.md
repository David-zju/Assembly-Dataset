# pipeline-persistence

管道状态序列化与反序列化的能力规格。确保 L0 和 L1 可以在不同 Python 进程中独立执行。

## ADDED Requirements

### Requirement: L0 输出可序列化为 JSON

系统 SHALL 将 L0 的输出（Part 列表 + face 元数据 + 几何指纹）序列化为结构化 JSON 文件。文件 SHALL 包含 metadata（源文件路径、管道版本、时间戳）。

#### Scenario: 序列化包含所有必要信息

- **WHEN** L0 处理完装配体（例如 19759 个面）
- **THEN** 输出 JSON 包含：metadata（source_file, pipeline_version, timestamp, num_faces）、parts 数组、faces 数组
- **AND** faces 数组中每个元素包含 face_uid, part_uid, part_face_index, geom_type, fingerprint

#### Scenario: 反序列化恢复 L0 数据

- **WHEN** L1 加载 L0 输出的 JSON 文件
- **THEN** 还原出 Part 列表和 face 元数据列表
- **AND** face 元数据中的 face_uid 与 L0 分配的一致

### Requirement: L1 可独立加载 STEP 并匹配 face_uid

系统 SHALL 在 L1 加载时，独立重新导入 STEP 文件，按 TopExp_Explorer 遍历顺序匹配 face_uid，并通过几何指纹进行首尾校验。

#### Scenario: 索引匹配成功

- **WHEN** L1 按遍历顺序对应 face_uid
- **THEN** 首尾面的几何指纹与 L0 记录一致（容差 1e-4）
- **AND** 构建 face_uid → cq.Face 内存映射用于后续几何查询

#### Scenario: 指纹不匹配回退

- **WHEN** 首尾面的几何指纹与 L0 记录不匹配（遍历顺序被破坏）
- **THEN** 系统输出 WARNING 日志
- **AND** 切换为全量指纹匹配模式（O(N²) 搜索最近指纹）

### Requirement: JSON 文件大小合理

单个 STEP 文件（~20000 面）的 L0 输出 JSON 文件大小 SHALL 不超过 10MB。

#### Scenario: 大文件 JSON 输出大小

- **WHEN** 处理 19759 个面的装配体
- **THEN** 输出 JSON 文件大小不超过 10MB
