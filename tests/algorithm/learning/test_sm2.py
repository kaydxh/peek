#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for peek SM-2 algorithm."""

import pytest

from peek.algorithm.learning.sm2 import SM2State, sm2_next_review


class TestSM2NextReview:
    """Test SM-2 scheduling logic."""

    def test_failure_resets_repetition(self):
        """Quality < 3 resets repetition count and interval to 1."""
        state = SM2State(interval_days=6.0, easiness=2.5, repetition_count=3, quality=4)
        result = sm2_next_review(state, quality=2)

        assert result.repetition_count == 0
        assert result.interval_days == 1.0
        assert result.quality == 2

    def test_first_success_interval_1(self):
        """First success: interval = 1 day."""
        state = SM2State(interval_days=1.0, easiness=2.5, repetition_count=0, quality=0)
        result = sm2_next_review(state, quality=4)

        assert result.repetition_count == 1
        assert result.interval_days == 1.0

    def test_second_success_interval_6(self):
        """Second success: interval = 6 days."""
        state = SM2State(interval_days=1.0, easiness=2.5, repetition_count=1, quality=4)
        result = sm2_next_review(state, quality=4)

        assert result.repetition_count == 2
        assert result.interval_days == 6.0

    def test_third_success_grows_by_ef(self):
        """Third+ success: interval *= EF."""
        state = SM2State(interval_days=6.0, easiness=2.5, repetition_count=2, quality=4)
        result = sm2_next_review(state, quality=4)

        assert result.repetition_count == 3
        assert result.interval_days == 6.0 * 2.5

    def test_easiness_never_below_1_3(self):
        """EF minimum clamp at 1.3."""
        state = SM2State(interval_days=1.0, easiness=1.3, repetition_count=0, quality=0)
        result = sm2_next_review(state, quality=0)

        assert result.easiness >= 1.3

    def test_perfect_response_increases_ef(self):
        """Quality 5 increases easiness factor."""
        state = SM2State(interval_days=1.0, easiness=2.5, repetition_count=0, quality=0)
        result = sm2_next_review(state, quality=5)

        assert result.easiness > 2.5

    def test_quality_clamped_to_0_5(self):
        """Quality values outside 0-5 get clamped."""
        state = SM2State()
        result_low = sm2_next_review(state, quality=-1)
        result_high = sm2_next_review(state, quality=10)

        assert result_low.quality == 0
        assert result_high.quality == 5

    def test_pure_function_no_mutation(self):
        """Input state not modified."""
        state = SM2State(interval_days=6.0, easiness=2.5, repetition_count=2, quality=4)
        sm2_next_review(state, quality=5)

        assert state.interval_days == 6.0
        assert state.repetition_count == 2
