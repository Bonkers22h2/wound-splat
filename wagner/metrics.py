"""Grade-specific and pooled metrics with a fixed four-grade label universe."""
import numpy as np
from . import GRADES


def classification_metrics(truth, predicted):
    if len(truth) == 0 or len(truth) != len(predicted):
        raise ValueError("Metrics need equally sized, nonempty labels and predictions.")
    if any(x not in GRADES for x in list(truth) + list(predicted)):
        raise ValueError("Metrics support only grades 1–4.")
    matrix = np.zeros((4, 4), dtype=int)
    for actual, prediction in zip(truth, predicted):
        matrix[actual - 1, prediction - 1] += 1
    per_grade = {}
    for index, grade in enumerate(GRADES):
        tp = int(matrix[index, index])
        support, positives = int(matrix[index].sum()), int(matrix[:, index].sum())
        precision = tp / positives if positives else 0.0
        recall = tp / support if support else 0.0
        per_grade[str(grade)] = {
            "precision": precision, "recall": recall,
            "f1": 2 * tp / (support + positives) if support + positives else 0.0,
            "support": support,
        }
    return {
        "accuracy": float(np.trace(matrix) / matrix.sum()),
        "macro_f1": float(np.mean([row["f1"] for row in per_grade.values()])),
        "per_grade": per_grade, "confusion_matrix": matrix.tolist(),
        "confusion_matrix_axes": "rows=true grade; columns=predicted grade; order=[1,2,3,4]",
        "zero_division": 0,
    }
