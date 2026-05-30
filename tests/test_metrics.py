import numpy as np
from cad_retriever.eval.metrics import recall_at_k, mean_reciprocal_rank


def test_recall_at_1_perfect():
    # Ground truth is index 0, retrieved [0, 1, 2, ...]
    retrieved = np.array([[0, 1, 2, 3, 4]])
    ground_truth = np.array([0])
    assert recall_at_k(retrieved, ground_truth, k=1) == 1.0


def test_recall_at_1_miss():
    retrieved = np.array([[5, 1, 2, 3, 4]])
    ground_truth = np.array([0])
    assert recall_at_k(retrieved, ground_truth, k=1) == 0.0


def test_recall_at_10_hit():
    retrieved = np.array([[5, 1, 2, 3, 4, 6, 7, 8, 9, 0]])
    ground_truth = np.array([0])
    assert recall_at_k(retrieved, ground_truth, k=10) == 1.0


def test_mrr_first_position():
    retrieved = np.array([[0, 1, 2]])
    ground_truth = np.array([0])
    assert mean_reciprocal_rank(retrieved, ground_truth) == 1.0


def test_mrr_third_position():
    retrieved = np.array([[5, 6, 0, 1, 2]])
    ground_truth = np.array([0])
    assert mean_reciprocal_rank(retrieved, ground_truth) == 1.0 / 3


def test_mrr_batch():
    retrieved = np.array([[0, 1, 2], [3, 0, 1]])
    ground_truth = np.array([0, 0])
    # First query: rank 1 (1/1), second query: rank 2 (1/2)
    assert mean_reciprocal_rank(retrieved, ground_truth) == (1.0 + 0.5) / 2
