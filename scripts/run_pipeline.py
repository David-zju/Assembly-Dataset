#!/usr/bin/env python3
"""运行 L0→L1 装配标注管道的 CLI 入口。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.pipeline.orchestrator import run_pipeline  # noqa: E402


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="运行 L0→L1 STEP 装配标注管道")
    parser.add_argument("step_file", help="输入 .step/.stp 文件路径")
    parser.add_argument("-o", "--output-dir", default=None, help="输出目录，默认读取 configs/pipeline.yaml")
    parser.add_argument("--pipeline-config", default=None, help="pipeline.yaml 路径")
    parser.add_argument("--thresholds", default=None, help="thresholds.yaml 路径")
    parser.add_argument("--skip-l1", action="store_true", help="仅运行 L0，不执行 L1")
    return parser.parse_args()


def main() -> None:
    """CLI 主函数。"""
    args = parse_args()
    context = run_pipeline(
        args.step_file,
        output_dir=args.output_dir,
        pipeline_config_path=args.pipeline_config,
        thresholds_path=args.thresholds,
        run_l1=not args.skip_l1,
    )
    summary = {
        "metadata": context.metadata,
        "layers": {
            name: None if output is None else getattr(output, "metadata", {})
            for name, output in context.layers.items()
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
