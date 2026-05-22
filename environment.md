# 环境说明

本项目主要依赖 CadQuery 和 OCP Python 绑定，用于 STEP 装配体分析、干涉检测和可视化显示。

## 1. 推荐环境

建议使用独立的 Conda 环境，避免和系统 Python、VS Code 解释器混用。

```bash
conda create -n cadquery python=3.13 -y
conda activate cadquery
```

如果你已经有名为 `cadquery` 的环境，也可以直接复用。

```bash
conda activate cadquery
python -m pip install --upgrade pip setuptools wheel
python -m pip install cadquery
```

安装完成后可以简单检查：

```bash
python -c "import cadquery as cq; print(cq.__version__)"
```

## 2. 安装 OCP 可视化后端

项目里的可视化分两种方式：

1. 在支持 `show_object` 的 CadQuery/Notebook 环境中直接显示。
2. 在 VS Code 里使用 `ocp_vscode` 作为 OCP Viewer 后端。

如果你希望在 VS Code 中可视化，安装：

```bash
python -m pip install ocp_vscode
```

验证是否安装成功：

```bash
python -c "from ocp_vscode import show; print('ocp_vscode ok')"
```