"""全局 UID 生成器。"""

from __future__ import annotations

from dataclasses import dataclass, field

from .exceptions import UIDError


@dataclass(slots=True)
class UIDManager:
    """按项目格式生成不可重复 UID。

    Example:
        >>> uids = UIDManager()
        >>> uids.next_part_uid()
        'p-0001'
        >>> uids.next_face_uid(1)
        'f-0001-00001'
    """

    part_seq: int = 0
    contact_seq: int = 0
    _seen: set[str] = field(default_factory=set)

    def _register(self, uid: str) -> str:
        """登记并返回 UID，若重复则抛出 UIDError。"""
        if uid in self._seen:
            raise UIDError(f"UID 重复: {uid}")
        self._seen.add(uid)
        return uid

    def next_part_uid(self) -> str:
        """生成 part_uid，格式 p-0001。"""
        self.part_seq += 1
        return self._register(f"p-{self.part_seq:04d}")

    def face_uid(self, part_seq: int, face_seq: int) -> str:
        """生成指定 part/face 序号的 face_uid。

        Args:
            part_seq: Part 序号，从 1 开始。
            face_seq: Part 内 face 序号，从 1 开始。
        """
        if part_seq <= 0 or face_seq <= 0:
            raise UIDError("part_seq 和 face_seq 必须从 1 开始")
        return self._register(f"f-{part_seq:04d}-{face_seq:05d}")

    def next_face_uid(self, part_seq: int, face_seq: int) -> str:
        """生成 face_uid 的兼容入口。"""
        return self.face_uid(part_seq, face_seq)

    def next_contact_uid(self) -> str:
        """生成 contact_uid，格式 c-000001。"""
        self.contact_seq += 1
        return self._register(f"c-{self.contact_seq:06d}")

    def register_existing(self, uid: str) -> None:
        """登记外部恢复出的 UID，防止后续生成重复。"""
        self._register(uid)

