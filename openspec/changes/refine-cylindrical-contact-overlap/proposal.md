## Why

当前 L1 的 Cylindrical Contact 已能判定孔轴类无限几何关系，但有限 trimmed cylinder face 的重叠验证仍不完整：轴向 overlap 使用 AABB 投影近似，周向覆盖仅标记 `needs_circumferential_check = true`，未实际判定。该问题会导致局部圆柱片、轴向错开的孔轴面在真实装配中产生误报，影响后续 L2 feature 和 L3 mate 的语义可靠性。

## What Changes

- **修改** Cylindrical Contact 判定：在现有 shaft/hole、共轴、半径匹配之后，增加有限圆柱面的轴向与周向 overlap 验证。
- **新增** 公共圆柱坐标系与圆柱 trimmed domain 提取：将两个共轴圆柱 face 的采样点投影到同一轴向/周向坐标系中比较，而不是直接比较各自原始 UV。
- **替换** 当前 `axis_bbox_interval` 作为 cylindrical 接触的主要轴向 overlap 方法；保留 bbox 方法仅作为诊断或 fallback。
- **新增** 配置项：周向最小重叠角度/比例、完整圆判断容差、圆柱 domain 采样数量。
- **增强** L1 输出参数：记录 `axial_overlap_method`、`circumferential_overlap_angle_deg`、`circumferential_overlap_ratio`、`circumferential_overlap_method`、`needs_exact_overlap` 等字段。
- **新增** 单元测试覆盖：轴向错开拒绝、局部圆柱周向错开拒绝、跨 `0/2π` 周向区间通过、非全局 Z 轴圆柱通过。
- **同步** `docs/verified_api/face_cylindrical.md`：归档 CadQuery/OCP 圆柱 `uvBounds()`、`positionAt()` 与周向参数行为验证。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `face-contact-detection`: Cylindrical Contact 从“共轴 + 半径 + AABB 轴向近似 + 周向待验证”升级为“共轴 + 半径 + 有限圆柱面轴向 overlap + 周向 overlap”判定。

## Impact

- **受影响模块**：
  - `src/l1_contact_detection/cylindrical_contact.py`
  - `src/l1_contact_detection/geometry_extractors.py`
  - 可选新增 `src/l1_contact_detection/cylindrical_overlap.py`
  - `src/common/tolerances.py`
  - `configs/thresholds.yaml`
- **测试影响**：
  - 扩展 `tests/test_l1/test_l1_detection.py`
  - 可新增 `tests/test_l1/test_cylindrical_overlap.py`
- **文档影响**：
  - 更新 `docs/verified_api/face_cylindrical.md`
  - 若实现发现设计偏差，同步更新本 change 的 design/spec/tasks
- **兼容性**：
  - 对完整 360° 孔轴配合应保持现有通过行为。
  - 对局部圆柱片和轴向错开场景会更严格，可能减少旧逻辑中的误报。
