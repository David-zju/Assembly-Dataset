# 平面属性

## API 说明

### 从 OCP Surface 获取平面参数

```python
from OCP.BRep import BRep_Tool
surf = BRep_Tool.Surface_s(face.wrapped)  # Geom_Plane
pln = surf.Pln()                            # gp_Pln — 注意是 Pln() 不是 Plane()
pos = pln.Position()                        # gp_Ax3 — 平面的局部坐标系
normal = pos.Direction()                    # gp_Dir — 法向量（几何参数方向）
origin = pos.Location()                     # gp_Pnt — 平面上一点（坐标系原点）
```

- 法向量分量用 `normal.X()`, `normal.Y()`, `normal.Z()`（大写）
- 原点分量用 `origin.X()`, `origin.Y()`, `origin.Z()`（大写）

### gp_Pln 其他方法

| 方法 | 返回值 | 说明 |
|------|--------|------|
| `pln.Axis()` | `gp_Ax1` | 平面的轴（法向量方向） |
| `pln.Position()` | `gp_Ax3` | 平面局部坐标系 |
| `pln.Location()` | `gp_Pnt` | 平面上一点 |
| `pln.Distance(pnt)` | `float` | 点到平面的距离 |
| `pln.Contains(pnt, tol)` | `bool` | 点是否在平面上 |
| `pln.Direct()` | `bool` | 坐标系是否为右手系 |

## 预期使用场景

- L1：获取平面法向量（与 normalAt 对比）
- L1：计算点到平面的距离（接触判定）
- L1：获取平面上一点用于投影计算

## 注意事项和坑

### 核心：`Pln()` 不是 `Plane()`

`Geom_Plane` 对象获取底层 `gp_Pln` 的方法是 `.Pln()`（三个字母），不是 `.Plane()`。

### gp_Pln → gp_Ax3 的路径

```
Geom_Plane → .Pln() → gp_Pln → .Position() → gp_Ax3 → .Direction() / .Location()
```

注意不是 `.Ax3()`（gp_Pln 没有 Ax3 方法）。

### 法向量方向差异

`pln.Position().Direction()` 返回的是**几何参数方向**，与 `face.normalAt()` 返回的**材料外法向量**可能相反。接触检测中应统一使用 `normalAt` 获取法向量，确保语义一致。详见 [face_normals.md](face_normals.md)。

## 已验证场景

### 验证场景 1：方块面的平面参数

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').box(10, 10, 10)` — 10×10×10 方块
**代码**：
```python
import cadquery as cq
from OCP.BRep import BRep_Tool

box = cq.Workplane('XY').box(10, 10, 10)
for i, face in enumerate(box.faces().vals()):
    surf = BRep_Tool.Surface_s(face.wrapped)
    pln = surf.Pln()           # ← 注意：Pln() 不是 Plane()
    pos = pln.Position()       # ← 注意：Position() 不是 Ax3()
    d = pos.Direction()        # 注意：大写 X/Y/Z
    loc = pos.Location()
    print(f'face {i}: loc=({loc.X():.1f},{loc.Y():.1f},{loc.Z():.1f}), normal=({d.X():.4f},{d.Y():.4f},{d.Z():.4f})')
```
**预期行为**：6 个面各输出位置和法向量
**实际结果**：
```
face 0: loc=(-5,-5,-5), normal=(1,0,0)    # 左面
face 1: loc=(5,-5,-5), normal=(1,0,0)     # 右面 (为什么法向量与face0相同？)
face 2: loc=(-5,-5,-5), normal=(0,1,0)    # 前面
face 3: loc=(-5,5,-5), normal=(0,1,0)     # 后面
face 4: loc=(-5,-5,-5), normal=(0,0,1)    # 底面
face 5: loc=(-5,-5,5), normal=(0,0,1)     # 顶面
```
**结论**：Position().Location() 的参考点对于平行平面可能相同（都取坐标系原点在参数域中的对应点）。Direction() 返回几何方向（非材料外法向）。

### 验证场景 2：平面局部 frame 应以材料外法向和 face center 为准

**日期**：2026-05-28
**模型/数据**：全局 XY/YZ/XZ 平面 face 与斜向 box face
**验证内容**：
- `BRep_Tool.Surface_s(face.wrapped).Pln().Position().Direction()` 仍表示几何参数方向，不保证等于材料外法向。
- `face.normalAt(u_mid, v_mid)[0]` 返回材料外法向，适合作为接触判定语义方向。
- `face.Center().toTuple()` 可作为局部投影 frame 的 origin，数值比直接使用 `pln.Position().Location()` 更贴近当前 trimmed face。

**结论**：L1 `PlaneFrame` 构造应使用 `face.normalAt()` 的材料外法向作为 normal，并优先使用 face center 作为 origin；`gp_Pln` 主要用于共面距离计算和 API 兜底，不应直接把 `pln.Position().Direction()` 当成接触法向。
