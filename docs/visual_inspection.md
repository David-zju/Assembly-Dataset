# L0/L1 可视化检查

本文档说明如何使用 `ocp_vscode` 检查 L0/L1 输出。可视化工具只读取已有 JSON 和原始 STEP，不会重跑 L1，也不会改写输出文件。

## 环境准备

```bash
conda activate cadquery
```

在 VS Code 中确保 OCP CAD Viewer 扩展可用，并打开 viewer 面板。若只想验证选择和 scene 构造，可加 `--dry-run`，此时不会连接 viewer。

## 检查 L0 face

```bash
python scripts/view_l0.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --face f-0001-00006
```

带 parent Part 上下文：

```bash
python scripts/view_l0.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --face f-0001-00006 \
  --context part
```

其他选择方式：

```bash
python scripts/view_l0.py --step test_case/simple_l0_l1_assembly.step --l0 outputs/simple_l0_l1_assembly/l0_output.json --part p-0001
python scripts/view_l0.py --step test_case/simple_l0_l1_assembly.step --l0 outputs/simple_l0_l1_assembly/l0_output.json --geom-type PLANE
python scripts/view_l0.py --step test_case/simple_l0_l1_assembly.step --l0 outputs/simple_l0_l1_assembly/l0_output.json --unsupported
```

## 浏览 L1 contacts

启动交互式 contact browser：

```bash
python scripts/browse_l1_contacts.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --l1 outputs/simple_l0_l1_assembly/l1_output.json
```

常用命令：

```text
list 20          列出前 20 条 contacts
show 0           显示当前列表第 0 条 contact
show c-000002    显示指定 contact_uid
search p-0003    搜索 contact_uid / part_uid / face_uid / contact_type
type planar      只看某类 contact
type all         清除类型过滤
exact on         只看 needs_exact_overlap=true
exact all        清除 needs_exact 过滤
conf 0.9         只看 confidence >= 0.9
part p-0001      只看涉及某个 Part 的 contacts
face f-0001-00006 只看涉及某个 face 的 contacts
q                退出
```

非交互显示单个 contact：

```bash
python scripts/browse_l1_contacts.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --l1 outputs/simple_l0_l1_assembly/l1_output.json \
  --show c-000002
```

## 大模型建议

对 `机器狗.STEP`，默认使用局部上下文：

```bash
python scripts/browse_l1_contacts.py \
  --step test_case/机器狗.STEP \
  --l0 outputs/机器狗/l0_output.json \
  --l1 outputs/机器狗/l1_output.json \
  --show c-000001
```

上下文模式：

```text
--context part   默认，显示两个 face 和 parent Part 上下文
--context none   只显示两个 contact faces
--context all    尝试显示整机上下文，大模型可能较慢
```

## dry-run

`--dry-run` 会打印将要显示的对象，不连接 viewer：

```bash
python scripts/browse_l1_contacts.py \
  --step test_case/simple_l0_l1_assembly.step \
  --l0 outputs/simple_l0_l1_assembly/l0_output.json \
  --l1 outputs/simple_l0_l1_assembly/l1_output.json \
  --show c-000002 \
  --dry-run
```
