# step-import

STEP 装配体文件导入与扁平化的能力规格。

## ADDED Requirements

### Requirement: 系统能够导入 STEP 装配体文件

系统 SHALL 读取 `.step` / `.stp` 文件，解析其装配体结构，并扁平化为 Part 列表。每个 Part 携带其在装配体根坐标系下的 4×4 齐次变换矩阵和被定位后的 B-rep shape 对象。

#### Scenario: 通过 importStep 成功导入大文件

- **WHEN** 输入 `test_case/装配体3.STEP`（32.4 MB）等大型 STEP 文件
- **THEN** 系统通过 `cq.importers.importStep()` 成功导入，并提取出所有 face（19759 个）
- **AND** 每个 face 可通过 `TopExp_Explorer` 遍历获取

#### Scenario: 通过 Assembly 成功导入

- **WHEN** 输入具有标准装配体结构的 STEP 文件
- **THEN** 系统通过 `cq.Assembly.load()` 解析，递归遍历 children 收集带 shape 的叶子节点
- **AND** 每个叶子节点的 shape 和 location 被正确读取

#### Scenario: 导入失败时回退

- **WHEN** `cq.Assembly.load()` 失败（抛出异常）
- **THEN** 系统回退到 `cq.importers.importStep()` 尝试导入
- **AND** 若两种方式均失败，抛出 `StepImportError` 并记录源文件路径

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
