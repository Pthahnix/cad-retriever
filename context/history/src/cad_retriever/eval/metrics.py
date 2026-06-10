import numpy as np


def recall_at_k(retrieved: np.ndarray, ground_truth: np.ndarray, k: int) -> float:
    """Compute Recall@K.
    retrieved: (n_queries, n_retrieved) — ranked indices
    ground_truth: (n_queries,) — correct index for each query
    """
    n = len(ground_truth)
    hits = 0
    for i in range(n):
        if ground_truth[i] in retrieved[i, :k]:
            hits += 1
    return hits / n


def mean_reciprocal_rank(retrieved: np.ndarray, ground_truth: np.ndarray) -> float:
    """Compute MRR.
    retrieved: (n_queries, n_retrieved)
    ground_truth: (n_queries,)
    """
    n = len(ground_truth)
    rr_sum = 0.0
    for i in range(n):
        positions = np.where(retrieved[i] == ground_truth[i])[0]
        if len(positions) > 0:
            rr_sum += 1.0 / (positions[0] + 1)
    return rr_sum / n
