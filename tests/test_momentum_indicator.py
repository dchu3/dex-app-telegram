import math

import pytest

from momentum_indicator import calculate_momentum_score


def test_upward_oversold_scores_high():
    score, _ = calculate_momentum_score(
        volume_divergence=12.0,
        persistence_count=3,
        rsi_value=28.0,
        dominant_dex_has_lower_price=True,
    )
    assert score >= 8.0


def test_single_detection_low_flow_scores_low():
    score, _ = calculate_momentum_score(
        volume_divergence=1.2,
        persistence_count=1,
        rsi_value=52.0,
        dominant_dex_has_lower_price=True,
    )
    assert score < 4.0


def test_directional_rsi_alignment_changes_score():
    upward_score, _ = calculate_momentum_score(
        volume_divergence=10.0,
        persistence_count=1,
        rsi_value=66.0,
        dominant_dex_has_lower_price=True,
    )
    downward_score, _ = calculate_momentum_score(
        volume_divergence=10.0,
        persistence_count=1,
        rsi_value=66.0,
        dominant_dex_has_lower_price=False,
    )
    assert downward_score - upward_score >= 0.5


def test_infinite_volume_is_clamped():
    score, _ = calculate_momentum_score(
        volume_divergence=math.inf,
        persistence_count=5,
        rsi_value=85.0,
        dominant_dex_has_lower_price=False,
    )
    assert 0 <= score <= 10.0
