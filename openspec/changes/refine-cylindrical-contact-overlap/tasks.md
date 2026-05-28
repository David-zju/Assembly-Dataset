## 1. API 验证与文档同步

- [x] 1.1 使用 CadQuery 构造完整圆柱 shaft、带孔 block 的 hole、局部圆柱片，验证 `face.uvBounds()` 的 U/V 范围、`positionAt(u, v)` 的 3D 坐标、`normalAt(u, v)` 的方向行为
- [x] 1.2 验证非全局 Z 轴圆柱（例如沿 X/Y 或任意斜轴）在 `surf.Axis()`、`positionAt()`、公共 frame 投影下的轴向/周向行为
- [x] 1.3 将新增验证记录同步到 `docs/verified_api/face_cylindrical.md`，包含完整圆、局部圆柱片、跨 `0/2π` 周向区间、非全局轴线四类场景

## 2. 配置与数据结构

- [x] 2.1 更新 `configs/thresholds.yaml`：新增 `min_circumferential_overlap_ratio`、`min_circumferential_overlap_deg`、`full_circle_angle_tol_deg`、`cylinder_domain_sample_count`
- [x] 2.2 更新 `src/common/tolerances.py`：在 `Tolerances` 中新增上述字段并从 YAML 加载，提供合理默认值
- [x] 2.3 新增 `src/l1_contact_detection/cylindrical_overlap.py`：定义 `CylinderFrame`、`CylinderTrimDomain`、`IntervalOverlap` 等数据结构，所有函数编写中文 docstring

## 3. 公共圆柱坐标系

- [x] 3.1 实现 `build_cylinder_frame(axis)`：基于圆柱轴线构造稳定正交基，避免轴线接近全局参考方向时退化
- [x] 3.2 实现 `project_point_to_cylinder_frame(point, frame)`：将 3D 点转换为 `(axial, angle, radial_distance)`，angle 归一化到 `[0, 2π)`
- [x] 3.3 编写公共 frame 单元测试：全局 Z 轴、全局 X/Y 轴、斜轴圆柱的投影结果稳定且可解释

## 4. CylinderTrimDomain 提取

- [x] 4.1 实现 `extract_cylinder_trim_domain(face, frame, tolerances)`：基于 `uvBounds()` 与 `positionAt()` 采样提取轴向区间和周向区间
- [x] 4.2 实现完整圆识别：当 `umax - umin >= 2π - full_circle_angle_tol` 时标记 `is_full_circle = true`
- [x] 4.3 实现非完整圆周向区间归一化：使用最大空隙补集算法，将跨 `0/2π` 的覆盖拆分为普通区间列表
- [x] 4.4 实现异常处理：`uvBounds()` / `positionAt()` 失败时返回可诊断错误，供 Cylindrical Contact 降级为 bbox fallback

## 5. Overlap 计算

- [x] 5.1 实现轴向 overlap 计算：返回 `axial_overlap_length`、`axial_overlap_ratio`，ratio 使用较短轴向区间长度作为分母
- [x] 5.2 实现周向 overlap 计算：完整圆与任意区间相交时按对方覆盖处理；两个局部区间列表相交时求总 overlap angle
- [x] 5.3 实现周向阈值判断：同时检查 `min_circumferential_overlap_deg` 与 `min_circumferential_overlap_ratio`
- [x] 5.4 编写 overlap 单元测试：不重叠、部分重叠、完全包含、跨零点、完整圆与局部圆

## 6. Cylindrical Contact 集成

- [x] 6.1 修改 `src/l1_contact_detection/cylindrical_contact.py`：在共轴/半径检查后调用 CylinderTrimDomain 提取与 overlap 判定
- [x] 6.2 将当前 `axis_bbox_interval()` 从主路径移除，仅作为 `uv_sampled` 失败时的 fallback/诊断路径
- [x] 6.3 更新 contact 参数输出：增加 `axial_overlap_method`、`circumferential_overlap_angle_deg`、`circumferential_overlap_ratio`、`circumferential_overlap_method`、`is_full_circle_a/b`、`needs_exact_overlap`
- [x] 6.4 调整 confidence 策略：完整圆 + UV sampled 通过保持较高置信度；局部圆柱片或 fallback 结果降低置信度并标记 `needs_exact_overlap = true`

## 7. 测试

- [x] 7.1 更新现有 Cylindrical Contact 测试：完整 shaft + 完整 hole 仍应通过，两 shaft/两 hole 和半径不匹配仍应拒绝
- [x] 7.2 新增轴向错开测试：共轴同半径但公共 frame 轴向区间不重叠时必须拒绝
- [x] 7.3 新增局部圆柱片周向重叠测试：共轴同半径、轴向重叠、周向重叠时通过
- [x] 7.4 新增局部圆柱片周向错开测试：共轴同半径、轴向重叠、周向无 overlap 时拒绝
- [x] 7.5 新增跨 `0/2π` 测试：短跨零弧段与真实重叠区间应通过，且不被误判为完整圆
- [x] 7.6 新增非全局 Z 轴测试：沿 X/Y 或斜轴的圆柱配合应正确计算轴向与周向 overlap
- [x] 7.7 运行 `conda run -n cadquery python -m pytest tests`，确保现有 L0/L1/integration 测试全部通过

## 8. OpenSpec 与收尾

- [x] 8.1 运行 `openspec validate refine-cylindrical-contact-overlap --strict`
- [x] 8.2 检查 `ARCHITECTURE.md` 不变式：L1 仍只依赖 common/* 与 L0 输出数据结构，不引入 L2+ 依赖
- [x] 8.3 若实现中发现新的 CadQuery/OCP API 行为或坑，同步补充到 `docs/verified_api/face_cylindrical.md`
