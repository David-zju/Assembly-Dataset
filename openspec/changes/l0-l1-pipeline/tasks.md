## 1. 项目骨架与公共模块

- [ ] 1.1 创建目录结构：`src/l0_face_extraction/`, `src/l1_contact_detection/`, `src/common/`, `src/pipeline/`, `configs/`, `tests/fixtures/`, `tests/test_l0/`, `tests/test_l1/`, `tests/test_common/`, `tests/integration/`，每个包添加 `__init__.py`
- [ ] 1.2 创建 `configs/thresholds.yaml`：定义所有几何容差（max_angle_deg, max_distance_mm, max_axis_angle_deg, max_radius_ratio, search_radius, overlap_min_ratio 等）
- [ ] 1.3 创建 `configs/pipeline.yaml`：定义管道行为配置（启用 L0/L1、并行度、输出格式、输出目录）
- [ ] 1.4 创建 `configs/logging.yaml`：定义日志级别与输出目标（按 l0/l1/pipeline 分层配置）
- [ ] 1.5 实现 `src/common/exceptions.py`：定义异常类层次（StepImportError, UIDError, SerializationError, FingerprintMismatchError）
- [ ] 1.6 实现 `src/common/logging.py`：`get_logger(name)` 工厂函数，从 `configs/logging.yaml` 加载配置
- [ ] 1.7 实现 `src/common/tolerances.py`：加载 `configs/thresholds.yaml` 并提供统一容差访问接口
- [ ] 1.8 实现 `src/common/uid_manager.py`：UID 生成器，支持 part_uid（`p-{seq:04d}`）、face_uid（`f-{part_seq:04d}-{face_seq:05d}`）、contact_uid（`c-{seq:06d}`），保证全局唯一且不可修改
- [ ] 1.9 实现 `src/common/data_models.py`：定义 Part, FaceMetadata, FaceContact, ContactType 等核心数据类（使用 `__slots__` 优化内存）

## 2. 几何工具函数

- [ ] 2.1 实现 `src/common/geometry.py`：封装常用 OCP 几何计算函数——向量点积/叉积、gp_Dir.Angle() 角度计算、gp_Pln.Distance() 点面距离、坐标系变换（4×4 齐次矩阵）
- [ ] 2.2 实现 `src/common/spatial_index.py`：AABB 包围盒类 + 膨胀/相交测试 + AABB Tree/BVH 构建与相交 pair 查询；树叶节点容量、search_radius 可配置
- [ ] 2.3 实现 `src/common/fingerprint.py`：几何指纹计算（geomType + area + center + bbox），含跨导入一致性校验接口（容差 1e-4）

## 3. L0: STEP 导入与装配体扁平化

- [ ] 3.1 实现 `src/l0_face_extraction/step_importer.py`：STEP 文件导入入口——优先 `cq.Assembly.load()` 解析装配体结构，失败时回退到 `cq.importers.importStep()`；两种方式均失败时抛出 StepImportError
- [ ] 3.2 实现 `src/l0_face_extraction/flattener.py`：递归展开 sub-assembly 为扁平 Part 列表；同一零件定义的多个实例各自独立为不同 Part（共享 source_definition_uid）；每个 Part 提取相对于根坐标系的 4×4 齐次变换矩阵
- [ ] 3.3 实现 `src/l0_face_extraction/encoding_recovery.py`：中文零件名编码恢复——复刻 test.py 的编码链穷举搜索逻辑；恢复失败时使用 `unnamed_part_<索引>` 兜底
- [ ] 3.4 验证 L0 导入：对 `test_case/装配体3.STEP` 成功提取 19759 个 face；排查 `test_case/001650主臂装配体1.STEP` 的 0 face 问题

## 4. L0: B-rep 面遍历与标识

- [ ] 4.1 实现 `src/l0_face_extraction/face_traversal.py`：用 `TopExp_Explorer(wrapped, TopAbs_FACE)` 遍历每个 Part 的所有 B-rep face；为每个 face 调用 `geomType()` 判定类型（PLANE/CYLINDER/CONE/SPHERE/TORUS/BSPLINE/BEZIER/OTHER）
- [ ] 4.2 实现面类型过滤：BEZIER / BSPLINE / OTHER 类型记录 DEBUG 日志后跳过；统计并输出 skipped_face_count
- [ ] 4.3 实现 Part 和 Face UID 分配：按遍历顺序为每个 Part 分配 part_uid，为每个 face 分配 face_uid；构建 `Dict[face_uid, cq.Face]` 内存映射
- [ ] 4.4 实现几何指纹生成：为每个有效 face 计算几何指纹（geomType + area + center + bbox），与 face_uid 关联存储
- [ ] 4.5 实现 L0 输出结构 `src/l0_face_extraction/l0_output.py`：组装 L0 输出（Part 列表 + face 元数据列表 + 几何指纹 + metadata），提供 `to_dict()` 和 `from_dict()` 序列化接口

## 5. L1: 面分类与空间索引

- [ ] 5.1 实现 `src/l1_contact_detection/face_classifier.py`：将所有 face 按 geomType 分组为 planes[], cylinders[], cones[], spheres[], tori[]；统计并记录类型分布
- [ ] 5.2 实现 `src/l1_contact_detection/candidate_generator.py`：复用 `src/common/spatial_index.py` 的 expanded AABB 与 AABB Tree/BVH 能力，为全部候选 face 保守生成跨 Part 候选对；支持按 search_radius 膨胀 AABB
- [ ] 5.3 实现候选对生成策略：通过 AABB Tree/BVH 枚举 expanded AABB 相交的 pair，过滤同 Part pair；避免先枚举所有跨 Part 的 (face_i, face_j) 对；确保任何真实接触 pair 不会在索引阶段被漏掉

## 6. L1: 几何接触判定

- [ ] 6.1 实现 `src/l1_contact_detection/planar_contact.py`：Planar 接触判定——法向量反向检查（180° ± max_angle_deg）、共面距离检查（< max_distance_mm）、trimmed face 的平面局部 2D 投影重叠检查（Level 1 bbox 近似 + Level 2 形状简化判定）；仅 bbox 近似命中时设置 confidence < 1.0 与 needs_exact_overlap；同一 Part 内 face 直接跳过
- [ ] 6.2 实现 `src/l1_contact_detection/cylindrical_contact.py`：Cylindrical 接触判定——shaft/hole 分类（dot(normal_at_mid, vector_to_surface) 符号）、共轴检查（轴线夹角 + 径向距离）、半径匹配（半径差比 < max_radius_ratio）、trimmed face 的轴向区间重叠（重叠长度比 > min_overlap_length_ratio），并预留周向覆盖验证接口
- [ ] 6.3 实现 `src/l1_contact_detection/tangency_contact.py`：Tangency 接触判定——圆柱轴线平行于平面（即垂直于平面法向量）检查、|dist(axis, plane) - radius| < max_distance_mm 检查、切线落在平面 face 边界和圆柱 V 参数范围内的有限边界检查
- [ ] 6.4 统一接触判定入口：对候选对按 (type_i, type_j) 组合路由到对应判定函数；记录判定所得 confidence 和中间参数

## 7. L1: 接触组装与输出

- [ ] 7.1 实现 FaceContact 构建：为每个检测到的接触创建 FaceContact 实体（含 contact_uid, face_uid_pair, contact_type, confidence, 判定参数如 radius_diff_ratio/axis_angle_deg/overlap_length）
- [ ] 7.2 实现 contact_uid 分配：格式 `c-{seq:06d}`，按检测顺序连续分配，保证全局唯一
- [ ] 7.3 实现 `PerPartContactIndex` 构建：`Dict[part_uid, List[contact_uid]]`，支持按 Part 快速查询其参与的所有接触
- [ ] 7.4 实现 L1 输出结构 `src/l1_contact_detection/l1_output.py`：组装 L1 输出（FaceContact 列表 + PerPartContactIndex + metadata），提供 `to_dict()` 和 `from_dict()` 序列化接口

## 8. 管道持久化

- [ ] 8.1 实现 `src/common/serialization.py`：L0 输出 JSON 序列化——包含 metadata（source_file, pipeline_version, timestamp, num_faces）、parts 数组、faces 数组；确保输出文件 < 10MB（19759 面场景）
- [ ] 8.2 实现 L0 JSON 反序列化：L1 独立加载 L0 JSON 后还原 Part 列表和 face 元数据列表
- [ ] 8.3 实现 L1 STEP 独立加载与 face_uid 匹配：L1 重新导入 STEP，按 TopExp_Explorer 遍历顺序匹配 face_uid；首尾面几何指纹校验（容差 1e-4），不匹配时输出 WARNING 并回退到 O(N²) 全量指纹匹配
- [ ] 8.4 实现 `src/pipeline/pipeline_context.py`：PipelineContext 层间数据容器——按层存储输出数据，支持层间读写和序列化全量管道状态

## 9. 管道编排与 CLI

- [ ] 9.1 实现 `src/pipeline/orchestrator.py`：主编排器——按序执行 L0→L1 各阶段，传递 PipelineContext；记录每阶段耗时与实体统计
- [ ] 9.2 实现 `scripts/run_pipeline.py`：CLI 入口脚本——接收 STEP 文件路径、输出目录、配置路径等参数；调用主编排器运行管道

## 10. 测试

- [ ] 10.1 创建 `tests/fixtures/` 极简测试 STEP 文件：1-3 个面/零件的装配体（含 PLANE 和 CYLINDER 面），用于 L0 和 L1 单元测试
- [ ] 10.2 编写 `tests/test_common/` 公共模块测试：UID 管理器（唯一性、格式正确性、不可变性）、容差管理（加载正确性）、几何工具（距离/角度计算与手动验证一致）
- [ ] 10.3 编写 `tests/test_l0/` L0 单元测试：装配体扁平化（多实例零件属性）、B-rep 面遍历（类型分布统计）、编码恢复（中文名用例）、L0 输出序列化/反序列化
- [ ] 10.4 编写 `tests/test_l1/` L1 单元测试：Planar 接触判定（法向量±180°通过、非反向拒绝、同 Part 跳过）、Cylindrical 接触判定（孔轴配合通过、同类型拒绝、半径不匹配拒绝）、Tangency 接触判定（相切通过、不平行拒绝）、Contact UID 连续分配
- [ ] 10.5 编写 `tests/integration/` 集成测试：L0→L1 完整管道 E2E（对 fixture STEP 文件运行全管道，验证 face_uid/contact_uid 引用完整性）

## 11. 文档与收尾

- [ ] 11.1 更新 `TODO.md`：标记 L0、L1 阶段为已完成
- [ ] 11.2 验证 ARCHITECTURE.md 不变式合规：确认 L0 只依赖 common/*，L1 只依赖 common/* + L0 数据结构，层间通过 PipelineContext 传递数据
- [ ] 11.3 同步更新 `docs/verified_api/`：若实现过程中发现新的 API 坑或验证结论，按 README.md 规定的格式归档
