# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Iterable, List, Set

from .word_utils import normalize_word

__all__ = ("extract_words_from_file",)


def _iter_items(payload: dict) -> Iterable[dict]:
    channel = payload.get("channel")
    if not isinstance(channel, dict):
        return []
    items = channel.get("item")
    if isinstance(items, dict):
        return [items]
    if isinstance(items, list):
        return items
    return []


def extract_words_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    seen: Set[str] = set()
    words: List[str] = []

    for item in _iter_items(payload):
        wordinfo = item.get("wordinfo")
        if not isinstance(wordinfo, dict):
            continue

        base = wordinfo.get("word")
        if isinstance(base, str):
            norm = normalize_word(base)
            if norm and norm not in seen:
                seen.add(norm)
                words.append(norm)

        # Some entries store variants in pronunciation_info[*].allomorph
        for pron in _iter_pronunciation_variants(wordinfo):
            if pron not in seen:
                seen.add(pron)
                words.append(pron)

    return words


def _iter_pronunciation_variants(wordinfo: dict) -> Iterable[str]:
    pronunciations = wordinfo.get("pronunciation_info")
    if isinstance(pronunciations, list):
        for entry in pronunciations:
            if not isinstance(entry, dict):
                continue
            token = entry.get("allomorph")
            if isinstance(token, str):
                for part in token.split(","):
                    norm = normalize_word(part)
                    if norm:
                        yield norm
    elif isinstance(pronunciations, dict):
        token = pronunciations.get("allomorph")
        if isinstance(token, str):
            for part in token.split(","):
                norm = normalize_word(part)
                if norm:
                    yield norm
