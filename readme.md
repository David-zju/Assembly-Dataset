# 装配数据集自动标注
[环境配置](environment.md)
## 1. 背景与目标
### 1.1 数据集背景
在上一篇工作中，我们提出了装配特征 (assembly feature) 和装配特征阵列 (assembly feature pattern) 两个高层语义概念，将预测目标从底层几何约束抬升至中间层的 feature mate 和 pattern mate。为支撑该方法的训练，上一篇工作配套构建了一个带 feature / pattern 标注的数据集，其规模为 529 个装配体、43,646 个零件、106,493 个 assembly feature 和 42,618 个 assembly feature pattern。但其构建方式存在若干根本性局限，使其难以支撑下一阶段的研究目标。本数据集是对其的一次重构。
### 1.2 上一版数据集的构建方式与局限
上一版数据集采用约束驱动 (constraint-driven) 的标注流程：以 CAD 模型中用户定义的装配约束为起点，反向推导出 feature 和 pattern 标注。具体流程包括三步：

- **约束重建 (Constraint reconstruction)**：检测用户约束的完整性，对缺失的约束（如标准件被简化后留下的"孔-孔对齐"）通过几何邻接搜索补全。
- **特征翻译 (Feature translation)**：将基于不同拓扑实体（face / edge / vertex）的用户约束统一翻译为基于 face 的 feature 表达，并通过物理接触检验过滤语义错误的约束。
- **阵列与阵列配对提取 (Pattern & pattern mate extraction)**：将共面的 feature mate 聚合为 pattern mate。

这一流程的根本假设是：用户定义的约束是可信起点，只需补全和翻译即可恢复完整的装配语义。但实际数据中，这一假设面临两个无法通过补全与翻译彻底解决的问题：

**问题一：约束的不完整性。** 用户定义约束的目的是约束零件的运动自由度，而非完整描述零件间的物理接触。一旦运动自由度被锁定，用户便不会再添加额外约束，即使物理上仍存在多处贴合面。进一步地，工业实践中存在大量标准件简化的情况——螺栓、销钉等紧固件在装配模型中常被省略以提升性能。这些被省略的紧固件原本承载的"孔-轴-孔"三段约束，在简化模型中只留下"孔-孔对齐"这种隐式的装配关系，原始 CAD 文件中并无任何显式约束记录，如图1（a）所示。

上一版数据集的"约束重建"步骤通过几何邻接搜索补全了部分缺失约束，但该补全过程本身仍以用户已标注的约束为起点向外扩散——如果某处贴合面完全没有被任何用户约束覆盖（例如一对完全冗余的端面接触），它就不会被搜索到。

**问题二：约束实体的语义偏差。** 在 CAD 系统中，同一个装配关系可以由不同的拓扑实体等价地定义。用户出于交互便利，常常选择 GUI 中最容易点击的实体而非物理上真正发生接触的实体。例如图1 (b) 所示的销轴-孔配合中，用户选择了销轴的外圆柱面与孔的内圆柱面做 coaxial 约束。这两个面共轴，几何求解器可以正确求解，但物理接触面其实是销轴外表面与孔内表面，标注实体与真实接触面不一致。

<figure style="text-align: center;">
  <img src="/pictures/ambiguous and under specified.png" alt="描述">
  <figcaption style="display: block; text-align: center;">图1 数据集中的典型标注错误来源</figcaption>
</figure>


## 2. 重要基本概念
### 2.1 Assembly Feature & Assembly Feature Mate
### 2.2 Assembly Feature

## 3. 总体Pipeline

## 4. 数据预处理

## 5. Face ID 持久化



