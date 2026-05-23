"""日志配置加载与 logger 工厂。"""

from __future__ import annotations

import logging
import logging.config
from pathlib import Path
from typing import Any

import yaml

_CONFIGURED = False
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "logging.yaml"


def configure_logging(config_path: str | Path | None = None) -> None:
    """加载日志配置。

    Args:
        config_path: 可选 YAML 配置路径；为 None 时读取 configs/logging.yaml。

    Example:
        >>> configure_logging()
        >>> logger = get_logger("l0.import")
    """
    global _CONFIGURED
    path = Path(config_path) if config_path else _DEFAULT_CONFIG_PATH
    if path.exists():
        data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        logging.config.dictConfig(data)
    else:
        logging.basicConfig(level=logging.INFO)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """返回按项目配置初始化过的 logger。

    Args:
        name: logger 名称，建议使用 l0.*、l1.* 或 pipeline。

    Returns:
        logging.Logger: 标准库 logger。
    """
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)

