# -*- coding: utf-8 -*-
"""Trace the initial-combination search to inspect decisions and scores."""

from __future__ import annotations

import argparse
import json
from typing import List

from lexicon.mnemo_mcp import generate_initial_combos, initials_from_words


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Trace the initial-letter combination search.")
    parser.add_argument(
        "items",
        nargs="+",
        help="Either individual initials or full words. Combine with --from-words to derive initials automatically.",
    )
    parser.add_argument("--beam", type=int, default=64, help="Beam width / frontier cap.")
    parser.add_argument("--max", type=int, default=10, help="Maximum number of combinations to collect.")
    parser.add_argument(
        "--from-words",
        action="store_true",
        help="Treat positional args as words and extract their first Hangul syllable.",
    )
    parser.add_argument(
        "--bag-mode",
        action="store_true",
        help="Allow reordering of initials (bag mode).",
    )
    parser.add_argument(
        "--trace-limit",
        type=int,
        default=0,
        help="Show only the first N trace events (0 = all).",
    )
    return parser.parse_args()


def coerce_initials(items: List[str], treat_as_words: bool) -> List[str]:
    if not treat_as_words:
        return items
    return initials_from_words(items)


def main() -> None:
    args = parse_args()
    initials = coerce_initials(args.items, args.from_words)

    results, trace = generate_initial_combos(
        initials,
        beam_width=args.beam,
        max_candidates=args.max,
        keep_order=not args.bag_mode,
        trace=True,
    )

    print("Initials:", initials)
    print("\nCombinations (ranked):")
    print(json.dumps(results, ensure_ascii=False, indent=2))

    limit = args.trace_limit if args.trace_limit and args.trace_limit > 0 else None
    print("\nTrace events:")
    for idx, event in enumerate(trace, 1):
        if limit is not None and idx > limit:
            print(f"... truncated after {limit} events.")
            break
        print(f"Step {idx}: {event['event']}")
        print(json.dumps(event, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
