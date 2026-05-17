#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seedance-2 参数校验与标准化模块。

职责：
- 对关键参数（时长、分辨率、种子等）做范围校验与裁剪
- 为生成过程提供统一、安全的默认值
- 提供随机种子参数的基础策略与说明（默认保持 -1 由服务端采样随机种子）
- 提供对部分易不稳定能力的开关（如联网搜索），并集中输出友好日志

本模块只依赖标准库，便于在任何环境下被脚本直接导入使用。
"""

from __future__ import annotations

import os
from typing import List, Tuple


# 与 pipeline.py 保持同步的默认值
DEFAULT_DURATION = 15
DEFAULT_RATIO = "9:16"
DEFAULT_RESOLUTION = "720p"

MIN_DURATION = 4
MAX_DURATION = 15


class ValidationError(Exception):
    """用于在参数完全不可用时中断执行。

    当前流水线更偏向“裁剪 + 兜底”而非直接抛错，因此实际使用场景较少。
    """


def _normalize_duration(duration: int, messages: List[str]) -> int:
    """将 duration 规范化到安全范围内。

    约定：
    - -1 表示“交给模型自行决定”，保持原样
    - 其他值将被裁剪到 [MIN_DURATION, MAX_DURATION]
    """

    if duration == -1:
        return duration
    if MIN_DURATION <= duration <= MAX_DURATION:
        return duration
    clipped = max(MIN_DURATION, min(MAX_DURATION, duration))
    messages.append(
        f"参数 duration={duration} 超出安全范围 [{MIN_DURATION}, {MAX_DURATION}]，已裁剪为 {clipped}。"
    )
    return clipped


def _apply_seed_strategy(args, messages: List[str]) -> None:
    """处理随机种子参数。

    策略：
    - 若未显式指定 --seed（保持默认值 -1），则由服务端自行采样随机种子。
    - 若显式指定为其他整数，则原样透传，用于获得确定性结果。
    当前函数保留为扩展点，不对 args.seed 做任何修改。
    """

    # 当前不修改 args.seed，仅通过文档约定其含义
    return


def _apply_feature_toggles(args, messages: List[str]) -> None:
    """易不稳定能力的开关控制。

    当前支持：
    - SEEDANCE_DISABLE_WEB_SEARCH=1 时，无视 --web-search 参数，关闭联网搜索工具
    """

    disable_web_search = os.getenv("SEEDANCE_DISABLE_WEB_SEARCH", "0").strip()
    if disable_web_search in {"1", "true", "True"} and getattr(args, "web_search", False):
        args.web_search = False
        messages.append(
            "检测到环境变量 SEEDANCE_DISABLE_WEB_SEARCH=1，已强制关闭联网搜索工具以提升稳定性。"
        )


def _derive_timeout_settings(args, messages: List[str]) -> None:
    """根据环境变量得出等待超时时间与轮询间隔。

    提供软性护栏：
    - SEEDANCE_MAX_WAIT_SECONDS：整体等待上限，默认 1800 秒
    - SEEDANCE_POLL_INTERVAL_SECONDS：轮询间隔，默认 30 秒
    - SEEDANCE_POLL_REQUEST_TIMEOUT：单次请求超时，默认 60 秒

    这些值通过在 args 上挂载内部字段提供给调用方（例如 pipeline），不改变公开 CLI。
    调用方如未使用这些字段，则行为与原先保持一致。
    """

    def _int_env(name: str, default: int) -> int:
        raw = os.getenv(name)
        if not raw:
            return default
        try:
            return int(raw)
        except ValueError:
            messages.append(f"环境变量 {name}={raw!r} 非法，已回退为 {default}。")
            return default

    max_wait = _int_env("SEEDANCE_MAX_WAIT_SECONDS", 1800)
    poll_interval = _int_env("SEEDANCE_POLL_INTERVAL_SECONDS", 30)
    poll_timeout = _int_env("SEEDANCE_POLL_REQUEST_TIMEOUT", 60)

    # 保证合理下限
    max_wait = max(60, max_wait)
    poll_interval = max(5, poll_interval)
    poll_timeout = max(10, poll_timeout)

    setattr(args, "_wait_timeout", max_wait)
    setattr(args, "_poll_interval", poll_interval)
    setattr(args, "_poll_timeout", poll_timeout)


def normalize_and_validate_args(args) -> Tuple[object, List[str]]:
    """对 pipeline 的参数做标准化与校验。

    返回：
        (args, messages)
        - args: 经过就地修改后的同一对象（便于调用方继续使用）
        - messages: 规范化与修正过程中产生的提示信息，可统一打印到 stderr
    """

    messages: List[str] = []

    # 1) 关键参数范围校验
    args.duration = _normalize_duration(getattr(args, "duration", DEFAULT_DURATION), messages)

    # 2) 统一随机种子策略
    _apply_seed_strategy(args, messages)

    # 3) 特性开关
    _apply_feature_toggles(args, messages)

    # 4) 超时与轮询设置（通过内部属性提供给调用方）
    _derive_timeout_settings(args, messages)

    return args, messages


__all__ = [
    "ValidationError",
    "normalize_and_validate_args",
]
