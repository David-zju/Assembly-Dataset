# step-import

STEP 装配体文件导入与扁平化的能力规格。

## ADDED Requirements

### Requirement: 系统能够导入 STEP 装配体文件

系统 SHALL 读取 `.step` / `.stp` 文件，解析其装配体结构，并扁平化为 Part 列表。每个 Part 携带其在装配体根坐标系下的 4×4 齐次变换矩阵和被定位后的 B-rep shape 对象。

#### Scenario: 通过 Assembly 成功导入

- **WHEN** 输入具有标准装配体结构的 STEP 文件
- **THEN** 系统通过 `cq.Assembly.load()` 解析，递归遍历 children 收集带 shape 的叶子节点
- **AND** 每个叶子节点的 shape 和 location 被正确读取
- **AND** 输出 Part 列表的 part_boundary_reliable = true
- **AND** metadata.import_strategy = "assembly_load"

#### Scenario: importStep 仅作为几何诊断兜底

- **WHEN** `cq.Assembly.load()` 失败或无法从装配体 leaf 提取有效 Part face
- **AND** `cq.importers.importStep()` 可提取 face
- **THEN** 系统 MAY 生成单个 synthetic Part 用于 L0 几何诊断和 API 验证
- **AND** part_boundary_reliable = false
- **AND** metadata.import_strategy = "import_step_fallback"
- **AND** 系统 SHALL NOT 继续执行 L1 跨 Part 接触检测

#### Scenario: 导入失败时回退

- **WHEN** `cq.Assembly.load()` 与 `cq.importers.importStep()` 均无法提取 face
- **THEN** 系统抛出 `StepImportError` 并记录源文件路径

#### Scenario: importStep 不得作为 Part 边界来源

- **WHEN** `cq.importers.importStep()` 返回单个 Compound 或 solids 列表
- **THEN** 系统不得将 Compound 内的 solids 解释为可靠 Part 列表
- **AND** 若继续保留几何诊断输出，则 part_boundary_reliable 必须为 false

### Requirement: 系统能够处理编码损坏的中文零件名

系统 SHALL 检测 STEP 文件中的中文零件名是否存在编码损坏（常见模式：UTF-8 字节被当作 Latin-1 解释后重新编码），并尝试恢复。

#### Scenario: 中文名编码恢复

- **WHEN** 零件名包含乱码字符（非预期字符集）
- **THEN** 系统使用编码链穷举搜索（复用 test.py 逻辑）尝试恢复
- **AND** 若恢复失败，使用 `unnamed_part_<索引>` 作为兜底名称

### Requirement: 系统能够扁平化装配体

系统 SHALL 将子装配体递归展开为扁平的 Part 列表。同一份零件定义被装配多次时，每个实例视为独立的 Part，分配不同的 part_uid，但共享 source_definition_uid。

#### Scenario: 扁平化多实例零件

- **WHEN** 同一零件定义对应 4 个装配位置（4 个实例）
- **THEN** 输出 4 个 Part 对象，各拥有不同的 part_uid
- **AND** 4 个 Part 共享相同的 source_definition_uid
- **AND** 每个 Part 携带各自的 4×4 位姿矩阵
