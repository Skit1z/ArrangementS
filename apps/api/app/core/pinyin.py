"""姓名 -> 拼音首字母小写，用于生成初始密码。

规则（见方案 3.2）：
- 使用稳定的中文拼音库生成首字母。
- 非中文字符保留字母并转小写。
- 空格、点号、连字符从缩写中移除。
"""
from __future__ import annotations

import re

from pypinyin import Style, lazy_pinyin

_STRIP = re.compile(r"[\s.\-·]+")


def pinyin_initials(full_name: str) -> str:
    if not full_name:
        return ""
    cleaned = _STRIP.sub("", full_name)
    initials: list[str] = []
    for token in lazy_pinyin(cleaned, style=Style.FIRST_LETTER, errors="default"):
        for ch in token:
            if ch.isalpha():
                initials.append(ch.lower())
                break
    return "".join(initials)


def build_initial_password(student_no: str, full_name: str) -> str:
    return f"{student_no.strip()}{pinyin_initials(full_name)}"
