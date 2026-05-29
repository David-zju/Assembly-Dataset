# ocp_vscode 可视化检查

## API 说明

### `ocp_vscode.show(*cad_objs, names=None, colors=None, alphas=None, ...)`

用于向 VS Code OCP CAD Viewer 发送一组 CadQuery/OCP 对象。

```python
from ocp_vscode import show

show(
    face_a,
    face_b,
    names=["face A", "face B"],
    colors=[(255, 59, 48), (0, 188, 212)],
    alphas=[1.0, 1.0],
    show_parent=True,
)
```

- `names`: viewer 对象树中的显示名称。
- `colors`: RGB tuple 列表，例如 `(255, 59, 48)`。
- `alphas`: 透明度列表，`1.0` 为不透明。
- `show_parent`: 对 face/edge/vertex 等子形状显示 parent wireframe，有助于定位局部面。

### `ocp_vscode.show_object(obj, name=None, options=None, update=False, ...)`

用于显示或更新单个对象。当前项目第一版可视化检查优先使用 `show()` 完整刷新 scene；后续若需要更细粒度增量更新，可使用 `show_object(update=True)`。

### `ocp_vscode.show_clear()` / `reset_show()`

可清空 viewer 或内部对象列表。自动测试中不调用真实 viewer，而是 mock 适配层。

## 预期使用场景

- L0：按 `face_uid`、`part_uid`、`geom_type` 或 unsupported 状态高亮检查。
- L1：按 `contact_uid` 高亮两个接触 face，并用半透明 parent Part 提供上下文。
- 大模型：默认只显示局部 contact 上下文，避免整机渲染卡顿。

## 注意事项和坑

### 不要在核心管道中导入 ocp_vscode

`ocp_vscode` 会导入 matplotlib、websocket 等 GUI/通信相关依赖，且需要 VS Code viewer 运行。项目核心管道 `scripts/run_pipeline.py` 不应导入它；只允许在 `src/visual_inspection/ocp_viewer.py` 和可视化脚本路径中延迟导入。

### viewer 连接失败应是可视化错误，不是数据准备错误

如果 VS Code OCP CAD Viewer 未启动，`show()` 可能无法连接 websocket。此时应提示用户启动 viewer，但不应否定 JSON 读取、selector 和 scene builder 的正确性。

### 大模型避免默认全量上下文

`机器狗.STEP` 约 19759 个 face。全量渲染会明显拖慢交互，L1 contact 检查默认应只显示两个 contact face 和 parent Part 上下文。

## 已验证场景

### 验证场景 1：函数签名与颜色/透明度参数

**日期**：2026-05-29
**模型/数据**：当前 `cadquery` conda 环境，`ocp_vscode 3.3.4`
**代码**：
```python
import inspect
import ocp_vscode
from ocp_vscode import show, show_object

print(ocp_vscode.__version__)
print(inspect.signature(show))
print(inspect.signature(show_object))
```
**预期行为**：`show()` 支持 `names`、`colors`、`alphas`；`show_object()` 支持 `name`、`options`、`update`。
**实际结果**：符合预期。
**结论**：可通过薄适配层向 viewer 发送已命名、已着色、带透明度的高亮对象。

### 验证场景 2：dry-run scene 构造

**日期**：2026-05-29
**模型/数据**：`outputs/simple_l0_l1_assembly/l0_output.json`、`outputs/simple_l0_l1_assembly/l1_output.json`
**代码**：
```bash
conda run -n cadquery python scripts/view_l0.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --face f-0001-00006 \
  --context part \
  --dry-run

conda run -n cadquery python scripts/browse_l1_contacts.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --l1 outputs/simple_l0_l1_assembly/l1_output.json \
  --show c-000002 \
  --dry-run
```
**预期行为**：不打开 viewer，但输出将要显示的对象名称、角色、颜色和透明度。
**实际结果**：可正确生成 L0 face + context part，以及 L1 contact 两个 face + parent part 上下文。
**结论**：可视化数据准备和 scene builder 可在无 GUI 自动测试路径中验证。
