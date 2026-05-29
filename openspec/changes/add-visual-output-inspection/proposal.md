## Why

当前 L0/L1 输出主要以 JSON 形式保存，开发者需要人工阅读 `face_uid`、`contact_uid` 和参数字段来判断标注结果是否可信。对于 `机器狗.STEP` 这类大型装配体，单靠 JSON 很难快速定位误报、漏报和 `needs_exact_overlap` 的真实几何原因，因此需要一个能结合原始 STEP 模型进行高亮检查的可视化诊断能力。

## What Changes

- 新增一个独立的可视化检查模块，用于从原始 STEP、L0 JSON 和 L1 JSON 恢复运行期几何并高亮检查输出实体。
- 支持 L0 检查：按 `face_uid`、`part_uid`、几何类型或 unsupported 状态高亮 face/part。
- 支持 L1 检查：提供可浏览的 contact 列表，并在选择 `contact_uid` 后高亮对应两个 face 及可选上下文 part。
- 默认面向大型模型采用局部渲染策略，只显示当前选中 contact 的两个 face 和相关 part，避免默认加载整机导致交互卡顿。
- 将跨进程恢复 `face_uid -> cq.Face` 的能力抽象为可被 L0/L1/L2+ 可视化复用的通用组件；如需迁移，应避免 `common` 反向依赖 L0 实现类。
- 不改变 L0/L1 JSON 格式和管道主流程；该能力作为诊断工具层存在。

## Capabilities

### New Capabilities

- `visual-output-inspection`: 覆盖 L0/L1 输出的可视化检查、contact 浏览、高亮渲染和几何重载能力。

### Modified Capabilities

无。

## Impact

- 影响新增代码区域：`src/visual_inspection/`、`scripts/view_l0.py`、`scripts/browse_l1_contacts.py`。
- 可能迁移或抽象现有 `src/l1_contact_detection/face_reloader.py`，以便 L0/L1 可视化共同复用。
- 新增运行时诊断依赖：`ocp_vscode`。该依赖已存在于 `cadquery` conda 环境中，但应保持为可视化脚本依赖，不进入核心管道必需路径。
- 测试层需要覆盖 JSON 读取、face/contact 选择、过滤排序和渲染对象构造；GUI/VS Code viewer 本身可通过薄封装 mock，不要求在自动测试中打开真实窗口。
