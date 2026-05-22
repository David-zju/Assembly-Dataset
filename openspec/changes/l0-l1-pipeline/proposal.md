## Why

项目目前仅完成概念定义（readme.md）和架构设计（ARCHITECTURE.md），尚无任何管道代码。L0（B-rep 面提取与标识）和 L1（几何接触检测）是标注流水线的基础层，所有后续层（L2 Feature、L3 Mate、L4 Group）都依赖其输出。尽早实现 L0→L1 可以建立项目的基本代码骨架、验证 CadQuery/OCP API 在真实 STEP 数据上的可用性，并为上层开发提供可测试的数据基础。

## What Changes

- **新增** L0 模块：STEP 文件导入、装配体扁平化、B-rep 面遍历、face_uid / part_uid 分配
- **新增** L1 模块：面分类与空间索引构建、Planar / Cylindrical / Tangency 三类几何接触判定、FaceContact 实体构建
- **新增** 管道层间数据传递机制：PipelineContext 容器的基本实现
- **新增** 管道状态持久化：L0 输出（Part 列表 + face 元数据）序列化为 JSON，L1 可独立加载执行
- **新增** 配置管理：thresholds.yaml 的加载与容差访问接口

## Capabilities

### New Capabilities

- `step-import`: STEP 装配体文件导入、编码恢复、装配体扁平化为 Part 列表
- `face-identification`: B-rep 面遍历、几何类型判定、face_uid / part_uid 全局唯一分配
- `face-contact-detection`: 基于几何判定的跨零件面接触检测（planar / cylindrical / tangency），空间索引加速，FaceContact 实体构建
- `pipeline-persistence`: L0 输出序列化为 JSON（Part 列表 + face 元数据 + 几何指纹），支持跨进程/跨阶段的管道执行

### Modified Capabilities

（无——此为项目的首次实现，不存在已有 spec）

## Impact

- **新增目录**: `src/l0_face_extraction/`, `src/l1_contact_detection/`, `src/common/`, `src/pipeline/`, `configs/`
- **依赖**: CadQuery 2.7.0 + OCP 7.8.1.1，numpy（用于矩阵运算和空间计算）
- **测试数据**: `test_case/simple_l0_l1_assembly.step`（3 Part / 15 face，小型有效装配验证件）和 `test_case/装配体3.STEP`（19759 面，验证大文件几何性能）
- **风险**: `importStep()` 会将大型装配体压成单个 Compound，不能作为可靠 Part 边界来源；真实 STEP 文件的 wire 提取须使用 TopExp_Explorer 而非 CadQuery 封装方法
