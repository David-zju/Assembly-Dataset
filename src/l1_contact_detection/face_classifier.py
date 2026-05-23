"""L1 face 类型分类。"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.common.data_models import FaceMetadata


@dataclass(slots=True)
class FaceClassification:
    """supported face 的类型分组和统计结果。"""

    planes: list[FaceMetadata] = field(default_factory=list)
    cylinders: list[FaceMetadata] = field(default_factory=list)
    cones: list[FaceMetadata] = field(default_factory=list)
    spheres: list[FaceMetadata] = field(default_factory=list)
    tori: list[FaceMetadata] = field(default_factory=list)
    type_distribution: dict[str, int] = field(default_factory=dict)
    supported_count: int = 0
    unsupported_count: int = 0

    @property
    def by_type(self) -> dict[str, list[FaceMetadata]]:
        """返回按 geom_type 分组的字典。"""
        return {
            "PLANE": self.planes,
            "CYLINDER": self.cylinders,
            "CONE": self.cones,
            "SPHERE": self.spheres,
            "TORUS": self.tori,
        }


def classify_faces(faces: list[FaceMetadata]) -> FaceClassification:
    """把 L0 face 元数据按几何类型分类。

    Args:
        faces: L0 输出中的 face 元数据列表；unsupported face 不进入分组。
    """
    result = FaceClassification()
    for face in faces:
        geom_type = face.geom_type.upper()
        result.type_distribution[geom_type] = result.type_distribution.get(geom_type, 0) + 1
        if not face.supported:
            result.unsupported_count += 1
            continue

        result.supported_count += 1
        if geom_type == "PLANE":
            result.planes.append(face)
        elif geom_type == "CYLINDER":
            result.cylinders.append(face)
        elif geom_type == "CONE":
            result.cones.append(face)
        elif geom_type == "SPHERE":
            result.spheres.append(face)
        elif geom_type == "TORUS":
            result.tori.append(face)
    return result
