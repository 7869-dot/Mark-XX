"""Lightweight text-similarity utilities for ranking Agent Card candidates.

No external ML dependencies — uses bag-of-words cosine similarity.
TODO: replace cosine_sim() with voyage-3 or text-embedding-3-small calls
      once an embeddings API key is available.  The AgentCard.embedding JSON
      column is reserved for that upgrade path.
"""
import re
from collections import Counter
from math import sqrt


def _tokenize(text: str) -> list[str]:
    """Lowercase, split on non-alpha, drop short tokens."""
    return [w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 2]


def cosine_sim(text_a: str, text_b: str) -> float:
    """Return cosine similarity ∈ [0, 1] between two text blobs."""
    freq_a = Counter(_tokenize(text_a))
    freq_b = Counter(_tokenize(text_b))

    common = set(freq_a) & set(freq_b)
    dot    = sum(freq_a[w] * freq_b[w] for w in common)
    mag_a  = sqrt(sum(v * v for v in freq_a.values()))
    mag_b  = sqrt(sum(v * v for v in freq_b.values()))

    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def card_text(card) -> str:
    """Flatten an AgentCard's public fields into one string for similarity."""
    tags = " ".join(card.tags or [])
    return f"{card.building} {card.looking_for} {card.can_offer} {tags}"


def rank_candidates(my_card, others: list) -> list:
    """Return `others` sorted by descending similarity to `my_card`."""
    my_text = card_text(my_card)
    scored = [(c, cosine_sim(my_text, card_text(c))) for c in others]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored]
