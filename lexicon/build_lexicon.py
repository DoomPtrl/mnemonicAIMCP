# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import gzip
import json
import os
import pickle
import re
from dataclasses import dataclass, field
from glob import glob
from typing import Callable, Dict, Iterable, List, Optional, Set

from .basic_parser import extract_words_from_file as extract_basic_words
from .stdict_parser import extract_headwords_from_file as extract_stdict_words
from .trie import Trie
from .urimal_parser import extract_words_from_file as extract_urimal_words

SOURCE_STD = "표준국어대사전"
SOURCE_URIMAL = "우리말샘"
SOURCE_BASIC = "한국어기초사전"

SOURCE_WEIGHTS: Dict[str, float] = {
    SOURCE_URIMAL: 1.0,
    SOURCE_STD: 2.0,
    SOURCE_BASIC: 3.0,
}

BASE_NUM_IN_NAME = re.compile(r".*_(\d+)\.json$")


def _sort_key(path: str) -> int:
    match = BASE_NUM_IN_NAME.match(os.path.basename(path))
    return int(match.group(1)) if match else 0


@dataclass
class WordRecord:
    word: str
    sources: Set[str] = field(default_factory=set)

    def add_source(self, source: str) -> None:
        self.sources.add(source)

    @property
    def score(self) -> float:
        if not self.sources:
            return 0.0
        return max(SOURCE_WEIGHTS.get(src, 0.0) for src in self.sources)


def _gather_from_dir(
    dir_path: Optional[str],
    source_label: str,
    extractor: Callable[[str], List[str]],
    add_word: Callable[[str, str], None],
) -> None:
    if not dir_path:
        return
    if not os.path.isdir(dir_path):
        print(f"[warn] {source_label} directory missing: {dir_path}")
        return

    paths = sorted(glob(os.path.join(dir_path, "*.json")), key=_sort_key)
    total = len(paths)
    if total == 0:
        print(f"[warn] {source_label}: no JSON files found in {dir_path}")
        return

    for idx, path in enumerate(paths, 1):
        try:
            words = extractor(path)
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[error] failed to parse {path}: {exc}")
            continue
        for word in words:
            add_word(word, source_label)
        if idx % 5 == 0 or idx == total:
            print(f"[{source_label}] {idx}/{total} files processed ...")


def build_lexicon(
    stdict_dir: Optional[str],
    urimal_dir: Optional[str],
    basic_dir: Optional[str],
) -> List[WordRecord]:
    registry: Dict[str, WordRecord] = {}

    def add_word(word: str, source: str) -> None:
        if not word:
            return
        record = registry.get(word)
        if record is None:
            record = WordRecord(word=word)
            registry[word] = record
        record.add_source(source)

    _gather_from_dir(stdict_dir, SOURCE_STD, extract_stdict_words, add_word)
    _gather_from_dir(urimal_dir, SOURCE_URIMAL, extract_urimal_words, add_word)
    _gather_from_dir(basic_dir, SOURCE_BASIC, extract_basic_words, add_word)

    records = sorted(
        registry.values(),
        key=lambda record: (-record.score, record.word),
    )
    print(f"Total unique words: {len(records)}")
    return records


def save_jsonl_gz(records: List[WordRecord], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as fh:
        for record in records:
            fh.write(
                json.dumps(
                    {
                        "w": record.word,
                        "sources": sorted(record.sources),
                        "score": record.score,
                    },
                    ensure_ascii=False,
                )
            )
            fh.write("\n")


def build_and_save_trie(records: List[WordRecord], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    trie = Trie(source_weights=SOURCE_WEIGHTS)
    for record in records:
        trie.insert(record.word, record.sources)
    with open(out_path, "wb") as fh:
        pickle.dump(trie, fh, protocol=pickle.HIGHEST_PROTOCOL)


def print_lexicon_report(records: List[WordRecord]) -> None:
    from collections import Counter

    total = len(records)
    print("[report] total unique:", total)

    length_counts = Counter(len(record.word) for record in records)
    print("[report] headword lengths (first 10):", dict(sorted(length_counts.items())[:10]))

    source_counter = Counter()
    for record in records:
        source_counter.update(record.sources)
    print("[report] source coverage:", dict(source_counter))

    probes = ["결근", "신상", "상피", "신경", "근육", "결합"]
    words_set = {record.word for record in records}
    for probe in probes:
        print(f"[report] contains {probe}:", "yes" if probe in words_set else "no")


def main() -> None:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    default_std = os.path.join(root_dir, "표준국어대사전")
    default_urimal = os.path.join(root_dir, "우리말샘")
    default_basic = os.path.join(root_dir, "한국어기초사전")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dict-dir",
        default=None,
        help="(Deprecated) Path to 표준국어대사전 dumps (alias for --stdict-dir).",
    )
    parser.add_argument(
        "--stdict-dir",
        default=default_std,
        help="Path to 표준국어대사전 JSON exports.",
    )
    parser.add_argument(
        "--urimal-dir",
        default=default_urimal,
        help="Path to 우리말샘 JSON exports.",
    )
    parser.add_argument(
        "--basic-dir",
        default=default_basic,
        help="Path to 한국어기초사전 JSON exports.",
    )
    parser.add_argument(
        "--jsonl-out",
        default=os.path.join(root_dir, "artifacts", "lexicon.jsonl.gz"),
        help="Destination for the merged lexicon (.jsonl.gz).",
    )
    parser.add_argument(
        "--trie-out",
        default=os.path.join(root_dir, "artifacts", "trie.pkl"),
        help="Destination for the merged trie pickle.",
    )

    args = parser.parse_args()

    stdict_dir = os.path.abspath(args.stdict_dir or args.dict_dir or default_std)
    urimal_dir = os.path.abspath(args.urimal_dir) if args.urimal_dir else None
    basic_dir = os.path.abspath(args.basic_dir) if args.basic_dir else None

    records = build_lexicon(stdict_dir, urimal_dir, basic_dir)
    save_jsonl_gz(records, os.path.abspath(args.jsonl_out))
    build_and_save_trie(records, os.path.abspath(args.trie_out))
    print_lexicon_report(records)
    print("Wrote:", args.jsonl_out, "and", args.trie_out)


if __name__ == "__main__":
    main()
