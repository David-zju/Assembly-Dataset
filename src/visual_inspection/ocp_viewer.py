"""ocp_vscode viewer 适配层。

本模块是可视化检查唯一直接导入 `ocp_vscode` 的位置。核心数据加载、
选择和 scene 构建逻辑不依赖 GUI，因此可以在自动测试中 mock 本适配层。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .scene_builder import SceneObject


class ViewerUnavailableError(RuntimeError):
    """无法连接或调用 ocp_vscode viewer 时抛出。"""


@dataclass(frozen=True, slots=True)
class ViewerResult:
    """viewer 调用结果。"""

    ok: bool
    message: str


class OcpViewer:
    """ocp_vscode 的薄封装。

    Args:
        port: 可选 viewer websocket 端口。
    """

    def __init__(self, *, port: int | None = None) -> None:
        self.port = port

    def show_scene(self, scene: list[SceneObject], *, reset_camera: bool = True, title: str | None = None) -> ViewerResult:
        """显示一组 SceneObject。

        Args:
            scene: scene builder 产生的对象列表。
            reset_camera: 是否重置相机。
            title: 可选标题，目前作为诊断消息使用。
        """
        if not scene:
            return ViewerResult(ok=False, message="没有可显示的对象")
        try:
            from ocp_vscode import Camera, show  # noqa: PLC0415

            camera_mode = Camera.RESET if reset_camera else Camera.CENTER

            show(
                *[item.obj for item in scene],
                names=[item.name for item in scene],
                colors=[item.color for item in scene],
                alphas=[item.alpha for item in scene],
                port=self.port,
                reset_camera=camera_mode,
                show_parent=True,
            )
        except Exception as exc:  # ocp_vscode 连接/序列化失败类型较多，统一提示。
            raise ViewerUnavailableError(
                "无法连接或更新 OCP CAD Viewer。请确认 VS Code 中已启动 OCP CAD Viewer，"
                "并且当前 conda cadquery 环境可以访问 ocp_vscode。"
                f"底层错误: {type(exc).__name__}: {exc}"
            ) from exc
        label = f"{title}: " if title else ""
        return ViewerResult(ok=True, message=f"{label}已发送 {len(scene)} 个对象到 OCP CAD Viewer")

    def update_scene(self, scene: list[SceneObject], *, title: str | None = None) -> ViewerResult:
        """更新 viewer 中的当前 scene。第一版使用完整 show 刷新。"""
        return self.show_scene(scene, reset_camera=False, title=title)


class RecordingViewer:
    """测试用 viewer，记录最近一次 scene 而不打开 GUI。"""

    def __init__(self) -> None:
        self.last_scene: list[SceneObject] = []

    def show_scene(self, scene: list[SceneObject], *, reset_camera: bool = True, title: str | None = None) -> ViewerResult:
        """记录 scene。"""
        self.last_scene = list(scene)
        return ViewerResult(ok=True, message=f"recorded {len(scene)} objects")

    def update_scene(self, scene: list[SceneObject], *, title: str | None = None) -> ViewerResult:
        """记录更新 scene。"""
        return self.show_scene(scene, reset_camera=False, title=title)


def scene_to_debug_rows(scene: list[SceneObject]) -> list[dict[str, Any]]:
    """将 scene 转为便于 CLI 打印或测试断言的字典列表。"""
    return [
        {
            "name": item.name,
            "role": item.role,
            "color": item.color,
            "alpha": item.alpha,
            "metadata": item.metadata,
        }
        for item in scene
    ]
