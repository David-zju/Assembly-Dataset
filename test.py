#!/usr/bin/env python3
"""
穷举编码转换链,寻找能把乱码字节还原成正常中文的路径
"""
import itertools

# 要测试的目标字节(从 STEP 文件中提取)
# 这个就是你之前看到的 "鏈" 对应的字节
TEST_CASES = [
    bytes.fromhex("e9 8f 88".replace(" ", "")),       # 你新文件中的字节
    # 也可以加更多用例:
    # bytes.fromhex("e9 96 ba".replace(" ", "")),     # "閺"
]

# 候选编码池
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


def is_likely_chinese(s: str) -> tuple[bool, float, str]:
    """
    判断字符串是否像正常中文
    返回 (是否像中文, 评分, 原因)
    评分越高越像合理的零件名
    """
    if not s:
        return False, 0, "empty"
    if '\ufffd' in s:
        return False, 0, "contains U+FFFD"
    
    # 统计各类字符
    cjk_common = 0       # 常用 CJK (U+4E00-U+9FFF)
    cjk_ext = 0          # 扩展 CJK
    ascii_alnum = 0      # ASCII 字母数字
    ascii_punct = 0      # ASCII 标点
    weird = 0            # 控制字符、罕见 Unicode
    
    for c in s:
        cp = ord(c)
        if 0x4E00 <= cp <= 0x9FFF:
            cjk_common += 1
        elif 0x3400 <= cp <= 0x4DBF or 0x20000 <= cp <= 0x2A6DF:
            cjk_ext += 1
        elif c.isalnum() and cp < 128:
            ascii_alnum += 1
        elif cp < 128 and c in ' .-_()[]':
            ascii_punct += 1
        elif cp < 0x20 or (0x7F <= cp < 0xA0):
            weird += 10  # 控制字符严重扣分
        elif cp > 0xFFFF:
            weird += 5
        else:
            # 其他 Unicode 字符,可能是奇怪符号
            weird += 1
    
    total = len(s)
    if total == 0:
        return False, 0, "empty"
    
    # 评分逻辑
    score = 0.0
    if cjk_common > 0:
        score += cjk_common * 10
    if cjk_ext > 0:
        score += cjk_ext * 3  # 扩展 CJK 是罕见字,降低权重
    score += ascii_alnum * 5
    score += ascii_punct * 1
    score -= weird * 5
    
    # 必须主要由 CJK 或 ASCII 字母数字组成
    valid_ratio = (cjk_common + cjk_ext + ascii_alnum + ascii_punct) / total
    if valid_ratio < 0.8:
        return False, score, f"too many weird chars (ratio={valid_ratio:.2f})"
    
    is_likely = (cjk_common > 0 or ascii_alnum > 0) and weird == 0
    
    reason = f"CJK={cjk_common}, CJK_ext={cjk_ext}, alnum={ascii_alnum}, weird={weird}"
    return is_likely, score, reason


def try_chain(data: bytes, chain: list[str]) -> str | None:
    """
    按编码链交替 decode/encode 转换
    chain 长度必须为奇数: decode, encode, decode, encode, decode, ...
    第 1 个是 decode,第 2 个 encode,以此类推
    最终结果是最后一个 decode 的输出
    """
    try:
        result = data.decode(chain[0], errors='strict')
        for i in range(1, len(chain)):
            if i % 2 == 1:  # encode
                result = result.encode(chain[i], errors='strict')
            else:  # decode
                result = result.decode(chain[i], errors='strict')
        return result
    except (UnicodeDecodeError, UnicodeEncodeError, LookupError):
        return None


def exhaustive_search(data: bytes, max_depth: int = 3):
    """
    穷举所有 1/2/3 重编码链
    单重: decode(enc)
    双重: decode(enc1) -> encode(enc2) -> decode(enc3)  
    三重: decode -> encode -> decode -> encode -> decode
    """
    print(f"\n{'='*70}")
    print(f"目标字节: {data.hex(' ')}")
    print(f"{'='*70}")
    
    candidates = []  # (score, depth, chain, result)
    
    # 单重 (depth=1):一次 decode
    for enc in ENCODINGS:
        result = try_chain(data, [enc])
        if result is None:
            continue
        is_likely, score, reason = is_likely_chinese(result)
        candidates.append((score, 1, [enc], result, is_likely, reason))
    
    # 双重 (depth=2):decode -> encode -> decode
    if max_depth >= 2:
        for e1, e2, e3 in itertools.product(ENCODINGS, repeat=3):
            if e1 == e3 and e1 == e2:
                continue  # 跳过完全平凡的
            result = try_chain(data, [e1, e2, e3])
            if result is None:
                continue
            is_likely, score, reason = is_likely_chinese(result)
            # 只保留高质量结果
            if score > 0:
                candidates.append((score, 2, [e1, e2, e3], result, is_likely, reason))
    
    # 三重 (depth=3):decode -> encode -> decode -> encode -> decode
    if max_depth >= 3:
        for e1, e2, e3, e4, e5 in itertools.product(ENCODINGS, repeat=5):
            result = try_chain(data, [e1, e2, e3, e4, e5])
            if result is None:
                continue
            is_likely, score, reason = is_likely_chinese(result)
            if score >= 10:  # 三重链太多,只保留较高分的
                candidates.append((score, 3, [e1, e2, e3, e4, e5], result, is_likely, reason))
    
    # 按评分排序
    candidates.sort(key=lambda x: (-x[0], x[1]))
    
    # 去重(相同 result 的只保留最短链)
    seen = {}
    for cand in candidates:
        score, depth, chain, result, is_likely, reason = cand
        if result not in seen or seen[result][1] > depth:
            seen[result] = cand
    
    unique = sorted(seen.values(), key=lambda x: (-x[0], x[1]))
    
    # 打印结果
    print(f"\n找到 {len(unique)} 个唯一结果\n")
    
    # 高质量结果(评分 >= 10)
    high_quality = [c for c in unique if c[0] >= 10]
    print(f"\n--- 高质量候选 (评分 >= 10) ---")
    if not high_quality:
        print("  (无)")
    for score, depth, chain, result, is_likely, reason in high_quality[:30]:
        chain_str = " -> ".join(chain)
        marker = "✓ LIKELY" if is_likely else " "
        print(f"\n  [{marker}] score={score:.1f}, depth={depth}")
        print(f"    Chain:  {chain_str}")
        print(f"    Result: {result!r}")
        print(f"    Reason: {reason}")
    
    # 中等质量
    medium = [c for c in unique if 0 < c[0] < 10]
    print(f"\n\n--- 中等质量候选 (0 < 评分 < 10) ---")
    for score, depth, chain, result, is_likely, reason in medium[:15]:
        chain_str = " -> ".join(chain)
        print(f"  score={score:.1f}, depth={depth}, chain={chain_str}, result={result!r}")
    
    return unique


def main():
    for data in TEST_CASES:
        exhaustive_search(data, max_depth=3)


if __name__ == "__main__":
    main()