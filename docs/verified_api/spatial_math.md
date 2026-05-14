# 空间计算

## API 说明

### 两条轴线的夹角

```python
import math

d1 = ax1.Direction()  # gp_Dir
d2 = ax2.Direction()
dot_abs = abs(d1.X()*d2.X() + d1.Y()*d2.Y() + d1.Z()*d2.Z())
angle_deg = math.degrees(math.acos(max(-1.0, min(1.0, dot_abs))))
```

### 两条轴线的最短距离

```python
from OCP.gp import gp_Vec

p1, d1 = ax1.Location(), ax1.Direction()  # gp_Pnt, gp_Dir
p2, d2 = ax2.Location(), ax2.Direction()

v = (p2.X()-p1.X(), p2.Y()-p1.Y(), p2.Z()-p1.Z())

# 方向叉积
cross = gp_Vec(d1.Y()*d2.Z() - d1.Z()*d2.Y(),
               d1.Z()*d2.X() - d1.X()*d2.Z(),
               d1.X()*d2.Y() - d1.Y()*d2.X())
cross_mag = math.sqrt(cross.X()**2 + cross.Y()**2 + cross.Z()**2)

if cross_mag < 1e-10:
    # 平行/共线：距离 = |v × d1|
    c = gp_Vec(v[1]*d1.Z()-v[2]*d1.Y(),
               v[2]*d1.X()-v[0]*d1.Z(),
               v[0]*d1.Y()-v[1]*d1.X())
    dist = math.sqrt(c.X()**2 + c.Y()**2 + c.Z()**2)
else:
    # 不平行：距离 = |v · (d1×d2)| / |d1×d2|
    dist = abs(v[0]*cross.X() + v[1]*cross.Y() + v[2]*cross.Z()) / cross_mag
```

### 点到平面的距离

```python
# 使用 gp_Pln.Distance()（需要先获取 gp_Pln 对象）
surf = BRep_Tool.Surface_s(face.wrapped)  # Geom_Plane
pln = surf.Pln()                            # gp_Pln
dist = pln.Distance(gp_Pnt(x, y, z))       # 带符号距离

# 或手动计算（已知平面法向量 normal 和平面上一点 origin）：
# dist = |dot(p - origin, normal)|
```

### 两点/两向量基本运算

```python
from OCP.gp import gp_Vec, gp_Pnt, gp_Dir

# gp_Vec: 向量
v = gp_Vec(x, y, z)
dot = v1.Dot(v2)
cross = v1.Crossed(v2)
mag = v.Magnitude()

# gp_Pnt: 点
p = gp_Pnt(x, y, z)
dist = p.Distance(other_pnt)  # 两点距离

# gp_Dir: 单位方向向量
d = gp_Dir(x, y, z)  # 自动归一化
angle = d1.Angle(d2)  # 弧度
```

## 预期使用场景

- L1 圆柱接触检测：判断两轴线是否共轴（夹角+径向距离）
- L1 平面接触检测：判断两面是否共面（点到平面距离）
- L1 切向接触检测：判断圆柱面是否与平面相切（轴到平面距离 ≈ 半径）

## 注意事项和坑

1. **`gp_Dir.Angle()` 返回弧度**，需要 `math.degrees()` 转换。
2. **`gp_Dir` 构造时自动归一化**，不需要手动处理。
3. **轴线夹角应取绝对值**（方向不重要），因为轴的正负方向对圆柱面无物理差异。
4. **浮点精度**：夹角判断应使用 `max_angle_deg` 容差（如 0.1°），不要用 `== 0`。
5. **平行轴线的距离计算**：使用叉积方式，避免除以零。
6. **`gp_Pln.Distance()` 返回带符号距离**，符号由点在平面的哪一侧决定。

## 已验证场景

### 验证场景 1：轴线距离与角度

**日期**：2026-05-11
**模型/数据**：手动构造的两条 `gp_Ax1`
**代码**：
```python
from OCP.gp import gp_Pnt, gp_Dir, gp_Ax1, gp_Vec
import math

# 几乎平行的两条线，径向偏移 0.1
ax1 = gp_Ax1(gp_Pnt(0, 0, 0), gp_Dir(0, 0, 1))
ax2 = gp_Ax1(gp_Pnt(0.1, 0, 5), gp_Dir(0, 0.001, 1))

p1, d1, p2, d2 = ax1.Location(), ax1.Direction(), ax2.Location(), ax2.Direction()

# 夹角
dot_abs = abs(d1.X()*d2.X() + d1.Y()*d2.Y() + d1.Z()*d2.Z())
angle = math.degrees(math.acos(max(-1, min(1, dot_abs))))
print(f'angle={angle:.4f}°')  # ≈ 0.0573°

# 距离
v = (p2.X()-p1.X(), p2.Y()-p1.Y(), p2.Z()-p1.Z())
cross = gp_Vec(d1.Y()*d2.Z()-d1.Z()*d2.Y(),
               d1.Z()*d2.X()-d1.X()*d2.Z(),
               d1.X()*d2.Y()-d1.Y()*d2.X())
cross_mag = math.sqrt(cross.X()**2 + cross.Y()**2 + cross.Z()**2)
if cross_mag < 1e-10:
    c = gp_Vec(v[1]*d1.Z()-v[2]*d1.Y(), v[2]*d1.X()-v[0]*d1.Z(), v[0]*d1.Y()-v[1]*d1.X())
    dist = math.sqrt(c.X()**2 + c.Y()**2 + c.Z()**2)
else:
    dist = abs(v[0]*cross.X() + v[1]*cross.Y() + v[2]*cross.Z()) / cross_mag
print(f'dist={dist:.6f}')  # ≈ 0.1
```
**预期行为**：夹角≈0.057°，距离≈0.1
**实际结果**：angle=0.0573°, dist=0.099999
**结论**：轴间距离和角度计算正确
