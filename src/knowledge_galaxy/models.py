from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Iterable


Vector = dict[str, float]
PairScores = dict[tuple[str, str], float]


@dataclass(frozen=True)
class TextModel:
    name: str
    version: str
    parameters: dict[str, object]
    analyzer: Callable[[str], list[str]]

    def fit_pair_scores(self, texts: dict[str, str]) -> PairScores:
        documents = {entity_id: self.analyzer(text) for entity_id, text in texts.items()}
        vectors = _tfidf_vectors(documents)
        ids = sorted(vectors)
        return {
            (left, right): _cosine(vectors[left], vectors[right])
            for position, left in enumerate(ids)
            for right in ids[position + 1 :]
        }


def default_models() -> list[TextModel]:
    return [
        TextModel(
            name="word_tfidf",
            version="1",
            parameters={"ngrams": [1, 2], "lowercase": True},
            analyzer=_word_ngrams,
        ),
        TextModel(
            name="char_tfidf",
            version="1",
            parameters={"ngramRange": [3, 5], "lowercase": True},
            analyzer=_char_ngrams,
        ),
    ]


def pair_scores_from_dense_embeddings(
    entity_ids: list[str], embeddings: list[list[float]]
) -> PairScores:
    if len(entity_ids) != len(embeddings):
        raise ValueError("embedding count does not match entity id count")
    dimensions = {len(vector) for vector in embeddings}
    if not dimensions or 0 in dimensions or len(dimensions) != 1:
        raise ValueError("embeddings must have one shared, non-zero dimension")
    normalized = [_normalize_dense(vector) for vector in embeddings]
    return {
        tuple(sorted((left, right))): sum(a * b for a, b in zip(normalized[i], normalized[j]))
        for i, left in enumerate(entity_ids)
        for j, right in enumerate(entity_ids[i + 1 :], start=i + 1)
    }


def score(scores: PairScores, left: str, right: str) -> float:
    if left == right:
        return 1.0
    return scores[tuple(sorted((left, right)))]


def _word_ngrams(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    bigrams = [f"{left}__{right}" for left, right in zip(words, words[1:])]
    return words + bigrams


def _char_ngrams(text: str) -> list[str]:
    normalized = " ".join(re.findall(r"[a-z0-9]+", text.lower()))
    return [
        normalized[index : index + size]
        for size in range(3, 6)
        for index in range(max(0, len(normalized) - size + 1))
    ]


def _tfidf_vectors(documents: dict[str, list[str]]) -> dict[str, Vector]:
    document_count = len(documents)
    document_frequency: Counter[str] = Counter()
    for tokens in documents.values():
        document_frequency.update(set(tokens))
    idf = {
        token: math.log((1 + document_count) / (1 + frequency)) + 1
        for token, frequency in document_frequency.items()
    }
    vectors: dict[str, Vector] = {}
    for entity_id, tokens in documents.items():
        counts = Counter(tokens)
        raw = {token: count * idf[token] for token, count in counts.items()}
        norm = math.sqrt(sum(value * value for value in raw.values())) or 1.0
        vectors[entity_id] = {token: value / norm for token, value in raw.items()}
    return vectors


def _cosine(left: Vector, right: Vector) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(token, 0.0) for token, value in left.items())


def _normalize_dense(vector: Iterable[float]) -> list[float]:
    values = [float(value) for value in vector]
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0:
        raise ValueError("embedding vectors must not be all zero")
    return [value / norm for value in values]
