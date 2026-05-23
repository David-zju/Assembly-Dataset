"""L0→L1 管道主编排器。"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from src.common.serialization import write_l0_json, write_l1_json
from src.common.tolerances import load_tolerances
from src.common.uid_manager import UIDManager
from src.l0_face_extraction.l0_output import build_l0_output
from src.l0_face_extraction.step_importer import import_step_file
from src.l1_contact_detection.l1_output import build_l1_output

from .pipeline_context import PipelineContext

_DEFAULT_PIPELINE_CONFIG = Path(__file__).resolve().parents[2] / "configs" / "pipeline.yaml"


def load_pipeline_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """读取管道行为配置。"""
    path = Path(config_path) if config_path else _DEFAULT_PIPELINE_CONFIG
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def run_pipeline(
    step_file: str | Path,
    *,
    output_dir: str | Path | None = None,
    pipeline_config_path: str | Path | None = None,
    thresholds_path: str | Path | None = None,
    run_l1: bool = True,
) -> PipelineContext:
    """按序执行 L0→L1 管道。

    Args:
        step_file: 输入 STEP 文件路径。
        output_dir: 可选输出目录；为空时使用 pipeline.yaml 中的 output_dir。
        pipeline_config_path: 可选管道配置路径。
        thresholds_path: 可选几何容差配置路径。
        run_l1: 是否执行 L1；调试 L0 时可关闭。
    """
    config = load_pipeline_config(pipeline_config_path)
    pipeline_cfg = config.get("pipeline", {})
    l0_cfg = config.get("l0", {})
    version = str(pipeline_cfg.get("pipeline_version", "0.1.0"))
    out_dir = Path(output_dir or pipeline_cfg.get("output_dir", "outputs"))
    out_dir.mkdir(parents=True, exist_ok=True)

    context = PipelineContext(
        metadata={
            "source_file": str(step_file),
            "pipeline_version": version,
            "output_dir": str(out_dir),
        }
    )
    uids = UIDManager()

    l0_started = perf_counter()
    imported = import_step_file(
        step_file,
        allow_import_step_fallback=bool(l0_cfg.get("allow_import_step_fallback", True)),
        uid_manager=uids,
    )
    l0_output = build_l0_output(imported, uid_manager=uids, pipeline_version=version)
    context.set_layer_output("l0", l0_output)
    context.metadata["l0_seconds"] = perf_counter() - l0_started
    write_l0_json(l0_output, out_dir / "l0_output.json")

    enabled_layers = set(pipeline_cfg.get("enabled_layers", ["l0", "l1"]))
    should_run_l1 = run_l1 and "l1" in enabled_layers
    if should_run_l1:
        l1_started = perf_counter()
        tolerances = load_tolerances(thresholds_path)
        l1_output = build_l1_output(l0_output, uid_manager=uids, tolerances=tolerances)
        context.set_layer_output("l1", l1_output)
        context.metadata["l1_seconds"] = perf_counter() - l1_started
        write_l1_json(l1_output, out_dir / "l1_output.json")
    else:
        context.set_layer_output("l1", None)

    return context
