# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

装配数据集自动标注项目。从 STEP 装配体文件出发，通过几何接触检测自底向上构建装配语义标注：Face Contact → Assembly Feature → Feature Mate → Pattern / Hub。

## 环境与命令

```bash
# 创建并激活环境
conda create -n cadquery python=3.11 -y
conda activate cadquery

# 安装依赖
python -m pip install --upgrade pip setuptools wheel
python -m pip install cadquery

# 可视化（可选）
python -m pip install ocp_vscode
```

## 核心依赖

- **CadQuery** — STEP 文件导入、装配体解析、B-rep 几何遍历、形状导出
- **OCP** (OpenCascade Python) — CadQuery 的底层几何内核绑定

## 实现架构

```
L0  B-rep faces (STEP 原始几何, face_uid 标识)
       │  几何接触检测 (planar/cylindrical 条件判定)
       ▼
L1  Face Contact (跨零件面接触)
       │  同一 part 内 contact 聚合 + 类型分类
       ▼
L2  Assembly Feature (单零件装配特征, atomic + composite)
       │  跨零件 feature 配对
       ▼
L3  Feature Mate
       │  mate 结构化聚合
       ▼
L4  Pattern (set-to-set) / Hub (one-to-many)
```

每层通过 uid 引用下层实体，构成有向无环引用图。

## 关键文件

- [examples/split.py](examples/split.py) — 将装配体 STEP 文件拆分为独立零件 STEP。使用 `cadquery.Assembly.load()` 解析，对每个 component 用 `cq.exporters.export()` 导出。若解析失败则回退到 `cq.importers.importStep()` 提取 solids。
- [test.py](test.py) — 编码检测工具。穷举编码转换链寻找将乱码字节还原为中文的路径，用于处理 STEP 文件中编码损坏的中文零件名。
- [test_case/](test_case/) — 测试用 STEP 装配体文件，中文零件名有乱码问题。

## 参考文档

- **CadQuery 官方文档** — https://cadquery.readthedocs.io/en/latest/
  当遇到以下情况时，应使用 `WebFetch` 工具查阅对应文档页面：
  - 不确定 CadQuery API 的准确用法（如 `cq.Workplane`、`cq.Assembly`、`cq.Shape` 的方法签名）
  - 需要确认 B-rep 拓扑遍历 API（`faces()`、`edges()`、`wires()` 等）
  - STEP 导入/导出参数选项（`cq.importers.importStep()`、`cq.exporters.export()`）
  - 装配体操作（`cq.Assembly` 的遍历、名称获取、子组件访问）
  - 几何查询方法（`Face.geomType()`、`Face.normalAt()` 等）

  查阅方式举例：
  - API 参考总览：`https://cadquery.readthedocs.io/en/latest/apireference.html`
  - 搜索特定类：`https://cadquery.readthedocs.io/en/latest/search.html?q=<关键词>`
  - 快速入门示例：`https://cadquery.readthedocs.io/en/latest/quickstart.html`

## 注意事项

- STEP 文件中的中文名称可能经过多重错误编码转换导致乱码（常见链：UTF-8 字节被当作 Latin-1 解释后重新编码），需要用 [test.py](test.py) 反推正确编码链。


## 边界条件

### 应当做的

- 本项目基于openspec的SDD规范开发，每次做出代码修改时请务必同步到对应文档中，（bug修复有关的内容也包括）。
- 所有的文档请使用中文编写，以便用户阅读。
- 编写的代码请用中文编写必要的注释。至少要为每个函数和模块文件编写注释，明确说明用途、参数解释与用例。

### 不应当做的

- 将敏感信息（cookie等）提交到git中。