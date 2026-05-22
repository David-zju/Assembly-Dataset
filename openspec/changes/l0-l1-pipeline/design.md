## Context

L0 和 L1 是装配数据集自动标注流水线的前两层。L0 负责 STEP 文件导入与 B-rep 面标识，L1 负责跨零件几何接触检测。两者通过 PipelineContext 传递数据，输出需可持久化以支持跨进程执行。

当前项目无任何管道代码，本设计基于已验证的 CadQuery/OCP API（见 `docs/verified_api/`）和 ARCHITECTURE.md 中定义的架构约束。

## Goals / Non-Goals

**Goals:**
- 实现 STEP 装配体文件的导入与扁平化，支持 CadQuery 构建模型和真实 STEP 文件（importStep + TopExp_Explorer）
- 为每个 Part 和 Face 分配全局唯一 UID，支持持久化后跨进程恢复
- 实现 Planar、Cylindrical、Tangency 三类几何接触检测
- 使用空间索引（expanded AABB + AABB Tree/BVH）保守生成候选面对，避免 O(N²) 面间检查
- L0 输出可序列化为 JSON，L1 可独立加载并执行

**Non-Goals:**
- Conical / Spherical / Toroidal 接触类型（readme 中的 checkbox，后续阶段处理）
- 投影重叠的精确 2D 布尔运算（先实现 bbox 近似，Level 2/3 留后续）
- L2 及以上层的实现
- 可视化（后续 scripts/ 中实现）

## Decisions

### 决策 1：持久化采用索引映射 + 几何指纹校验

**选择**：基于 TopExp_Explorer 遍历顺序的确定性（已验证 19759/19759 面顺序完全一致），L0 按遍历顺序分配 face_uid，L1 重新导入 STEP 后按相同索引匹配。

**备选方案**：
- hashCode 方案：已验证 hashCode 跨导入完全不稳定（0/19759 匹配），不可用
- 内存引用方案：不可序列化，跨进程失效

**几何指纹**：对首尾面做指纹校验（geomType + area + center + bbox），不匹配时回退到全量指纹匹配。

### 决策 2：真实 STEP 文件使用 TopExp_Explorer 遍历

**选择**：统一使用 `TopExp_Explorer(wrapped, TopAbs_FACE)` 遍历面、`TopExp_Explorer(face_ts, TopAbs_WIRE/EDGE)` 遍历 wire 和 edge。

**原因**：已验证 CadQuery 封装方法（`face.outerWire().edges().vals()`）在真实 STEP 文件上崩溃（Compound 无 vals 方法），而 TopExp_Explorer 在所有场景下稳定。

### 决策 3：L0 不预提取所有几何属性

**选择**：L0 只提取和持久化面标识元数据（face_uid, part_uid, geomType, 几何指纹）。L1 按需通过 face_uid → Face 对象调用 CadQuery/OCP API 查询详细几何属性（法向量、半径、轴线等）。

**原因**：架构已放宽"仅 L0 可用 CadQuery"约束，各层均可直接使用 OCP。预提取所有属性反而增加不必要的序列化负担。

### 决策 4：接触检测分五阶段执行

```
[1. 面收集与分类] → [2. 空间索引构建] → [3. 候选对生成] → [4. 几何判定] → [5. 接触组装]
```

- 阶段 1-3 对所有候选面统一处理
- 阶段 4 按类型组合路由到三个独立判定函数（planar / cylindrical / tangency）
- 阶段 5 统一分配 contact_uid、构建 FaceContact 和 PerPartContactIndex
- Tangency 判定中，"圆柱轴线平行于平面" 等价于圆柱轴线垂直于平面法向量（axis ⟂ normal）；不得解释为圆柱轴线平行于平面法向量。

### 决策 4.1：空间索引采用 AABB Tree/BVH，而非 KDTree

**选择**：为每个候选 face 计算按 `search_radius` 膨胀后的 expanded AABB，构建 AABB Tree/BVH，并通过树遍历枚举所有 expanded AABB 相交的跨 Part face pair。

**原因**：L1 候选生成需要回答的是"两个有限面的包围盒是否可能相交"，这是 AABB overlap 查询，而不是点近邻查询。KDTree 适合点近邻搜索；若用 face 采样点作为 KDTree 索引，采样点未命中可能漏掉真实接触。AABB Tree/BVH 的语义与本问题一致：expanded AABB 不相交的 pair 可以安全排除，相交的 pair 保守进入后续几何判定。

**候选生成不变式**：
- 空间索引必须是保守的：任何真实接触 pair 不得因为索引阶段被漏掉
- 只有 expanded AABB 不相交可以作为硬排除依据
- expanded AABB 相交只表示"可能接触"，仍需进入 Planar / Cylindrical / Tangency 几何判定

**BVH v1 实现策略**：
- 数据结构：静态二叉 AABB Tree。每个节点保存 `bbox`（子树所有 AABB 的 union）、`left`、`right`、`items`。内部节点只保存子节点，叶节点保存 face 条目列表。
- AABB 条目：每个条目至少包含 expanded AABB 的 `min_xyz` / `max_xyz`、`face_uid`、`part_uid`、`geom_type`。expanded AABB 由原始 face AABB 按 `search_radius` 向六个方向膨胀得到。
- 构建方式：当条目数 `<= bvh_leaf_size` 时生成叶节点；否则计算各条目 AABB center，选择 center 跨度最大的轴，按该轴 center 排序并做 median split。
- 退化处理：如果所有 center 坐标相同，仍按排序后的索引中位数强制二分；若达到 `bvh_max_depth`，直接生成叶节点，避免无限递归。
- 默认参数：`bvh_leaf_size = 8`，可配置范围建议为 4 到 32；`bvh_max_depth` 可选，默认按 `ceil(log2(num_items / bvh_leaf_size)) * 2` 估算。
- 查询方式：使用树-树自相交遍历枚举所有 expanded AABB 相交 pair。节点 bbox 不相交则剪枝；叶-叶时枚举条目笛卡尔积；同一节点自查询时只枚举 `i < j`，避免重复。
- 输出过滤：生成 pair 时过滤同 Part pair，并用 expanded AABB overlap 复核。v1 可维护 `seen_pairs` 集合作为保险去重，key 使用排序后的 `(face_uid_a, face_uid_b)`。
- 复杂度：构建期望为 `O(N log N)`（若每层完整排序，实际可接近 `O(N log^2 N)`，19759 面规模可接受）；查询平均为 `O(N log N + K)`，其中 `K` 是 expanded AABB 相交候选数。若大量 AABB 互相重叠，候选数本身可退化为 `O(N^2)`，这是保守 broad phase 的固有限制。

**暂不采用的备选方案**：
- SAH（Surface Area Heuristic）：查询质量更好，但实现复杂、调参多，留作 v2 优化。
- LBVH / Morton code：构建快，但实现细节复杂且对空间分布敏感，暂不适合 v1。
- Dynamic AABB Tree：适合实时更新场景，本项目 STEP 几何为静态输入，暂无必要。
- Uniform Grid：可作为备选 broad phase，但 cell size 难以统一适配大/小面混合的装配体。

### 决策 5：有限修剪面的重叠判定

- Level 1（BBox 粗筛）：expanded AABB 不重叠 → 直接排除，阈值可配置
- Level 2（形状简化判定）：矩形面（4 LINE edge）和圆形面（1 CIRCLE edge）用近似公式
- Level 3（完整布尔运算）：复杂形状 → 预留接口，先标记为"需要完整判定"

L1 不能只判断无限几何关系，还必须确认接触落在两个 trimmed face 的有限边界内：
- Planar：平面共面后，在平面局部 2D 坐标中检查两个面边界的投影重叠
- Cylindrical：共轴和半径匹配后，检查轴向区间重叠，并保留周向覆盖验证接口
- Tangency：圆柱轴线到平面距离匹配后，检查切线落在平面 face 边界内，且落在圆柱面的 V 参数范围内

L1 v1 实现 Level 1+2，Level 3 留后续。仅通过 bbox 近似的重叠判定不得输出 `confidence = 1.0`，应记录 `overlap_method = "bbox_approx"` 和 `needs_exact_overlap = true`，并给出低于 1.0 的 confidence。

### 决策 6：面形状分类需做保险性检查

在判断形状复杂度之前，必须：
1. 用 `TopExp_Explorer` 遍历 wire（不用 `face.outerWire()`）
2. 用 `wire.Closed()` 检查闭合性
3. 非闭合 wire → 直接标记为复杂形状

## Risks / Trade-offs

- **[R1] 001650 文件导入失败**：importStep 返回 0 面，Assembly 的 36 个 children 中 Compound 为空 → 需在 L0 实现时优先调查，可能需特殊处理路径
- **[R2] 索引映射失效**：如果未来 OCP 版本改变遍历顺序 → 首尾指纹不匹配时自动回退到 O(N²) 全量指纹匹配
- **[R3] 大文件的 AABB Tree/BVH 构建与查询开销**：19759 面规模下需要控制树节点内存和候选 pair 数量 → AABB 只存储必要的 min/max、face_uid、part_uid，树叶节点容量可配置，并记录候选生成耗时与候选数量
- **[R4] 仅 bbox 近似判定可能产生误报**：两个平面 bbox 有轻微重叠但实际面边界无交集 → bbox_overlap_min_ratio 阈值设为 0（保守策略：宁可多检不漏检），该类结果必须降低 confidence 并标记 `needs_exact_overlap = true`，留待 Level 3 精确判定排除
