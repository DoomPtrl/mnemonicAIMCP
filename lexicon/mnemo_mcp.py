# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import pickle
import unicodedata as ud
from collections import Counter
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from fastmcp import FastMCP
except Exception:  # pragma: no cover - FastMCP optional for library usage
    FastMCP = None

from lexicon.trie import Trie

HERE = os.path.dirname(__file__)
CANDIDATE_TRIE_PATHS = [
    os.path.join(HERE, "artifacts", "trie.pkl"),
    os.path.join(HERE, "..", "artifacts", "trie.pkl"),
]
TRIE_PATH = next((p for p in CANDIDATE_TRIE_PATHS if os.path.exists(p)), None)
if TRIE_PATH is None:
    raise SystemExit("Missing artifacts/trie.pkl. Run: python -m lexicon.build_lexicon")

with open(TRIE_PATH, "rb") as f:
    KOREAN_LEXICON_TRIE: Trie = pickle.load(f)

SEGMENT_PENALTY = 0.2  # mild penalty per segment to prefer compact combinations


@dataclass
class InitialCombo:
    combo: str
    words: List[str]
    word_sources: List[List[str]]
    word_scores: List[float]
    coverage: List[str]
    mode: str  # "sequence" or "bag"
    score: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "combo": self.combo,
            "words": self.words,
            "word_sources": self.word_sources,
            "word_scores": self.word_scores,
            "coverage": self.coverage,
            "mode": self.mode,
            "score": self.score,
        }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def score_word(word: str) -> float:
    info = KOREAN_LEXICON_TRIE.get_word_info(word)
    base = info["score"] if info else 0.0
    length_bonus = 0.3 * max(0, len(word) - 1)
    return base + length_bonus


def score_prefix_hint(prefix: str) -> float:
    iterator = KOREAN_LEXICON_TRIE.iter_words_with_prefix(prefix, limit=1, with_metadata=True)
    top = next(iterator, None)
    score = top["score"] if isinstance(top, dict) else 0.0
    return 0.1 * len(prefix) + 0.2 * score


def prune_to_beam(frontier: List[Tuple[float, tuple]], k: int) -> List[Tuple[float, tuple]]:
    frontier.sort(key=lambda x: x[0], reverse=True)
    return frontier[:k]


def canonicalise_words(words: Tuple[str, ...], keep_order: bool) -> Tuple[str, ...]:
    if keep_order:
        return words
    return tuple(sorted(words, key=lambda w: (-len(w), w)))


def combination_sort_key(combo: Dict[str, Any]) -> Tuple:
    words = combo["words"]
    multi = sum(1 for w in words if len(w) > 1)
    singles = len(words) - multi
    length_sum = sum(len(w) for w in words)
    return (
        -multi,
        singles,
        len(words),
        -combo.get("score", 0.0),
        -length_sum,
        combo.get("combo", ""),
    )


# ---------------------------------------------------------------------------
# Lexicon utilities exposed as MCP tools
# ---------------------------------------------------------------------------

def lexicon_words_starting_with(letter: str, limit: int = 50, with_metadata: bool = False) -> List[Any]:
    if not letter or len(letter) != 1:
        return []
    return list(
        KOREAN_LEXICON_TRIE.iter_words_with_prefix(letter, limit=limit, with_metadata=with_metadata)
    )


def lexicon_check_word(word: str) -> Dict[str, Any]:
    info = KOREAN_LEXICON_TRIE.get_word_info(word)
    return {
        "is_word": bool(info),
        "has_prefix": KOREAN_LEXICON_TRIE.has_word_with_prefix(word),
        "sources": sorted(info["sources"]) if info else [],
        "score": info["score"] if info else 0.0,
    }


# ---------------------------------------------------------------------------
# Combination search
# ---------------------------------------------------------------------------

def generate_initial_combos(
    initials: List[str],
    *,
    beam_width: int = 64,
    max_candidates: int = 20,
    keep_order: bool = True,
    trace: bool = False,
) -> List[Dict[str, object]] | Tuple[List[Dict[str, object]], List[Dict[str, Any]]]:
    """Build 두문자 조합 (initial-letter word combinations) from the provided initials.

    Each initial must be used exactly once. Segments must be valid dictionary words in the
    lexicon trie. The search prefers fewer/longer words. Set ``keep_order=False`` to allow
    bag-mode (any ordering). If ``trace=True`` the trace log is returned alongside results.
    """

    initials_counter = Counter(initials)
    frontier: List[Tuple[float, tuple]] = [(0.0, (tuple(sorted(initials_counter.items())), "", tuple()))]
    results: List[InitialCombo] = []
    trace_log: List[Dict[str, Any]] | None = [] if trace else None

    while frontier and len(results) < max_candidates:
        score, (remaining_tuple, current_prefix, words_so_far) = frontier.pop(0)
        remaining_counter = Counter(dict(remaining_tuple))

        if trace_log is not None:
            trace_log.append(
                {
                    "event": "pop",
                    "score": score,
                    "prefix": current_prefix,
                    "words": list(words_so_far),
                    "remaining": dict(remaining_counter),
                    "frontier_size": len(frontier),
                }
            )

        if not remaining_counter:
            if not current_prefix or KOREAN_LEXICON_TRIE.contains(current_prefix):
                completed_words = words_so_far + ((current_prefix,) if current_prefix else tuple())
                canonical_words = canonicalise_words(completed_words, keep_order)
                combo_text = "".join(canonical_words)
                word_infos = [KOREAN_LEXICON_TRIE.get_word_info(w) for w in canonical_words]
                sources = [sorted(info["sources"]) if info else [] for info in word_infos]
                scores = [score_word(w) for w in canonical_words]
                combo_score = sum(scores) - SEGMENT_PENALTY * len(canonical_words)
                mode = "sequence" if keep_order else "bag"
                coverage = list(initials)
                results.append(
                    InitialCombo(
                        combo=combo_text,
                        words=list(canonical_words),
                        word_sources=sources,
                        word_scores=scores,
                        coverage=coverage,
                        mode=mode,
                        score=combo_score,
                    )
                )
                if trace_log is not None:
                    trace_log.append(
                        {
                            "event": "result",
                            "combo": combo_text,
                            "words": list(canonical_words),
                            "word_scores": scores,
                            "score": combo_score,
                        }
                    )
            continue

        if current_prefix and KOREAN_LEXICON_TRIE.contains(current_prefix):
            can_extend = any(KOREAN_LEXICON_TRIE.has_word_with_prefix(current_prefix + nxt) for nxt in remaining_counter)
            if len(current_prefix) == 1 and can_extend:
                pass
            else:
                next_score = score + score_word(current_prefix)
                next_state = (
                    tuple(sorted(remaining_counter.items())),
                    "",
                    words_so_far + (current_prefix,),
                )
                frontier.append((next_score, next_state))
                if trace_log is not None:
                    trace_log.append(
                        {
                            "event": "commit",
                            "word": current_prefix,
                            "words": list(words_so_far + (current_prefix,)),
                            "score": next_score,
                            "remaining": dict(remaining_counter),
                        }
                    )

        for letter, _ in list(remaining_counter.items()):
            next_prefix = current_prefix + letter
            if not KOREAN_LEXICON_TRIE.has_word_with_prefix(next_prefix):
                continue
            remaining_copy = remaining_counter.copy()
            remaining_copy[letter] -= 1
            if remaining_copy[letter] == 0:
                del remaining_copy[letter]
            next_score = score + score_prefix_hint(next_prefix)
            next_state = (
                tuple(sorted(remaining_copy.items())),
                next_prefix,
                words_so_far,
            )
            frontier.append((next_score, next_state))
            if trace_log is not None:
                trace_log.append(
                    {
                        "event": "extend",
                        "letter": letter,
                        "next_prefix": next_prefix,
                        "score": next_score,
                        "remaining": dict(remaining_copy),
                    }
                )

        frontier = prune_to_beam(frontier, beam_width)
        if trace_log is not None:
            trace_log.append(
                {
                    "event": "prune",
                    "frontier_size": len(frontier),
                }
            )

    deduped: Dict[Tuple[str, ...], InitialCombo] = {}
    for combo in results:
        key = tuple(combo.words)
        existing = deduped.get(key)
        if existing is None or combo.score > existing.score:
            deduped[key] = combo

    ordered = sorted((c.as_dict() for c in deduped.values()), key=combination_sort_key)

    if trace_log is not None:
        trace_log.append({"event": "complete", "result_count": len(ordered)})
        return ordered, trace_log
    return ordered


# ---------------------------------------------------------------------------
# Initial extraction helpers
# ---------------------------------------------------------------------------

def initials_from_words(words: Iterable[str]) -> List[str]:
    initials: List[str] = []
    for word in words:
        s = ud.normalize("NFC", (word or "").strip())
        if len(s) == 1 and "가" <= s <= "힣":
            initials.append(s)
            continue
        for ch in s:
            if "가" <= ch <= "힣":
                initials.append(ch)
                break
    return initials


# ---------------------------------------------------------------------------
# MCP tool surface (optional)
# ---------------------------------------------------------------------------

if FastMCP is not None:
    mcp = FastMCP("initial-combos")

    @mcp.tool("initial_combos.suggest")
    async def initial_combos_suggest(
        initials: list[str],
        beam_width: int = 64,
        max_candidates: int = 20,
        keep_order: bool = True,
    ) -> list[dict]:
        """Return ranked 두문자 조합 from a list of initials. Does not generate a phrase."""
        return generate_initial_combos(
            initials,
            beam_width=beam_width,
            max_candidates=max_candidates,
            keep_order=keep_order,
            trace=False,
        )

    @mcp.tool("initial_combos.from_words")
    async def initial_combos_from_words(
        words: list[str],
        beam_width: int = 64,
        max_candidates: int = 20,
        keep_order: bool = True,
    ) -> list[dict]:
        """Extract first Hangul syllable of each word, then delegate to initial_combos.suggest."""
        initials = initials_from_words(words)
        return generate_initial_combos(
            initials,
            beam_width=beam_width,
            max_candidates=max_candidates,
            keep_order=keep_order,
            trace=False,
        )

    @mcp.tool("lexicon.check_word")
    async def lexicon_check(word: str) -> dict:
        """Look up a word in the offline lexicon and return dictionary metadata."""
        return lexicon_check_word(word)

    @mcp.tool("lexicon.words_starting_with")
    async def lexicon_words(letter: str, limit: int = 50, with_metadata: bool = False) -> list[Any]:
        """Yield words beginning with the provided letter (optionally including metadata)."""
        return lexicon_words_starting_with(letter, limit=limit, with_metadata=with_metadata)

else:
    mcp = None  # type: ignore


# ---------------------------------------------------------------------------
# CLI entry point helper
# ---------------------------------------------------------------------------

def main() -> None:
    if FastMCP is None or mcp is None:
        raise SystemExit("fastmcp is not installed. Install fastmcp to run the MCP server.")

    transport = os.environ.get("MCP_TRANSPORT", "stdio").lower()
    if transport == "http":
        host = os.environ.get("MCP_HOST", "0.0.0.0")
        port = int(os.environ.get("MCP_PORT", "8000"))
        path = os.environ.get("MCP_PATH", "/mcp")
        mcp.run(transport="http", host=host, port=port, path=path)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
