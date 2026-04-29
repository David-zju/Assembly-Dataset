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

### 1.3 本数据集重要改进
针对上述缺陷，本数据集利用装配体中零件已经确定的相对位置，通过几何关系检测不同零件之间的五力接触，再自底向上聚合形成feature，pattern，hub以及mate信息。这种方法的优势在于：
- **完整性：** 只要两个 face 在几何上满足接触条件，无论用户是否标注过相关约束，都会被检测到。
- **物理一致性：** 检测的对象本身就是物理接触面，从源头上规避了语义偏差问题。
- **泛用性：** 标注流程仅依赖几何输入和确定性几何判定规则，不依赖用户标注质量，便于跨数据源复用。

# 2. 重要基本概念

## 2.1 装配体

**Part (零件)**：装配体的基本组成单位，对应一个独立的 B-rep 模型。本数据集不区分零件的实例与定义——同一份零件被装配多次时，每个实例视为独立的 part 对象，但通过 part_uid 可追溯回相同的零件定义。

**Assembly (装配体)**：由若干 part 通过位姿摆放形成的整体。本数据集将所有装配体扁平化为单层结构，不保留 sub-assembly 的层级语义（这与 Vergez 的处理一致）。Sub-assembly 在扁平化后仅作为一组共同移动的 part 集合存在。

**装配位姿 (Assembly pose)**：每个 part 在装配体根坐标系下的 4×4 齐次变换矩阵。本数据集**假设装配位姿是输入**——即所有源数据集（Fusion 360 Gallery、AutoMate、自采）已经提供摆放好的装配体。

## 2.4 接触与配对

**Face Contact (面接触, L1)**：两个分别属于不同 part 的 face 之间满足几何接触条件（共面 + 反向 + 距离容差，或共轴 + 反向 + 半径容差）的对偶。这是本数据集的最底层装配语义实体，对应 Vergez 等人工作中的 "slot" 概念。

Face contact 在本数据集中的类型有：

- **Planar contact**：两个 plane 类型 face 之间的共面反向接触
- **Cylindrical contact**：两个 cylinder 类型 face 之间的共轴反向接触
- **Tangency**: cylinder和plane相切。

- [ ] 可以检查一下是否存在别的接触类型，例如conical / spherical / toroidal contact
## 2.5 Assembly Feature

**Assembly Feature (装配特征, AF)**：单个 part 上装配相关的局部区域，由若干 face 组成，承载一个完整的装配语义。

$$F = (GE, A)$$

其中 $GE = \{f_1, f_2, ..., f_n\}$ 是组成该 feature 的 face 集合（通过 face_uid 引用），$A = (d_1, ..., d_m, t)$ 是属性向量，包含尺寸参数 $d_i$（如孔的半径、深度）和类型标签 $t$（hole / shaft / slot / ...）。

**原子特征 (Atomic feature)**：不可再分解的基本装配特征，如简单孔、单段轴、矩形槽等。

**组合特征 (Composite feature)**：由两个或多个原子特征通过特定的空间关系组合而成的复合结构，如沉头孔（counterbore = 大径孔 + 同轴小径孔 + 端面）、阶梯轴、通孔等。

<!-- **Feature interface**：feature 中真正参与跨零件配合的 face 子集。一个 feature 的所有 face 不一定都参与配合，例如一个台阶孔的两个端面只有一个端面参与与外部零件的端面贴合。 -->



## 2.6 Assembly Feature Mate

**Assembly Feature Mate (装配特征对, AFM)**：如果两个零件通过一对feature构成了装配关系，则这一对Assembly Feature则构成 Assembly Feature Mate.

$$FM = (F, \overline{F}, C)$$

其中 $F, \overline{F}$ 是两个分属不同零件的 feature，$C = \{c_1, c_2, ..., c_k\}$ 是绑定它们的几何约束集合（如轴对齐 + 端面贴合）。

每个 mate 关联一组 face contact。例如一对 hole-shaft mate 通常包含 1 个 cylindrical contact（孔内壁与轴外壁）和 0~1 个 planar contact（孔的端面与轴的肩面）。

<figure style="text-align: center;">
  <img src="/pictures/assembly feature.png" alt="描述">
  <figcaption style="display: block; text-align: center;">图2 装配特征对</figcaption>
</figure>

## 2.7 Mate Group

**Mate Group (装配配对组)**：多个 feature mate 之间共同形成的高层共结构 (co-structure)。其核心观察是：装配关系往往不是孤立成立的，而是以**组**的形式存在，组内的 mate 之间存在结构化的几何或拓扑关系。识别 mate group 可以将"局部合理但全局不一致"的 mate 误判过滤掉。

本数据集定义两类 mate group：

### 2.7.1 Pattern & Pattern Mate 

**Pattern**：一个零件上存在关联的一组 assembly feature。这一组 assembly feature 会一起组成一个高层的装配语义。

$$P = (\{F_i\}_{i=1}^N, \text{Pose}, \text{Layout}, \text{Type})$$

其中 $\{F_i\}$ 是构成阵列的 N 个同类型 feature，Pose 是阵列在参考面上的外参（原点 + 方向），Layout 是阵列的内部结构。本数据集相对于上一版的增量是引入 **Type** 字段，将 Layout 进一步分类为四个子类型：

- **Linear pattern**：沿单一方向等间距排列。参数：方向向量、起点、间距、数量。
- **Rectangular pattern**：沿两个方向构成矩形网格。参数：两个方向向量、起点、两方向间距、两方向数量。
- **Circular pattern**：绕一中心轴等角度排列。参数：中心轴、半径、起始角、角度间距、数量。
- **Free-form pattern**：不符合上述规则但仍存在 set-to-set 几何同构关系。仍以距离矩阵 D 表征 layout，作为兜底类别。

- [ ] 需要注意的是，pattern可能存在多种的语义理解方式。例如一个 4×3 的孔阵在与一个 4 孔板配合时是 4-12-pattern mate，与一个 12 孔板配合时是 12-12-pattern mate。实际检测的过程中需要通过contact的部分搜索邻域补全完整pattern。
  
**Pattern Mate (PM)**：两个互补 pattern 之间的配对关系：

$$PM = (P, \overline{P}, M, C)$$

其中 $M \subseteq \{1,...,N\} \times \{1,...,\overline{N}\}$ 是两个 pattern 内 feature 的对应关系，$C$ 是关联的几何约束集合。

### 2.7.2 Hub 

**Hub**：由一个**中心特征**和**多个外围特征**构成的 one-to-many mate。Hub 的核心特征是：存在一个中心 part 同时与 $N \geq 2$ 个外围 part 发生装配关系

形式化定义：

$$H = (F_{\text{center}}, \{(F_i, FM_i)\}_{i=1}^N, \text{Layout})$$

- $F_{\text{center}}$：中心 atomic feature（如一根 shaft）
- $\{F_i\}_{i=1}^N$：与中心配对的 N 个外围 atomic feature（如 N 个 hole），各 $F_i$ 分属不同 part
- $FM_i$：中心 feature 与第 $i$ 个外围 feature 之间的 mate
- Layout：hub 内部的空间结构

| Hub 子类型 | 中心 feature | 外围 feature | 典型场景 |
|------------|------------|------------|---------|
| **Cylindrical Hub** | shaft（圆柱面 atomic feature）| hole | 传动轴穿轴承座+齿轮、销轴穿铰链片、螺栓穿多板、导杆穿滑动轴承 |
| **Prismatic Hub**| key / rail（沿单一方向延伸的棱柱形 feature）| slot / groove | 键穿键槽、导轨承载多滑块 |

可能的场景：一个轴穿过多个孔，一个键嵌入多个槽，一个导轨承载多个滑块。

**Layout 参数化**：
 
由于 cylindrical hub 在中心轴上呈一维排列，layout 可以表示为：
 
$$\text{Layout} = (\vec{a}, \{F_1, F_2,...F_N\})$$
 
- $\vec{a}$：中心 feature 的主轴方向（单位向量）
- $\{F_1, F_2,...F_N\}$：外围feature 按照轴向排列的顺序。

## 2.8 标注层级总览

```
L0  B-rep faces (原始几何, face_uid 标识)
       │ 几何接触检测 (planar/cylindrical 条件判定)
       ▼
L1  Face Contact (跨零件面接触, contact_uid 标识)
       │     ├── Planar Contact
       │     └── Cylindrical Contact
       │ 同一 part 内 contact 聚合 + 类型分类
       ▼
L2  Assembly Feature (单零件装配特征, atomic + composite, feature_uid 标识)
       │ 单零件装配面补全 + 单零件feature构建
       ▼
L3  Mate (跨零件 feature 配对, mate_uid 标识)
       │ feature 配对
       ▼
L4  Assembly Relation Group
        ├── Pattern (set-to-set, 4 子类型) 
        └── Hub (one-to-many radiating) 
```

每一层的标注通过 uid 引用下层实体，构成一个**有向无环引用图**。

## 3. 总体Pipeline

## 4. 数据预处理

## 5. Face ID 持久化



