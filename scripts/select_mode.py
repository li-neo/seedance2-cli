#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seedance-2 自动模式选择与输入解析模块。

本模块负责：
- 统一解析多模态素材（图片 / 视频 / 音频等）
- 根据素材组合与文本提示自动判定视频生成模式
- 给出带置信度的决策结果，用于上层流水线路由

设计目标：
- 保持对外接口简单稳定：核心对外函数以纯 Python 类型（dataclass）为主
- 与现有脚本解耦：不直接依赖 Ark/TOS/Assets 等外部服务
- 可单独被单元测试调用（见 scripts/tests/test_pipeline.py 中的 `_select_mode` 用例）
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional


# -----------------------------
# 数据结构定义
# -----------------------------


@dataclass(frozen=True)
class Material:
    """单个输入素材的抽象表示。

    Attributes:
        path: 原始路径或 URL
        kind: 解析出的素材类型：image / video / audio / pose / segmentation / other
        source: 来自哪个参数，例如 first_frame / last_frame / reference_image / reference_video / reference_audio
        is_local: 是否为本地路径（非 http/https/asset://）
    """

    path: str
    kind: str
    source: str
    is_local: bool = False


@dataclass(frozen=True)
class ModeDecision:
    """模式选择结果。

    Attributes:
        mode: 细分模式标签，例如 t2v / i2v / fl2v / multi_i2v / multimodal_ref2v
        confidence: 0.0~1.0 的置信度分数
        reason: 文本化决策理由，便于上层日志输出
        warnings: 附加告警信息列表，例如输入缺失、模式退化说明等
        counts: 各类素材数量统计，便于后续判断和路由
    """

    mode: str
    confidence: float
    reason: str
    warnings: List[str]
    counts: Dict[str, int]

    @property
    def seedance_mode(self) -> str:
        """映射为 Seedance API 使用的核心模式。

        Seedance API 当前公开模式主要为：t2v / i2v / fl2v / multimodal_ref2v。
        本地细分模式（如 multi_i2v）在这里统一映射为最接近的 API 模式，
        仅影响内容拼装，不改变外部服务接口。

        额外规则：当仅存在音频参考而无任何图像/视频时，为避免调用
        Seedance CLI 中对纯音频多模态模式的限制，会退化为 t2v，交由上层决定
        是否在提示词中补充“参考音频”的文字描述。
        """

        # 明确的基础模式直接透传
        if self.mode in {"t2v", "i2v", "fl2v"}:
            return self.mode

        # 多模态参考模式：对“纯音频”场景进行特殊降级处理
        if self.mode == "multimodal_ref2v":
            img = self.counts.get("image_like", 0)
            vid = self.counts.get("video", 0)
            aud = self.counts.get("audio", 0)
            if img == 0 and vid == 0 and aud > 0:
                # 仅有音频参考时退化为 t2v，以避免底层 Seedance CLI 对纯音频
                # multimodal_ref2v 的限制造成硬错误。
                return "t2v"
            return "multimodal_ref2v"

        # 多图 i2v 统一走多模态参考分支
        if self.mode == "multi_i2v":
            return "multimodal_ref2v"

        # 极端兜底：当出现未知标签时退化为 t2v，保证不会构造非法参数
        return "t2v"


# -----------------------------
# 基础判定工具
# -----------------------------

_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
_AUDIO_EXT = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".flac"}


def kind_from_path(path: str) -> str:
    """根据文件扩展名和命名模式推断素材类型。

    - 标准类型：image / video / audio
    - 特殊子类：pose / segmentation（基于文件名关键词识别）
    - 不支持的扩展名会抛出 ValueError（用于单元测试严格校验）
    """

    # 仅根据路径字符串推断，不做存在性检查
    lower = path.lower()
    _, ext = os.path.splitext(lower)

    # 先基于扩展名判定粗粒度类型
    if ext in _IMAGE_EXT:
        # 进一步根据文件名关键词区分姿态图 / 分割图（仅影响日志与文档归类）
        if any(tag in lower for tag in ["_pose", "pose_", "_skeleton", "skeleton_"]):
            return "pose"
        if any(tag in lower for tag in ["_seg", "seg_", "_mask", "mask_"]):
            return "segmentation"
        return "image"

    if ext in _VIDEO_EXT:
        return "video"

    if ext in _AUDIO_EXT:
        return "audio"

    raise ValueError(f"无法从路径推断素材类型（不支持的扩展名）: {path}")


def _is_local_path(p: str) -> bool:
    return not (p.startswith("http://") or p.startswith("https://") or p.startswith("asset://"))


# -----------------------------
# 从 CLI 参数构造素材列表
# -----------------------------


def build_materials_from_args(args) -> List[Material]:  # pragma: no cover - 简单组装函数
    """从 argparse.Namespace 构造素材列表。

    约定使用以下字段（若不存在则视为缺省）：
        - first_frame, last_frame: 单帧关键帧
        - reference_image: List[str]
        - reference_video: List[str]
        - reference_audio: List[str]
    """

    materials: List[Material] = []

    def add_one(path: Optional[str], source: str) -> None:
        if not path:
            return
        try:
            kind = kind_from_path(path)
        except ValueError:
            # 不支持的扩展名：归类为 other，但仍保留原始路径，交由上层决定是否忽略
            kind = "other"
        materials.append(Material(path=path, kind=kind, source=source, is_local=_is_local_path(path)))

    # 单帧参数
    add_one(getattr(args, "first_frame", None), "first_frame")
    add_one(getattr(args, "last_frame", None), "last_frame")

    # 列表参数
    for p in getattr(args, "reference_image", []) or []:
        add_one(p, "reference_image")
    for p in getattr(args, "reference_video", []) or []:
        add_one(p, "reference_video")
    for p in getattr(args, "reference_audio", []) or []:
        add_one(p, "reference_audio")

    return materials


# -----------------------------
# 模式判定主逻辑
# -----------------------------


def _count_materials(materials: List[Material]) -> Dict[str, int]:
    counts: Dict[str, int] = {
        "image_like": 0,  # image / pose / segmentation
        "video": 0,
        "audio": 0,
        "other": 0,
    }
    for m in materials:
        if m.kind in {"image", "pose", "segmentation"}:
            counts["image_like"] += 1
        elif m.kind == "video":
            counts["video"] += 1
        elif m.kind == "audio":
            counts["audio"] += 1
        else:
            counts["other"] += 1
    return counts


def select_mode_from_materials(
    materials: List[Material], *, text_present: bool
) -> ModeDecision:
    """根据素材组合和文本提示自动判定模式。

    规则说明（优先级从高到低）：
    1. 无任何素材：
       - 有文本 → t2v
       - 无文本 → t2v（置信度较低，并给出告警）
    2. 视频 + 文本 → multimodal_ref2v（视频续写/编辑）
    3. 只有视频（1 个） → multimodal_ref2v（视频续写/编辑）
    4. 只有图片：
       - 1 张 → i2v
       - 2 张 → fl2v
       - ≥3 张 → multi_i2v
    5. 存在多种模态（图片 / 视频 / 音频 任意组合）→ multimodal_ref2v
    6. 只有音频 → multimodal_ref2v（但会标记为低置信度，推荐补充画面参考）
    """

    counts = _count_materials(materials)
    img = counts["image_like"]
    vid = counts["video"]
    aud = counts["audio"]

    warnings: List[str] = []

    # 1) 无任何素材
    if img == 0 and vid == 0 and aud == 0:
        if text_present:
            return ModeDecision(
                mode="t2v",
                confidence=0.95,
                reason="仅检测到文本提示，未发现图片/视频/音频素材，按文生视频处理。",
                warnings=warnings,
                counts=counts,
            )
        warnings.append("未检测到文本提示或任何参考素材，将退化为文生视频模式，生成结果高度依赖模型默认行为。")
        return ModeDecision(
            mode="t2v",
            confidence=0.6,
            reason="既没有文本也没有多模态素材，退化为 t2v 兜底。",
            warnings=warnings,
            counts=counts,
        )

    # 2) 视频 + 文本 → multimodal_ref2v（视频续写/编辑）
    if vid >= 1 and img == 0 and text_present:
        warnings.append(
            "视频+文本为“续写/编辑”，不等同于“换脸/换角色”。如需更强的人物控制，建议同时提供参考图片。"
        )
        return ModeDecision(
            mode="multimodal_ref2v",
            confidence=0.95,
            reason="检测到视频 + 文本参考，按多模态参考（续写/编辑）处理。",
            warnings=warnings,
            counts=counts,
        )

    # 3) 单视频纯参考 → multimodal_ref2v（视频续写/编辑）
    if vid == 1 and img == 0 and aud == 0:
        return ModeDecision(
            mode="multimodal_ref2v",
            confidence=0.95,
            reason="检测到 1 个视频参考且无其他素材，按多模态参考模式进行视频续写/编辑处理。",
            warnings=warnings,
            counts=counts,
        )

    # 4) 只有图片
    if vid == 0 and aud == 0 and img > 0:
        if img == 1:
            return ModeDecision(
                mode="i2v",
                confidence=0.95,
                reason="检测到 1 张图片参考，无视频/音频，按图生视频（单首帧）处理。",
                warnings=warnings,
                counts=counts,
            )
        if img == 2:
            return ModeDecision(
                mode="fl2v",
                confidence=0.95,
                reason="检测到 2 张图片参考，无视频/音频，按首尾帧图生视频处理。",
                warnings=warnings,
                counts=counts,
            )
        # 3 张及以上图片 → multi_i2v
        return ModeDecision(
            mode="multi_i2v",
            confidence=0.9,
            reason="检测到 ≥3 张图片参考，无视频/音频，按多图驱动的图生视频序列处理。",
            warnings=warnings,
            counts=counts,
        )

    # 5) 只有音频
    if img == 0 and vid == 0 and aud > 0:
        warnings.append(
            "仅检测到音频参考，Seedance 2.0 对纯音频驱动的生成能力有限，建议同时提供至少一张图片或一个视频以增强可控性。"
        )
        return ModeDecision(
            mode="multimodal_ref2v",
            confidence=0.6,
            reason="仅有音频参考，按多模态参考生视频处理并给出稳定性告警。",
            warnings=warnings,
            counts=counts,
        )

    # 6) 其他任意多模态组合 → multimodal_ref2v
    return ModeDecision(
        mode="multimodal_ref2v",
        confidence=0.9,
        reason="检测到图片/视频/音频的混合输入，按多模态参考生视频模式处理。",
        warnings=warnings,
        counts=counts,
    )


# -----------------------------
# 为现有单元测试提供的简单包装
# -----------------------------


def simple_select_mode(materials: List[Material]) -> str:
    """兼容 scripts/tests/test_pipeline.py 中使用的 `_select_mode` 接口。

    仅返回模式字符串，不暴露置信度与统计信息，方便做表驱动测试。
    """

    decision = select_mode_from_materials(materials, text_present=False)
    return decision.mode


__all__ = [
    "Material",
    "ModeDecision",
    "kind_from_path",
    "build_materials_from_args",
    "select_mode_from_materials",
    "simple_select_mode",
]
