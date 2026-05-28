# 圆柱面属性

## API 说明

### 获取圆柱面的 OCP Surface 对象

```python
from OCP.BRep import BRep_Tool
surf = BRep_Tool.Surface_s(face.wrapped)  # Geom_CylindricalSurface
```

### `surf.Radius()`
- **返回值**：`float` — 圆柱面的半径

### `surf.Axis()`
- **返回值**：`gp_Ax1` — 圆柱面的轴线
  - `.Direction()` → `gp_Dir`：轴线单位方向向量，用 `.X()`, `.Y()`, `.Z()` 获取分量（注意是大写）
  - `.Location()` → `gp_Pnt`：轴线上的一点，用 `.X()`, `.Y()`, `.Z()` 获取分量（注意是大写）

### 圆柱面 UV 范围

```python
umin, umax, vmin, vmax = face.uvBounds()
```
- **U**：角度参数（弧度），范围通常是 `[0, 2π]`
- **V**：轴向参数，范围取决于圆柱面的长度
- 轴向长度估算：`|face.positionAt(0, vmax) - face.positionAt(0, vmin)|`

## 预期使用场景

- L1：圆柱接触检测 — 获取半径判断是否匹配
- L1：共轴检查 — 比较两轴线的方向和位置
- L1：内/外圆柱判断 — 判断是 hole 还是 shaft

## 注意事项和坑

### gp_Dir / gp_Pnt 分量访问

`gp_Dir.X()` 和 `gp_Pnt.X()` —— 注意是**大写**，不是 `.x`（小写是 CadQuery Vector 的方法）

### 内外圆柱判断方法（已验证可靠）

```python
# 在 UV 中点取法向量
umin, umax, vmin, vmax = face.uvBounds()
u_mid = (umin + umax) / 2.0
v_mid = (vmin + vmax) / 2.0

n_dir = face.normalAt(u_mid, v_mid)[0]          # 材料外法向量
pt = face.positionAt(u_mid, v_mid).toTuple()    # 面上该点坐标

# 从轴线上一点指向表面点的向量
axis_loc = surf.Axis().Location()
to_surf = (pt[0]-axis_loc.X(), pt[1]-axis_loc.Y(), pt[2]-axis_loc.Z())

# 点积判断
dot_val = n_dir.toTuple()[0]*to_surf[0] + n_dir.toTuple()[1]*to_surf[1] + n_dir.toTuple()[2]*to_surf[2]
# dot_val > 0 → 外圆柱 (shaft)，法向量远离轴线
# dot_val < 0 → 内圆柱 (hole)，法向量指向轴线
```

### 轴线上的参考点

`gp_Ax1.Location()` 返回的是轴线坐标系的原点（通常是轴线上的某参考点），不一定是面上最近的点。

### UV 参数含义

- `U = 0` 对应角度原点（随模型而异）
- `V` 方向沿轴线，但正负方向取决于具体定义

### 构造受限 U/V 圆柱面的 API 注意事项

在 CadQuery 2.7.0 / OCP 环境中，`Geom_CylindricalSurface` 的构造函数接受 `gp_Ax3` 或 `gp_Cylinder`，不接受 `gp_Ax2`：

```python
from OCP.gp import gp_Ax3, gp_Pnt, gp_Dir
from OCP.Geom import Geom_CylindricalSurface
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace

surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 2.5)
face = cq.Face(BRepBuilderAPI_MakeFace(surf, umin, umax, vmin, vmax, 1e-7).Face())
```

可用 `cq.Face(face.wrapped.Reversed())` 反转 face orientation。反转后 `face.normalAt(u, v)` 的材料外法向会反向，内外圆柱判断中的点积符号会从正变负，可用于构造局部 hole face 测试样本。

## 已验证场景

### 验证场景 1：外圆柱（extrude 创建的圆柱）

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').circle(5).extrude(10)` — 半径5、高度10的圆柱
**代码**：
```python
import cadquery as cq
from OCP.BRep import BRep_Tool

cyl = cq.Workplane('XY').circle(5).extrude(10)
face = cyl.faces().vals()[0]  # 侧面（圆柱面）
surf = BRep_Tool.Surface_s(face.wrapped)

print(f'Radius: {surf.Radius()}')  # 5.0
print(f'Axis type: {type(surf.Axis()).__name__}')  # gp_Ax1

axis = surf.Axis()
print(f'Axis dir: ({axis.Direction().X():.4f}, {axis.Direction().Y():.4f}, {axis.Direction().Z():.4f})')
print(f'Axis loc: ({axis.Location().X():.4f}, {axis.Location().Y():.4f}, {axis.Location().Z():.4f})')
# 输出: Axis dir=(0,0,-1), loc=(0,0,0)

# 内外判断
umin, umax, vmin, vmax = face.uvBounds()
u_mid, v_mid = (umin+umax)/2, (vmin+vmax)/2
n = face.normalAt(u_mid, v_mid)[0].toTuple()
pt = face.positionAt(u_mid, v_mid).toTuple()
to_surf = (pt[0]-axis.Location().X(), pt[1]-axis.Location().Y(), pt[2]-axis.Location().Z())
dot = n[0]*to_surf[0] + n[1]*to_surf[1] + n[2]*to_surf[2]
print(f'dot={dot:.4f} → {"shaft" if dot>0 else "hole"}')
# 输出: dot=5.0 → shaft ✓
```
**预期行为**：Radius=5、轴线沿Z轴、判断为外圆柱
**实际结果**：完全符合预期
**结论**：Radius()、Axis()、内外判断均可靠

### 验证场景 2：内圆柱（hole 操作创建的孔）

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').box(20,20,10).faces('>Z').workplane().hole(5,10)` — 带孔方块
**代码**：
```python
import cadquery as cq
from OCP.BRep import BRep_Tool

block = cq.Workplane('XY').box(20,20,10).faces('>Z').workplane().hole(5,10)
for face in block.faces().vals():
    if face.geomType() == 'CYLINDER':
        surf = BRep_Tool.Surface_s(face.wrapped)
        axis = surf.Axis()
        umin, umax, vmin, vmax = face.uvBounds()
        u_mid, v_mid = (umin+umax)/2, (vmin+vmax)/2
        n = face.normalAt(u_mid, v_mid)[0].toTuple()
        pt = face.positionAt(u_mid, v_mid).toTuple()
        to_surf = (pt[0]-axis.Location().X(), pt[1]-axis.Location().Y(), pt[2]-axis.Location().Z())
        dot = n[0]*to_surf[0] + n[1]*to_surf[1] + n[2]*to_surf[2]
        print(f'Radius={surf.Radius()}, dot={dot:.4f} → {"shaft" if dot>0 else "hole"}')
        # 输出: Radius=2.5, dot=-2.5 → hole ✓
```
**预期行为**：Radius=2.5、判断为内圆柱（hole）
**实际结果**：完全符合预期
**结论**：内外判断对 hole 也可靠

### 验证场景 3：局部圆柱片与跨 0/2π 的 U 范围

**日期**：2026-05-28
**模型/数据**：使用 `Geom_CylindricalSurface(gp_Ax3(...), radius)` + `BRepBuilderAPI_MakeFace` 构造 U 范围为 350° 到 370°、V 范围为 -5 到 5 的局部圆柱片
**代码**：
```python
import math
import cadquery as cq
from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.gp import gp_Ax3, gp_Pnt, gp_Dir
from OCP.Geom import Geom_CylindricalSurface

surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1)), 2.5)
face = cq.Face(BRepBuilderAPI_MakeFace(
    surf,
    math.radians(350),
    math.radians(370),
    -5,
    5,
    1e-7,
).Face())

umin, umax, vmin, vmax = face.uvBounds()
u_mid, v_mid = (umin + umax) / 2, (vmin + vmax) / 2
pt = face.positionAt(u_mid, v_mid).toTuple()
normal = face.normalAt(u_mid, v_mid)[0].toTuple()
axis = BRep_Tool.Surface_s(face.wrapped).Axis()
```
**实际结果**：
- `uvBounds()` 返回 `U=[6.108652, 6.457718]`，跨度约 `0.349066 rad`（20°）
- `V=[-5.0, 5.0]`
- 中点约为 `(2.5, 0.0, 0.0)`
- `normalAt()` 中点法向约为 `(1.0, 0.0, 0.0)`
- 角度范围可以超过 `2π`，因此后续算法不能简单把 U clamp 到 `[0, 2π]` 后再取 min/max
**结论**：局部圆柱片可通过受限 U/V 构造；跨 0/2π 的短弧段需要用公共 frame 中的角度采样和最大空隙补集归一化。

### 验证场景 4：反转局部圆柱片 orientation 构造局部 hole face

**日期**：2026-05-28
**模型/数据**：验证场景 3 的局部圆柱片，调用 `face.wrapped.Reversed()`
**代码**：
```python
reversed_face = cq.Face(face.wrapped.Reversed())
u_mid, v_mid = (umin + umax) / 2, (vmin + vmax) / 2
normal = reversed_face.normalAt(u_mid, v_mid)[0].toTuple()
pt = reversed_face.positionAt(u_mid, v_mid).toTuple()
```
**实际结果**：
- 反转前中点法向约为 `(1.0, 0.0, 0.0)`，内外判断点积 `dot=2.5`，为 shaft
- 反转后中点法向约为 `(-1.0, 0.0, 0.0)`，内外判断点积 `dot=-2.5`，为 hole
- `uvBounds()` 保持不变
**结论**：反转 orientation 可稳定构造局部 hole face 测试样本，适合覆盖局部圆柱片周向 overlap / mismatch 场景。

### 验证场景 5：非全局 Z 轴圆柱

**日期**：2026-05-28
**模型/数据**：使用 `gp_Ax3(gp_Pnt(0,0,0), gp_Dir(1,0,0))` 构造轴线沿 X 轴、U 范围 0 到 90°、V 范围 -4 到 6 的局部圆柱片
**实际结果**：
- `surf.Axis().Direction()` 返回 `(1.0, 0.0, 0.0)`
- `uvBounds()` 返回 `U=[0, 1.570796]`，`V=[-4, 6]`
- `positionAt(0, -4)` 约为 `(-4, 0, 2.5)`
- `positionAt(π/2, -4)` 约为 `(-4, -2.5, 0)`
- 中点法向约为 `(0, -0.707107, 0.707107)`
**结论**：V 参数沿圆柱轴线方向变化，但轴线可为任意方向；L1 不能依赖全局 Z 轴，应基于 `surf.Axis()` 构造公共圆柱坐标系。
