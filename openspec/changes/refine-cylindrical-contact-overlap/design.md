## Context

L1 Cylindrical Contact 当前用于识别孔-轴类跨 Part 面接触。已有实现可以判断两个 `CYLINDER` face 是否分别为 shaft/hole、是否共轴、半径是否匹配，并用 `axis_bbox_interval()` 估算轴向重叠；但它没有实际验证周向覆盖，只在输出参数中标记 `needs_circumferential_check = true`。

这意味着当前逻辑更接近“无限圆柱面关系 + 有限面粗筛”，而不是完整的 trimmed cylinder face 接触。对完整 360° 孔轴配合通常足够，但对局部圆柱片、切开的孔壁、半圆槽、复杂 STEP 面片等场景容易误报。由于 L2 feature 和 L3 mate 会依赖 L1 FaceContact，Cylindrical Contact 的误报会向上污染 hole-shaft mate、hub 和 pattern 识别。

现有已验证 CadQuery/OCP API：
- `BRep_Tool.Surface_s(face.wrapped)` 可获取圆柱 surface
- `surf.Radius()` / `surf.Axis()` 可获取半径和轴线
- `face.uvBounds()` 可获取圆柱 face 的 U/V 参数范围
- `face.positionAt(u, v)` 可将 UV 参数点映射到 3D 点
- `face.normalAt(u, v)` 可用于 shaft/hole 判断

## Goals / Non-Goals

**Goals:**
- 用公共圆柱坐标系比较两个共轴圆柱 face 的有限接触区域。
- 将 Cylindrical Contact 的有限面验证拆成轴向 overlap 和周向 overlap 两部分。
- 用 `positionAt()` 采样替代 AABB 投影作为主要轴向 overlap 计算方式。
- 对完整 360° 圆柱面、局部圆柱片、跨 `0/2π` 的角度区间给出稳定判定。
- 在 L1 输出参数中记录轴向/周向 overlap 的数值、方法、是否仍需精确验证。
- 保持现有完整 hole-shaft 测试用例通过，并新增局部圆柱片误报防护测试。

**Non-Goals:**
- 不实现圆柱 trimmed face 的完整 pcurve 布尔运算或 OCP 精确面域求交。
- 不改变 Planar / Tangency Contact 的有限面重叠策略。
- 不改变 BVH broad phase 的候选生成策略。
- 不改变 L0 face_uid、Part 边界或跨进程恢复机制。
- 不新增 conical / spherical / toroidal 接触类型。

## Decisions

### 决策 1：建立公共圆柱坐标系，而不是直接比较两个 face 的原始 UV

**选择**：对通过共轴检查的两个圆柱 face，使用第一个圆柱的轴线作为公共 frame 的 Z 轴；构造稳定的 X/Y 正交基；把两个 face 的采样点都转换为 `(axial, angle)` 坐标后比较。

**原因**：两个 `Geom_CylindricalSurface` 的 U 原点可能不同。即使两个圆柱 face 在真实空间中周向重叠，其原始 `uvBounds()` 的 U 范围也未必在同一角度参考系下可直接比较。直接比较 `umin/umax` 容易产生误判。

**公共 frame 构造**：
- `origin = cyl_a.axis.Location()`
- `z = normalize(cyl_a.axis.Direction())`
- `reference = global Z`，若与 `z` 近似平行则改用 global X
- `x = normalize(reference × z)`
- `y = z × x`
- 对 3D 点 `p`：
  - `delta = p - origin`
  - `axial = dot(delta, z)`
  - `radial = delta - axial * z`
  - `angle = atan2(dot(radial, y), dot(radial, x)) mod 2π`

### 决策 2：用采样提取 CylinderTrimDomain

**选择**：新增 `CylinderTrimDomain` 数据结构，保存：
- `axial_interval: tuple[float, float]`
- `angular_intervals: list[tuple[float, float]]`
- `is_full_circle: bool`
- `sample_count: int`
- `method: "uv_sampled"`

通过 `face.uvBounds()` 取得 `umin, umax, vmin, vmax`，并使用 `positionAt()` 采样边界和中线点：
- 轴向：采样 `(u_i, vmin)` 与 `(u_i, vmax)`，投影到公共 frame 的 axial 轴，取 min/max。
- 周向：采样 `(u_i, v_mid)`，投影到公共 frame 的 angle；若 `umax - umin >= 2π - full_circle_angle_tol`，视为完整圆。

**原因**：相比 AABB 8 角点投影，UV 采样更贴近圆柱 trimmed face 的真实参数域，也能自然支持任意方向的圆柱轴线。相比完整 pcurve/布尔求交，采样法实现成本低，适合作为当前 L1 的 Level 2 判定。

### 决策 3：周向区间使用“最大空隙补集”归一化

**选择**：对非完整圆柱的采样 angle 集合，排序后寻找相邻角度之间的最大空隙；覆盖弧段取最大空隙的补集。若覆盖弧段跨 `0/2π`，拆成两个普通区间，例如 `[350°, 360°] + [0°, 10°]`。

**原因**：局部圆柱片的 U 范围可能跨越 `0/2π`，简单取 `min(angle), max(angle)` 会把很短的跨零弧段误解成接近完整圆。最大空隙补集能更稳定地估算局部角度覆盖。

### 决策 4：Cylindrical Contact 必须同时满足轴向和周向 overlap

**选择**：在现有无限几何检查通过后，执行：
1. `axial_overlap_length > 0`
2. `axial_overlap_ratio > min_overlap_length_ratio`
3. 若任一 face 为完整圆柱，则周向 overlap 对该 face 视为无限制
4. 若两者都是局部圆柱，则要求周向 overlap 同时满足：
   - `circumferential_overlap_angle_deg >= min_circumferential_overlap_deg`
   - `circumferential_overlap_ratio >= min_circumferential_overlap_ratio`

**输出参数**：
- `axial_overlap_length`
- `axial_overlap_ratio`
- `axial_overlap_method = "uv_sampled"`
- `circumferential_overlap_angle_deg`
- `circumferential_overlap_ratio`
- `circumferential_overlap_method = "uv_sampled_common_frame"`
- `is_full_circle_a`
- `is_full_circle_b`
- `needs_exact_overlap = true`

**置信度策略**：由于采样仍不是精确布尔，非完整圆柱片结果不得输出 `confidence = 1.0`。完整 360° 圆柱 + 轴向 UV 采样通过可保持较高置信度；局部圆柱片应略低并保留 `needs_exact_overlap = true`。

### 决策 5：保留 AABB interval 作为 fallback/诊断，不作为主判定

**选择**：`axis_bbox_interval()` 不删除，但 Cylindrical Contact 不再默认调用它作为主轴向 overlap 方法。若 `uvBounds()` 或 `positionAt()` 失败，可降级为 bbox interval，并必须在输出参数中记录 `axial_overlap_method = "axis_interval_bbox_fallback"`、`needs_exact_overlap = true`、降低 confidence。

**原因**：真实 STEP 上可能存在异常/退化面。fallback 能提高诊断能力，但不能让近似结果伪装成精确有限面接触。

### 决策 6：新增配置项并集中在 tolerances 中读取

**新增配置建议**：

```yaml
geometry:
  min_circumferential_overlap_ratio: 0.01
  min_circumferential_overlap_deg: 1.0
  full_circle_angle_tol_deg: 0.1
  cylinder_domain_sample_count: 16
```

这些配置进入 `Tolerances`，避免在判定器中硬编码。

## Risks / Trade-offs

- **[R1] 采样不是精确 trimmed face 布尔** → 输出保留 `needs_exact_overlap = true`，并将完整精确判定留给后续 Level 3。
- **[R2] U/V 参数域可能存在周期、方向翻转或异常边界** → 不直接比较原始 U；通过 `positionAt()` 转换到公共 frame；新增跨零和非全局轴测试。
- **[R3] sample_count 太低可能漏掉复杂局部边界** → 默认 16，并配置化；复杂面可提高采样数或未来接入 wire/pcurve 边界。
- **[R4] 对旧逻辑会更严格，可能减少原先输出的 contact 数量** → 这是预期修正；测试应覆盖完整圆柱孔轴配合不回退。
- **[R5] 真实 STEP 中局部圆柱 face 的 UV 行为需要更多验证** → 实施前/实施中应在 `docs/verified_api/face_cylindrical.md` 补充 CadQuery 构造模型和真实 STEP 样本验证记录。
