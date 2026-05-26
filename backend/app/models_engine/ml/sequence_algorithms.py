from __future__ import annotations

import math
from collections.abc import Sequence

from backend.app.models_engine.ml.tabular_algorithms import dot


def sigmoid(value: float) -> float:
    numeric = float(value)
    if numeric >= 0:
        return 1.0 / (1.0 + math.exp(-numeric))
    exp_value = math.exp(numeric)
    return exp_value / (1.0 + exp_value)


def tanh_vector(values: Sequence[float]) -> list[float]:
    return [math.tanh(float(value)) for value in values]


def softmax(values: Sequence[float]) -> list[float]:
    numbers = [float(value) for value in values]
    if not numbers:
        raise ValueError("values must not be empty")
    max_value = max(numbers)
    exps = [math.exp(value - max_value) for value in numbers]
    total = sum(exps)
    return [value / total for value in exps]


def dense_gate(
    x_t: Sequence[float],
    h_prev: Sequence[float],
    weights_x: Sequence[float],
    weights_h: Sequence[float],
    bias: float,
    activation: str,
) -> float:
    z_value = dot(x_t, weights_x) + dot(h_prev, weights_h) + float(bias)
    if activation == "sigmoid":
        return sigmoid(z_value)
    if activation == "tanh":
        return math.tanh(z_value)
    raise ValueError("activation must be sigmoid or tanh")


def lstm_scalar_step(
    x_t: Sequence[float],
    h_prev: Sequence[float],
    c_prev: float,
    weights: dict[str, Sequence[float]],
    recurrent_weights: dict[str, Sequence[float]],
    biases: dict[str, float],
) -> dict[str, float]:
    forget_gate = dense_gate(
        x_t,
        h_prev,
        weights["forget"],
        recurrent_weights["forget"],
        biases.get("forget", 0.0),
        "sigmoid",
    )
    input_gate = dense_gate(
        x_t,
        h_prev,
        weights["input"],
        recurrent_weights["input"],
        biases.get("input", 0.0),
        "sigmoid",
    )
    candidate = dense_gate(
        x_t,
        h_prev,
        weights["candidate"],
        recurrent_weights["candidate"],
        biases.get("candidate", 0.0),
        "tanh",
    )
    output_gate = dense_gate(
        x_t,
        h_prev,
        weights["output"],
        recurrent_weights["output"],
        biases.get("output", 0.0),
        "sigmoid",
    )
    c_t = forget_gate * float(c_prev) + input_gate * candidate
    h_t = output_gate * math.tanh(c_t)
    return {
        "forget_gate": forget_gate,
        "input_gate": input_gate,
        "candidate": candidate,
        "output_gate": output_gate,
        "cell_state": c_t,
        "hidden_state": h_t,
    }


def attention_weights(
    hidden_states: Sequence[Sequence[float]],
    query: Sequence[float],
) -> list[float]:
    states = [[float(value) for value in state] for state in hidden_states]
    if not states:
        raise ValueError("hidden_states must not be empty")
    scores = [dot(state, query) for state in states]
    return softmax(scores)


def attention_context(
    hidden_states: Sequence[Sequence[float]],
    weights: Sequence[float],
) -> list[float]:
    states = [[float(value) for value in state] for state in hidden_states]
    attention = [float(value) for value in weights]
    if len(states) != len(attention) or not states:
        raise ValueError("hidden_states and weights must be aligned")
    width = len(states[0])
    if any(len(state) != width for state in states):
        raise ValueError("hidden states must have the same width")
    return [
        sum(weight * state[index] for state, weight in zip(states, attention))
        for index in range(width)
    ]
