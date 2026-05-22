# ARCHITECTURE

本文档描述了本项目的目录结构与整体架构，是后续所有实现工作的指导性文档。

## 整体架构

本项目采用五层自底向上的标注流水线架构，从 STEP 装配体文件出发，通过几何接触检测逐层构建装配语义标注：

```text
scripts/                    CLI 入口脚本
    │
src/pipeline/               管道编排（按序调用 L0→L1→L2→L3→L4）
    │
    ├── L0: src/l0_face_extraction/        STEP 导入 + B-rep 面提取 + face_uid 分配
    ├── L1: src/l1_contact_detection/      跨零件几何接触检测 (planar/cylindrical/tangency)
    ├── L2: src/l2_feature_construction/   单零件装配特征构建 (atomic + composite)
    ├── L3: src/l3_mate_pairing/           跨零件特征配对
    └── L4: src/l4_mate_group/             高层关系组 (Pattern & Hub)
    │
src/common/                 跨层共享（数据模型、几何工具、UID、序列化、日志等）
    │
configs/                    配置文件（管道参数、几何容差、日志）
```

### 数据流

```text
STEP 文件
  → L0: Part 列表 + GeometryCache（面几何属性缓存）
  → L1: FaceContact 列表（跨零件面接触）
  → L2: AssemblyFeature 列表（per-part 装配特征）
  → L3: FeatureMate 列表（跨零件特征配对）
  → L4: Pattern + Hub（高层关系组）
  → JSON / Parquet 输出
```

每一层的标注通过 UID 引用下层实体，构成有向无环引用图（DAG）。

### 关键设计决策

1. **扁平化 Part 模型**：sub-assembly 被递归展开为扁平的 Part 列表，每个 Part 携带相对于根坐标系的 4×4 齐次变换矩阵。不保留 sub-assembly 的层级语义。

2. **L2 按 Part 独立构建**：每个 Part 的 feature 构建不依赖其他 Part 的 feature 构建结果。这保证 L2 可完全并行化。

3. **L0 负责 STEP 导入与几何初始化**：L0 完成 STEP 文件的解析、装配体扁平化和 B-rep 面的初始提取。各层均可按需使用 CadQuery/OCP 进行几何查询与计算，不做强制隔离。

---

## 目录结构

```text
src/
├── l0_face_extraction/         STEP 导入、B-rep 拓扑遍历、face_uid 分配、装配体扁平化。
│                               "STEP 如何被解析？B-rep face 如何提取并赋予唯一标识？"
│
├── l1_contact_detection/       跨零件面接触检测。包含几何判定（共面/共轴/相切）、
│                               空间邻近搜索、接触类型分类与接触实体构建。
│                               "两个 face 是否接触？什么类型？如何高效搜索候选对？"
│
├── l2_feature_construction/    单零件装配特征构建。在同一 part 内将 L1 接触关联的 face
│                               按几何邻接分组，识别原子特征和组合特征，提取尺寸参数。
│                               "一个 part 上有哪些装配特征？各是什么类型和参数？"
│
├── l3_mate_pairing/            跨零件特征配对。基于 L1 接触信息和 L2 特征信息，
│                               匹配互补特征对（如孔-轴、键-槽），验证物理合理性。
│                               "两个 feature 是否构成装配关系？共享哪些接触？"
│
├── l4_mate_group/              高层关系组检测。包含 Pattern 检测与配对（set-to-set）、
│                               Hub 检测（one-to-many）及 Layout 参数化分析。
│                               "哪些 mate 构成 pattern？哪些构成 hub？layout 如何？"
│
├── common/                     跨层共享模块：核心数据类定义、纯数值几何工具、UID 管理器、
│                               空间索引、容差管理、日志配置、异常类、序列化（JSON/Parquet）。
│                               "UID 怎么生成？几何工具在哪？容差是多少？怎么序列化？"
│
└── pipeline/                   管道编排。主编排器按序执行 L0-L4、PipelineContext 层间数据容器、
                                执行报告（耗时与实体统计）。
                                "完整处理流程如何编排？层间数据如何传递？"

tests/
├── fixtures/                   极简测试用 STEP 文件（1-3 个面/零件的装配体）
├── test_l0/                    L0 单元测试
├── test_l1/                    L1 单元测试（几何判定、邻近搜索）
├── test_l2/                    L2 单元测试
├── test_l3/                    L3 单元测试
├── test_l4/                    L4 单元测试
├── test_common/                共享模块测试
└── integration/                集成测试（每层转换 + 完整管道 E2E）

configs/
├── pipeline.yaml               管道行为配置（启用层级、并行度、输出格式、输出目录）
├── thresholds.yaml             几何容差（平面距离、角度、半径比、搜索半径等）
└── logging.yaml                日志级别与输出目标

scripts/                        CLI 入口脚本（运行管道、可视化、导出等）

examples/                       使用示例与工具脚本（含已有的 split.py）

docs/                           文档（由 OpenSpec SDD 生成）

test_case/                      测试用完整 STEP 装配体文件

pictures/                       文档引用的图片资源
```

---

## 系统边界

### 几何内核

项目基于 CadQuery/OCP 进行几何计算。各层可按需直接调用 CadQuery API 进行几何查询，不做强制隔离。`src/common/` 中封装常用的几何工具函数（距离计算、法向量运算、坐标变换等），减少重复代码。

### 层间依赖边界

| 层 | 可导入 | 禁止导入 |
|----|--------|---------|
| L0 | common/* | l1, l2, l3, l4 |
| L1 | common/*, L0 输出的数据结构（只读） | l0 实现细节, l2, l3, l4 |
| L2 | common/*, L1 输出的数据结构（只读） | l0, l1 实现, l3, l4 |
| L3 | common/*, L2 输出的数据结构（只读） | l0, l1, l2 实现, l4 |
| L4 | common/*, L3 输出的数据结构（只读） | l0, l1, l2, l3 实现 |

每层通过 `PipelineContext` 读取下层数据、写入本层输出。层与层之间通过数据解耦，不直接调用。

### I/O 边界

- **输入端**：仅 L0 读取 .step/.stp 文件；编码损坏的中文零件名在此处恢复（复用 test.py 的编码链检测逻辑）
- **输出端**：`src/common/` 中的序列化模块从 PipelineContext 读取全部标注数据并输出 JSON/Parquet
- **配置**：`configs/` 中的 YAML 被 `common/`（容差）和 `pipeline/`（管道参数）读取，其他模块通过这两个入口间接获取配置

---

## 架构不变式

以下规则在项目的整个生命周期中**必须始终为真**，违反任何一条即为架构缺陷：

### INV-01 依赖方向

L(N) 只能依赖 `common/*` 和 L(N-1) 的**数据结构**（只读使用）。绝不依赖 L(N+1) 或更高层的任何模块。

### INV-02 UID 全局唯一

同一管道运行中所有 UID（face_uid, contact_uid, feature_uid, mate_uid, group_uid）全局唯一，格式统一为 `<前缀>-<序号>`。

### INV-03 UID 不可变

一旦分配，UID 不可修改。实体被删除时 UID 作废，但不重新分配给其他实体。

### INV-04 DAG 无环

UID 引用链 `face → contact → feature → mate → group` 必须构成有向无环图，不得出现循环引用。

### INV-05 单一几何数据源

几何数据只来源于 L0 解析的 STEP 文件。后续层标注实体只引用几何（通过 face_uid），不复制几何数据。

### INV-06 STEP 数据只读

L0 解析后的 Part 列表和 GeometryCache 为只读。管道过程只能追加标注实体，不能修改原始几何数据。

### INV-07 跨零件接触

L1 FaceContact 的两个 face 必须属于不同 Part。同一 Part 内的面邻接关系在 L2 中处理。

### INV-08 L2 per-part 独立性

任意 Part A 的 L2 feature 构建不依赖 Part B 的 feature 构建结果。这保证 L2 可完全并行化。

### INV-09 输出完整性

管道正常结束时每层输出不可缺失（至少为空列表 `[]`）。metadata 必须记录源文件路径、管道版本、检测阈值、时间戳。

---

## 横切关注点

### 日志

- **分层命名**：`l0.*`, `l1.*`, `l2.*`, `l3.*`, `l4.*`, `pipeline`
- **级别约定**：
  - DEBUG：单面级检测细节
  - INFO：阶段起止与实体数量统计
  - WARNING：容差边界情况、跳过的不支持几何类型
  - ERROR：不可恢复的错误（如 STEP 解析失败）
- 由 `common/` 提供统一的 `get_logger(name)` 工厂函数，从 `configs/logging.yaml` 加载配置

### 错误处理

| 错误类型 | 处理策略 |
|---------|---------|
| STEP 解析失败 | 抛出异常，管道中止，记录源文件路径 |
| B-rep 遍历异常 | WARNING + 跳过该实体，继续处理 |
| 不支持的几何类型 | DEBUG 记录 + 跳过该 face |
| 容差边界情况 | WARNING + 标记低置信度（confidence < 1.0），不丢弃 |
| 特征分类不确定 | 标记为 ambiguous 类型，保留所有候选类型 |

异常类统一定义在 `common/` 中，形成清晰的层次结构。

### 测试策略

- **单元测试**：使用人工构造的几何参数测试几何判定函数、特征分类器、序列化逻辑，不依赖 STEP 文件
- **集成测试**：验证每层转换的 UID 引用完整性和数据结构一致性
- **E2E 测试**：对 `test_case/` 中的完整装配体运行全管道
- **测试 Fixtures**：`tests/fixtures/` 中放置极简 STEP 文件（少量面和零件的装配体），用于 L0 测试

### 性能

- **空间索引**：expanded AABB + AABB Tree/BVH 保守生成候选面对，避免先枚举 O(N²) 面对；后续几何判定负责裁掉误报
- **几何缓存**：L0 可一次性提取 face 的常用几何属性并缓存，减少后续层的重复 OCP 调用；使用 `__slots__` 减少内存开销
- **L2 并行化**：基于 per-part 独立性的天然并行度，由 config 控制最大并发数

### 配置管理

- 所有几何容差从 `configs/thresholds.yaml` 加载，禁止硬编码
- `common/` 提供统一的容差访问接口
- 管道行为（启用层级、并行度、输出格式、输出目录）从 `configs/pipeline.yaml` 加载

### 序列化

- **JSON 输出**：层级化结构，每层一个数组，实体间通过 UID 引用关联。支持两种模式：
  - 引用模式（默认）：各层独立数组 + UID 引用，文件紧凑
  - 内联模式：递归展开 UID 引用为完整嵌套树，便于直接阅读
- **Parquet 备选**：每层输出为一个 .parquet 文件，列式存储便于 DataFrame 查询和统计分析
- **输出校验**：验证 UID 格式一致性、引用完整性（被引用的 UID 必须存在）、DAG 无环约束
