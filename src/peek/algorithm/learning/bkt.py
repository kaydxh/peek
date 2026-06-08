#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bayesian Knowledge Tracing (BKT)

Estimates probability of student knowledge mastery based on observed evidence.

Core formulas:
- On correct: P(L|correct) = P(L)*(1-P(S)) / P(correct)
- On incorrect: P(L|incorrect) = P(L)*P(S) / P(incorrect)
- After observation: P(L_n) = P(L|obs) + (1 - P(L|obs)) * P(T)

Reference: Corbett & Anderson, 1994

This module is domain-agnostic: works with any knowledge-tracing scenario
where binary correct/incorrect outcomes are observed.
"""

from dataclasses import dataclass


@dataclass
class BKTParams:
    """BKT model parameters for a single knowledge component.

    Attributes:
        p_mastery: P(L) current mastery probability [0, 1]
        p_transit: P(T) probability of learning on each opportunity [0, 1]
        p_guess: P(G) probability of correct guess when not mastered [0, 1]
        p_slip: P(S) probability of slip when mastered [0, 1]
    """

    p_mastery: float = 0.1
    p_transit: float = 0.1
    p_guess: float = 0.2
    p_slip: float = 0.1


def bkt_update(params: BKTParams, correct: bool) -> BKTParams:
    """Update mastery probability given new evidence.

    Pure function. Does not modify input params.

    Args:
        params: current BKT parameters
        correct: whether the student answered correctly

    Returns:
        New BKTParams with updated p_mastery
    """
    p_l = params.p_mastery
    p_t = params.p_transit
    p_g = params.p_guess
    p_s = params.p_slip

    if correct:
        # P(correct) = P(L)*(1-P(S)) + (1-P(L))*P(G)
        p_obs = p_l * (1 - p_s) + (1 - p_l) * p_g
        # P(L | correct)
        p_l_given_obs = (p_l * (1 - p_s)) / p_obs if p_obs > 0 else p_l
    else:
        # P(incorrect) = P(L)*P(S) + (1-P(L))*(1-P(G))
        p_obs = p_l * p_s + (1 - p_l) * (1 - p_g)
        # P(L | incorrect)
        p_l_given_obs = (p_l * p_s) / p_obs if p_obs > 0 else p_l

    # Learning transition: P(L_n) = P(L|obs) + (1 - P(L|obs)) * P(T)
    p_l_new = p_l_given_obs + (1 - p_l_given_obs) * p_t
    p_l_new = max(0.0, min(1.0, p_l_new))

    return BKTParams(
        p_mastery=p_l_new,
        p_transit=p_t,
        p_guess=p_g,
        p_slip=p_s,
    )


def mastery_to_quality(p_mastery: float, correct: bool) -> int:
    """Map mastery probability + correctness to SM-2 quality rating (0-5).

    Mapping logic:
    - correct + high mastery -> 5 (perfect response)
    - correct + low mastery -> 3 (correct with difficulty)
    - incorrect + high mastery -> 2 (slip)
    - incorrect + low mastery -> 0 (blackout)

    Args:
        p_mastery: current mastery probability [0, 1]
        correct: whether student answered correctly

    Returns:
        SM-2 quality rating (0-5)
    """
    if correct:
        if p_mastery >= 0.8:
            return 5
        elif p_mastery >= 0.6:
            return 4
        else:
            return 3
    else:
        if p_mastery >= 0.7:
            return 2
        elif p_mastery >= 0.4:
            return 1
        else:
            return 0
