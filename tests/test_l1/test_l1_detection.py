"""L1 接触检测单元测试。"""

from __future__ import annotations

from pathlib import Path

import cadquery as cq
import math
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
from OCP.Geom import Geom_CylindricalSurface
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt

from src.common.data_models import FaceMetadata
from src.common.fingerprint import compute_face_fingerprint
from src.common.tolerances import load_tolerances
from src.common.uid_manager import UIDManager
from src.l0_face_extraction.l0_output import build_l0_output
from src.l0_face_extraction.step_importer import import_step_file
from src.l1_contact_detection.cylindrical_contact import detect_cylindrical_contact
from src.l1_contact_detection.l1_output import build_l1_output
from src.l1_contact_detection.planar_contact import detect_planar_contact
from src.l1_contact_detection.tangency_contact import detect_tangency_contact

FIXTURE = Path("tests/fixtures/simple_l0_l1_assembly.step")


def _first_face(shape: cq.Workplane, geom_type: str) -> cq.Face:
    """从 Workplane 中取第一个指定类型 face。"""
    for face in shape.faces().vals():
        if str(face.geomType()).upper() == geom_type:
            return face
    raise AssertionError(f"未找到 {geom_type} face")


def _meta(face_uid: str, part_uid: str, geom_type: str, face: cq.Face) -> FaceMetadata:
    """构造测试用 FaceMetadata。"""
    return FaceMetadata(
        face_uid=face_uid,
        part_uid=part_uid,
        global_face_index=0,
        part_face_index=0,
        geom_type=geom_type,
        supported=True,
        skip_reason=None,
        fingerprint=compute_face_fingerprint(face),
    )


def _partial_cylinder_face(
    start_deg: float,
    end_deg: float,
    *,
    vmin: float = -5.0,
    vmax: float = 5.0,
    axis_dir: tuple[float, float, float] = (0.0, 0.0, 1.0),
    reversed_orientation: bool = False,
) -> cq.Face:
    """构造测试用局部圆柱 face。"""
    surf = Geom_CylindricalSurface(gp_Ax3(gp_Pnt(0, 0, 0), gp_Dir(*axis_dir)), 2.5)
    face = cq.Face(
        BRepBuilderAPI_MakeFace(
            surf,
            math.radians(start_deg),
            math.radians(end_deg),
            vmin,
            vmax,
            1e-7,
        ).Face(),
    )
    if reversed_orientation:
        return cq.Face(face.wrapped.Reversed())
    return face


def test_planar_contact_detected_and_same_part_skipped() -> None:
    """验证平面接触通过，同 Part 直接跳过。"""
    uids = UIDManager()
    l0 = build_l0_output(import_step_file(FIXTURE, uid_manager=uids), uid_manager=uids)
    by_uid = {face.face_uid: face for face in l0.faces}
    meta_a = by_uid["f-0001-00006"]
    meta_b = by_uid["f-0002-00005"]
    tol = load_tolerances()
    detection = detect_planar_contact(meta_a, l0.face_map[meta_a.face_uid], meta_b, l0.face_map[meta_b.face_uid], tol)
    assert detection is not None
    assert detection.confidence < 1.0
    same_part = detect_planar_contact(meta_a, l0.face_map[meta_a.face_uid], meta_a, l0.face_map[meta_a.face_uid], tol)
    assert same_part is None


def test_cylindrical_contact_accepts_hole_shaft_and_rejects_mismatch() -> None:
    """验证孔轴圆柱接触、同类型拒绝和半径不匹配拒绝。"""
    shaft_face = _first_face(cq.Workplane("XY").circle(2.5).extrude(10), "CYLINDER")
    hole_face = _first_face(cq.Workplane("XY").box(20, 20, 10).faces(">Z").workplane().hole(5, 10), "CYLINDER")
    small_shaft_face = _first_face(cq.Workplane("XY").circle(2.0).extrude(10), "CYLINDER")
    tol = load_tolerances()

    shaft_meta = _meta("f-0001-00001", "p-0001", "CYLINDER", shaft_face)
    hole_meta = _meta("f-0002-00001", "p-0002", "CYLINDER", hole_face)
    small_meta = _meta("f-0003-00001", "p-0003", "CYLINDER", small_shaft_face)

    detection = detect_cylindrical_contact(shaft_meta, shaft_face, hole_meta, hole_face, tol)
    assert detection is not None
    assert detection.parameters["axial_overlap_method"] == "uv_sampled"
    assert detection.parameters["circumferential_overlap_method"] == "uv_sampled_common_frame"
    assert detect_cylindrical_contact(shaft_meta, shaft_face, shaft_meta, shaft_face, tol) is None
    assert detect_cylindrical_contact(small_meta, small_shaft_face, hole_meta, hole_face, tol) is None


def test_cylindrical_contact_rejects_axial_mismatch() -> None:
    """验证共轴同半径但轴向不重叠时拒绝。"""
    shaft = _partial_cylinder_face(0, 360, vmin=-5, vmax=-1)
    hole = _partial_cylinder_face(0, 360, vmin=1, vmax=5, reversed_orientation=True)
    tol = load_tolerances()

    shaft_meta = _meta("f-0001-00001", "p-0001", "CYLINDER", shaft)
    hole_meta = _meta("f-0002-00001", "p-0002", "CYLINDER", hole)

    assert detect_cylindrical_contact(shaft_meta, shaft, hole_meta, hole, tol) is None


def test_cylindrical_contact_detects_and_rejects_partial_circumference() -> None:
    """验证局部圆柱片周向重叠通过、周向错开拒绝。"""
    shaft = _partial_cylinder_face(350, 370, vmin=-5, vmax=5)
    matching_hole = _partial_cylinder_face(355, 365, vmin=-4, vmax=4, reversed_orientation=True)
    shifted_hole = _partial_cylinder_face(90, 110, vmin=-4, vmax=4, reversed_orientation=True)
    tol = load_tolerances()

    shaft_meta = _meta("f-0001-00001", "p-0001", "CYLINDER", shaft)
    matching_meta = _meta("f-0002-00001", "p-0002", "CYLINDER", matching_hole)
    shifted_meta = _meta("f-0003-00001", "p-0003", "CYLINDER", shifted_hole)

    detection = detect_cylindrical_contact(shaft_meta, shaft, matching_meta, matching_hole, tol)
    assert detection is not None
    assert detection.parameters["needs_exact_overlap"] is True
    assert detection.parameters["circumferential_overlap_angle_deg"] > 1.0
    assert detect_cylindrical_contact(shaft_meta, shaft, shifted_meta, shifted_hole, tol) is None


def test_cylindrical_contact_handles_non_global_axis() -> None:
    """验证非全局 Z 轴圆柱可正确计算轴向与周向 overlap。"""
    shaft = _partial_cylinder_face(0, 120, vmin=-5, vmax=5, axis_dir=(1.0, 0.0, 0.0))
    hole = _partial_cylinder_face(30, 90, vmin=-4, vmax=4, axis_dir=(1.0, 0.0, 0.0), reversed_orientation=True)
    tol = load_tolerances()

    shaft_meta = _meta("f-0001-00001", "p-0001", "CYLINDER", shaft)
    hole_meta = _meta("f-0002-00001", "p-0002", "CYLINDER", hole)

    detection = detect_cylindrical_contact(shaft_meta, shaft, hole_meta, hole, tol)
    assert detection is not None
    assert detection.parameters["axial_overlap_method"] == "uv_sampled"


def test_tangency_contact_detected_and_non_parallel_rejected() -> None:
    """验证圆柱-平面相切通过，非平行轴线拒绝。"""
    cylinder_face = _first_face(cq.Workplane("YZ").circle(2.5).extrude(10), "CYLINDER")
    tangent_plane = cq.Workplane("XY").box(12, 0.2, 12).translate((5, 2.4, 0)).faces(">Y").val()
    non_parallel_plane = cq.Workplane("XY").box(0.2, 12, 12).translate((2.4, 0, 0)).faces(">X").val()
    tol = load_tolerances()

    cyl_meta = _meta("f-0001-00001", "p-0001", "CYLINDER", cylinder_face)
    plane_meta = _meta("f-0002-00001", "p-0002", "PLANE", tangent_plane)
    other_plane_meta = _meta("f-0003-00001", "p-0003", "PLANE", non_parallel_plane)

    assert detect_tangency_contact(cyl_meta, cylinder_face, plane_meta, tangent_plane, tol) is not None
    assert detect_tangency_contact(cyl_meta, cylinder_face, other_plane_meta, non_parallel_plane, tol) is None


def test_l1_output_contact_uid_is_continuous() -> None:
    """验证 L1 输出 contact_uid 连续分配。"""
    uids = UIDManager()
    l0 = build_l0_output(import_step_file(FIXTURE, uid_manager=uids), uid_manager=uids)
    l1 = build_l1_output(l0, uid_manager=uids)
    assert [contact.contact_uid for contact in l1.contacts] == ["c-000001", "c-000002"]
    assert "p-0001" in l1.per_part_contact_index
