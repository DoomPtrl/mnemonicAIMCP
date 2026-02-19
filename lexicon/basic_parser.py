# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from typing import Dict, Iterable, List, Optional, Set

from .word_utils import normalize_word

__all__ = ("extract_words_from_file",)


def extract_words_from_file(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    lexicon_section = payload.get("LexicalResource", {}).get("Lexicon")
    lexicons: List[dict]
    if isinstance(lexicon_section, list):
        lexicons = [lex for lex in lexicon_section if isinstance(lex, dict)]
    elif isinstance(lexicon_section, dict):
        lexicons = [lexicon_section]
    else:
        return []

    words: List[str] = []
    seen: Set[str] = set()

    for lexicon in lexicons:
        entries = lexicon.get("LexicalEntry")
        if isinstance(entries, dict):
            iterable: Iterable[dict] = [entries]
        elif isinstance(entries, list):
            iterable = [entry for entry in entries if isinstance(entry, dict)]
        else:
            continue

        for entry in iterable:
            norm = _extract_written_form(entry)
            if norm and norm not in seen:
                seen.add(norm)
                words.append(norm)

    return words


def _extract_written_form(entry: Dict[str, object]) -> Optional[str]:
    lemma = entry.get("Lemma")
    if isinstance(lemma, dict):
        # Primary pattern: feat {"att": "writtenForm", "val": "..."}
        feat = lemma.get("feat")
        value = _resolve_feat_value(feat)
        if value:
            return normalize_word(value)

        # Some entries may store written form in FormRepresentation
        form_rep = lemma.get("FormRepresentation")
        if isinstance(form_rep, dict):
            value = _resolve_feat_value(form_rep.get("feat"))
            if value:
                return normalize_word(value)
        elif isinstance(form_rep, list):
            for item in form_rep:
                if isinstance(item, dict):
                    value = _resolve_feat_value(item.get("feat"))
                    if value:
                        return normalize_word(value)
    return None


def _resolve_feat_value(feat: object) -> Optional[str]:
    if isinstance(feat, dict):
        if feat.get("att") == "writtenForm":
            return feat.get("val")
    elif isinstance(feat, list):
        for item in feat:
            if isinstance(item, dict) and item.get("att") == "writtenForm":
                return item.get("val")
    return None
