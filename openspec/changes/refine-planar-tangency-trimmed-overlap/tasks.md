## 1. API 验证与文档同步

- [ ] 1.1 使用 CadQuery 构造矩形平面、错位矩形平面、带圆弧边界平面和带孔平面，验证 `TopExp_Explorer(face.wrapped, TopAbs_WIRE/EDGE)` 提取 wire/edge 的顺序、闭合性、edge geomType 和端点行为
- [ ] 1.2 验证平面局部 frame 构造：全局 XY/YZ/XZ 平面、任意斜平面中的 `face.normalAt()`、`BRep_Tool.Surface_s(face.wrapped).Pln()`、投影坐标方向是否稳定
- [ ] 1.3 验证 edge 离散化所需 API：LINE edge 端点、CIRCLE/ARC edge 采样点、异常 edge 的失败模式
- [ ] 1.4 将新增验证记录同步到 `docs/verified_api/face_planar.md`、`docs/verified_api/face_wires.md` 或新增专门的平面边界投影文档

## 2. 配置与数据结构

- [ ] 2.1 更新 `configs/thresholds.yaml`：新增 `min_planar_overlap_area_mm2`、`min_planar_overlap_ratio`、`min_tangency_overlap_length_mm`、`min_tangency_overlap_ratio`、`plane_edge_sample_count`、`max_plane_polygon_vertices`
- [ ] 2.2 更新 `src/common/tolerances.py`：在 `Tolerances` 中新增上述字段并从 YAML 加载，提供向后兼容默认值
- [ ] 2.3 新增 `src/l1_contact_detection/planar_overlap.py`：定义 `PlaneFrame`、`PlaneTrimDomain`、`PlanarOverlapResult` 等数据结构，所有函数编写中文 docstring
- [ ] 2.4 新增 `src/l1_contact_detection/line_overlap.py`：定义 line/polygon interval 与一维 interval overlap 相关数据结构和函数，所有函数编写中文 docstring

## 3. PlaneFrame 与 PlaneTrimDomain

- [ ] 3.1 实现 `build_plane_frame(face)`：使用材料外法向和 face center 构造稳定正交基，避免 normal 接近全局参考轴时退化
- [ ] 3.2 实现 `project_point_to_plane_frame(point, frame)`：将 3D 点转换为平面局部 2D 坐标，并提供反向诊断所需的投影残差
- [ ] 3.3 实现 `extract_plane_trim_domain(face, frame, tolerances)`：使用 `TopExp_Explorer` 遍历 wires/edges，将 closed wire 转换为 2D ring
- [ ] 3.4 实现 outer/holes 识别：按 ring 投影面积选择 outer boundary，其余 ring 标记为 holes；有 holes 时初始版本返回 unsupported/fallback
- [ ] 3.5 实现边界支持分级：LINE-only 无孔多边形为主路径；CIRCLE/ARC 可采样为多边形；BSPLINE/ELLIPSE、非闭合 wire、多 outer 或顶点数超限标记为 unsupported

## 4. 平面多边形 overlap

- [ ] 4.1 实现 2D bbox 快速拒绝：两个 PlaneTrimDomain bbox 不相交时直接返回 overlap_area = 0
- [ ] 4.2 实现 polygon area 与方向归一化：用 shoelace formula 计算面积，并将多边形顶点顺序规范化
- [ ] 4.3 实现凸多边形裁剪：使用 Sutherland-Hodgman 或等价半平面裁剪计算两个无孔凸多边形交集
- [ ] 4.4 实现 `compute_planar_overlap(domain_a, domain_b, tolerances)`：返回 overlap_area、overlap_ratio、overlap_method、needs_exact_overlap
- [ ] 4.5 编写平面 overlap 单元测试：完全重叠、部分重叠、bbox 相交但多边形不重叠、边界接触面积为 0、斜平面重叠

## 5. Planar Contact 集成

- [ ] 5.1 修改 `src/l1_contact_detection/planar_contact.py`：在法向量和共面距离通过后调用 PlaneTrimDomain 和 polygon overlap 主路径
- [ ] 5.2 将 `projected_bbox_overlap_ratio()` 从 Planar 主判定路径移除，仅保留为 unsupported/异常场景的 fallback 或诊断路径
- [ ] 5.3 更新 Planar Contact 输出参数：增加 `overlap_area`、`overlap_method`、`plane_domain_supported_a/b`、`needs_exact_overlap`
- [ ] 5.4 调整 Planar confidence 策略：LINE-only polygon clip 结果保持较高置信度；曲线采样和 bbox fallback 降低置信度并标记 `needs_exact_overlap = true`
- [ ] 5.5 编写 Planar Contact 集成测试：标准矩形贴合通过、距离超容差拒绝、法向不反向拒绝、同 Part 跳过、bbox 误报场景拒绝、复杂面 fallback 可诊断

## 6. Tangency 有限切线 overlap

- [ ] 6.1 实现理论切线计算：在圆柱轴线和平面无限几何关系通过后，计算切线点、切线方向和 distance_error
- [ ] 6.2 实现 `line_polygon_intervals()`：将理论切线投影到 PlaneFrame，并计算其与无孔凸 PlaneTrimDomain 的有效线段 interval
- [ ] 6.3 实现 `intersect_1d_intervals()` 与 `segment_overlap_length()`：用于平面切线 interval 与圆柱轴向 interval 的交集计算
- [ ] 6.4 复用或补齐 `CylinderTrimDomain` 最小接口：提取圆柱轴向 interval、判断 fixed tangent angle 是否在周向 coverage 内，支持完整 360° 圆柱
- [ ] 6.5 修改 `src/l1_contact_detection/tangency_contact.py`：将 `expanded_aabb_intersects()` 从主判定路径移除，改为理论切线 + PlaneTrimDomain + CylinderTrimDomain overlap
- [ ] 6.6 更新 Tangency 输出参数：增加 `tangent_overlap_length`、`plane_tangent_interval`、`cylinder_axial_interval`、`cylinder_angle_supported`、`overlap_method`、`needs_exact_overlap`
- [ ] 6.7 调整 Tangency confidence 策略：trimmed domain 主路径通过保持较高置信度；任一 domain fallback 时降低置信度并标记 `needs_exact_overlap = true`

## 7. Tangency 测试

- [ ] 7.1 新增标准圆柱-平面相切测试：理论切线位于平面边界内且圆柱有限轴向/周向覆盖时通过
- [ ] 7.2 新增平面太小测试：无限几何相切但理论切线落在 PlaneTrimDomain 外时拒绝
- [ ] 7.3 新增圆柱轴向不覆盖测试：理论切线与平面有交集但圆柱 trimmed 轴向 interval 不重叠时拒绝
- [ ] 7.4 新增圆柱周向不覆盖测试：理论切线对应周向角不在局部圆柱片 coverage 内时拒绝
- [ ] 7.5 新增非全局方向测试：圆柱轴线和平面方向不与全局坐标轴对齐时仍正确判定
- [ ] 7.6 新增 fallback 测试：复杂平面或圆柱 domain 提取失败时输出低置信度诊断字段，不伪装成精确 overlap

## 8. 回归、验证与收尾

- [ ] 8.1 运行 `conda run -n cadquery python -m pytest tests`，确保现有 L0/L1/integration 测试全部通过
- [ ] 8.2 运行新增的 Planar/Tangency overlap 单元测试和集成测试，确认 spec 中所有场景均有覆盖
- [ ] 8.3 运行 `openspec validate refine-planar-tangency-trimmed-overlap --strict`
- [ ] 8.4 检查 `ARCHITECTURE.md` 不变式：L1 仍只依赖 `common/*` 与 L0 输出数据结构，不引入 L2+ 依赖
- [ ] 8.5 若实现中发现新的 CadQuery/OCP API 行为或坑，同步补充到 `docs/verified_api/`
