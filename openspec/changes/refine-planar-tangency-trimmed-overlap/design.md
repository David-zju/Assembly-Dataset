## Context

L1 当前的 Planar Contact 与 Tangency Contact 已经能判断无限几何关系：
- Planar：两个 PLANE face 法向量反向、共面距离在容差内。
- Tangency：CYLINDER 轴线平行于 PLANE，且轴线到平面的距离等于圆柱半径。

但二者对有限 trimmed face 的验证仍是近似：
- `planar_contact.py` 使用 `projected_bbox_overlap_ratio()`，只比较两个 face 在主投影平面上的 bbox 重叠。
- `tangency_contact.py` 使用 `expanded_aabb_intersects()`，只确认圆柱 face 与平面 face 的 AABB 膨胀后相交。

这会导致“无限几何关系成立，但有限面域不接触”的误报。例如两个共面矩形 bbox 相交但多边形实际错开，或者圆柱与平面理论相切但切线落在平面 trimmed 边界之外。由于 L2/L3 会把 L1 contact 当作语义输入，L1 的误报会向上污染 feature、mate、pattern/hub。

现有已验证 API 约束：
- 真实 STEP face 的 wire/edge 遍历必须使用 `TopExp_Explorer(face_ts, TopAbs_WIRE/EDGE)`，不能依赖 `face.outerWire().edges().vals()`。
- 平面底层参数可通过 `BRep_Tool.Surface_s(face.wrapped).Pln()` 获取。
- `pln.Position().Direction()` 与 `face.normalAt()` 的方向语义可能相反，接触判定仍以 `normalAt()` 的材料外法向为准。

## Goals / Non-Goals

**Goals:**
- 将 Planar Contact 的有限面验证从 bbox 投影近似升级为平面局部 2D trimmed domain 重叠判定。
- 将 Tangency Contact 的有限面验证从 expanded AABB 升级为理论切线在两个 trimmed domain 中的有效重叠判定。
- 对简单无孔平面 face 支持确定性的 2D 多边形 overlap。
- 对复杂边界、有孔、暂不支持曲线离散化的场景提供显式 fallback、低置信度与 `needs_exact_overlap = true` 标记。
- 保持 L1 只依赖 `common/*` 和 L0 输出数据结构，不引入 L2+ 依赖。
- 与 `refine-cylindrical-contact-overlap` 的圆柱有限域工具保持可复用接口，避免重复实现圆柱 UV/domain 逻辑。

**Non-Goals:**
- 不实现完整 OCP 2D pcurve 布尔运算或精确 B-rep 面域求交。
- 不新增 Shapely、CGAL 等外部几何依赖，除非后续单独评估并获得确认。
- 不改变 BVH broad phase：expanded AABB 仍只负责保守候选生成。
- 不改变 L0 face_uid、Part 边界、跨进程恢复机制。
- 不处理 CONE/SPHERE/TORUS/BSPLINE 面之间的新接触类型。

## Decisions

### 决策 1：建立 `PlaneFrame`，所有有限平面检查都在局部 2D 坐标中完成

**选择**：新增 `src/l1_contact_detection/planar_overlap.py`，定义：
- `PlaneFrame(origin, x_axis, y_axis, normal)`
- `PlaneTrimDomain(outer_polygon, holes, source_edge_types, method, is_supported)`
- `PlanarOverlapResult(overlap_area, overlap_ratio, method, needs_exact_overlap)`

`PlaneFrame` 以第一个 PLANE face 为参考：
- `normal` 使用 `face.normalAt()` 得到的材料外法向。
- `origin` 使用 face center 或平面上一点，保证投影坐标数值稳定。
- `x_axis/y_axis` 用与 normal 不平行的参考轴构造正交基；不得使用“丢弃最大法向分量”的全局主投影作为主要判定。

**原因**：全局主投影 bbox 会丢失真实 trimmed 边界信息，也不适合任意方向平面。局部 2D frame 可以把面域问题转化为可测试、可复用的平面多边形问题。

### 决策 2：真实 STEP face 边界必须通过 `TopExp_Explorer` 提取

**选择**：`extract_plane_trim_domain(face, frame, tolerances)` 使用 OCP 拓扑遍历：
1. 从 `face.wrapped` 遍历所有 WIRE。
2. 对每个 WIRE 遍历 EDGE。
3. 将 EDGE 的 3D 边界点投影到 `PlaneFrame` 的 2D 坐标。
4. 以投影后绝对面积最大的闭合 ring 作为 outer boundary，其余 ring 作为 holes。

**边界支持分级**：
- Level 2A：无孔、全部 LINE edge 的闭合凸/简单多边形，作为高置信度主路径。
- Level 2B：无孔、CIRCLE/ARC 等可验证离散化的曲线边界，用配置化采样点数近似为多边形，并保留 `needs_exact_overlap = true`。
- Fallback：有孔、多 outer、非闭合 wire、BSPLINE/ELLIPSE 等暂未验证边界，降级为 bbox/诊断，不作为高置信度有限面 overlap。

**原因**：真实 STEP 文件中 CadQuery 的 `outerWire()` 路径已验证存在坑；`TopExp_Explorer` 是当前项目中对真实 STEP 更稳妥的路径。按 ring 面积识别 outer/holes 比“第一个 wire 一定是 outer”更稳健。

### 决策 3：Planar overlap 主算法采用本地 2D 多边形裁剪，不引入新依赖

**选择**：对 Level 2A 的简单凸多边形，使用本地实现的 2D polygon clipping 计算交集多边形面积：
- 先做 2D bbox 快速拒绝。
- 使用 Sutherland-Hodgman 或等价半平面裁剪算法处理凸多边形。
- 用 shoelace formula 计算 polygon area。
- `overlap_ratio = overlap_area / min(area_a, area_b)`。

当 face 边界包含可离散化曲线时，先按配置采样为多边形，再复用同一 overlap 流程，但方法字段必须表明采样来源。

**备选方案**：
- OCP 精确面域求交：精度最高，但 API 路径和异常处理复杂，不适合作为当前 L1 Level 2 修正。
- Shapely：实现成本低，但新增依赖，不符合当前项目“CadQuery/OCP 为核心依赖”的收敛方向。
- 继续 bbox 近似：实现最简单，但无法修正本变更要解决的误报。

**建议**：先实现无外部依赖的凸多边形裁剪，并对 unsupported/complex face 明确 fallback。后续若真实 STEP 中复杂面占比高，再单独引入精确 2D 布尔或受控依赖。

### 决策 4：Planar Contact 不再以 bbox overlap 作为默认通过条件

**选择**：`detect_planar_contact()` 的顺序调整为：
1. 过滤同 Part。
2. 检查两个 PLANE face 法向量是否反向。
3. 检查共面距离。
4. 使用同一个 `PlaneFrame` 提取两个 `PlaneTrimDomain`。
5. 对 supported domain 执行 polygon overlap。
6. 仅当 overlap 面积和比例达到阈值时输出 Planar Contact。
7. domain 提取或多边形裁剪失败时，才进入 bbox fallback；fallback 输出必须降低 confidence，并标记 `needs_exact_overlap = true`。

**输出参数建议**：
- `normal_angle_deg`
- `plane_distance`
- `overlap_area`
- `overlap_ratio`
- `overlap_method = "plane_polygon_clip" | "plane_polygon_sampled" | "bbox_fallback"`
- `plane_domain_supported_a/b`
- `needs_exact_overlap`

**原因**：bbox 仍适合 broad phase 和异常诊断，但不应作为“有限面确实重叠”的主证据。

### 决策 5：Tangency Contact 必须显式构造理论切线

**选择**：在无限几何关系通过后，计算圆柱-平面的理论切线：
- 圆柱轴线方向 `d` 与平面法向 `n` 垂直。
- 取圆柱轴线上一点 `a0`，计算其到平面的 signed distance `s = dot(a0 - plane_origin, n)`。
- 当 `abs(abs(s) - radius) <= max_distance_mm` 时，理论切线上的一点为 `t0 = a0 - s * n`。
- 切线方向为圆柱轴线方向 `d`。

随后将这条 3D line 同步投影/参数化到两个有限 domain：
- 在 `PlaneFrame` 中求 line 与 `PlaneTrimDomain` 的 2D 交集线段。
- 在圆柱公共 frame 中求该固定周向角是否落入 `CylinderTrimDomain`，并取圆柱轴向 interval。
- 将平面 line interval 与圆柱 axial interval 取交集，得到最终 `finite_tangent_overlap_length`。

**原因**：expanded AABB 只能说明两个形状空间上接近，不能说明理论切线落入有限平面面域，更不能说明圆柱 trimmed face 覆盖该切线。

### 决策 6：Tangency 复用圆柱 trimmed domain 工具

**选择**：Tangency 的圆柱有限域检查优先复用 `refine-cylindrical-contact-overlap` 规划的 `CylinderFrame` / `CylinderTrimDomain` / angle interval 工具。若两个 change 并行实现，应将这些数据结构放在 `src/l1_contact_detection/cylindrical_overlap.py`，供 Cylindrical Contact 和 Tangency Contact 共同调用。

Tangency 需要的圆柱 domain 能力包括：
- 提取轴向 interval。
- 判断 fixed tangent angle 是否在圆柱周向 coverage 内。
- 对完整 360° 圆柱面跳过周向限制。
- 提供 `uv_sampled` / fallback 方法字段。

**原因**：Tangency 与 Cylindrical 都需要从 CYLINDER face 提取有限 UV/domain。复用同一工具可减少两个判定器在周期角、跨零区间、非全局轴线方面产生不一致。

### 决策 7：Line overlap 独立成小模块，供 Tangency 和未来特征使用

**选择**：新增 `src/l1_contact_detection/line_overlap.py`，提供：
- `line_polygon_intervals(line_point_2d, line_dir_2d, polygon)`
- `intersect_1d_intervals(intervals_a, intervals_b)`
- `segment_overlap_length(interval_a, interval_b)`

初始版本只要求支持无孔凸多边形。对于 holes/复杂多边形，返回 unsupported，并由 Tangency fallback 逻辑处理。

**原因**：Tangency 的核心有限性检查是“无限切线与有限面域的线段交集”。将 line-polygon 逻辑独立出来，能避免把几何细节塞进 `tangency_contact.py`。

### 决策 8：新增容差项，避免把面积/线长阈值硬编码在判定器中

**新增配置建议**：

```yaml
geometry:
  min_planar_overlap_area_mm2: 1.0e-6
  min_planar_overlap_ratio: 0.0
  min_tangency_overlap_length_mm: 1.0e-6
  min_tangency_overlap_ratio: 0.0
  plane_edge_sample_count: 16
  max_plane_polygon_vertices: 256
```

这些配置进入 `Tolerances`。`bbox_overlap_min_ratio` 可保留给 fallback 或历史诊断字段，但不再作为 Planar 主路径的主要阈值。

## Risks / Trade-offs

- **[R1] 多边形裁剪不是完整 B-rep 精确求交** → 对 LINE-only 凸多边形可作为高置信度；对曲线离散化和复杂边界保留 `needs_exact_overlap = true`。
- **[R2] 真实 STEP 中 wire 顺序和方向可能不稳定** → 不依赖 wire 顺序；使用投影面积识别 outer；实现前/实现中将新增 API 验证记录同步到 `docs/verified_api/`。
- **[R3] 曲线边界采样可能漏掉细小重叠** → 采样数量配置化，并限制 sampled 方法的置信度；必要时后续升级为 pcurve/布尔求交。
- **[R4] 凸多边形算法无法覆盖所有平面 trimmed face** → unsupported domain 走 fallback，不把复杂结果伪装成精确 overlap。
- **[R5] Tangency 依赖圆柱 domain 工具的落地顺序** → 与 `refine-cylindrical-contact-overlap` 共用 `cylindrical_overlap.py`；若先实现本 change，则先实现 Tangency 所需的最小公共接口，再供 cylindrical change 复用。
- **[R6] 新逻辑更严格，contact 数量可能减少** → 这是修正误报的预期结果；测试必须覆盖标准矩形贴合、标准圆柱-平面相切仍通过。
