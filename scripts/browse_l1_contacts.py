#!/usr/bin/env python3
"""交互式浏览并高亮检查 L1 contacts。"""

from __future__ import annotations

import argparse
import cmd
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# ocp_vscode 在当前 cadquery 环境中需要先于 cadquery/OCP 导入，否则可能触发
# pyexpat 动态库符号冲突。只在脚本入口预导入，不影响核心管道。
try:
    import ocp_vscode  # noqa: F401,E402
except Exception:
    ocp_vscode = None  # type: ignore[assignment]

from src.common.data_models import FaceContact  # noqa: E402
from src.visual_inspection.data_loader import (  # noqa: E402
    VisualInspectionError,
    contact_summary,
    load_l1_inspection_data,
)
from src.visual_inspection.ocp_viewer import OcpViewer, ViewerUnavailableError, scene_to_debug_rows  # noqa: E402
from src.visual_inspection.scene_builder import build_l1_contact_scene  # noqa: E402
from src.visual_inspection.selectors import ContactFilter, filter_contacts, sort_contacts  # noqa: E402


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="浏览 L1 contacts 并用 ocp_vscode 高亮")
    parser.add_argument("--step", required=True, help="原始 STEP 文件路径")
    parser.add_argument("--l0", required=True, help="l0_output.json 路径")
    parser.add_argument("--l1", required=True, help="l1_output.json 路径")
    parser.add_argument("--context", choices=["none", "part", "all"], default="part", help="contact 显示上下文")
    parser.add_argument("--type", dest="contact_type", default=None, help="初始 contact_type 过滤")
    parser.add_argument("--needs-exact", action="store_true", help="初始只显示 needs_exact_overlap=true")
    parser.add_argument("--min-confidence", type=float, default=None, help="初始最小 confidence")
    parser.add_argument("--sort", choices=["contact_uid", "confidence", "contact_type"], default="contact_uid", help="排序字段")
    parser.add_argument("--desc", action="store_true", help="降序排序")
    parser.add_argument("--show", help="非交互模式：直接显示指定 contact_uid 或当前列表 index")
    parser.add_argument("--dry-run", action="store_true", help="只打印 scene，不调用 ocp_vscode")
    parser.add_argument("--port", type=int, default=None, help="OCP CAD Viewer 端口")
    return parser.parse_args()


class ContactBrowser(cmd.Cmd):
    """基于标准库 cmd 的 contact 浏览器。"""

    intro = "L1 Contact Browser。输入 help 查看命令，输入 show 0 显示第一条 contact，q 退出。"
    prompt = "l1> "

    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__()
        self.args = args
        self.data = load_l1_inspection_data(args.l0, args.l1, step_file=args.step, restore_faces=True)
        self.viewer = OcpViewer(port=args.port)
        self.criteria = ContactFilter(
            contact_type=args.contact_type,
            needs_exact=True if args.needs_exact else None,
            min_confidence=args.min_confidence,
        )
        self.sort_key = args.sort
        self.descending = bool(args.desc)
        self.contacts = self._current_contacts()
        self.current_index = 0
        print(self._summary())
        if not args.show:
            self.do_list("10")

    def _current_contacts(self) -> list[FaceContact]:
        """返回当前过滤/排序后的 contacts。"""
        return sort_contacts(filter_contacts(self.data, self.criteria), sort_key=self.sort_key, descending=self.descending)

    def _refresh(self) -> None:
        """刷新当前 contact 列表。"""
        self.contacts = self._current_contacts()
        self.current_index = min(self.current_index, max(0, len(self.contacts) - 1))
        print(self._summary())

    def _summary(self) -> str:
        """返回当前过滤摘要。"""
        return f"contacts={len(self.contacts)} type={self.criteria.contact_type or '*'} needs_exact={self.criteria.needs_exact} min_conf={self.criteria.min_confidence}"

    def do_list(self, arg: str) -> None:
        """list [N]：列出前 N 条当前 contacts。"""
        limit = int(arg.strip() or "20")
        if not self.contacts:
            print("当前过滤条件下没有 contacts")
            return
        for index, contact in enumerate(self.contacts[:limit]):
            row = contact_summary(contact, self.data.l0_data.faces_by_uid)
            exact = " needs_exact" if row["needs_exact_overlap"] else ""
            print(
                f"{index:04d} {row['contact_uid']} {row['contact_type']} "
                f"conf={row['confidence']:.2f} parts={row['part_uid_pair']} faces={row['face_uid_pair']}{exact}"
            )

    def do_show(self, arg: str) -> None:
        """show [INDEX_OR_CONTACT_UID]：高亮指定或当前 contact。"""
        value = arg.strip()
        try:
            contact = self._contact_from_arg(value) if value else self._contact_from_arg(str(self.current_index))
            if self.args.context == "all":
                print("提示: --context all 可能在大型模型上较慢。")
            scene = build_l1_contact_scene(self.data, contact.contact_uid, context=self.args.context)
            for row in scene_to_debug_rows(scene):
                print(f"- {row['role']}: {row['name']} color={row['color']} alpha={row['alpha']}")
            if self.args.dry_run:
                return
            result = self.viewer.update_scene(scene, title=contact.contact_uid)
            print(result.message)
        except (VisualInspectionError, ViewerUnavailableError, ValueError) as exc:
            print(f"错误: {exc}")

    def do_j(self, arg: str) -> None:
        """j：移动到下一条 contact 并显示。"""
        self._move(1)

    def do_k(self, arg: str) -> None:
        """k：移动到上一条 contact 并显示。"""
        self._move(-1)

    def do_next(self, arg: str) -> None:
        """next：移动到下一条 contact 并显示。"""
        self._move(1)

    def do_prev(self, arg: str) -> None:
        """prev：移动到上一条 contact 并显示。"""
        self._move(-1)

    def do_search(self, arg: str) -> None:
        """search TEXT：按 contact_uid/part_uid/face_uid/contact_type 搜索。"""
        self.criteria = ContactFilter(
            contact_type=self.criteria.contact_type,
            needs_exact=self.criteria.needs_exact,
            part_uid=self.criteria.part_uid,
            face_uid=self.criteria.face_uid,
            min_confidence=self.criteria.min_confidence,
            query=arg.strip() or None,
        )
        self._refresh()
        self.do_list("10")

    def do_type(self, arg: str) -> None:
        """type TYPE|all：按 contact_type 过滤。"""
        value = arg.strip().lower()
        self.criteria = ContactFilter(
            contact_type=None if value in {"", "all", "*"} else value,
            needs_exact=self.criteria.needs_exact,
            part_uid=self.criteria.part_uid,
            face_uid=self.criteria.face_uid,
            min_confidence=self.criteria.min_confidence,
            query=self.criteria.query,
        )
        self._refresh()
        self.do_list("10")

    def do_exact(self, arg: str) -> None:
        """exact on|off|all：按 needs_exact_overlap 过滤。"""
        value = arg.strip().lower()
        needs_exact = None if value in {"", "all", "*"} else value in {"on", "true", "1", "yes"}
        self.criteria = ContactFilter(
            contact_type=self.criteria.contact_type,
            needs_exact=needs_exact,
            part_uid=self.criteria.part_uid,
            face_uid=self.criteria.face_uid,
            min_confidence=self.criteria.min_confidence,
            query=self.criteria.query,
        )
        self._refresh()
        self.do_list("10")

    def do_conf(self, arg: str) -> None:
        """conf VALUE|all：设置最小 confidence。"""
        value = arg.strip().lower()
        min_confidence = None if value in {"", "all", "*"} else float(value)
        self.criteria = ContactFilter(
            contact_type=self.criteria.contact_type,
            needs_exact=self.criteria.needs_exact,
            part_uid=self.criteria.part_uid,
            face_uid=self.criteria.face_uid,
            min_confidence=min_confidence,
            query=self.criteria.query,
        )
        self._refresh()
        self.do_list("10")

    def do_part(self, arg: str) -> None:
        """part PART_UID|all：按参与 Part 过滤。"""
        value = arg.strip()
        self.criteria = ContactFilter(
            contact_type=self.criteria.contact_type,
            needs_exact=self.criteria.needs_exact,
            part_uid=None if value in {"", "all", "*"} else value,
            face_uid=self.criteria.face_uid,
            min_confidence=self.criteria.min_confidence,
            query=self.criteria.query,
        )
        self._refresh()
        self.do_list("10")

    def do_face(self, arg: str) -> None:
        """face FACE_UID|all：按参与 face 过滤。"""
        value = arg.strip()
        self.criteria = ContactFilter(
            contact_type=self.criteria.contact_type,
            needs_exact=self.criteria.needs_exact,
            part_uid=self.criteria.part_uid,
            face_uid=None if value in {"", "all", "*"} else value,
            min_confidence=self.criteria.min_confidence,
            query=self.criteria.query,
        )
        self._refresh()
        self.do_list("10")

    def do_q(self, arg: str) -> bool:
        """q：退出。"""
        return True

    def do_quit(self, arg: str) -> bool:
        """quit：退出。"""
        return True

    def _contact_from_arg(self, value: str) -> FaceContact:
        """从列表 index 或 contact_uid 取得 contact。"""
        if value.isdigit():
            index = int(value)
            try:
                contact = self.contacts[index]
            except IndexError as exc:
                raise ValueError(f"列表 index 越界: {index}") from exc
            self.current_index = index
            return contact
        try:
            contact = self.data.contacts_by_uid[value]
        except KeyError as exc:
            raise VisualInspectionError(f"未找到 contact_uid: {value}") from exc
        for index, candidate in enumerate(self.contacts):
            if candidate.contact_uid == value:
                self.current_index = index
                break
        return contact

    def _move(self, delta: int) -> None:
        """移动当前列表位置并显示 contact。"""
        if not self.contacts:
            print("当前过滤条件下没有 contacts")
            return
        self.current_index = max(0, min(len(self.contacts) - 1, self.current_index + delta))
        self.do_show(str(self.current_index))


def main() -> int:
    """CLI 主入口。"""
    args = parse_args()
    try:
        browser = ContactBrowser(args)
        if args.show:
            browser.do_show(args.show)
        else:
            browser.cmdloop()
        return 0
    except VisualInspectionError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
