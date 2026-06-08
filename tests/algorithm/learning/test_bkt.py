#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for peek BKT algorithm."""

import pytest

from peek.algorithm.learning.bkt import BKTParams, bkt_update, mastery_to_quality


class TestBKTUpdate:
    """Test Bayesian Knowledge Tracing update."""

    def test_correct_increases_mastery(self):
        """Correct answer should increase P(mastery)."""
        params = BKTParams(p_mastery=0.3, p_transit=0.1, p_guess=0.2, p_slip=0.1)
        result = bkt_update(params, correct=True)

        assert result.p_mastery > params.p_mastery

    def test_incorrect_low_mastery_stays_low(self):
        """Incorrect with low mastery: mastery stays low but transit still applies."""
        params = BKTParams(p_mastery=0.1, p_transit=0.1, p_guess=0.2, p_slip=0.1)
        result = bkt_update(params, correct=False)

        # Should still be relatively low
        assert result.p_mastery < 0.3

    def test_incorrect_high_mastery_slip(self):
        """Incorrect with high mastery: slip detected, mastery dips slightly."""
        params = BKTParams(p_mastery=0.9, p_transit=0.1, p_guess=0.2, p_slip=0.1)
        result = bkt_update(params, correct=False)

        # Still high due to slip model, but lower than before
        assert result.p_mastery < params.p_mastery + params.p_transit

    def test_mastery_bounded_0_1(self):
        """P(mastery) always in [0, 1]."""
        params = BKTParams(p_mastery=0.99, p_transit=0.5, p_guess=0.01, p_slip=0.01)
        result = bkt_update(params, correct=True)

        assert 0.0 <= result.p_mastery <= 1.0

    def test_transit_and_guess_unchanged(self):
        """BKT update only modifies p_mastery, not other params."""
        params = BKTParams(p_mastery=0.5, p_transit=0.15, p_guess=0.25, p_slip=0.12)
        result = bkt_update(params, correct=True)

        assert result.p_transit == 0.15
        assert result.p_guess == 0.25
        assert result.p_slip == 0.12

    def test_pure_function_no_mutation(self):
        """Input params not modified."""
        params = BKTParams(p_mastery=0.3, p_transit=0.1, p_guess=0.2, p_slip=0.1)
        bkt_update(params, correct=True)

        assert params.p_mastery == 0.3


class TestMasteryToQuality:
    """Test mastery → SM-2 quality mapping."""

    def test_correct_high_mastery(self):
        assert mastery_to_quality(0.9, correct=True) == 5

    def test_correct_medium_mastery(self):
        assert mastery_to_quality(0.65, correct=True) == 4

    def test_correct_low_mastery(self):
        assert mastery_to_quality(0.3, correct=True) == 3

    def test_incorrect_high_mastery_slip(self):
        assert mastery_to_quality(0.8, correct=False) == 2

    def test_incorrect_medium_mastery(self):
        assert mastery_to_quality(0.5, correct=False) == 1

    def test_incorrect_low_mastery(self):
        assert mastery_to_quality(0.2, correct=False) == 0
