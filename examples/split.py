# 拆分装配体 STEP 文件为独立 component STEP 文件

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import cadquery as cq


def _sanitize_name(name: str) -> str:
	cleaned = re.sub(r"[^\w\-.]+", "_", name.strip())
	cleaned = cleaned.strip("._")
	return cleaned or "component"


def _iter_step_files(path: Path) -> Iterable[Path]:
	if path.is_file() and path.suffix.lower() in {".step", ".stp"}:
		yield path
		return

	if path.is_dir():
		for file_path in sorted(path.iterdir()):
			if file_path.suffix.lower() in {".step", ".stp"}:
				yield file_path


def split_step_components(step_file: Path, output_dir: Path | None = None) -> int:
	step_file = step_file.resolve()
	if output_dir is None:
		raise ValueError("output_dir 不能为空")
	exported = 0
	try:
		assembly = cq.Assembly.load(str(step_file))
		for index, (shape, name, loc, _color) in enumerate(assembly, start=1):
			if shape is None:
				continue
			part_name = _sanitize_name(name or f"component_{index:03d}")
			out_file = output_dir / f"{index:03d}_{part_name}.step"
			cq.exporters.export(shape.located(loc), str(out_file))
			exported += 1
	except Exception:
		imported = cq.importers.importStep(str(step_file))
		solids = imported.solids().vals()
		for index, solid in enumerate(solids, start=1):
			out_file = output_dir / f"{index:03d}_solid.step"
			cq.exporters.export(solid, str(out_file))
			exported += 1

	if exported == 0:
		raise RuntimeError(f"未在 {step_file} 中找到可导出的 component/solid")

	return exported


def main(input_path: Path | str, output_dir: Path | str | None = None) -> int:
	"""Library-style entry: 拆分单个 STEP 文件并返回导出的文件数量。

	Args:
		input_path: STEP 文件路径（字符串或 Path）。
		output_dir: 输出目录路径（字符串或 Path）。若为 None，默认在输入文件同目录创建 "<stem>_components"。

	Returns:
		已导出的文件数量（int）。
	"""
	step_file = Path(input_path).resolve()
	if not step_file.is_file() or step_file.suffix.lower() not in {".step", ".stp"}:
		raise FileNotFoundError(f"未找到 STEP 文件: {step_file}")

	out_dir = Path(output_dir).resolve() if output_dir else step_file.parent / f"{step_file.stem}_components"
	out_dir.mkdir(parents=True, exist_ok=True)

	count = split_step_components(step_file, out_dir)
	print(f"{step_file.name}: 已导出 {count} 个文件")
	return count


def _cli() -> None:
	parser = argparse.ArgumentParser(description="拆分装配体 STEP 文件为独立 component STEP 文件")
	parser.add_argument(
		"input_path",
		help="输入 STEP 文件路径（必须为单个 .step/.stp 文件）",
	)
	parser.add_argument(
		"-o",
		"--output",
		default=None,
		help="输出目录（若不存在则创建；默认在输入文件同目录创建 *_components）",
	)
	args = parser.parse_args()
	main(args.input_path, args.output)


if __name__ == "__main__":
	# _cli()
	main("./test_case/装配体3.STEP")
