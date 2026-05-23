"""L0 STEP 导入、面遍历和序列化测试。"""

from __future__ import annotations

from pathlib import Path

from src.common.data_models import FaceMetadata
from src.common.uid_manager import UIDManager
from src.l0_face_extraction.encoding_recovery import recover_part_name
from src.l0_face_extraction.face_traversal import is_supported_geom_type
from src.l0_face_extraction.l0_output import L0Output, build_l0_output
from src.l0_face_extraction.step_importer import import_step_file

FIXTURE = Path("tests/fixtures/simple_l0_l1_assembly.step")


def test_assembly_load_recovers_three_parts_and_all_faces() -> None:
    """验证小型有效装配体可恢复 3 个 Part / 15 个 face。"""
    uids = UIDManager()
    imported = import_step_file(FIXTURE, uid_manager=uids)
    l0 = build_l0_output(imported, uid_manager=uids)
    assert imported.part_boundary_reliable is True
    assert l0.metadata["import_strategy"] == "assembly_load"
    assert len(l0.parts) == 3
    assert len(l0.faces) == 15
    assert len(l0.face_map) == 15
    assert l0.metadata["type_distribution"] == {"PLANE": 14, "CYLINDER": 1}


def test_l0_output_roundtrip_preserves_uids_and_fingerprints() -> None:
    """验证 L0 to_dict/from_dict 保留 face_uid 和 fingerprint。"""
    uids = UIDManager()
    l0 = build_l0_output(import_step_file(FIXTURE, uid_manager=uids), uid_manager=uids)
    restored = L0Output.from_dict(l0.to_dict())
    assert restored.parts[0].part_uid == "p-0001"
    assert restored.faces[0].face_uid == "f-0001-00001"
    assert restored.faces[-1].fingerprint.geom_type == l0.faces[-1].fingerprint.geom_type


def test_encoding_recovery_fallback_and_ascii_name() -> None:
    """验证零件名恢复的 ASCII 直通和兜底命名。"""
    assert recover_part_name("base_plate", 1) == "base_plate"
    assert recover_part_name("", 2) == "unnamed_part_2"


def test_unsupported_face_metadata_is_serializable() -> None:
    """验证 unsupported face 可保留 UID、索引和指纹。"""
    assert is_supported_geom_type("BSPLINE") is False
    uids = UIDManager()
    l0 = build_l0_output(import_step_file(FIXTURE, uid_manager=uids), uid_manager=uids)
    unsupported = FaceMetadata(
        face_uid="f-9999-00001",
        part_uid=l0.parts[0].part_uid,
        global_face_index=999,
        part_face_index=999,
        geom_type="BSPLINE",
        supported=False,
        skip_reason="unsupported_geom_type",
        fingerprint=l0.faces[0].fingerprint,
    )
    data = unsupported.to_dict()
    restored = FaceMetadata.from_dict(data)
    assert restored.supported is False
    assert restored.skip_reason == "unsupported_geom_type"
