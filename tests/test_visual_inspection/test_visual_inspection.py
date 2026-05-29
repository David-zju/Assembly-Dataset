"""L0/L1 可视化检查模块测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.common.data_models import ImportStrategy
from src.common.exceptions import StepImportError
from src.common.face_reloader import restore_face_map_from_step
from src.common.serialization import read_l0_json
from src.l0_face_extraction.l0_output import L0Output
from src.pipeline.orchestrator import run_pipeline
from src.visual_inspection.data_loader import (
    VisualInspectionError,
    contact_summary,
    load_l0_inspection_data,
    load_l1_inspection_data,
)
from src.visual_inspection.ocp_viewer import RecordingViewer, scene_to_debug_rows
from src.visual_inspection.scene_builder import build_l0_face_scene, build_l0_part_scene, build_l1_contact_scene
from src.visual_inspection.selectors import (
    ContactFilter,
    filter_contacts,
    require_contact,
    require_face,
    select_faces,
    select_geom_type_faces,
    select_part_faces,
    sort_contacts,
)

FIXTURE = Path("tests/fixtures/simple_l0_l1_assembly.step")


@pytest.fixture()
def pipeline_outputs(tmp_path: Path) -> Path:
    """生成测试用 L0/L1 JSON 输出目录。"""
    run_pipeline(FIXTURE, output_dir=tmp_path)
    return tmp_path


def test_common_face_reloader_restores_mapping_without_l0_dependency(pipeline_outputs: Path) -> None:
    """验证通用 face reloader 可从 L0 JSON 与 STEP 恢复 face_map。"""
    l0 = L0Output.from_dict(read_l0_json(pipeline_outputs / "l0_output.json"))
    face_map = restore_face_map_from_step(FIXTURE, l0.parts, l0.faces, l0.metadata)

    assert len(face_map) == len(l0.faces)
    assert "f-0001-00006" in face_map


def test_common_face_reloader_rejects_unreliable_boundary(pipeline_outputs: Path) -> None:
    """验证 Part 边界不可靠时拒绝恢复。"""
    l0 = L0Output.from_dict(read_l0_json(pipeline_outputs / "l0_output.json"))
    l0.metadata["part_boundary_reliable"] = False

    with pytest.raises(StepImportError, match="Part 边界不可靠"):
        restore_face_map_from_step(FIXTURE, l0.parts, l0.faces, l0.metadata)


def test_l0_data_loader_and_selectors(pipeline_outputs: Path) -> None:
    """验证 L0 数据加载、索引和选择器。"""
    data = load_l0_inspection_data(pipeline_outputs / "l0_output.json", step_file=FIXTURE, restore_faces=True)

    assert len(data.parts_by_uid) == 3
    assert require_face(data, "f-0001-00006").part_uid == "p-0001"
    assert len(select_faces(data, ["f-0001-00006", "f-0002-00005"])) == 2
    assert len(select_part_faces(data, "p-0001")) == 6
    assert len(select_geom_type_faces(data, "PLANE")) == 14
    with pytest.raises(VisualInspectionError, match="未找到 face_uid"):
        require_face(data, "f-missing")


def test_l1_contact_index_filter_sort_and_summary(pipeline_outputs: Path) -> None:
    """验证 L1 contact 索引、过滤、排序和摘要。"""
    data = load_l1_inspection_data(
        pipeline_outputs / "l0_output.json",
        pipeline_outputs / "l1_output.json",
        step_file=FIXTURE,
        restore_faces=True,
    )

    assert require_contact(data, "c-000001").confidence == 0.95
    exact_contacts = filter_contacts(data, ContactFilter(needs_exact=True))
    assert [contact.contact_uid for contact in exact_contacts] == ["c-000002"]
    p3_contacts = filter_contacts(data, ContactFilter(part_uid="p-0003"))
    assert [contact.contact_uid for contact in p3_contacts] == ["c-000002"]
    sorted_contacts = sort_contacts(list(data.l1.contacts), sort_key="confidence", descending=True)
    assert [contact.contact_uid for contact in sorted_contacts] == ["c-000001", "c-000002"]
    summary = contact_summary(require_contact(data, "c-000002"), data.l0_data.faces_by_uid)
    assert summary["needs_exact_overlap"] is True
    assert summary["part_uid_pair"] == ["p-0001", "p-0003"]


def test_scene_builders_and_recording_viewer(pipeline_outputs: Path) -> None:
    """验证 scene builder 输出角色、名称、颜色和 mock viewer 记录。"""
    l1_data = load_l1_inspection_data(
        pipeline_outputs / "l0_output.json",
        pipeline_outputs / "l1_output.json",
        step_file=FIXTURE,
        restore_faces=True,
    )
    l0_data = l1_data.l0_data

    l0_face_scene = build_l0_face_scene(l0_data, select_faces(l0_data, ["f-0001-00006"]), context="part")
    assert {item.role for item in l0_face_scene} == {"context_part", "l0_face"}

    l0_part_scene = build_l0_part_scene(l0_data, "p-0001")
    assert l0_part_scene[0].role == "l0_part"
    assert "faces=6" in l0_part_scene[0].name

    l1_scene = build_l1_contact_scene(l1_data, "c-000002", context="part")
    roles = [item.role for item in l1_scene]
    assert roles.count("context_part") == 2
    assert "l1_face_a" in roles
    assert "l1_face_b" in roles
    rows = scene_to_debug_rows(l1_scene)
    assert any(row["metadata"].get("needs_exact_overlap") is True for row in rows)

    viewer = RecordingViewer()
    result = viewer.show_scene(l1_scene)
    assert result.ok is True
    assert len(viewer.last_scene) == len(l1_scene)


def test_data_loader_rejects_missing_contact(pipeline_outputs: Path) -> None:
    """验证缺失 contact_uid 的错误清晰。"""
    data = load_l1_inspection_data(
        pipeline_outputs / "l0_output.json",
        pipeline_outputs / "l1_output.json",
        step_file=FIXTURE,
        restore_faces=False,
    )
    with pytest.raises(VisualInspectionError, match="未找到 contact_uid"):
        require_contact(data, "c-missing")
