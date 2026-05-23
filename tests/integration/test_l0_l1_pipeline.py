"""L0→L1 管道集成测试。"""

from __future__ import annotations

from pathlib import Path

from src.common.serialization import read_l0_json
from src.l0_face_extraction.l0_output import L0Output
from src.l1_contact_detection.face_reloader import restore_l0_face_map_from_step
from src.l1_contact_detection.l1_output import build_l1_output
from src.pipeline.orchestrator import run_pipeline

FIXTURE = Path("tests/fixtures/simple_l0_l1_assembly.step")


def test_pipeline_e2e_outputs_valid_uid_references(tmp_path: Path) -> None:
    """验证完整管道输出的 face_uid/contact_uid 引用完整。"""
    context = run_pipeline(FIXTURE, output_dir=tmp_path)
    l0 = context.get_layer_output("l0")
    l1 = context.get_layer_output("l1")
    face_uids = {face.face_uid for face in l0.faces}
    assert len(l0.parts) == 3
    assert len(l1.contacts) == 2
    for contact in l1.contacts:
        assert set(contact.face_uid_pair) <= face_uids


def test_l1_can_reload_l0_json_and_rerun(tmp_path: Path) -> None:
    """验证 L1 可独立加载 L0 JSON 并恢复 face_map。"""
    run_pipeline(FIXTURE, output_dir=tmp_path)
    l0 = L0Output.from_dict(read_l0_json(tmp_path / "l0_output.json"))
    restore_l0_face_map_from_step(l0)
    l1 = build_l1_output(l0)
    assert len(l0.face_map) == 15
    assert len(l1.contacts) == 2
