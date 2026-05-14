# Face 基本属性

## API 说明

### `face.geomType()`
- **返回值**：`str` — 面的几何类型
- **可能的值**：`'PLANE'`, `'CYLINDER'`, `'CONE'`, `'SPHERE'`, `'TORUS'`, `'BSPLINE'`, `'BEZIER'`, `'OTHER'`

### `face.Area()`
- **返回值**：`float` — 面的面积

### `face.Center()`
- **返回值**：`Vector` — 面的质心。使用 `.toTuple()` 获取 `(x, y, z)` 分量

### `face.BoundingBox()`
- **返回值**：`BoundBox` — 轴对齐包围盒
- **属性**：`.xmin`, `.xmax`, `.ymin`, `.ymax`, `.zmin`, `.zmax`（float）
- **属性**：`.center`（Vector）— 包围盒中心

### `face.isValid()`
- **返回值**：`bool` — 面是否有效

### `face.hashCode()`
- **返回值**：`int` — 面的哈希码，同一面多次获取相同，不同面不同

### `face.isSame(other)` / `face.isEqual(other)`
- **返回值**：`bool` — 判断两个面是否为同一个面

## 预期使用场景

- L0：遍历面时获取基本属性
- L1：面分类、空间索引构建（bbox、center）
- 所有层：通过 hashCode 快速比较两个 Face 对象是否同一

## 注意事项和坑

1. **`Center()` 返回的是面的质心，不是几何中心**。对于不规则形状可能偏向一侧。
2. **`BoundingBox()` 返回的是 AABB（轴对齐包围盒）**，不随面的实际朝向旋转。
3. **`geomType()` 返回字符串**（如 `'PLANE'`），不是枚举值。
4. **Vector 类型访问分量用 `.toTuple()`**，不能用 `.x` / `.X` 属性。
5. **BoundBox 的 `.center` 是 Vector 类型**，同样用 `.toTuple()` 取分量。

## 已验证场景

### 验证场景 1：方块模型面属性

**日期**：2026-05-11
**模型/数据**：`cq.Workplane('XY').box(10, 10, 10)` — 10×10×10 方块
**代码**：
```python
import cadquery as cq
box = cq.Workplane('XY').box(10, 10, 10)
for i, face in enumerate(box.faces().vals()):
    gt = face.geomType()
    c = face.Center()
    bbox = face.BoundingBox()
    area = face.Area()
    print(f'face {i}: {gt}')
    print(f'  Center=({c.toTuple()})')
    print(f'  Area={area:.4f}')
    print(f'  BBox=({bbox.xmin:.1f},{bbox.xmax:.1f}, {bbox.ymin:.1f},{bbox.ymax:.1f}, {bbox.zmin:.1f},{bbox.zmax:.1f})')
    print(f'  isValid={face.isValid()}, hashCode={face.hashCode()}')
```
**预期行为**：6 个面，均为 PLANE 类型，面积约 100，bounding box 覆盖整个方块
**实际结果**：6 个面均为 PLANE，面积=100，验证通过
**结论**：geomType、Area、Center、BoundingBox、isValid、hashCode 均可正常使用

### 验证场景 2：hashCode 一致性

**日期**：2026-05-11
**模型/数据**：同上
**代码**：
```python
f1 = box.faces().vals()[0]
f2 = box.faces().vals()[0]  # 重新获取
f3 = box.faces().vals()[1]
print(f1.hashCode() == f2.hashCode())  # True
print(f1.isSame(f2))                    # True
print(f1.hashCode() == f3.hashCode())  # False
print(f1.isSame(f3))                    # False
```
**预期行为**：同一面 hashCode 相同，不同面不同
**实际结果**：完全符合预期
**结论**：hashCode 可用于 face_uid → Face 对象的映射查找
