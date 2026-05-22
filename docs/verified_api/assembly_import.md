# 装配体导入

## API 说明

### `cq.Assembly.load(path)`
- **参数**：`path` (str/Path) — STEP 文件路径
- **返回值**：`cq.Assembly` — 装配体树

### Assembly 结构
- `.name` — 装配体/零件名称
- `.children` — 子 Assembly 列表
- `.obj` — 关联的 Shape 对象（叶子节点才有，可能为 None）
- `.loc` — 相对于父 Assembly 的位置（Location 对象）

### `cq.importers.importStep(path)`
- **参数**：`path` (str/Path) — STEP 文件路径
- **返回值**：`cq.Workplane` — 导入结果
  - `.vals()` → `list` — 包含的顶层 Shape 列表
  - `.solids().vals()` → `list[Solid]` — 所有 solid
  - `.faces().vals()` → `list[Face]` — 所有 face

## 预期使用场景

- L0：STEP 文件的解析与装配体扁平化

## 注意事项和坑

### Assembly 遍历

`Assembly.__iter__` 在某些 STEP 文件上返回 0 个元素。需要手动递归遍历 children：

```python
assembly = cq.Assembly.load(path)

def collect_leaves(assy):
    """递归收集所有带 shape 的叶子节点"""
    leaves = []
    for child in assy.children:
        if child.obj is not None:
            leaves.append(child)
        if len(child.children) > 0:
            leaves.extend(collect_leaves(child))
    return leaves
```

### Compound 对象

Assembly 叶子节点的 `.obj` 可能是 `Compound` 类型。Compound 的以下方法返回空：
- `obj.Faces()` → 空 list
- `obj.Solids()` → 空 list
- `obj.CompSolids()` → 空 list
- `TopExp_Explorer` 遍历 FACE/SOLID/SHELL → 0 个

**当前状态**：从 `test_case/001650主臂装配体1.STEP` 文件导入时，36 个叶子节点均为 Compound，但所有几何提取方法均返回空。`importStep` 同样返回空。该文件已由人工检查确认为无效模型，后续不再作为验证数据使用。

### Part 边界可靠性

`cq.Assembly.load()` 是装配体 Part 边界的可靠来源：它返回装配树、子节点名称和 location，可用于扁平化为 Part 列表。

`cq.importers.importStep()` 只能作为几何兜底，不应作为装配体 Part 边界来源。已验证在大型装配 STEP 上，`importStep()` 会返回单个 `Compound`，虽然可从中提取 solids 和 faces，但顶层装配树、Part 名称、实例路径和位姿语义已经丢失。`solids()` 列表不得被解释为可靠 Part 列表，因为一个 Part 可能包含多个 solid，同一零件定义也可能有多个装配实例。

### 已验证可行的方式

通过 CadQuery 直接构建的 Shape（如 `box(10,10,10)`、`circle(5).extrude(10)`）的 face 遍历和几何查询均正常工作。实现 L0→L1 时应：
1. 先用 CadQuery 构建的简单模型驱动开发和测试
2. 对真实 STEP 文件的导入问题做专项调查

### 已验证场景

### 验证场景 1：CadQuery 构建模型的遍历（正常）

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').box(10, 10, 10)`
**代码**：
```python
import cadquery as cq
box = cq.Workplane('XY').box(10, 10, 10)
faces = box.faces().vals()
print(f'faces: {len(faces)}')
for f in faces:
    print(f'  {f.geomType()}')
```
**预期行为**：6 个 PLANE 面
**实际结果**：6 个 PLANE 面
**结论**：CadQuery 构建的模型完全可用

### 验证场景 2：大 STEP 文件 importStep（正常）

**日期**：2026-05-11
**模型/数据**：`test_case/装配体3.STEP`（32.4 MB）和 `test_case/机器狗.STEP`（32.4 MB）
**代码**：
```python
import cadquery as cq
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE

for step_name in ['test_case/装配体3.STEP', 'test_case/机器狗.STEP']:
    imported = cq.importers.importStep(step_name)
    vals = imported.vals()
    total_faces = 0
    for v in vals:
        exp = TopExp_Explorer(v.wrapped, TopAbs_FACE)
        while exp.More():
            total_faces += 1
            exp.Next()
    print(f'{step_name}: {len(vals)} items, {total_faces} faces')
```
**预期行为**：应能提取大量 face
**实际结果**：两个文件均提取到 **19,759 个 face**
**结论**：`importStep` + `TopExp_Explorer` 对大型 STEP 文件的几何提取有效，但不保证保留装配体 Part 边界

### 验证场景 3：无效小 STEP 文件导入问题（历史记录，不再用于验证）

**日期**：2026-05-11
**模型/数据**：`test_case/001650主臂装配体1.STEP`（110 KB）
**代码**：同验证场景 2
**预期行为**：应能提取 face
**实际结果**：Assembly 有 36 个 children，但 `importStep` 返回 face 数为 0
**结论**：该文件后续经人工检查确认为无效模型，不再作为验证数据使用。

## 已验证场景

### 验证场景 1：CadQuery 构建模型的遍历（正常）

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').box(10, 10, 10)`
**代码**：
```python
import cadquery as cq
box = cq.Workplane('XY').box(10, 10, 10)
faces = box.faces().vals()
print(f'faces: {len(faces)}')
for f in faces:
    print(f'  {f.geomType()}')
```
**预期行为**：6 个 PLANE 面
**实际结果**：6 个 PLANE 面 ✓
**结论**：CadQuery 构建的模型完全可用

### 验证场景 2：无效真实 STEP 文件导入（历史记录，不再用于验证）

**日期**：2026-05-11
**模型/数据**：`test_case/001650主臂装配体1.STEP`（110 KB）
**代码**：
```python
import cadquery as cq
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE

# Assembly.load 方式
assembly = cq.Assembly.load('test_case/001650主臂装配体1.STEP')
# assembly 有 36 个 children，但叶子节点的 Compound 对象中提取不到 face

# importStep 方式
imported = cq.importers.importStep('test_case/001650主臂装配体1.STEP')
# 返回 1 个 Compound，TopExp_Explorer 遍历无 face
```
**预期行为**：应能从 STEP 文件中提取出 face 列表
**实际结果**：Assembly 结构存在（36 个命名子组件），但 face 遍历返回空
**结论**：该文件后续经人工检查确认为无效模型，不再作为验证数据使用。

### 验证场景 3：importStep 会压平大型装配体 Part 边界

**日期**：2026-05-22
**模型/数据**：`test_case/装配体3.STEP`、`test_case/机器狗.STEP`
**代码**：
```python
import cadquery as cq
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer


def count_faces(shape):
    exp = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    count = 0
    while exp.More():
        count += 1
        exp.Next()
    return count


for step_file in ["test_case/装配体3.STEP", "test_case/机器狗.STEP"]:
    imported = cq.importers.importStep(step_file)
    vals = imported.vals()
    solids = imported.solids().vals()
    faces = imported.faces().vals()
    top_face_counts = [count_faces(shape) for shape in vals]

    print(step_file)
    print("vals:", len(vals), [type(v).__name__ for v in vals])
    print("solids:", len(solids))
    print("faces:", len(faces))
    print("top_face_counts:", top_face_counts, "sum:", sum(top_face_counts))
```
**预期行为**：若 `importStep()` 可保留装配体 Part 边界，应返回多个顶层 component 或可恢复 Part 的结构。
**实际结果**：
```text
test_case/装配体3.STEP
vals: 1 ['Compound']
solids: 298
faces: 19759
top_face_counts: [19759] sum: 19759

test_case/机器狗.STEP
vals: 1 ['Compound']
solids: 298
faces: 19759
top_face_counts: [19759] sum: 19759
```
**结论**：`importStep()` 能提取几何，但会将大型装配体压成单个 `Compound`，不能作为可靠 Part 边界来源。L0 正式装配体导入应以 `cq.Assembly.load()` 的装配树为准；`importStep()` 只能作为几何诊断兜底，并应标记 `part_boundary_reliable = false`。

### 验证场景 4：小型有效装配 STEP 的 Part 边界恢复

**日期**：2026-05-22
**模型/数据**：`test_case/simple_l0_l1_assembly.step`（由 CadQuery Assembly 生成，包含 base_plate、top_block、vertical_pin 三个 Part）
**代码**：
```python
import cadquery as cq
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer


def count_faces(shape):
    exp = TopExp_Explorer(shape.wrapped, TopAbs_FACE)
    count = 0
    while exp.More():
        count += 1
        exp.Next()
    return count


def collect_leaves(assy):
    leaves = []

    def rec(node, path="root"):
        for index, child in enumerate(getattr(node, "children", []) or []):
            child_path = f"{path}/{index}:{getattr(child, 'name', '')}"
            if getattr(child, "obj", None) is not None:
                leaves.append((child_path, type(child.obj).__name__, count_faces(child.obj)))
            rec(child, child_path)

    rec(assy)
    return leaves


step_file = "test_case/simple_l0_l1_assembly.step"
assembly = cq.Assembly.load(step_file)
leaves = collect_leaves(assembly)
print("Assembly leaves:", leaves)

imported = cq.importers.importStep(step_file)
vals = imported.vals()
print("importStep vals:", len(vals), [type(v).__name__ for v in vals])
print("importStep solids:", len(imported.solids().vals()))
print("importStep faces:", len(imported.faces().vals()))
```
**预期行为**：`Assembly.load()` 能恢复 3 个 Part；`importStep()` 仍可能只返回几何 Compound。
**实际结果**：
```text
Assembly root_children 3
leaves_with_obj 3
face_sum 15
Assembly leaves [
  ('root/0:base_plate', 'Solid', 6),
  ('root/1:top_block', 'Solid', 6),
  ('root/2:vertical_pin', 'Solid', 3)
]
importStep vals 1 ['Compound']
solids 3
faces 15
```
**结论**：`simple_l0_l1_assembly.step` 是小型有效装配验证件。`Assembly.load()` 可恢复可靠 Part 边界；`importStep()` 仍只适合作为几何兜底。
