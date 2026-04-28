"""
similarity.py — Hybrid BM25 + Fuzzy + Semantic Cosine similarity for SmartGrader
----------------------------------------------------------------------------------

LOGIC OVERVIEW
--------------
For each key concept we compute:

    final_score = 0.25 × BM25_score + 0.25 × fuzzy_score + 0.50 × cosine_score

BM25   → catches exact / near-exact keyword matches
Fuzzy  → catches misspellings ("mitocondia" ≈ "mitochondria" → 92%)
Cosine → catches paraphrases, casual language, same-meaning different-words

KEY IMPROVEMENT — sentence-level matching:
    Instead of comparing the full student answer against a keyword (noisy),
    we split the answer into sentences and take the MAX similarity across
    all sentences for each keyword.

    "the part of the cell that makes energy. it uses oxygen to do this."
         s1 vs "mitochondria" → 0.74   ← taken
         s2 vs "mitochondria" → 0.31

    This prevents relevant sentences getting diluted by irrelevant ones.

THRESHOLDS (tuned for casual/non-jargon student language):
    >= 0.70  →  present  (full marks)
    0.45–0.69 →  partial  (half marks)
    < 0.45   →  missing  (zero marks)

PARTIAL MARK MULTIPLIER:
    multiplier = (present×1.0 + partial×0.5) / total_concepts
    This is passed to the LLM as a suggested starting point for marks.

EXAMPLES:
    "mitochondria produces ATP"
    vs student: "the part of cell that makes energy packets using oxygen"
        BM25:   0.05  (no word overlap)
        Fuzzy:  0.10  (no spelling match)
        Cosine: 0.73  (model understands same meaning)
        Hybrid: 0.25×0.05 + 0.25×0.10 + 0.50×0.73 = 0.402 → partial ✓

    "mitochondria produces ATP"
    vs student: "mitocondia makes adenosine triphosphate"  (misspelled!)
        BM25:   0.05
        Fuzzy:  0.88  (token_set_ratio catches the misspelling)
        Cosine: 0.79
        Hybrid: 0.25×0.05 + 0.25×0.88 + 0.50×0.79 = 0.630 → present ✓

    "photosynthesis"
    vs student: "process by which plants prepare their own food using sunlight"
        BM25:   0.02
        Fuzzy:  0.05
        Cosine: 0.78
        Hybrid: 0.25×0.02 + 0.25×0.05 + 0.50×0.78 = 0.408 → partial ✓
"""

import re
import numpy as np
from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer, util

# ── Load once at import time ──────────────────────────────────────────────────
print("[similarity] Loading embedding model (multi-qa-mpnet-base-dot-v1)...")
_embedder = SentenceTransformer("multi-qa-mpnet-base-dot-v1")
print("[similarity] Model ready.")

# ── Tunable weights ───────────────────────────────────────────────────────────
BM25_WEIGHT   = 0.25   # exact word match weight  ← jargon bonus
FUZZY_WEIGHT  = 0.15   # misspelling-tolerant match weight
COSINE_WEIGHT = 0.60   # semantic meaning weight

# ── Score thresholds ──────────────────────────────────────────────────────────
THRESHOLD_PRESENT = 0.70   # full credit
THRESHOLD_PARTIAL = 0.45   # half credit — catches casual language / no jargon


# ── Universal symbol → word map (unambiguous only) ───────────────────────────
# Only symbols that mean the same thing regardless of subject.
# Abbreviations like EMF, AC, DNA, ATP are intentionally NOT expanded.
SYMBOL_MAP = {
    # Superscripts / math notation
    "²": " squared",   "³": " cubed",   "⁴": " to the power 4",
    "√": " root ",     "∫": " integral ", "π": " pi ",
    # Comparison operators
    "≥": " greater than or equal to ",
    "≤": " less than or equal to ",
    "≠": " not equal to ",
    "≈": " approximately equal to ",
    "∝": " proportional to ",
    # Arithmetic
    "×": " times ",    "÷": " divided by ",
    # Units / measures
    "°": " degrees ",  "%": " percent ",  "∞": " infinity ",
    # Change / sum
    "Δ": " delta ",   "Σ": " sigma sum ",
    # Greek letters
    "α": " alpha ",   "β": " beta ",    "γ": " gamma ",
    "θ": " theta ",   "ω": " omega ",   "λ": " lambda ",
    "μ": " mu ",      "ρ": " rho ",     "σ": " sigma ",
    "φ": " phi ",     "η": " eta ",     "ε": " epsilon ",
    # Arrows
    "→": " leads to ",  "⇒": " implies ",
}


def _normalize_symbols(text: str) -> str:
    """
    Replace math/science symbols with plain-English equivalents.
    Abbreviations (EMF, AC, DNA, ATP) are intentionally left unchanged
    so BM25/fuzzy can still match them exactly.
    """
    for symbol, word in SYMBOL_MAP.items():
        text = text.replace(symbol, word)
    # Collapse multiple spaces introduced by replacements
    text = re.sub(r" {2,}", " ", text).strip()
    return text


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """
    Split text into sentences. Falls back to the full text as one sentence
    if no sentence boundary is found.
    """
    text = text.strip()
    if not text:
        return []
    # Split on . ! ? followed by whitespace or end of string
    sentences = re.split(r"(?<=[.!?])\s+", text)
    # Also split on newlines (students often write one point per line)
    result = []
    for s in sentences:
        result.extend(s.split("\n"))
    # Clean and filter empty
    result = [s.strip() for s in result if s.strip()]
    return result if result else [text]


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into tokens."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return [t for t in text.split() if t]


def _bm25_score(query: str, document: str) -> float:
    """
    BM25 relevance of query against document.
    Normalised to 0.0–1.0 using tanh soft-cap.
    """
    doc_tokens   = _tokenize(document)
    query_tokens = _tokenize(query)

    if not doc_tokens or not query_tokens:
        return 0.0

    bm25 = BM25Okapi([doc_tokens])
    raw  = bm25.get_scores(query_tokens)[0]

    # tanh(x/5) maps [0,∞) → [0,1) smoothly
    normalised = float(np.tanh(raw / 5.0))
    return round(max(0.0, min(1.0, normalised)), 4)


def _fuzzy_score(text_a: str, text_b: str) -> float:
    """
    Fuzzy token-set similarity between two texts.
    Uses rapidfuzz.fuzz.token_set_ratio which:
      - is case-insensitive
      - ignores word order
      - handles misspellings via character-level edit distance

    Examples:
      "mitocondia"  vs "mitochondria"   → ~0.92  (misspelling caught)
      "ATP"         vs "adenosine triphosphate" → ~0.45 (abbreviation)
      "nucleus"     vs "mitochondria"   → ~0.21
    """
    if not text_a.strip() or not text_b.strip():
        return 0.0
    # token_set_ratio returns 0–100
    score = fuzz.token_set_ratio(text_a.lower(), text_b.lower()) / 100.0
    return round(max(0.0, min(1.0, score)), 4)


def _cosine_score(text_a: str, text_b: str) -> float:
    """Cosine similarity between two texts using dense embeddings."""
    if not text_a.strip() or not text_b.strip():
        return 0.0
    embs  = _embedder.encode([text_a, text_b], convert_to_tensor=True)
    score = float(util.cos_sim(embs[0], embs[1]))
    return round(max(0.0, min(1.0, score)), 4)


def _hybrid(text_a: str, text_b: str) -> tuple[float, float, float, float]:
    """
    Raw hybrid score between two strings.
    Returns (hybrid, bm25, fuzzy, cosine).
    """
    bm25_s   = _bm25_score(text_a, text_b)
    fuzzy_s  = _fuzzy_score(text_a, text_b)
    cosine_s = _cosine_score(text_a, text_b)
    hybrid_s = round(BM25_WEIGHT * bm25_s + FUZZY_WEIGHT * fuzzy_s + COSINE_WEIGHT * cosine_s, 4)
    return hybrid_s, bm25_s, fuzzy_s, cosine_s


def _best_sentence_score(sentences: list[str], concept: str) -> tuple[float, float, float, float, str]:
    """
    For a concept, find which sentence in the student answer matches best.

    Returns:
        (best_hybrid, best_bm25, best_fuzzy, best_cosine, best_sentence)
    """
    if not sentences:
        return 0.0, 0.0, 0.0, 0.0, ""

    best_hybrid  = -1.0
    best_bm25    = 0.0
    best_fuzzy   = 0.0
    best_cosine  = 0.0
    best_sent    = ""

    for sent in sentences:
        h, b, f, c = _hybrid(sent, concept)
        if h > best_hybrid:
            best_hybrid  = h
            best_bm25    = b
            best_fuzzy   = f
            best_cosine  = c
            best_sent    = sent

    return best_hybrid, best_bm25, best_fuzzy, best_cosine, best_sent


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def hybrid_sim(student_answer: str, concept: str) -> float:
    """
    Single hybrid score between student_answer and one concept.
    Uses sentence-level matching — takes the best matching sentence.
    Returns float 0.0–1.0.
    """
    sentences = _split_sentences(student_answer)
    score, _, _, _, _ = _best_sentence_score(sentences, concept)
    return max(0.0, score)


def keyword_report(
    student_answer: str,
    key_concepts: list[str],
    threshold_present: float = THRESHOLD_PRESENT,
    threshold_partial: float = THRESHOLD_PARTIAL,
) -> dict:
    """
    Run hybrid similarity for every key concept using sentence-level matching.

    Returns:
    {
        "per_keyword": [
            {
                "keyword":          str,
                "bm25":             float,
                "fuzzy":            float,   ← NEW: misspelling-tolerant score
                "cosine":           float,
                "hybrid":           float,
                "status":           "present" | "partial" | "missing",
                "matched_sentence": str      ← which sentence triggered this
            }
        ],
        "present":                 [str, ...],
        "partial":                 [str, ...],
        "missing":                 [str, ...],
        "partial_mark_multiplier": float      ← 0.0–1.0, guide for LLM
    }
    """
    if not key_concepts:
        return {
            "per_keyword": [],
            "present": [], "partial": [], "missing": [],
            "partial_mark_multiplier": 1.0
        }

    # Normalize symbols before scoring
    student_answer = _normalize_symbols(student_answer)
    key_concepts   = [_normalize_symbols(kw) for kw in key_concepts]

    sentences = _split_sentences(student_answer)

    per_keyword               = []
    present, partial, missing = [], [], []

    for kw in key_concepts:
        hybrid_s, bm25_s, fuzzy_s, cosine_s, matched_sent = _best_sentence_score(sentences, kw)
        hybrid_s = max(0.0, hybrid_s)

        if hybrid_s >= threshold_present:
            status = "present";  present.append(kw)
        elif hybrid_s >= threshold_partial:
            status = "partial";  partial.append(kw)
        else:
            status = "missing";  missing.append(kw)

        per_keyword.append({
            "keyword":          kw,
            "bm25":             bm25_s,
            "fuzzy":            fuzzy_s,
            "cosine":           cosine_s,
            "hybrid":           hybrid_s,
            "status":           status,
            "matched_sentence": matched_sent
        })

    total      = len(key_concepts)
    raw_score  = (len(present) * 1.0 + len(partial) * 0.5) / total
    multiplier = round(max(0.0, min(1.0, raw_score)), 4)

    return {
        "per_keyword":             per_keyword,
        "present":                 present,
        "partial":                 partial,
        "missing":                 missing,
        "partial_mark_multiplier": multiplier
    }


def answer_level_sim(student_answer: str, correct_answer: str) -> float:
    """
    Overall hybrid similarity between full student answer and full model answer.
    Uses sentence-level — takes best matching sentence from student vs full correct answer.
    """
    # Normalize symbols before scoring
    student_answer = _normalize_symbols(student_answer)
    correct_answer = _normalize_symbols(correct_answer)
    sentences = _split_sentences(student_answer)
    if not sentences:
        return 0.0
    best = max(_hybrid(s, correct_answer)[0] for s in sentences)
    return round(best, 4)


def format_sim_context(report: dict, answer_sim: float) -> str:
    """
    Formats similarity report as readable string to inject into LLM grading prompt.
    Includes which sentence triggered each score so LLM has full context.
    """
    lines = [
        "SEMANTIC SIMILARITY ANALYSIS (hybrid BM25 + Fuzzy + Cosine, scale 0–1):",
        f"Overall answer similarity vs model answer: {answer_sim}",
        "",
        "Per key concept (scored against best matching sentence in student answer):"
    ]

    for r in report["per_keyword"]:
        status_label = {
            "present": "✓ PRESENT",
            "partial": "~ PARTIAL",
            "missing": "✗ MISSING"
        }.get(r["status"], r["status"])

        lines.append(
            f"  • '{r['keyword']}'"
            f" → hybrid={r['hybrid']}"
            f" (bm25={r['bm25']}, fuzzy={r['fuzzy']}, cosine={r['cosine']})"
            f" [{status_label}]"
        )
        if r["matched_sentence"]:
            lines.append(f"    matched: \"{r['matched_sentence'][:120]}\"")

    lines += [
        "",
        f"Fully matched (≥0.70):        {report['present'] or 'none'}",
        f"Partially matched (0.45–0.69): {report['partial'] or 'none'}",
        f"  → student likely knew these but used different/casual/misspelled language",
        f"Missing (<0.45):              {report['missing'] or 'none'}",
        "",
        f"Suggested mark multiplier: {report['partial_mark_multiplier']}",
        f"  (present=full credit, partial=half credit, missing=no credit)",
        "",
        "GRADING INSTRUCTIONS:",
        "- 'present' → award full concept credit even if exact jargon not used",
        "- 'partial' → student grasped concept (casual/different/misspelled) → half credit",
        "- 'missing' → likely not covered → no credit unless you find it",
        "- Use multiplier as starting point, apply subject judgment on top",
    ]

    return "\n".join(lines)
