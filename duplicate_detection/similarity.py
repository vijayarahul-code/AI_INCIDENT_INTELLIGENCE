from __future__ import annotations

import re
from typing import List, Sequence, Tuple

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

GENERIC_INCIDENT_TERMS = {
    "incident", "issue", "problem", "error", "failure", "failed", "unavailable",
    "available", "unable", "working", "work", "completely", "service", "system",
}
SIMILARITY_STOP_WORDS = ENGLISH_STOP_WORDS.union(GENERIC_INCIDENT_TERMS)


def _normalize_token(token: str) -> str:
    value = re.sub(r"[^a-z0-9]", "", token.lower())
    if len(value) <= 3:
        return value
    if value.endswith("ing"):
        value = value[:-3]
    elif value.endswith("ed"):
        value = value[:-2]
        if value.endswith("ir"):
            value += "e"
    elif value.endswith("s"):
        value = value[:-1]
    return value


_NORMALIZED_STOP_WORDS = {_normalize_token(word) for word in SIMILARITY_STOP_WORDS}


def _tokenize(text: str) -> List[str]:
    tokens = []
    for raw in re.findall(r"[a-z0-9]+", text.lower()):
        if raw in SIMILARITY_STOP_WORDS:
            continue
        token = _normalize_token(raw)
        if len(token) > 2 and token not in _NORMALIZED_STOP_WORDS:
            tokens.append(token)
    return tokens


def _token_overlap_score(left: str, right: str) -> float:
    left_tokens = {
        _normalize_token(token) for token in left.lower().split()
        if token and _normalize_token(token) not in SIMILARITY_STOP_WORDS
    }
    right_tokens = {
        _normalize_token(token) for token in right.lower().split()
        if token and _normalize_token(token) not in SIMILARITY_STOP_WORDS
    }
    if not left_tokens or not right_tokens:
        return 0.0
    overlap = left_tokens.intersection(right_tokens)
    if not overlap:
        return 0.0
    return len(overlap) / max(1, min(len(left_tokens), len(right_tokens)))


def compute_similarity_scores(texts: Sequence[str], threshold: float = 0.70) -> List[Tuple[int, int, float]]:
    if len(texts) < 2:
        return []

    vectorizer = TfidfVectorizer(tokenizer=_tokenize, token_pattern=None, lowercase=False)
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return []
    distance = cosine_similarity(matrix)
    results: List[Tuple[int, int, float]] = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            # Use normalized, stop-word-filtered token Dice as a secondary
            # signal. The previous overlap boost used unfiltered raw words,
            # so generic terms such as "error" inflated unrelated pairs.
            left_tokens = set(_tokenize(texts[i]))
            right_tokens = set(_tokenize(texts[j]))
            shared = len(left_tokens & right_tokens)
            dice_score = (2 * shared / (len(left_tokens) + len(right_tokens))) if shared else 0.0
            similarity_score = max(0.0, min(1.0, float(distance[i][j]), 1.0))
            similarity_score = max(similarity_score, dice_score)
            if similarity_score >= threshold:
                results.append((i, j, similarity_score))
    return results


def find_potential_duplicates(descriptions: Sequence[str], threshold: float = 0.70) -> List[Tuple[int, int, float]]:
    return compute_similarity_scores(descriptions, threshold=threshold)


def trim_similarities(results: List[Tuple[int, int, float]], max_results: int = 10) -> List[Tuple[int, int, float]]:
    sorted_results = sorted(results, key=lambda item: item[2], reverse=True)
    return sorted_results[:max_results]


def describe_keyword_overlap(left: str, right: str) -> List[str]:
    left_tokens = { _normalize_token(token) for token in left.lower().split() if token }
    right_tokens = { _normalize_token(token) for token in right.lower().split() if token }
    overlap = sorted(left_tokens.intersection(right_tokens))
    return overlap
