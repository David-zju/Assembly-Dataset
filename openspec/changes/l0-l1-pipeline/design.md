## Context

L0 和 L1 是装配数据集自动标注流水线的前两层。L0 负责 STEP 文件导入与 B-rep 面标识，L1 负责跨零件几何接触检测。两者通过 PipelineContext 传递数据，输出需可持久化以支持跨进程执行。

当前项目无任何管道代码，本设计基于已验证的 CadQuery/OCP API（见 `docs/verified_api/`）和 ARCHITECTURE.md 中定义的架构约束。

## Goals / Non-Goals

**Goals:**
- 实现 STEP 装配体文件的导入与扁平化，支持 CadQuery 构建模型和真实 STEP 文件（importStep + TopExp_Explorer）
- 为每个 Part 和 Face 分配全局唯一 UID，支持持久化后跨进程恢复
- 实现 Planar、Cylindrical、Tangency 三类几何接触检测
- 使用空间索引（AABB 粗筛 + KD-Tree）避免 O(N²) 面间检查
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

### 决策 5：投影重叠用三级判定策略

- Level 1（BBox 粗筛）：AABB 不重叠 → 直接排除，阈值可配置
- Level 2（形状简化判定）：矩形面（4 LINE edge）和圆形面（1 CIRCLE edge）用近似公式
- Level 3（完整布尔运算）：复杂形状 → 预留接口，先标记为"需要完整判定"

L1 v1 实现 Level 1+2，Level 3 留后续。

### 决策 6：面形状分类需做保险性检查

在判断形状复杂度之前，必须：
1. 用 `TopExp_Explorer` 遍历 wire（不用 `face.outerWire()`）
2. 用 `wire.Closed()` 检查闭合性
3. 非闭合 wire → 直接标记为复杂形状

## Risks / Trade-offs

- **[R1] 001650 文件导入失败**：importStep 返回 0 面，Assembly 的 36 个 children 中 Compound 为空 → 需在 L0 实现时优先调查，可能需特殊处理路径
- **[R2] 索引映射失效**：如果未来 OCP 版本改变遍历顺序 → 首尾指纹不匹配时自动回退到 O(N²) 全量指纹匹配
- **[R3] 大文件的 KD-Tree 内存开销**：19759 面 × 多采样点 → 内存可能较大 → 采样点数量按面积分级（小面 1 点、中面 9 点、大面 25 点），可配置
- **[R4] 仅 bbox 近似判定可能产生误报**：两个平面 bbox 有轻微重叠但实际面边界无交集 → bbox_overlap_min_ratio 阈值设为 0（保守策略：宁可多检不漏检），留待 Level 3 精确判定排除
