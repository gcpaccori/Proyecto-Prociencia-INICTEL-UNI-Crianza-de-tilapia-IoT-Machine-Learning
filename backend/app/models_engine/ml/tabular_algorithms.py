from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence


def _vector(values: Sequence[float]) -> list[float]:
    if not values:
        raise ValueError("vector must not be empty")
    return [float(value) for value in values]


def _matrix(rows: Sequence[Sequence[float]]) -> list[list[float]]:
    if not rows:
        raise ValueError("matrix must not be empty")
    matrix = [_vector(row) for row in rows]
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError("matrix rows must have the same width")
    return matrix


def dot(left: Sequence[float], right: Sequence[float]) -> float:
    left_values = _vector(left)
    right_values = _vector(right)
    if len(left_values) != len(right_values):
        raise ValueError("vectors must have the same length")
    return sum(left_i * right_i for left_i, right_i in zip(left_values, right_values))


def linear_regression_predict(
    features: Sequence[float],
    coefficients: Sequence[float],
    intercept: float = 0.0,
) -> float:
    return float(intercept) + dot(features, coefficients)


def linear_regression_fit_gradient_descent(
    rows: Sequence[Sequence[float]],
    targets: Sequence[float],
    learning_rate: float = 0.01,
    epochs: int = 500,
) -> dict[str, object]:
    x = _matrix(rows)
    y = _vector(targets)
    if len(x) != len(y):
        raise ValueError("rows and targets must have the same length")
    if learning_rate <= 0 or epochs <= 0:
        raise ValueError("learning_rate and epochs must be positive")
    coefficients = [0.0 for _ in x[0]]
    intercept = 0.0
    n = len(x)
    for _ in range(epochs):
        gradient_b = 0.0
        gradient_w = [0.0 for _ in coefficients]
        for row, target in zip(x, y):
            error = linear_regression_predict(row, coefficients, intercept) - target
            gradient_b += error
            for index, value in enumerate(row):
                gradient_w[index] += error * value
        intercept -= learning_rate * gradient_b / n
        coefficients = [
            coefficient - learning_rate * gradient / n
            for coefficient, gradient in zip(coefficients, gradient_w)
        ]
    return {"intercept": intercept, "coefficients": coefficients}


def logistic_probability(
    features: Sequence[float],
    coefficients: Sequence[float],
    intercept: float = 0.0,
) -> float:
    z_value = linear_regression_predict(features, coefficients, intercept)
    if z_value >= 0:
        return 1.0 / (1.0 + math.exp(-z_value))
    exp_z = math.exp(z_value)
    return exp_z / (1.0 + exp_z)


def logistic_predict(
    features: Sequence[float],
    coefficients: Sequence[float],
    intercept: float = 0.0,
    threshold: float = 0.5,
) -> int:
    return int(logistic_probability(features, coefficients, intercept) >= threshold)


def svm_decision_score(
    features: Sequence[float],
    weights: Sequence[float],
    bias: float = 0.0,
) -> float:
    return dot(features, weights) + float(bias)


def svm_hinge_loss(
    rows: Sequence[Sequence[float]],
    labels: Sequence[float],
    weights: Sequence[float],
    bias: float = 0.0,
    c_value: float = 1.0,
) -> float:
    x = _matrix(rows)
    y = _vector(labels)
    w = _vector(weights)
    if len(x) != len(y):
        raise ValueError("rows and labels must have the same length")
    regularization = 0.5 * dot(w, w)
    penalty = sum(
        max(0.0, 1.0 - label * svm_decision_score(row, w, bias))
        for row, label in zip(x, y)
    )
    return regularization + float(c_value) * penalty


def epsilon_svr_loss(
    observed: Sequence[float],
    predicted: Sequence[float],
    epsilon: float = 0.1,
) -> float:
    obs = _vector(observed)
    pred = _vector(predicted)
    if len(obs) != len(pred):
        raise ValueError("observed and predicted must have the same length")
    return sum(max(0.0, abs(o_i - p_i) - float(epsilon)) for o_i, p_i in zip(obs, pred))


def random_forest_regression_predict(tree_predictions: Sequence[float]) -> float:
    predictions = _vector(tree_predictions)
    return sum(predictions) / len(predictions)


def random_forest_classification_predict(tree_predictions: Sequence[object]) -> object:
    if not tree_predictions:
        raise ValueError("tree_predictions must not be empty")
    return Counter(tree_predictions).most_common(1)[0][0]


def euclidean_distance(left: Sequence[float], right: Sequence[float]) -> float:
    left_values = _vector(left)
    right_values = _vector(right)
    if len(left_values) != len(right_values):
        raise ValueError("vectors must have the same length")
    return sum((left_i - right_i) ** 2 for left_i, right_i in zip(left_values, right_values)) ** 0.5


def kmeans_assign(
    point: Sequence[float],
    centroids: Sequence[Sequence[float]],
) -> int:
    centers = _matrix(centroids)
    distances = [euclidean_distance(point, center) for center in centers]
    return min(range(len(distances)), key=lambda index: distances[index])


def kmeans_update_centroids(
    rows: Sequence[Sequence[float]],
    assignments: Sequence[int],
    k: int,
) -> list[list[float]]:
    x = _matrix(rows)
    if len(x) != len(assignments):
        raise ValueError("rows and assignments must have the same length")
    if k <= 0:
        raise ValueError("k must be positive")
    width = len(x[0])
    centroids: list[list[float]] = []
    for cluster in range(k):
        members = [row for row, assignment in zip(x, assignments) if assignment == cluster]
        if not members:
            centroids.append([0.0 for _ in range(width)])
            continue
        centroids.append(
            [sum(row[index] for row in members) / len(members) for index in range(width)]
        )
    return centroids


def kmeans_fit(
    rows: Sequence[Sequence[float]],
    initial_centroids: Sequence[Sequence[float]],
    iterations: int = 10,
) -> dict[str, object]:
    x = _matrix(rows)
    centroids = _matrix(initial_centroids)
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    assignments = [0 for _ in x]
    for _ in range(iterations):
        assignments = [kmeans_assign(row, centroids) for row in x]
        centroids = kmeans_update_centroids(x, assignments, len(centroids))
    objective = sum(
        euclidean_distance(row, centroids[assignment]) ** 2
        for row, assignment in zip(x, assignments)
    )
    return {"centroids": centroids, "assignments": assignments, "objective": objective}


def center_matrix(rows: Sequence[Sequence[float]]) -> dict[str, object]:
    x = _matrix(rows)
    width = len(x[0])
    means = [sum(row[index] for row in x) / len(x) for index in range(width)]
    centered = [[value - means[index] for index, value in enumerate(row)] for row in x]
    return {"means": means, "centered": centered}


def covariance_matrix(rows: Sequence[Sequence[float]]) -> list[list[float]]:
    centered_payload = center_matrix(rows)
    centered = centered_payload["centered"]
    width = len(centered[0])
    denominator = max(1, len(centered) - 1)
    return [
        [
            sum(row[i] * row[j] for row in centered) / denominator
            for j in range(width)
        ]
        for i in range(width)
    ]


def pca_project(
    rows: Sequence[Sequence[float]],
    components: Sequence[Sequence[float]],
) -> list[list[float]]:
    centered = center_matrix(rows)["centered"]
    vectors = _matrix(components)
    return [[dot(row, component) for component in vectors] for row in centered]


def knn_regression_predict(
    rows: Sequence[Sequence[float]],
    targets: Sequence[float],
    query: Sequence[float],
    k: int = 3,
) -> float:
    x = _matrix(rows)
    y = _vector(targets)
    if len(x) != len(y):
        raise ValueError("rows and targets must have the same length")
    if k <= 0:
        raise ValueError("k must be positive")
    neighbors = sorted(
        zip(x, y),
        key=lambda item: euclidean_distance(item[0], query),
    )[:k]
    return sum(target for _, target in neighbors) / len(neighbors)


def knn_classification_predict(
    rows: Sequence[Sequence[float]],
    labels: Sequence[object],
    query: Sequence[float],
    k: int = 3,
) -> object:
    x = _matrix(rows)
    if len(x) != len(labels):
        raise ValueError("rows and labels must have the same length")
    if k <= 0:
        raise ValueError("k must be positive")
    neighbors = sorted(
        zip(x, labels),
        key=lambda item: euclidean_distance(item[0], query),
    )[:k]
    return Counter(label for _, label in neighbors).most_common(1)[0][0]


def som_gaussian_neighborhood(
    winner_position: Sequence[float],
    node_position: Sequence[float],
    sigma: float,
) -> float:
    if sigma <= 0:
        raise ValueError("sigma must be positive")
    distance = euclidean_distance(winner_position, node_position)
    return math.exp(-(distance**2) / (2.0 * sigma**2))


def som_update_weight(
    weight: Sequence[float],
    sample: Sequence[float],
    learning_rate: float,
    neighborhood: float,
) -> list[float]:
    if learning_rate < 0:
        raise ValueError("learning_rate must be non-negative")
    w = _vector(weight)
    x = _vector(sample)
    if len(w) != len(x):
        raise ValueError("weight and sample must have the same length")
    factor = float(learning_rate) * float(neighborhood)
    return [w_i + factor * (x_i - w_i) for w_i, x_i in zip(w, x)]


def q_learning_update(
    current_q: float,
    reward: float,
    next_max_q: float,
    alpha: float,
    gamma: float,
) -> float:
    if alpha < 0 or alpha > 1:
        raise ValueError("alpha must be between 0 and 1")
    if gamma < 0 or gamma > 1:
        raise ValueError("gamma must be between 0 and 1")
    return float(current_q) + float(alpha) * (
        float(reward) + float(gamma) * float(next_max_q) - float(current_q)
    )
