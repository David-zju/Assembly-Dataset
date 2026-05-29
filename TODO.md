# TODO

## L0 -> L1

已完成：已实现 STEP 装配体导入、Part 扁平化、B-rep face_uid 标识、L0 JSON 持久化、BVH 候选生成、Planar/Cylindrical/Tangency 接触检测、Cylindrical Contact 的公共圆柱坐标系下轴向/周向有限 overlap 判定、Planar Contact 的平面局部 2D trimmed domain overlap 判定、Tangency Contact 的理论切线有限 domain overlap 判定、L1 输出与 CLI。已补充 OCP `Geom_RectangularTrimmedSurface` 底层曲面解包，避免真实 STEP 中平面/圆柱被 trimmed wrapper 包裹时 L1 几何提取失败。正在补充 L0/L1 输出可视化检查工具：通过原始 STEP + L0/L1 JSON 恢复 face_uid 映射，并用 ocp_vscode 高亮检查 face、part 与 contact。

## L1 -> L2

未开始

## L2 -> L3

未开始

## L3 -> L4

未开始
