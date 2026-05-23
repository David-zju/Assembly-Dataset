"""face 几何指纹计算与比较。"""

from __future__ import annotations

from dataclasses import dataclass

from .data_models import FaceFingerprint


def compute_face_fingerprint(face) -> FaceFingerprint:
    """计算 CadQuery Face 的几何指纹。

    Args:
        face: CadQuery Face 对象，需支持 geomType/Area/Center/BoundingBox。

    Returns:
        FaceFingerprint: 可序列化的几何摘要。
    """
    geom_type = str(face.geomType())
    center = tuple(float(v) for v in face.Center().toTuple())
    bbox = face.BoundingBox()
    bbox_tuple = (
        float(bbox.xmin),
        float(bbox.xmax),
        float(bbox.ymin),
        float(bbox.ymax),
        float(bbox.zmin),
        float(bbox.zmax),
    )
    return FaceFingerprint(
        geom_type=geom_type,
        area=float(face.Area()),
        center=center,  # type: ignore[arg-type]
        bbox=bbox_tuple,
    )


@dataclass(frozen=True, slots=True)
class FingerprintComparison:
    """几何指纹比较结果。"""

    matches: bool
    max_delta: float
    reason: str


def fingerprints_match(a: FaceFingerprint, b: FaceFingerprint, abs_tol: float = 1e-4) -> FingerprintComparison:
    """比较两个几何指纹是否在容差内一致。

    Args:
        a: 第一个指纹。
        b: 第二个指纹。
        abs_tol: 浮点绝对容差。
    """
    if a.geom_type != b.geom_type:
        return FingerprintComparison(False, float("inf"), "geom_type mismatch")

    deltas = [abs(a.area - b.area)]
    deltas.extend(abs(x - y) for x, y in zip(a.center, b.center, strict=True))
    deltas.extend(abs(x - y) for x, y in zip(a.bbox, b.bbox, strict=True))
    max_delta = max(deltas) if deltas else 0.0
    if max_delta <= abs_tol:
        return FingerprintComparison(True, max_delta, "match")
    return FingerprintComparison(False, max_delta, "numeric delta exceeds tolerance")

