# 已验证 API 参考

本目录记录在项目开发过程中已验证的 CadQuery/OCP API 用法、注意事项和已验证场景。

**使用原则**：在使用某个 API 之前，优先查阅本目录中的相关文档。找不到时再去参考 CadQuery 在线文档。任何时候验证了新的 API 用法，都应该按规范归档到本目录中。

## 文档索引

| 文档 | 内容 |
|------|------|
| [face_basics.md](face_basics.md) | Face 基本属性：geomType、Area、Center、BoundingBox、isValid |
| [face_normals.md](face_normals.md) | 法向量获取：normalAt 与 Surface 的差异和注意事项 |
| [face_cylindrical.md](face_cylindrical.md) | 圆柱面属性：Radius、Axis、内外判断、UV 范围 |
| [face_planar.md](face_planar.md) | 平面属性：Pln、Position、Direction、Location |
| [face_wires.md](face_wires.md) | 面边界：outerWire、innerWires、edges |
| [face_sampling.md](face_sampling.md) | 面采样点：positionAt、uvBounds、均匀采样策略 |
| [assembly_import.md](assembly_import.md) | 装配体导入：Assembly.load、importStep、遍历与 Compound 处理 |
| [spatial_math.md](spatial_math.md) | 空间计算：轴线间最短距离、轴线夹角、点到平面距离 |
| [persistence_scheme.md](persistence_scheme.md) | L0→L1 持久化方案：face_uid 映射方案选择与序列化格式 |

## 文档规范

每份文档应包含：
1. **API 说明** — 函数签名、参数、返回值类型
2. **预期使用场景** — 在项目的哪个阶段/模块中使用
3. **已验证的代码** — 可直接复制使用的代码片段
4. **注意事项和坑** — 容易出错的地方、API 的行为细节
5. **已验证场景** — 每次验证单独记录，包含：使用的模型/数据、完整可复现的代码、预期输出与实际输出的对比

## 已验证场景记录模板

```markdown
### 验证场景 N：<简短描述>

**日期**：YYYY-MM-DD
**模型/数据**：<使用的 STEP 文件或 CadQuery 构建的模型>
**代码**：
\`\`\`python
# 可直接运行的完整代码
\`\`\`
**预期行为**：<描述>
**实际结果**：<描述>
**结论**：<API 是否可用、注意事项>
```
