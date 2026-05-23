"""管道层间数据容器。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class PipelineContext:
    """按层保存管道输出的轻量容器。

    Args:
        metadata: 管道级元数据，如源文件、版本、耗时。
        layers: 层名到输出对象的映射。输出对象可为带 `to_dict()` 的数据类。
    """

    metadata: dict[str, Any] = field(default_factory=dict)
    layers: dict[str, Any] = field(default_factory=dict)

    def set_layer_output(self, layer_name: str, output: Any) -> None:
        """写入某一层输出。"""
        self.layers[layer_name] = output

    def get_layer_output(self, layer_name: str) -> Any:
        """读取某一层输出；不存在时抛出 KeyError。"""
        return self.layers[layer_name]

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典。"""
        serialized_layers: dict[str, Any] = {}
        for name, output in self.layers.items():
            if hasattr(output, "to_dict"):
                serialized_layers[name] = output.to_dict()
            else:
                serialized_layers[name] = output
        return {"metadata": self.metadata, "layers": serialized_layers}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PipelineContext":
        """从字典恢复 PipelineContext；层输出保持为原始字典。"""
        return cls(metadata=dict(data.get("metadata", {})), layers=dict(data.get("layers", {})))
