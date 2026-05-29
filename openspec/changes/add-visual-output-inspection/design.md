## Context

项目当前已完成 L0→L1 管道，L0 输出包含 Part/Face manifest 与几何指纹，L1 输出包含 `FaceContact` 列表、`contact_uid`、`face_uid_pair`、接触类型、置信度和诊断参数。JSON 能支持程序化验证，但不适合人工快速判断面接触是否真实，尤其是 `机器狗.STEP` 这类包含 298 个 Part、19759 个 face、1998 个 L1 contacts 的大型模型。

现有 `src/l1_contact_detection/face_reloader.py` 已能通过 `l0_output.json + 原始 STEP` 恢复跨进程 `face_uid -> cq.Face` 映射。该能力本质上是 L0 UID 与原始几何之间的通用桥梁，不应长期作为 L1 专属模块存在。开发环境中的 `cadquery` conda 环境已安装 `ocp_vscode 3.3.4`，其 `show()` / `show_object()` 支持对象命名、颜色、透明度、更新与 VS Code viewer 对象树交互。

## Goals / Non-Goals

**Goals:**

- 提供独立的可视化检查模块，用于 L0/L1 输出诊断，不改变管道算法和 JSON schema。
- 支持按 `face_uid`、`part_uid`、几何类型和 unsupported 状态检查 L0 输出。
- 支持以列表方式浏览 L1 contacts，并在选择 contact 后高亮两个接触 face。
- 支持大型模型的局部渲染，默认只显示当前 contact 相关的 face/part。
- 将 face 重载能力整理为可被 L0/L1/L2+ 可视化复用的通用组件，同时保持架构依赖方向。
- 将 `ocp_vscode` 调用隔离在 viewer 适配层，便于测试和未来替换 viewer。

**Non-Goals:**

- 不实现 CAD 几何编辑、手工修正标注或写回 JSON。
- 不在自动测试中打开真实 VS Code viewer 或要求 GUI 环境。
- 不在第一版实现完整 Web 前端或自定义 Three.js viewer。
- 不重新运行 L1 检测来生成可视化数据；可视化应使用已有 L0/L1 输出。
- 不默认渲染大型装配体的全部几何。

## Decisions

### 决策 1：新增 `src/visual_inspection/` 作为诊断工具层

新增模块建议结构：

```text
src/visual_inspection/
├── data_loader.py       # 读取 L0/L1 JSON，恢复 dataclass 或轻量索引
├── face_reloader.py     # 可选：通用 face_uid -> cq.Face 恢复入口
├── selectors.py         # face/contact/part 选择与过滤
├── scene_builder.py     # 将选择结果转换为待渲染对象列表
├── palettes.py          # 高亮配色、透明度、命名规则
└── ocp_viewer.py        # ocp_vscode 适配层
```

理由：可视化是横切诊断能力，不属于 L0/L1 算法核心。单独模块可以清楚隔离 GUI 依赖、命令行交互和高亮策略。

替代方案：把脚本直接写在 `scripts/` 中。该方案实现快，但容易复制 JSON 读取、face 恢复和选择逻辑，不利于后续 L2/L3 扩展。

### 决策 2：抽象 face 重载能力，避免 `common` 反向依赖 L0

`restore_l0_face_map_from_step()` 可被迁移或包装为通用能力，但不应让 `src/common/` 直接依赖 `src/l0_face_extraction.l0_output.L0Output`。推荐抽象为：

```text
restore_face_map_from_step(step_file, parts, faces, metadata, tolerances)
```

其中 `parts` 为 `list[Part]`，`faces` 为 `list[FaceMetadata]`，`metadata` 提供 `import_strategy` 和 `part_boundary_reliable`。L0/L1/visual 调用方负责从 `L0Output` 或 JSON 中取出这些通用数据。

理由：`Part` 和 `FaceMetadata` 定义在 `common.data_models`，属于全局数据合同；`L0Output` 是 L0 层输出结构，不应被 `common` 反向导入。

替代方案：保留在 `src/l1_contact_detection/face_reloader.py` 并由可视化模块导入。该方案最小变更，但语义上会出现 L0 可视化依赖 L1 模块的问题。

### 决策 3：第一版交互列表采用终端 Contact Browser + ocp_vscode 动态高亮

提供 `scripts/browse_l1_contacts.py`，启动后读取 L1 contacts 并在终端中提供可过滤列表。用户通过键盘选择 contact，脚本调用 `ocp_vscode.show()` / `show_object(update=True)` 刷新 viewer 中的高亮对象。

建议交互：

```text
j/k 或 ↑/↓    上下切换 contact
Enter         高亮当前 contact
/             搜索 contact_uid / part_uid / face_uid
t             按 contact_type 过滤
e             只看 needs_exact_overlap=true
c             按 confidence 阈值过滤
q             退出
```

理由：`ocp_vscode` 内置对象树适合显示 CAD 对象，但不提供自定义 contact 表格控件。终端列表实现成本低、可测试性好，且与 VS Code viewer 可以并排使用。

替代方案 A：只把所有 contacts 作为 viewer 树节点发送给 ocp_vscode。该方案简单，但对大型模型会产生大量对象，且筛选能力弱。

替代方案 B：实现 Web/Streamlit/Tkinter GUI。该方案体验更强，但引入新的 UI 运行时和测试复杂度，不适合作为第一版。

### 决策 4：大型模型默认局部渲染

L1 contact 检查默认只显示：

- contact face A
- contact face B
- 两个 parent part 的半透明上下文

可选 `--context all` 才尝试渲染全装配体，可选 `--context none` 只显示两个 face。

理由：`机器狗.STEP` 体量较大，默认全量渲染会拖慢检查流程。局部渲染更符合“逐个验证 contact”的工作方式。

### 决策 5：测试重点放在选择、索引和 scene 构造

自动测试不打开 VS Code viewer，而是 mock `ocp_viewer` 适配层，验证：

- L0/L1 JSON 读取正确。
- `contact_uid`、`part_uid`、`face_uid` 查询正确。
- filter/sort 结果正确。
- scene builder 输出的对象名称、颜色、alpha 和角色正确。
- face_map 恢复在 fixture STEP 上保持稳定。

## Risks / Trade-offs

- [Risk] 大型 STEP 每次恢复 face_map 耗时较长。→ Mitigation: 支持启动时一次性恢复并在浏览期间缓存；后续可增加轻量缓存清单，但第一版不引入持久化缓存。
- [Risk] `ocp_vscode` viewer 连接不可用或 VS Code 插件未启动。→ Mitigation: viewer 适配层检测连接失败并给出明确提示；核心列表/选择逻辑仍可测试。
- [Risk] 将 face 重载迁移到 `common` 时破坏依赖方向。→ Mitigation: 通用函数只依赖 `common.data_models`、`common.fingerprint`、`common.tolerances` 和 CadQuery/OCP，不导入 L0/L1 输出类。
- [Risk] `001650主臂装配体1.STEP` 无有效 face，无法作为可视化验证模型。→ Mitigation: 文档中明确使用 `simple_l0_l1_assembly.step` 和 `机器狗.STEP` 验证；无效模型应给出无 face 的诊断提示。
- [Risk] 终端列表不是完整 GUI。→ Mitigation: 第一版优先解决连续浏览和高亮检查；后续可以在同一 selector/scene_builder 基础上增加 Web GUI。

## Migration Plan

1. 保留现有 `src/l1_contact_detection/face_reloader.py` 行为，先新增通用恢复函数并让旧入口委托到新入口，避免破坏现有测试。
2. 新增 `src/visual_inspection/` 模块和脚本。
3. 为 `simple_l0_l1_assembly.step` 建立自动测试，覆盖 L0/L1 可视化数据准备。
4. 手动在 `cadquery` 环境中用 `ocp_vscode` 验证小模型；对 `机器狗.STEP` 验证局部 contact 渲染。

## Open Questions

- 第一版终端交互使用标准库 `cmd`/`curses`，还是引入 `textual`/`questionary`？当前环境已有 `questionary`，但方向键实时列表体验可能需要额外确认。
- 是否需要为 contact 浏览提供批量标记功能，例如人工确认/误报记录？目前不在本 change 范围内。
- 是否需要在 L0/L1 JSON 中记录可视化辅助信息？当前设计不需要，但未来若恢复性能不足，可另设诊断缓存文件。
