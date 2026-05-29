# scripts 使用说明

本目录存放面向开发与检查流程的 CLI 入口脚本。运行脚本前建议先进入仓库根目录，并激活 `cadquery` 环境：

```bash
cd /home/tml104/Assembly-Dataset
conda activate cadquery
```

如果暂时不想激活环境，也可以用 `conda run -n cadquery python ...` 的形式运行。以下示例默认已经处于仓库根目录和 `cadquery` 环境中。

## 通用约定

- 输入 STEP 与输出 JSON 必须来自同一次或匹配的管道运行，否则可视化脚本可能无法从 `face_uid` 恢复对应几何面。
- 可视化脚本依赖 `ocp_vscode`。在 VS Code 中先运行 `OCP CAD Viewer: Open Viewer`，若后端端口是 `3939`，脚本中传入 `--port 3939`。
- 可视化脚本都支持 `--dry-run`，用于只检查将要显示哪些对象，不连接 OCP CAD Viewer。
- 当前环境中 `ocp_vscode` 需要先于 CadQuery/OCP 导入，以避免 `pyexpat` 动态库符号冲突。相关入口脚本已经在文件开头做了预导入，修改脚本时不要随意移除。
- 新增、删除或修改 `scripts/` 下的脚本时，必须同步更新本文档，至少说明用途、运行命令、关键参数、输入输出和环境注意事项。

## run_pipeline.py

用途：从 STEP 装配体运行标注管道。目前默认执行 L0 和 L1，生成 `l0_output.json` 与 `l1_output.json`。

基本用法：

```bash
python scripts/run_pipeline.py test_case/simple_l0_l1_assembly.step -o outputs/simple_l0_l1_assembly
```

中文路径或带空格路径请加引号：

```bash
python scripts/run_pipeline.py "test_case/机器狗.STEP" -o "outputs/机器狗"
```

只运行 L0，不执行 L1：

```bash
python scripts/run_pipeline.py "test_case/机器狗.STEP" -o "outputs/机器狗_l0_only" --skip-l1
```

常用参数：

- `step_file`：必填，输入 `.step` 或 `.stp` 文件。
- `-o, --output-dir`：输出目录；不传时读取 `configs/pipeline.yaml` 中的默认设置。
- `--pipeline-config`：指定自定义 `pipeline.yaml`。
- `--thresholds`：指定自定义 `thresholds.yaml`。
- `--skip-l1`：只运行 L0。

输出：

- `l0_output.json`：L0 face/part 输出。
- `l1_output.json`：L1 contact 输出，除非使用 `--skip-l1`。
- 标准输出会打印本次运行的 metadata 与各层摘要。

## view_l0.py

用途：结合原始 STEP 与 `l0_output.json`，在 OCP CAD Viewer 中高亮检查 L0 的 face 或 part。

运行前需要准备：

- 原始 STEP 文件，例如 `test_case/simple_l0_l1_assembly.step`。
- 与该 STEP 匹配的 `l0_output.json`。
- 已打开 OCP CAD Viewer；常见端口为 `3939`。

高亮单个 face：

```bash
python scripts/view_l0.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --face face-000001 \
  --context part \
  --port 3939
```

高亮多个 face：

```bash
python scripts/view_l0.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --faces face-000001,face-000002 \
  --port 3939
```

按 part 或几何类型检查：

```bash
python scripts/view_l0.py --step test_case/simple_l0_l1_assembly.step --l0 outputs/simple_l0_l1_assembly/l0_output.json --part part-000001 --port 3939
python scripts/view_l0.py --step test_case/simple_l0_l1_assembly.step --l0 outputs/simple_l0_l1_assembly/l0_output.json --geom-type PLANE --port 3939
python scripts/view_l0.py --step test_case/simple_l0_l1_assembly.step --l0 outputs/simple_l0_l1_assembly/l0_output.json --unsupported --port 3939
```

只打印将显示的对象，不连接 Viewer：

```bash
python scripts/view_l0.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --face face-000001 \
  --dry-run
```

选择方式必须且只能指定一种：

- `--face`：单个 `face_uid`。
- `--faces`：逗号分隔的多个 `face_uid`。
- `--part`：某个 `part_uid` 下的所有 face。
- `--geom-type`：某类几何面，例如 `PLANE`。
- `--unsupported`：所有未支持的 face。

`--context` 控制上下文显示：

- `none`：只显示被选中的 face。
- `part`：同时显示所属 part 的半透明上下文。

## browse_l1_contacts.py

用途：结合原始 STEP、`l0_output.json` 与 `l1_output.json`，交互式浏览并高亮检查 L1 contacts。它适合在列表中切换不同 `contact_uid`，逐个检查接触结果。

运行前需要准备：

- 原始 STEP 文件。
- 与该 STEP 匹配的 `l0_output.json`。
- 基于同一 L0 输出生成的 `l1_output.json`。
- 已打开 OCP CAD Viewer；常见端口为 `3939`。

直接显示某个 contact，适合快速复查：

```bash
python scripts/browse_l1_contacts.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --l1 outputs/simple_l0_l1_assembly/l1_output.json \
  --show c-000002 \
  --port 3939
```

进入交互式浏览：

```bash
python scripts/browse_l1_contacts.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --l1 outputs/simple_l0_l1_assembly/l1_output.json \
  --port 3939
```

带初始过滤条件进入：

```bash
python scripts/browse_l1_contacts.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --l1 outputs/simple_l0_l1_assembly/l1_output.json \
  --type planar_overlap \
  --min-confidence 0.8 \
  --needs-exact \
  --port 3939
```

常用参数：

- `--context none|part|all`：控制 contact 的上下文显示。默认 `part`；`all` 会显示全模型上下文，大模型上可能较慢。
- `--type`：初始按 `contact_type` 过滤。
- `--needs-exact`：初始只显示 `needs_exact_overlap=true` 的 contact。
- `--min-confidence`：初始最小置信度。
- `--sort contact_uid|confidence|contact_type`：初始排序字段。
- `--desc`：降序排序。
- `--show`：非交互模式，传入 `contact_uid` 或当前列表 index 后直接显示。
- `--dry-run`：只打印场景对象，不连接 Viewer。
- `--port`：OCP CAD Viewer 后端端口。

交互命令：

- `list [N]`：列出当前过滤结果前 N 条，默认 20。
- `show [INDEX_OR_CONTACT_UID]`：显示指定 index 或 `contact_uid`；不传参数时显示当前位置。
- `j` / `next`：移动到下一条并显示。
- `k` / `prev`：移动到上一条并显示。
- `search TEXT`：按 `contact_uid`、`part_uid`、`face_uid` 或 `contact_type` 搜索。
- `type TYPE|all`：按 contact 类型过滤，`all` 表示清除该过滤。
- `exact on|off|all`：按 `needs_exact_overlap` 过滤。
- `conf VALUE|all`：设置或清除最小置信度。
- `part PART_UID|all`：按参与的 part 过滤。
- `face FACE_UID|all`：按参与的 face 过滤。
- `q` / `quit`：退出。

只检查命令和数据选择是否正确，不更新 Viewer：

```bash
python scripts/browse_l1_contacts.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --l1 outputs/simple_l0_l1_assembly/l1_output.json \
  --show c-000002 \
  --dry-run
```
