# app.py
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import os

from lexicon.mnemo_mcp import generate_initial_combos, initials_from_words

API_KEY = os.getenv("MNEMO_API_KEY")  # set this env var in prod

app = FastAPI(
    title="Korean Initial-Combination (두문자 조합) API",
    version="1.0.0",
    description="Builds initial-letter word combinations (두문자 조합) using a Korean lexicon trie."
)

def require_key(x_api_key: Optional[str]):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")

class InitialCombo(BaseModel):
    combo: str = Field(..., description="Concatenated string of the words, e.g., '결근신상'")
    words: List[str] = Field(..., description="Segmented words, e.g., ['결근','신상']")
    score: float
    mode: Literal["sequence", "bag"]
    coverage: List[str] = Field(..., description="Initials used, e.g., ['결','근','신','상']")

class SuggestByInitialsRequest(BaseModel):
    initials: List[str]
    beam_width: int = 64
    max_candidates: int = 20
    keep_order: bool = True
    trace: bool = False

class FromWordsRequest(BaseModel):
    words: List[str] = Field(..., description="Target words, e.g., ['결합','근육','상피','신경']")
    beam_width: int = 64
    max_candidates: int = 20
    keep_order: bool = True
    trace: bool = False

@app.post("/initial-combos/suggest", response_model=List[InitialCombo], tags=["initial-combos"])
def suggest_by_initials(req: SuggestByInitialsRequest, x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    results = generate_initial_combos(
        initials=req.initials,
        beam_width=req.beam_width,
        max_candidates=req.max_candidates,
        keep_order=req.keep_order,
        trace=req.trace,
    )
    return results[0] if req.trace else results

@app.post("/initial-combos/from-words", response_model=List[InitialCombo], tags=["initial-combos"])
def suggest_from_words(req: FromWordsRequest, x_api_key: Optional[str] = Header(None)):
    require_key(x_api_key)
    # Extract first Hangul syllable of each word (your lib likely already has this)
    initials = initials_from_words(req.words)
    results = generate_initial_combos(
        initials=initials,
        beam_width=req.beam_width,
        max_candidates=req.max_candidates,
        keep_order=req.keep_order,
        trace=req.trace,
    )
    return results[0] if req.trace else results
