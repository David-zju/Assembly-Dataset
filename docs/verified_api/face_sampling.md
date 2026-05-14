# 面采样点

## API 说明

### `face.uvBounds()`
- **返回值**：`tuple` — `(umin, umax, vmin, vmax)`，面的 UV 参数范围
- **U**：第一参数方向（对圆柱面是角度，0→2π）
- **V**：第二参数方向（对圆柱面是轴向）

### `face.positionAt(u, v)`
- **参数**：`u` (float), `v` (float) — UV 参数坐标
- **返回值**：`Vector` — 面上该 UV 坐标处的 3D 点，使用 `.toTuple()` 获取 `(x, y, z)`

### `face.normalAt(u, v)`
- **参数**：`u` (float), `v` (float) — UV 参数坐标
- **返回值**：`tuple` — `(direction: Vector, position: Vector)`，详见 [face_normals.md](face_normals.md)

## 预期使用场景

- L1：空间索引的多采样点生成（大面积 face 需要多个采样点避免遗漏接触）
- L1：获取 face 中心点的法向量用于类型判定
- L1：获取圆柱面的轴向长度（通过 V 参数范围）

## 注意事项和坑

1. **`positionAt()` 返回 Vector**，用 `.toTuple()` 获取 `(x, y, z)` 分量。
2. **UV 参数的具体含义取决于面的几何类型**：
   - 平面：U, V 是面上的 2D 坐标
   - 圆柱面：U 是角度（弧度，0→2π），V 是轴向参数
3. **UV 范围可能超出标准域**（如圆柱面的 U 范围可能是 [0, 2π] 也可能不同）。
4. **`positionAt(u, v)` 在面外的 UV 值时可能返回面上最近点或报错**，应保持在 `uvBounds()` 范围内。

## 已验证场景

### 验证场景 1：圆柱面 UV 范围与轴向长度

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').circle(5).extrude(10)` — 半径5、高度10的圆柱
**代码**：
```python
import cadquery as cq
import math

cyl = cq.Workplane('XY').circle(5).extrude(10)
face = cyl.faces().vals()[0]  # 圆柱侧面

umin, umax, vmin, vmax = face.uvBounds()
print(f'U: [{umin:.4f}, {umax:.4f}] (角度, 弧度)')
print(f'V: [{vmin:.4f}, {vmax:.4f}] (轴向)')

# 估算轴向长度
pt_vmin = face.positionAt(0, vmin).toTuple()
pt_vmax = face.positionAt(0, vmax).toTuple()
length = math.sqrt(sum((pt_vmax[i]-pt_vmin[i])**2 for i in range(3)))
print(f'轴向长度: {length:.4f}')  # 10.0
```
**预期行为**：U 范围 0→2π，V 范围对应高度 10
**实际结果**：`U∈[0, 6.2832]`, `V∈[-10, 0]`，轴向长度=10
**结论**：uvBounds + positionAt 可正确获取 UV 范围和轴向长度

### 验证场景 2：面均匀采样

**日期**：2026-05-11
**模型/数据**：同上 + 方块
**代码**：
```python
import cadquery as cq

def sample_face(face, n_u=3, n_v=3):
    """在面的 UV 域内均匀采样 n_u × n_v 个点"""
    umin, umax, vmin, vmax = face.uvBounds()
    pts = []
    for i in range(n_u):
        for j in range(n_v):
            u = umin + (umax - umin) * (i + 0.5) / n_u
            v = vmin + (vmax - vmin) * (j + 0.5) / n_v
            pt = face.positionAt(u, v)
            pts.append(pt.toTuple())
    return pts

box = cq.Workplane('XY').box(10, 10, 10)
face = box.faces().vals()[0]
pts = sample_face(face, 3, 3)
for k, pt in enumerate(pts):
    print(f'  {k}: ({pt[0]:.2f}, {pt[1]:.2f}, {pt[2]:.2f})')
```
**预期行为**：在面上生成 9 个均匀分布的采样点
**实际结果**：生成 9 个点，合理分布在面上
**结论**：positionAt + uvBounds 可用于多采样点生成
