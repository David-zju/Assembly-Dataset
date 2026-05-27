## Why

当前 L1 的 Planar Contact 和 Tangency Contact 已能判断无限几何关系，但有限 trimmed face 的重叠验证仍主要依赖 bbox 近似：Planar 使用平面投影 bbox overlap，Tangency 使用 expanded AABB 相交作为有限范围检查。该近似会把 bbox 相交但真实面域或切线无交集的 face pair 误报为接触，进而污染 L2 feature 和 L3 mate 识别。

## What Changes

- **修改** Planar Contact 判定：在法向量反向、共面距离通过后，使用平面局部坐标系中的 trimmed face 边界重叠计算作为主要有限面验证，不再把 bbox overlap 作为默认通过依据。
- **新增** 平面局部 2D domain 提取：基于 `TopExp_Explorer` 遍历真实 STEP face 的 wire/edge，将平面 face 边界投影到 `PlaneFrame` 中形成 `PlaneTrimDomain`。
- **新增** 简单多边形 overlap 判定：对无孔、边界可离散化的有限平面 face 计算 2D 多边形面积重叠，并输出 overlap 面积、比例与方法字段。
- **修改** Tangency Contact 判定：显式构造圆柱-平面的理论切线，并验证切线与有限平面 face domain、有限圆柱 face domain 是否有足够重叠。
- **新增** fallback 与置信度策略：复杂边界、有孔面、BSPLINE/ELLIPSE 等暂不支持精确多边形化的场景可降级为 bbox/采样诊断，但必须降低 confidence 并标记 `needs_exact_overlap = true`。
- **新增** 单元测试覆盖：Planar bbox 误报拒绝、部分重叠通过、有孔/复杂面 fallback、Tangency 切线落在平面外拒绝、圆柱有限范围不覆盖切线拒绝、非全局坐标方向通过。
- **同步** `docs/verified_api/`：补充平面 face wire/edge 投影、边界离散化与切线验证相关的 CadQuery/OCP API 记录。

## Capabilities

### New Capabilities

（无）

### Modified Capabilities

- `face-contact-detection`: Planar Contact 从“共面反向 + bbox 投影近似”升级为“共面反向 + trimmed plane domain 重叠”；Tangency Contact 从“无限切向关系 + expanded AABB”升级为“无限切向关系 + 理论切线在两个有限 trimmed face domain 中均有效”。

## Impact

- **受影响模块**：
  - `src/l1_contact_detection/planar_contact.py`
  - `src/l1_contact_detection/tangency_contact.py`
  - `src/l1_contact_detection/geometry_extractors.py`
  - 可新增 `src/l1_contact_detection/planar_overlap.py`
  - 可新增 `src/l1_contact_detection/line_overlap.py`
  - `src/common/tolerances.py`
  - `configs/thresholds.yaml`
- **测试影响**：
  - 扩展现有 L1 contact detection 测试
  - 可新增 `tests/test_l1/test_planar_overlap.py`
  - 可新增 `tests/test_l1/test_tangency_overlap.py`
- **文档影响**：
  - 更新 `docs/verified_api/face_planar.md`
  - 更新 `docs/verified_api/face_wires.md` 或新增平面边界投影 API 记录
  - 若实现与设计有差异，同步更新本 change 的 design/spec/tasks
- **兼容性**：
  - 对规则矩形平面贴合和标准圆柱-平面相切场景应保持通过行为。
  - 对仅 bbox/AABB 相交但真实有限面域无交集的场景会更严格，可能减少旧逻辑中的误报。
