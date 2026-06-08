#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SM-2 Spaced Repetition Algorithm

Calculates optimal review intervals based on recall quality.

Core rules:
- quality < 3: reset repetition=0, interval=1
- quality >= 3: interval grows by EF factor
- EF' = EF + (0.1 - (5-q)*(0.08+(5-q)*0.02))
- EF minimum = 1.3

Reference: Wozniak, 1990 (SuperMemo 2)

This module is domain-agnostic: works with any spaced repetition
scenario where quality ratings (0-5) are provided.
"""

from dataclasses import dataclass


@dataclass
class SM2State:
    """SM-2 scheduling state for a single item.

    Attributes:
        interval_days: days until next review
        easiness: EF (easiness factor), >= 1.3
        repetition_count: consecutive successful repetitions
        quality: last quality rating (0-5)
    """

    interval_days: float = 1.0
    easiness: float = 2.5
    repetition_count: int = 0
    quality: int = 0


def sm2_next_review(state: SM2State, quality: int) -> SM2State:
    """Calculate next review state given quality rating.

    Pure function. Does not modify input state.

    Args:
        state: current SM-2 state
        quality: answer quality (0-5)
            0 = complete blackout
            1 = incorrect, but recognized after
            2 = incorrect, but easy to recall
            3 = correct with serious difficulty
            4 = correct after hesitation
            5 = perfect response

    Returns:
        New SM2State with updated scheduling
    """
    quality = max(0, min(5, quality))

    repetition = state.repetition_count
    easiness = state.easiness
    interval = state.interval_days

    if quality < 3:
        # Failure: reset
        repetition = 0
        interval = 1.0
    else:
        # Success: grow interval
        if repetition == 0:
            interval = 1.0
        elif repetition == 1:
            interval = 6.0
        else:
            interval = interval * easiness
        repetition += 1

    # Update EF (Easiness Factor)
    easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    easiness = max(1.3, easiness)

    return SM2State(
        interval_days=interval,
        easiness=round(easiness, 4),
        repetition_count=repetition,
        quality=quality,
    )
