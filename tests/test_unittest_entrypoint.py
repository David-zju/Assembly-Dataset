"""标准库 unittest 测试入口。

当前 cadquery 环境未安装 pytest；本文件复用 pytest 风格测试函数，确保
`python -m unittest discover tests` 也能执行核心验证。
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.integration import test_l0_l1_pipeline as integration_tests
from tests.test_common import test_common_modules as common_tests
from tests.test_l0 import test_l0_pipeline as l0_tests
from tests.test_l1 import test_l1_detection as l1_tests


class L0L1SmokeTest(unittest.TestCase):
    """复用现有测试函数的 unittest 入口。"""

    def test_common_l0_l1_and_integration(self) -> None:
        """执行公共模块、L0、L1 和集成 smoke 测试。"""
        functions = [
            common_tests.test_uid_manager_formats_and_uniqueness,
            common_tests.test_tolerances_load_defaults,
            common_tests.test_axis_geometry_matches_manual_expectation,
            common_tests.test_bvh_intersections_filter_same_part_and_deduplicate,
            common_tests.test_bvh_degenerate_centers_and_long_thin_boxes,
            l0_tests.test_assembly_load_recovers_three_parts_and_all_faces,
            l0_tests.test_l0_output_roundtrip_preserves_uids_and_fingerprints,
            l0_tests.test_encoding_recovery_fallback_and_ascii_name,
            l0_tests.test_unsupported_face_metadata_is_serializable,
            l1_tests.test_planar_contact_detected_and_same_part_skipped,
            l1_tests.test_cylindrical_contact_accepts_hole_shaft_and_rejects_mismatch,
            l1_tests.test_tangency_contact_detected_and_non_parallel_rejected,
            l1_tests.test_l1_output_contact_uid_is_continuous,
        ]
        for function in functions:
            with self.subTest(function=function.__name__):
                function()

        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            integration_tests.test_pipeline_e2e_outputs_valid_uid_references(tmp_path)
            integration_tests.test_l1_can_reload_l0_json_and_rerun(tmp_path)


if __name__ == "__main__":
    unittest.main()
