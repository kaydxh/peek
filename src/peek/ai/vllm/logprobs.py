# -*- coding: utf-8 -*-
"""vLLM Logprobs 工具 - 二分类预测解析

从 ChatCompletionResponse 中提取 logprobs，计算二分类概率并应用阈值判定。
适用于 TRUE/FALSE 等二分类场景（如一致性审核、合规审核等）。
"""

import logging
import math
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BinaryClassificationResult:
    """二分类预测结果"""

    prediction: Optional[str] = None  # 预测标签（如 "TRUE" / "FALSE"）
    positive_score: Optional[float] = None  # 正类概率 P(positive_label)
    negative_score: Optional[float] = None  # 负类概率 P(negative_label)
    is_positive: bool = False  # 是否为正类


def extract_prediction_from_token(
    token: str,
    positive_label: str = "TRUE",
    negative_label: str = "FALSE",
) -> Optional[str]:
    """从 token 字符串中提取预测标签。

    Args:
        token: token 文本
        positive_label: 正类标签
        negative_label: 负类标签

    Returns:
        匹配到的标签，或 None
    """
    token_upper = (token or "").upper()
    if negative_label.upper() in token_upper:
        return negative_label
    if positive_label.upper() in token_upper:
        return positive_label
    return None


def extract_prediction_from_text(
    text: str,
    positive_label: str = "TRUE",
    negative_label: str = "FALSE",
) -> Optional[str]:
    """从文本内容中提取预测标签。

    支持 <|TRUE|> / <|FALSE|> 格式和普通文本匹配。

    Args:
        text: 响应文本内容
        positive_label: 正类标签
        negative_label: 负类标签

    Returns:
        匹配到的标签，或 None
    """
    text_upper = (text or "").upper()
    for label in (positive_label, negative_label):
        if f"<|{label.upper()}|>" in text_upper:
            return label
    return extract_prediction_from_token(text, positive_label, negative_label)


def extract_binary_logprobs(
    choice,
    positive_label: str = "TRUE",
    negative_label: str = "FALSE",
) -> Tuple[Optional[str], Optional[float]]:
    """从 Choice 对象中提取二分类 logprobs，计算负类概率。

    Args:
        choice: peek.ai.vllm.types.Choice 对象
        positive_label: 正类标签
        negative_label: 负类标签

    Returns:
        (prediction, negative_score): 预测标签和负类概率 P(negative_label)
    """
    logprobs = choice.logprobs
    if logprobs is None or logprobs.content is None or not logprobs.content:
        return None, None

    first_entry = logprobs.content[0]
    first_token = first_entry.token
    prediction = extract_prediction_from_token(first_token, positive_label, negative_label)

    # 收集 logprobs
    token_logprobs: Dict[str, float] = {}
    if first_entry.top_logprobs:
        for item in first_entry.top_logprobs:
            pred = extract_prediction_from_token(item.token, positive_label, negative_label)
            if pred and pred not in token_logprobs and item.logprob is not None:
                token_logprobs[pred] = float(item.logprob)

    # 补充 first token 的 logprob
    first_pred = extract_prediction_from_token(first_token, positive_label, negative_label)
    if first_pred and first_pred not in token_logprobs and first_entry.logprob is not None:
        token_logprobs[first_pred] = float(first_entry.logprob)

    # 计算负类概率
    negative_score = None
    neg_key = negative_label.upper()

    if neg_key in token_logprobs and len(token_logprobs) >= 2:
        # softmax 归一化
        mx = max(token_logprobs.values())
        exps = {k: math.exp(v - mx) for k, v in token_logprobs.items()}
        total = sum(exps.values())
        negative_score = float(exps[neg_key] / total) if total else None
    elif neg_key in token_logprobs:
        negative_score = 1.0
    elif token_logprobs:
        negative_score = 0.0

    return prediction, negative_score


def parse_binary_classification(
    response,
    positive_label: str = "TRUE",
    negative_label: str = "FALSE",
) -> BinaryClassificationResult:
    """解析 ChatCompletionResponse，提取二分类预测结果。

    Args:
        response: peek.ai.vllm.types.ChatCompletionResponse 对象
        positive_label: 正类标签
        negative_label: 负类标签

    Returns:
        BinaryClassificationResult: 二分类预测结果
    """
    if not response.choices:
        return BinaryClassificationResult(
            prediction=None,
            negative_score=1.0,
            positive_score=0.0,
            is_positive=False,
        )

    choice = response.choices[0]
    prediction, negative_score = extract_binary_logprobs(choice, positive_label, negative_label)
    content = (choice.message.content or "").strip()

    # 如果 logprobs 未能提取预测，从文本中提取
    if prediction is None:
        prediction = extract_prediction_from_text(content, positive_label, negative_label)

    # 计算分数
    if negative_score is not None:
        positive_score = 1.0 - negative_score
    else:
        positive_score = 1.0 if prediction == positive_label else 0.0
        negative_score = 1.0 - positive_score

    is_positive = prediction == positive_label

    return BinaryClassificationResult(
        prediction=prediction,
        positive_score=positive_score,
        negative_score=negative_score,
        is_positive=is_positive,
    )


def apply_threshold(
    result: BinaryClassificationResult,
    threshold: float,
    positive_label: str = "TRUE",
    negative_label: str = "FALSE",
) -> BinaryClassificationResult:
    """按负类概率阈值改写判定结果。

    negative_score > threshold → 判定为负类，否则为正类。

    Args:
        result: 原始二分类结果
        threshold: 负类概率阈值
        positive_label: 正类标签
        negative_label: 负类标签

    Returns:
        BinaryClassificationResult: 应用阈值后的结果
    """
    if result.negative_score is None:
        return result

    is_positive = float(result.negative_score) <= float(threshold)
    prediction = positive_label if is_positive else negative_label

    return BinaryClassificationResult(
        prediction=prediction,
        positive_score=result.positive_score,
        negative_score=result.negative_score,
        is_positive=is_positive,
    )
