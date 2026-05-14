# 法向量获取

## API 说明

### 方法 A：`face.normalAt(u, v)`
- **参数**：`u` (float), `v` (float) — 面上的 UV 参数坐标
- **返回值**：`tuple` — `(direction: Vector, position: Vector)`
  - `[0]`：方向向量（Vector），使用 `.toTuple()` 获取 `(x, y, z)` 分量
  - `[1]`：位置向量（Vector），面上该 UV 坐标处的点
- **含义**：返回的是**材料外法向量**（从材料指向外部空间）

### 方法 B：通过 OCP Surface 获取（仅平面）
```python
from OCP.BRep import BRep_Tool
surf = BRep_Tool.Surface_s(face.wrapped)  # Geom_Plane
pln = surf.Pln()                            # gp_Pln
pos = pln.Position()                        # gp_Ax3
normal = pos.Direction()                    # gp_Dir → 几何法向量
origin = pos.Location()                     # gp_Pnt → 平面上一点
```
- **含义**：返回的是**几何参数方向**，不一定与材料外法向量同向

### 方法 C：通过 `face.normals()`
- **返回值**：返回面上多个采样点的法向量列表（待进一步验证）

## 预期使用场景

- L1：平面接触检测中获取法向量判断是否反向
- L1：圆柱面接触检测中判断内/外圆柱
- L1：切向接触检测中判断圆柱轴与平面法向量的关系

## 注意事项和坑

### 关键：两种方法的法向量方向可能相反！

**`normalAt()` 返回材料外法向量**（material-outward normal），而 **`Surface.Position().Direction()` 返回几何参数方向**。两者可能同向也可能反向。

验证结果表明：
- 方块 face 0（x=-5 面）：`normalAt` = `(-1, 0, 0)`，`Surface` = `(1, 0, 0)` → **反向**
- 因为材料在 x > -5 一侧，外法向量指向 -x

**建议**：在接触检测中统一使用 `face.normalAt(face_center_u, face_center_v)` 获取法向量，因为它是材料外法向量，语义更符合"两面是否相对"的判断需求。

### Vector 分量访问

`normalAt` 返回的 Vector 使用 `.toTuple()` 获取分量 `(x, y, z)`，不能用 `.x` 或 `.X`。

### UV 参数

需要用 `face.uvBounds()` 获取 UV 范围，然后取中点作为 `normalAt` 的输入参数。

## 已验证场景

### 验证场景 1：normalAt vs Surface 方向对比

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').box(10, 10, 10)` — 10×10×10 方块
**代码**：
```python
import cadquery as cq
from OCP.BRep import BRep_Tool

box = cq.Workplane('XY').box(10, 10, 10)
face = box.faces().vals()[0]  # x=-5 面

# 方法 A: normalAt
umin, umax, vmin, vmax = face.uvBounds()
u_mid = (umin + umax) / 2.0
v_mid = (vmin + vmax) / 2.0
n_result = face.normalAt(u_mid, v_mid)
n_direction = n_result[0].toTuple()
n_position = n_result[1].toTuple()
print(f'normalAt: direction={n_direction}, position={n_position}')

# 方法 B: Surface
surf = BRep_Tool.Surface_s(face.wrapped)
pln = surf.Pln()
pos = pln.Position()
n_surf = (pos.Direction().X(), pos.Direction().Y(), pos.Direction().Z())
origin = (pos.Location().X(), pos.Location().Y(), pos.Location().Z())
print(f'Surface: direction={n_surf}, origin={origin}')

# 对比
dot = n_direction[0]*n_surf[0] + n_direction[1]*n_surf[1] + n_direction[2]*n_surf[2]
print(f'dot={dot:.4f} → {"同向" if dot>0 else "反向"}')
```
**预期行为**：两种方法都返回法向量，但方向可能相反
**实际结果**：`normalAt` 返回 `(-1, 0, 0)`，`Surface` 返回 `(1, 0, 0)` — 反向
**结论**：接触检测中使用 `normalAt`（材料外法向量），语义正确
