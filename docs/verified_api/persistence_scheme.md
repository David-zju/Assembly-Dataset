# L0→L1 持久化方案

## 核心发现

| 方案 | 方法 | 结果 |
|------|------|------|
| A (Face引用) | 内存中存 `Dict[face_uid, cq.Face]` | 不可序列化，跨进程失效 |
| B (索引) | face 遍历顺序 | **顺序完全确定性** (19759/19759) |
| C (hash) | hashCode | **跨导入不稳定** (0/19759 匹配) |

## 推荐方案：B (索引映射) + 几何指纹校验

### 原理

`TopExp_Explorer` 遍历 face 的顺序在多次独立导入中**完全确定**。利用这一特性：
1. L0 按遍历顺序为 face 分配 face_uid
2. L0 将 face 列表（含几何指纹）序列化到磁盘
3. L1 重新导入 STEP，按相同顺序遍历 face，依赖索引匹配 face_uid
4. 用几何指纹做首尾校验，确保顺序未被破坏

### L0 输出格式

```json
{
  "metadata": {
    "source_file": "装配体3.STEP",
    "pipeline_version": "1.0.0",
    "timestamp": "2026-05-13T...",
    "num_parts": 1,
    "num_faces": 19759
  },
  "parts": [
    {
      "part_uid": "p-0001",
      "name": "装配体3",
      "face_count": 19759,
      "face_uid_prefix": "f-0001"
    }
  ],
  "faces": [
    {
      "face_uid": "f-0001-00001",
      "part_uid": "p-0001",
      "part_face_index": 0,
      "geom_type": "PLANE",
      "fingerprint": {
        "area": 1234.5678,
        "center": [10.1234, 20.5678, 30.9012],
        "bbox": [0.0, 100.0, 0.0, 50.0, 30.0, 30.5]
      }
    }
  ]
}
```

### L1 加载流程

```text
1. 读取 L0 输出的 JSON 文件
   → 获取 part 列表 + face 列表（含 face_uid + fingerprint）

2. 重新导入 STEP 文件
   → importStep(path) → TopExp_Explorer 按相同顺序遍历 face

3. 索引匹配
   for i, face_ts in enumerate(faces_in_order):
       face_uid = l0_faces[i]["face_uid"]    # 按索引对应
       face = cq.Face(face_ts)
       
4. 几何指纹校验（首尾抽样）
   检查第 0 个和第 N-1 个 face 的指纹是否匹配
   不匹配 → WARNING + 回退到全量指纹匹配模式

5. 构建 face_uid → Face 的内存映射
   mapping[face_uid] = face  # 供后续 L1 几何查询使用
```

### 几何指纹结构

```python
@dataclass
class FaceFingerprint:
    """面的几何指纹 — 用于跨导入会话验证面身份"""
    geom_type: str              # 'PLANE' | 'CYLINDER' | 'CONE' | ...
    area: float                 # 面积 (精度: 1e-4)
    center: tuple[float,float,float]  # 质心 (精度: 1e-4)
    bbox: tuple[float,...]      # (xmin, xmax, ymin, ymax, zmin, zmax)
    
    # 类型特定 (可选, 增强判别力)
    normal: Optional[tuple]     # 仅 PLANE
    radius: Optional[float]     # 仅 CYLINDER
    axis_dir: Optional[tuple]   # 仅 CYLINDER
```

### 指纹匹配容差

所有浮点数比较使用绝对容差 `1e-4`（考虑 OCP 浮点精度和 STEP 导入的微小数差）。

## 异常处理

| 情况 | 处理 |
|------|------|
| 索引超出 L0 face 列表 | 文件被修改/不匹配 → ERROR，中止 |
| 索引不足（实际 face 少于 L0 记录） | 同上 |
| 首尾指纹不匹配 | WARNING + 切换为全量指纹匹配（O(N²) 但可靠） |
| 指纹匹配时出现多个候选 | 添加更多属性到指纹（如 normal/radius），重新匹配 |

## JSON 文件大小预估

19759 个 face，每个 face 约 200 字节 JSON → 约 4 MB。可接受。

若需压缩，可选 MsgPack 或 Parquet 格式。
