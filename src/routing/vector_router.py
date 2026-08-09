"""D2 Layer 3 - L2 Vector Router.

Medium speed: embedding similarity matching (~10ms).
Uses pre-computed intent centroid vectors to classify by semantic similarity.
Pure Python implementation - no numpy dependency required.
"""

import math
import hashlib
import random
from .base import BaseRouter, RouteResult
from src.models.adapter import ModelAdapter

def _vec_mean(vectors: list[list[float]]) -> list[float]:
    """Compute element-wise mean of a list of vectors."""
    if not vectors:
        return []
    dim = len(vectors[0])
    result = [0.0] * dim
    for vec in vectors:
        for i in range(dim):
            result[i] += vec[i]
    n = len(vectors)
    return [v / n for v in result]


def _vec_norm(vec: list[float]) -> float:
    """L2 norm of a vector."""
    return math.sqrt(sum(v * v for v in vec))


def _vec_normalize(vec: list[float]) -> list[float]:
    """Return normalized copy of vector."""
    norm = _vec_norm(vec)
    if norm < 1e-8:
        return vec
    return [v / norm for v in vec]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = _vec_norm(a)
    norm_b = _vec_norm(b)
    denom = norm_a * norm_b + 1e-8
    return dot / denom


def _deterministic_vector(seed_text: str, dim: int = 64) -> list[float]:
    """Generate a deterministic pseudo-embedding from text (for offline mode)."""
    h = int(hashlib.md5(seed_text.encode()).hexdigest(), 16)
    rng = random.Random(h)
    vec = [rng.gauss(0, 1) for _ in range(dim)]
    return _vec_normalize(vec)


class VectorRouter(BaseRouter):
    """L2: Embedding-based intent routing via cosine similarity."""

    INTENT_EXAMPLES: dict[str, list[str]] = {
        "query_order": [
            "我的订单到哪了",
            "查一下物流信息",
            "订单状态怎么样了",
            "快递什么时候到",
            "帮我看看我的单子",
        ],
        "refund": [
            "我要退款",
            "商品坏了想退货",
            "申请退钱",
            "东西不满意想退",
            "退款流程是什么",
        ],
        "faq": [
            "怎么使用优惠券",
            "会员有什么权益",
            "积分怎么兑换",
            "营业时间是什么时候",
            "怎么修改收货地址",
        ],
        "complaint": [
            "我要投诉",
            "服务态度太差了",
            "给我个说法",
        ],
    }

    CONFIDENCE_THRESHOLD = 0.75
    MOCK_CONFIDENCE_THRESHOLD = 0.0  # Mock mode: return best match regardless of score

    def __init__(self, embedding_adapter: ModelAdapter | None = None):
        self._embedding_adapter = embedding_adapter
        self._centroids: dict[str, list[float]] | None = None
        self._mock_centroids = self._build_mock_centroids()

    async def route(self, user_input: str) -> RouteResult | None:
        if self._embedding_adapter is None:
            return self._mock_route(user_input)

        await self._ensure_centroids()
        query_vec = await self._get_embedding(user_input)

        best_intent = None
        best_score = 0.0

        for intent, centroid in self._centroids.items():
            score = _cosine_similarity(query_vec, centroid)
            if score > best_score:
                best_score = score
                best_intent = intent

        if best_score >= self.CONFIDENCE_THRESHOLD:
            return RouteResult(best_intent, best_score, "L2")
        return None

    async def _ensure_centroids(self):
        if self._centroids is not None:
            return
        centroids = {}
        for intent, examples in self.INTENT_EXAMPLES.items():
            embeddings = []
            for text in examples:
                vec = await self._get_embedding(text)
                embeddings.append(vec)
            centroids[intent] = _vec_mean(embeddings)
        self._centroids = centroids

    async def _get_embedding(self, text: str) -> list[float]:
        if self._embedding_adapter is None:
            return _deterministic_vector(text)
        raw = await self._embedding_adapter.generate(text)
        if isinstance(raw, list):
            vec = [float(v) for v in raw]
        else:
            vec = _deterministic_vector(text)
        return _vec_normalize(vec)

    def _build_mock_centroids(self) -> dict[str, list[float]]:
        """Deterministic pseudo-embeddings for offline mode."""
        centroids = {}
        for intent, examples in self.INTENT_EXAMPLES.items():
            vecs = [_deterministic_vector(text) for text in examples]
            centroids[intent] = _vec_mean(vecs)
        return centroids

    def _mock_route(self, user_input: str) -> RouteResult | None:
        query_vec = _deterministic_vector(user_input)
        best_intent = None
        best_score = 0.0
        for intent, centroid in self._mock_centroids.items():
            score = _cosine_similarity(query_vec, centroid)
            if score > best_score:
                best_score = score
                best_intent = intent
        # In mock mode, return best match even with low confidence
        # (real mode uses CONFIDENCE_THRESHOLD)
        if best_intent is not None:
            return RouteResult(best_intent, best_score, "L2")
        return None
