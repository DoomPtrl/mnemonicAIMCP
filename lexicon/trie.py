# -*- coding: utf-8 -*-
from __future__ import annotations

import heapq
from typing import Dict, Iterable, Iterator, List, Optional, Set, Tuple

__all__ = ("Trie",)


class Trie:
    class _Node:
        __slots__ = ("children", "terminal", "sources", "base_score")

        def __init__(self) -> None:
            self.children: Dict[str, Trie._Node] = {}
            self.terminal: bool = False
            self.sources: Set[str] = set()
            self.base_score: float = 0.0

    DEFAULT_SOURCE_WEIGHTS: Dict[str, float] = {}

    def __init__(self, source_weights: Optional[Dict[str, float]] = None) -> None:
        self._root = Trie._Node()
        self._size = 0
        self._source_weights: Dict[str, float] = dict(source_weights or self.DEFAULT_SOURCE_WEIGHTS)

    # ------------------------------------------------------------------ #
    # Mutation helpers
    # ------------------------------------------------------------------ #

    def _source_weight(self, source: str) -> float:
        return self._source_weights.get(source, 0.0)

    def insert(self, word: str, sources: Iterable[str]) -> None:
        if not word:
            return
        node = self._root
        for ch in word:
            node = node.children.setdefault(ch, Trie._Node())
        if not node.terminal:
            node.terminal = True
            self._size += 1

        incoming = set(sources)
        if incoming:
            node.sources.update(incoming)
            node.base_score = max([node.base_score, *[self._source_weight(s) for s in incoming]])

    # ------------------------------------------------------------------ #
    # Query helpers
    # ------------------------------------------------------------------ #

    def __contains__(self, word: str) -> bool:
        return self.contains(word)

    def contains(self, word: str) -> bool:
        node = self._root
        for ch in word:
            node = node.children.get(ch)
            if node is None:
                return False
        return node.terminal

    def __len__(self) -> int:
        return self._size

    def has_prefix(self, prefix: str) -> bool:
        node = self._root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return False
        return True

    def get_word_info(self, word: str) -> Optional[Dict[str, object]]:
        node = self._root
        for ch in word:
            node = node.children.get(ch)
            if node is None:
                return None
        if not node.terminal:
            return None
        return {
            "word": word,
            "sources": set(node.sources),
            "score": node.base_score,
        }

    # Backwards compat shims
    def lookup(self, word: str) -> Optional[Dict[str, object]]:
        return self.get_word_info(word)

    def has_prefix(self, prefix: str) -> bool:
        return self.has_word_with_prefix(prefix)

    def iter_with_prefix(
        self,
        prefix: str,
        limit: Optional[int] = None,
        with_metadata: bool = False,
    ) -> Iterator[object]:
        return self.iter_words_with_prefix(prefix, limit=limit, with_metadata=with_metadata)

    def has_word_with_prefix(self, prefix: str) -> bool:
        node = self._root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return False
        return True

    def iter_words_with_prefix(
        self,
        prefix: str,
        limit: Optional[int] = None,
        with_metadata: bool = False,
    ) -> Iterator[object]:
        if limit is not None and limit <= 0:
            return iter(())

        node = self._root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return iter(())

        results: List[Tuple[float, str, Tuple[str, ...]]] = []
        heap: List[Tuple[float, str, Tuple[str, ...]]] = []
        use_heap = limit is not None

        def push(score: float, word: str, sources: Set[str]) -> None:
            entry = (score, word, tuple(sorted(sources)))
            if not use_heap:
                results.append(entry)
                return
            if len(heap) < (limit or 0):
                heapq.heappush(heap, entry)
                return
            worst_score, worst_word, _ = heap[0]
            if entry[0] > worst_score or (entry[0] == worst_score and entry[1] < worst_word):
                heapq.heapreplace(heap, entry)

        def gather(current: Trie._Node, path: str) -> None:
            if current.terminal:
                push(current.base_score, path, current.sources)
            for ch, child in current.children.items():
                gather(child, path + ch)

        gather(node, prefix)
        collected = heap if use_heap else results
        collected.sort(key=lambda item: (-item[0], item[1]))

        def generator() -> Iterator[object]:
            for score, word, sources in collected:
                if with_metadata:
                    yield {"word": word, "sources": list(sources), "score": score}
                else:
                    yield word

        return generator()
