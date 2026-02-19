# app.py
# Minimal GPT Actions gateway for your repo:
#   1) POST /combinations/generate  -> generate_initial_combos()
#   2) POST /lexicon/validate       -> lexicon_check_word() in bulk (fallback uses trie.pkl)

from __future__ import annotations
import os
import sys
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

# ---------- auth ----------
API_KEY = os.environ.get("MNEMONIC_API_KEY")


def auth_or_401(key: Optional[str]):
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")


# Make sure "lexicon" is importable when running anywhere
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Optional imports from your repo (we keep runtime robust)
try:
    from lexicon.mnemo_mcp import (
        generate_initial_combos,
        initials_from_words,
        lexicon_check_word,
    )
except Exception as e:  # pragma: no cover - defensive import guard
    generate_initial_combos = None
    initials_from_words = None
    lexicon_check_word = None
    mnemo_import_err = e
else:
    mnemo_import_err = None


# Fallback: direct Trie load (for validate endpoint only)
TRIE = None


def load_trie():
    global TRIE
    if TRIE is not None:
        return TRIE
    candidates = [
        REPO_ROOT / "lexicon" / "artifacts" / "trie.pkl",
        REPO_ROOT / "artifacts" / "trie.pkl",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if not path:
        raise RuntimeError("trie.pkl not found. Checked: " + ", ".join(map(str, candidates)))
    with open(path, "rb") as f:
        TRIE = pickle.load(f)
    return TRIE


# ---------- API models ----------
class GenerateReq(BaseModel):
    """Request schema for initial-letter combination search."""

    letters: Optional[List[str]] = Field(default=None, example=["결", "근", "신", "상"])
    words: Optional[List[str]] = Field(default=None, example=["결근", "신상"])
    target: Optional[str] = Field(default=None, example="결근신상")
    beam_width: int = Field(default=64, ge=1, le=4096)
    max_candidates: int = Field(default=20, ge=1, le=100)
    keep_order: bool = Field(default=True, description="Keep the initial order (sequence mode).")
    bag_mode: Optional[bool] = Field(default=None, description="If true, allow reordering; overrides keep_order.")
    order_sensitive: Optional[bool] = Field(default=None, description="Deprecated alias for keep_order.")
    include_trace: bool = False

    def effective_keep_order(self) -> bool:
        if self.bag_mode is not None:
            return not self.bag_mode
        if self.order_sensitive is not None:
            return bool(self.order_sensitive)
        return self.keep_order


class ComboCandidate(BaseModel):
    combo: str
    words: List[str]
    word_sources: Optional[List[List[str]]] = None
    word_scores: Optional[List[float]] = None
    coverage: Optional[List[str]] = None
    mode: Optional[str] = None
    score: float


class GenerateResp(BaseModel):
    candidates: List[ComboCandidate]
    initials: List[str]
    trace: Optional[List[Dict[str, Any]]] = None


class ValidateReq(BaseModel):
    words: List[str] = Field(..., min_items=1, max_items=200)


class ValidateItem(BaseModel):
    word: str
    in_dict: bool
    has_prefix: bool
    sources: List[str] = []
    score: float = 0.0


class ValidateResp(BaseModel):
    results: List[ValidateItem]


# ---------- app ----------
app = FastAPI(title="Mnemonic MCP Gateway", version="0.1.0")


@app.get("/health")
def health():
    return {"ok": True, "mnemo_loaded": generate_initial_combos is not None}


def _derive_initials(req: GenerateReq) -> List[str]:
    if req.letters:
        return req.letters
    if req.words and initials_from_words is not None:
        return initials_from_words(req.words)
    if req.target:
        return list(req.target)
    raise HTTPException(status_code=400, detail="Provide one of: letters[], words[], or target string.")


@app.post("/combinations/generate", response_model=GenerateResp)
@app.post("/mnemonics/generate", response_model=GenerateResp, include_in_schema=False)
def generate(req: GenerateReq, x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    auth_or_401(x_api_key)

    if generate_initial_combos is None:
        raise HTTPException(
            status_code=503,
            detail=f"mnemo_mcp not available (import error: {mnemo_import_err}). "
                   f"Install its dependencies or run inside your repo environment.",
        )

    initials = _derive_initials(req)
    keep_order = req.effective_keep_order()

    if req.include_trace:
        combos, trace = generate_initial_combos(
            initials,
            beam_width=req.beam_width,
            max_candidates=req.max_candidates,
            keep_order=keep_order,
            trace=True,
        )
        return {"candidates": combos, "initials": initials, "trace": trace}

    combos = generate_initial_combos(
        initials,
        beam_width=req.beam_width,
        max_candidates=req.max_candidates,
        keep_order=keep_order,
        trace=False,
    )
    return {"candidates": combos, "initials": initials}


@app.post("/lexicon/validate", response_model=ValidateResp)
def validate(req: ValidateReq, x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    auth_or_401(x_api_key)

    out: List[ValidateItem] = []
    if lexicon_check_word is not None:
        check = lexicon_check_word
        for word in req.words:
            info = check(word)
            out.append(
                ValidateItem(
                    word=word,
                    in_dict=bool(info.get("is_word")),
                    has_prefix=bool(info.get("has_prefix")),
                    sources=info.get("sources", []) or [],
                    score=float(info.get("score", 0.0)),
                )
            )
        return {"results": out}

    try:
        trie = load_trie()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"validate fallback failed (trie load): {exc}")

    for word in req.words:
        info = trie.get_word_info(word)
        out.append(
            ValidateItem(
                word=word,
                in_dict=bool(info),
                has_prefix=trie.has_word_with_prefix(word),
                sources=sorted(info["sources"]) if info else [],
                score=float(info["score"]) if info else 0.0,
            )
        )
    return {"results": out}
