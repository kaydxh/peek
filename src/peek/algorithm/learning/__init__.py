#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Package learning provides educational learning algorithms.

Includes:
- BKT (Bayesian Knowledge Tracing): knowledge mastery estimation
- SM-2 (SuperMemo 2): spaced repetition scheduling
"""

from peek.algorithm.learning.bkt import (
    BKTParams,
    bkt_update,
    mastery_to_quality,
)
from peek.algorithm.learning.sm2 import (
    SM2State,
    sm2_next_review,
)

__all__ = [
    "BKTParams",
    "bkt_update",
    "mastery_to_quality",
    "SM2State",
    "sm2_next_review",
]
