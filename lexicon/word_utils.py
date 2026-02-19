# -*- coding: utf-8 -*-
from __future__ import annotations

import re
import unicodedata as ud
from typing import Dict, Iterator, Optional

__all__ = ("normalize_word", "iter_dicts", "iter_strings")

_ZERO_WIDTH = ("\ufeff", "\u200b", "\u200c", "\u200d", "\u2060")
_SOFT_HYPHENS = ("\u00ad",)
_WS = re.compile(r"\s+")
_TRAILING_NUM = re.compile(r"\d+$")          # e.g. 단어01 -> 단어
_HANGUL_ONLY = re.compile(r"[^가-힣]+")


def normalize_word(raw: str) -> str:
    s = raw or ""
    for ch in _ZERO_WIDTH + _SOFT_HYPHENS:
        s = s.replace(ch, "")
    s = _WS.sub(" ", s.strip())
    s = ud.normalize("NFC", s)
    s = _TRAILING_NUM.sub("", s)
    s = _HANGUL_ONLY.sub("", s)
    return s


def iter_dicts(value: Optional[object]) -> Iterator[Dict[str, object]]:
    if isinstance(value, dict):
        yield value
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, dict):
                yield entry


def iter_strings(value: Optional[object]) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for entry in value:
            if isinstance(entry, str):
                yield entry
