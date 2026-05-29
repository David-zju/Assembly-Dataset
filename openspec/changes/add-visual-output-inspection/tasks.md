## 1. 通用几何恢复与数据加载

- [ ] 1.1 设计并实现通用 `restore_face_map_from_step(step_file, parts, faces, metadata, tolerances)`，只依赖 `common.data_models`、指纹校验和 CadQuery/OCP，不导入 L0/L1 输出类。
- [ ] 1.2 保留现有 `src/l1_contact_detection/face_reloader.py` 对外行为，并改为委托到新的通用恢复函数，确保现有集成测试不破坏。
- [ ] 1.3 新增 `src/visual_inspection/data_loader.py`，读取 L0/L1 JSON 并构建 `part_uid`、`face_uid`、`contact_uid` 的查询索引。
- [ ] 1.4 为 STEP/L0 不匹配、`part_boundary_reliable=false`、缺失文件、无效 `face_uid` / `part_uid` / `contact_uid` 提供明确异常和中文诊断消息。
- [ ] 1.5 为通用恢复函数和 data loader 编写中文模块注释、函数 docstring 和小模型回归测试。

## 2. L0 可视化选择能力

- [ ] 2.1 新增 L0 selector：支持按 `face_uid`、多个 `face_uid`、`part_uid`、`geom_type` 和 unsupported 状态选择实体。
- [ ] 2.2 新增 L0 scene builder：将选择结果转换为 viewer 可渲染对象，包含对象角色、名称、颜色、透明度和诊断字段。
- [ ] 2.3 新增 `scripts/view_l0.py` CLI，支持指定 `--step`、`--l0`、`--face`、`--faces`、`--part`、`--geom-type`、`--unsupported`、`--context`。
- [ ] 2.4 在 `simple_l0_l1_assembly.step` 上验证按 face/part 高亮；对无效选择返回清晰错误。

## 3. L1 Contact 浏览与过滤

- [ ] 3.1 新增 contact index：从 L1 输出中提取 `contact_uid`、`contact_type`、confidence、`face_uid_pair`、关联 `part_uid` 和 `needs_exact_overlap`。
- [ ] 3.2 实现 contact 过滤：按 `contact_type`、`needs_exact_overlap`、`part_uid`、`face_uid`、confidence 阈值过滤。
- [ ] 3.3 实现 contact 排序：按 `contact_uid`、confidence、`contact_type` 排序，支持升序/降序。
- [ ] 3.4 新增 L1 scene builder：选中 contact 时高亮 face A / face B，并按 `--context none|part|all` 构建上下文对象。
- [ ] 3.5 新增 `scripts/browse_l1_contacts.py`，启动后提供可连续选择的 contact 列表，不要求用户每次重启脚本输入单个 `contact_uid`。
- [ ] 3.6 为浏览器实现基础交互：上下移动、搜索、类型过滤、`needs_exact_overlap` 过滤、显示当前 contact、退出。
- [ ] 3.7 在 `outputs/simple_l0_l1_assembly/l1_output.json` 上验证可浏览 2 个 contacts，并能连续切换高亮。

## 4. ocp_vscode 适配层

- [ ] 4.1 新增 `src/visual_inspection/ocp_viewer.py`，封装 `ocp_vscode.show()`、`show_object()`、`remove_object()` 和 viewer 更新逻辑。
- [ ] 4.2 新增 `src/visual_inspection/palettes.py`，定义 L0 face/part、unsupported face、L1 face A/B、上下文 part、`needs_exact_overlap` 的配色和透明度。
- [ ] 4.3 viewer 适配层在连接失败时返回可操作诊断，提示确认 VS Code OCP CAD Viewer 是否已启动。
- [ ] 4.4 自动测试中 mock viewer 适配层，验证 scene builder 输出对象名称、颜色、透明度和角色，不打开真实 GUI。
- [ ] 4.5 在 `cadquery` 环境中手动验证 ocp_vscode 对象树可点击、隐藏、隔离高亮对象。

## 5. 大模型与性能验证

- [ ] 5.1 对 `机器狗.STEP` 验证 L1 浏览器默认局部渲染：仅显示当前 contact 两个 face 和 parent part 上下文。
- [ ] 5.2 验证 `--context none` 只显示两个 contact faces。
- [ ] 5.3 验证 `--context all` 会给出大型模型性能提示，并能在用户明确请求时尝试全量上下文。
- [ ] 5.4 记录 `机器狗.STEP` 启动恢复 face_map 的耗时和首次 contact 渲染耗时，作为后续缓存优化基线。
- [ ] 5.5 确认可视化脚本不会修改 L0/L1 JSON 输出文件。

## 6. 文档、OpenSpec 与回归

- [ ] 6.1 更新 `TODO.md`，同步 L0/L1 可视化检查能力的完成状态或进行中状态。
- [ ] 6.2 更新 `docs/verified_api/`，记录本次验证到的 `ocp_vscode.show()` / `show_object()` 颜色、透明度、对象树和更新行为。
- [ ] 6.3 新增或更新用户文档，说明如何启动 VS Code OCP CAD Viewer、如何运行 `view_l0.py` 和 `browse_l1_contacts.py`。
- [ ] 6.4 运行 `conda run -n cadquery python -m pytest tests -q`，确保现有测试和新增测试通过。
- [ ] 6.5 运行 `openspec validate add-visual-output-inspection --strict`。
