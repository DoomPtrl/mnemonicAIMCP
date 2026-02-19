# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Dict, Iterable, Iterator, List, Optional

from .word_utils import iter_dicts, iter_strings, normalize_word

__all__ = ("extract_headwords_from_file",)


def _variant_words(info: Dict[str, object]) -> Iterator[str]:
    # relation/lexical related headwords
    for key in ("relation_info", "lexical_info"):
        for entry in iter_dicts(info.get(key)):
            word = entry.get("word")
            if isinstance(word, str):
                norm = normalize_word(word)
                if norm:
                    yield norm
    # pronunciation_info[*].allomorph – comma-separated variants
    for pronunciation in iter_dicts(info.get("pronunciation_info")):
        for token in iter_strings(pronunciation.get("allomorph")):
            for part in token.split(","):
                norm = normalize_word(part)
                if norm:
                    yield norm


def extract_headwords_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    channel = payload.get("channel")
    if not isinstance(channel, dict):
        return []

    items = channel.get("item")
    if isinstance(items, dict):
        iterable: Iterable[object] = [items]
    elif isinstance(items, list):
        iterable = items
    else:
        return []

    out: List[str] = []
    seen: set[str] = set()

    for item in iterable:
        if not isinstance(item, dict):
            continue
        info = item.get("word_info")
        if not isinstance(info, dict):
            continue

        candidates: List[str] = []
        base = info.get("word")
        if isinstance(base, str):
            base = normalize_word(base)
            if base:
                candidates.append(base)

        candidates.extend(_variant_words(info))

        for word in candidates:
            if word and word not in seen:
                seen.add(word)
                out.append(word)

    return out
