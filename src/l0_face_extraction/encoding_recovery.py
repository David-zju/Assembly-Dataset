"""零件名称编码恢复工具。

本模块复用根目录 `test.py` 中的编码链穷举思路，尝试把 STEP 文件中常见的
中文乱码名称恢复为可读文本。恢复失败时，调用方可以使用稳定的
`unnamed_part_<index>` 兜底名称。
"""

from __future__ import annotations

import itertools

ENCODINGS = [
    "utf-8",
    "gbk",
    "gb18030",
    "gb2312",
    "big5",
    "cp936",
    "cp950",
    "cp932",
    "shift_jis",
    "euc-jp",
    "euc-kr",
    "latin-1",
    "cp1252",
    "utf-16-le",
    "utf-16-be",
]


def is_likely_chinese_or_ascii(text: str) -> tuple[bool, float, str]:
    """判断字符串是否像正常中文或 ASCII 零件名。

    Args:
        text: 待评分的字符串。

    Returns:
        tuple[bool, float, str]: 是否可信、评分、评分原因。
    """
    if not text:
        return False, 0.0, "empty"
    if "\ufffd" in text:
        return False, 0.0, "contains U+FFFD"

    cjk_common = 0
    cjk_ext = 0
    ascii_alnum = 0
    ascii_punct = 0
    weird = 0

    for char in text:
        cp = ord(char)
        if 0x4E00 <= cp <= 0x9FFF:
            cjk_common += 1
        elif 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF:
            cjk_ext += 1
        elif char.isalnum() and cp < 128:
            ascii_alnum += 1
        elif cp < 128 and char in " .-_()[]#/":
            ascii_punct += 1
        elif cp < 0x20 or (0x7F <= cp < 0xA0):
            weird += 10
        elif cp > 0xFFFF:
            weird += 5
        else:
            weird += 1

    total = len(text)
    valid_ratio = (cjk_common + cjk_ext + ascii_alnum + ascii_punct) / total
    score = cjk_common * 10.0 + cjk_ext * 3.0 + ascii_alnum * 5.0 + ascii_punct - weird * 5.0
    if valid_ratio < 0.8:
        return False, score, f"too many weird chars (ratio={valid_ratio:.2f})"

    likely = (cjk_common > 0 or ascii_alnum > 0) and weird == 0
    return likely, score, f"CJK={cjk_common}, CJK_ext={cjk_ext}, alnum={ascii_alnum}, weird={weird}"


def _try_chain(data: bytes, chain: list[str]) -> str | None:
    """按 decode/encode/decode 交替链尝试恢复文本。"""
    try:
        result: str | bytes = data.decode(chain[0], errors="strict")
        for index in range(1, len(chain)):
            if index % 2 == 1:
                result = str(result).encode(chain[index], errors="strict")
            else:
                if not isinstance(result, bytes):
                    return None
                result = result.decode(chain[index], errors="strict")
        return result if isinstance(result, str) else None
    except (UnicodeDecodeError, UnicodeEncodeError, LookupError):
        return None


def _candidate_byte_sources(text: str) -> list[bytes]:
    """从乱码字符串构造可能的原始字节序列。"""
    sources: list[bytes] = []
    for encoding in ENCODINGS:
        try:
            data = text.encode(encoding, errors="strict")
        except UnicodeEncodeError:
            continue
        if data not in sources:
            sources.append(data)
    return sources


def recover_part_name(name: str | None, index: int, *, max_depth: int = 2) -> str:
    """恢复零件名，失败时返回 `unnamed_part_<index>`。

    Args:
        name: CadQuery/OCP 读出的原始零件名。
        index: 当前 Part 的 1-based 序号，用于兜底命名。
        max_depth: 编码链最大深度，默认只做单重和双重搜索以控制开销。

    Returns:
        str: 恢复后的稳定 Part 名称。
    """
    fallback = f"unnamed_part_{index}"
    text = (name or "").strip()
    if not text:
        return fallback

    likely, base_score, _reason = is_likely_chinese_or_ascii(text)
    if likely:
        return text

    candidates: list[tuple[float, int, str]] = []
    for data in _candidate_byte_sources(text):
        for encoding in ENCODINGS:
            result = _try_chain(data, [encoding])
            if result is None:
                continue
            recovered_likely, score, _ = is_likely_chinese_or_ascii(result)
            if recovered_likely and score > base_score:
                candidates.append((score, 1, result))

        if max_depth >= 2:
            for e1, e2, e3 in itertools.product(ENCODINGS, repeat=3):
                if e1 == e2 == e3:
                    continue
                result = _try_chain(data, [e1, e2, e3])
                if result is None:
                    continue
                recovered_likely, score, _ = is_likely_chinese_or_ascii(result)
                if recovered_likely and score > base_score:
                    candidates.append((score, 2, result))

    if not candidates:
        return fallback

    candidates.sort(key=lambda item: (-item[0], item[1], len(item[2])))
    return candidates[0][2].strip() or fallback
