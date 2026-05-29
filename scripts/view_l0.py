#!/usr/bin/env python3
"""用 ocp_vscode 高亮检查 L0 输出。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ocp_vscode 在当前 cadquery 环境中需要先于 cadquery/OCP 导入，否则可能触发
# pyexpat 动态库符号冲突。只在脚本入口预导入，不影响核心管道。
try:
    import ocp_vscode  # noqa: F401,E402
except Exception:
    ocp_vscode = None  # type: ignore[assignment]

from src.visual_inspection.data_loader import VisualInspectionError, load_l0_inspection_data  # noqa: E402
from src.visual_inspection.ocp_viewer import OcpViewer, ViewerUnavailableError, scene_to_debug_rows  # noqa: E402
from src.visual_inspection.scene_builder import build_l0_face_scene, build_l0_part_scene  # noqa: E402
from src.visual_inspection.selectors import (  # noqa: E402
    select_faces,
    select_geom_type_faces,
    select_part_faces,
    select_unsupported_faces,
)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="可视化检查 L0 face/part 输出")
    parser.add_argument("--step", required=True, help="原始 STEP 文件路径")
    parser.add_argument("--l0", required=True, help="l0_output.json 路径")
    parser.add_argument("--face", help="要高亮的单个 face_uid")
    parser.add_argument("--faces", help="逗号分隔的多个 face_uid")
    parser.add_argument("--part", help="要高亮的 part_uid")
    parser.add_argument("--geom-type", help="要高亮的几何类型，如 PLANE")
    parser.add_argument("--unsupported", action="store_true", help="高亮所有 unsupported face")
    parser.add_argument("--context", choices=["none", "part"], default="none", help="face 高亮上下文")
    parser.add_argument("--dry-run", action="store_true", help="只打印将显示的对象，不调用 ocp_vscode")
    parser.add_argument("--port", type=int, default=None, help="OCP CAD Viewer 端口")
    return parser.parse_args()


def main() -> int:
    """CLI 主入口。"""
    args = parse_args()
    try:
        data = load_l0_inspection_data(args.l0, step_file=args.step, restore_faces=True)
        selected_modes = sum(bool(value) for value in (args.face, args.faces, args.part, args.geom_type, args.unsupported))
        if selected_modes != 1:
            raise VisualInspectionError("必须且只能指定一种选择方式：--face/--faces/--part/--geom-type/--unsupported")

        if args.part:
            scene = build_l0_part_scene(data, args.part)
        else:
            if args.face:
                faces = select_faces(data, [args.face])
            elif args.faces:
                faces = select_faces(data, [value.strip() for value in args.faces.split(",") if value.strip()])
            elif args.geom_type:
                faces = select_geom_type_faces(data, args.geom_type)
            else:
                faces = select_unsupported_faces(data)
            if not faces:
                raise VisualInspectionError("选择结果为空，没有可显示对象")
            scene = build_l0_face_scene(data, faces, context=args.context)

        print(f"准备显示 {len(scene)} 个对象")
        for row in scene_to_debug_rows(scene):
            print(f"- {row['role']}: {row['name']} color={row['color']} alpha={row['alpha']}")
        if args.dry_run:
            return 0
        result = OcpViewer(port=args.port).show_scene(scene, title="L0 visual inspection")
        print(result.message)
        return 0
    except (VisualInspectionError, ViewerUnavailableError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
