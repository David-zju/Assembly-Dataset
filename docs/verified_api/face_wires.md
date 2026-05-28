# 面边界（Wires）

## API 说明

### Wire 提取的正确方式

**CadQuery 构建的模型**可使用 `face.outerWire()` / `face.innerWires()`：
- `face.outerWire()` → `Wire` — 面的外边界
- `face.innerWires()` → `list[Wire]` — 面的内边界列表（如孔洞边界）
- `wire.edges().vals()` → `list[Edge]` — wire 包含的边列表

**真实 STEP 文件的 face 必须使用 TopExp_Explorer**（CadQuery 封装方法可能返回错误类型）：

```python
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE

# 从 face 的 TopoDS_Shape 遍历 wire
exp_w = TopExp_Explorer(face_ts, TopAbs_WIRE)
while exp_w.More():
    wire = cq.Wire(exp_w.Current())
    # 处理 wire
    exp_w.Next()

# 从 wire 遍历 edge
exp_e = TopExp_Explorer(wire_ts, TopAbs_EDGE)
while exp_e.More():
    edge = cq.Edge(exp_e.Current())
    # 处理 edge
    exp_e.Next()
```

### `wire.Closed()` / `wire.IsClosed()`
- **返回值**：`bool` — wire 是否闭合

### `edge.geomType()`
- **返回值**：`str` — 边的几何类型（`'LINE'`, `'CIRCLE'`, `'BSPLINE'`, `'ELLIPSE'` 等）

### `edge.Length()` （如果适用）
- **返回值**：`float` — 边的长度

## 预期使用场景

- L1：判断面的形状复杂度（简单形状 vs 复杂形状），用于选择重叠判定策略
- L1：获取 2D 边界多边形用于投影重叠计算
- L2：面补全时分析面的拓扑邻接关系

## 注意事项和坑

### 核心：真实 STEP 文件中 wire 提取的坑

在真实 STEP 文件（如 `装配体3.STEP`）中：
1. **`face.outerWire()` 的后续调用会失败**：`outer.edges().vals()` 报错 `'Compound' object has no attribute 'vals'`
2. **必须使用 `TopExp_Explorer`** 逐层遍历：`Face → WIRE → EDGE`
3. **`wire.Closed()` 在所有场景下都可靠**（CadQuery 模型和真实 STEP 文件均可）

### 保险性检查流程

```python
# 1. 用 TopExp_Explorer 遍历 wire（不用 face.outerWire()）
exp_w = TopExp_Explorer(face_ts, TopAbs_WIRE)
if not exp_w.More():
    # 无外边界 → 异常面，跳过或标记
    return "degenerate"

wire = cq.Wire(exp_w.Current())

# 2. 闭合性检查
if not wire.Closed():
    # 非闭合 wire → 可能是开放曲面，标记为复杂形状
    return "complex"

# 3. 遍历 edges
exp_e = TopExp_Explorer(wire_ts, TopAbs_EDGE)
edge_count = 0
edge_types = {}
while exp_e.More():
    edge = cq.Edge(exp_e.Current())
    et = edge.geomType()
    edge_types[et] = edge_types.get(et, 0) + 1
    edge_count += 1
    exp_e.Next()

# 4. 检查 innerWires（孔洞）
exp_iw = TopExp_Explorer(face_ts, TopAbs_WIRE)
has_inner = False
exp_iw.Next()  # 跳过第一个（outerWire）
has_inner = exp_iw.More()

# 5. 形状分类
if not has_inner:
    if edge_count == 4 and edge_types.get('LINE', 0) == 4:
        shape_type = "rectangle"     # 简化判定
    elif edge_count == 1 and edge_types.get('CIRCLE', 0) == 1:
        shape_type = "circle"        # 简化判定
    elif edge_count <= 6:
        shape_type = "simple_polygon"
    else:
        shape_type = "complex"       # 完整布尔运算
else:
    shape_type = "complex_with_holes"  # 有孔 → 完整布尔运算
```

### innerWires 为空列表时表示无孔洞（不是 None）

## 已验证场景

### 验证场景 1：方块面的边界（CadQuery 模型）

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').box(10, 10, 10)` — 10×10×10 方块
**代码**：
```python
import cadquery as cq
box = cq.Workplane('XY').box(10, 10, 10)
face = box.faces().vals()[0]
outer = face.outerWire()
print(f'Closed: {outer.Closed()}')  # True
edges = outer.edges().vals()
print(f'边数: {len(edges)}')  # 4
```
**结论**：CadQuery 模型上 outerWire + edges 正常，wire 闭合

### 验证场景 2：带孔面的边界

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').box(20,20,10).faces('>Z').workplane().hole(5,10)` — 带孔方块
**结论**：innerWires 可正确检测孔边界，innerWire.Closed()=True

### 验证场景 3：真实 STEP 文件的 wire 提取

**日期**：2026-05-13
**模型/数据**：`test_case/装配体3.STEP`（32.4 MB，19759 个面）
**代码**：
```python
import cadquery as cq
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_FACE, TopAbs_WIRE, TopAbs_EDGE

imported = cq.importers.importStep('test_case/装配体3.STEP')
for v in imported.vals():
    exp = TopExp_Explorer(v.wrapped, TopAbs_FACE)
    if exp.More():
        face_ts = exp.Current()
        face = cq.Face(face_ts)
        
        # 方法A (失败): face.outerWire().edges().vals() → Compound has no 'vals'
        
        # 方法B (成功): TopExp_Explorer
        exp_w = TopExp_Explorer(face_ts, TopAbs_WIRE)
        exp_w.More()  # True
        wire = cq.Wire(exp_w.Current())
        print(f'Closed: {wire.Closed()}')  # True
        
        exp_e = TopExp_Explorer(exp_w.Current(), TopAbs_EDGE)
        edges = 0
        types = {}
        while exp_e.More():
            et = cq.Edge(exp_e.Current()).geomType()
            types[et] = types.get(et, 0) + 1
            edges += 1
            exp_e.Next()
        print(f'Edges: {edges}, types: {types}')  # 7 edges: LINE×4 + BSPLINE×3
        break
```
**预期行为**：能从真实 STEP 面提取 wire 和 edges
**实际结果**：wire.Closed()=True，7 条边（LINE×4 + BSPLINE×3），识别为复杂形状
**结论**：必须使用 TopExp_Explorer 遍历 wires/edges；wire.Closed() 在所有场景下可靠

### 验证场景 4：平面 face 的 LINE/CIRCLE edge 端点和采样

**日期**：2026-05-28
**模型/数据**：
- `cq.Workplane("XY").box(10, 20, 2).faces(">Z").val()` — 矩形平面 face
- `cq.Workplane("XY").box(20,20,2).edges("|Z").fillet(2).faces(">Z").val()` — 含圆弧边界的平面 face

**代码**：
```python
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_WIRE, TopAbs_EDGE

exp_w = TopExp_Explorer(face.wrapped, TopAbs_WIRE)
wire = cq.Wire(exp_w.Current())
print(wire.Closed())  # True

exp_e = TopExp_Explorer(exp_w.Current(), TopAbs_EDGE)
while exp_e.More():
    edge = cq.Edge(exp_e.Current())
    print(edge.geomType(), edge.Length())
    print(edge.startPoint().toTuple())
    print(edge.endPoint().toTuple())
    print(edge.positionAt(0.5).toTuple())
    exp_e.Next()
```

**实际结果**：
- 矩形平面 face 提取到 4 条 `LINE` edge，`startPoint()` / `endPoint()` 均返回正确顶点。
- 圆角平面 face 提取到 `LINE` 和 `CIRCLE` edge，`CIRCLE.positionAt(0.5)` 返回圆弧中点。
- `edge.positionAt(t)` 可用 `t ∈ [0, 1]` 对 LINE/CIRCLE edge 做归一化采样。
- `TopExp_Explorer` 能遍历 wire 内 edges，但 edge 自身 orientation 可能与 ring 连接方向相反；直接按遍历顺序拼接 `startPoint/endPoint` 可能得到退化 ring。

**结论**：L1 平面边界离散化可基于 `TopExp_Explorer` + `edge.startPoint()` / `edge.endPoint()` / `edge.positionAt(t)` 实现。若需要严格按 wire 方向重建 ring，应使用更专门的 wire explorer 或做端点连接排序；当前 L1 Level 2 实现对凸边界采用“收集边界采样点后按 centroid 极角排序”的策略。初始实现应支持 `LINE` 主路径，并可对 `CIRCLE` edge 做采样近似；`BSPLINE` / `ELLIPSE` / 非凸边界等仍标记为复杂边界。
