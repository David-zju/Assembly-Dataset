"""管道 JSON 序列化工具。

本模块只处理通用 JSON 读写和带 `to_dict()` 对象的持久化，不保存 CadQuery/OCP
运行期几何对象。L0/L1 的具体数据结构恢复由各层输出类的 `from_dict()` 完成。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .exceptions import SerializationError


class Serializable(Protocol):
    """提供 `to_dict()` 的可序列化对象协议。"""

    def to_dict(self) -> dict[str, Any]:
        """转换为 JSON 友好的字典。"""


def write_json_dict(
    data: dict[str, Any],
    output_file: str | Path,
    *,
    max_bytes: int | None = None,
    indent: int | None = 2,
) -> Path:
    """将字典写入 JSON 文件。

    Args:
        data: JSON 友好的字典。
        output_file: 输出文件路径。
        max_bytes: 可选文件大小上限，超过时抛出 SerializationError。
        indent: JSON 缩进；为 None 时使用紧凑格式。
    """
    path = Path(output_file)
    path.parent.mkdir(parents=True, exist_ok=True)
    separators = (",", ":") if indent is None else None
    text = json.dumps(data, ensure_ascii=False, indent=indent, sort_keys=False, separators=separators)
    encoded = text.encode("utf-8")
    if max_bytes is not None and len(encoded) > max_bytes:
        raise SerializationError(f"JSON 输出超过大小限制: {len(encoded)} > {max_bytes} bytes")
    path.write_text(text + "\n", encoding="utf-8")
    return path


def read_json_dict(input_file: str | Path) -> dict[str, Any]:
    """读取 JSON 文件为字典。"""
    path = Path(input_file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SerializationError(f"JSON 读取失败: {path}; error={exc!r}") from exc
    if not isinstance(data, dict):
        raise SerializationError(f"JSON 顶层结构必须是对象: {path}")
    return data


def write_l0_json(l0_output: Serializable, output_file: str | Path, *, max_bytes: int = 10 * 1024 * 1024) -> Path:
    """写入 L0 输出 JSON，并默认限制在 10MB 内。"""
    return write_json_dict(l0_output.to_dict(), output_file, max_bytes=max_bytes, indent=None)


def read_l0_json(input_file: str | Path) -> dict[str, Any]:
    """读取 L0 输出 JSON 的原始字典。

    调用方应使用 `L0Output.from_dict(read_l0_json(path))` 恢复数据结构。
    """
    return read_json_dict(input_file)


def write_l1_json(l1_output: Serializable, output_file: str | Path) -> Path:
    """写入 L1 输出 JSON。"""
    return write_json_dict(l1_output.to_dict(), output_file)
