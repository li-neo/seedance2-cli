#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多模态大模型理解 CLI (VLM)

支持：图片理解、视频理解、文档理解、音频理解
所有调用均基于火山引擎 Ark Runtime Responses API 实现。

特点：
- 所有逻辑封装在 VolcVLM 类内。
- 自动识别输入媒体类型（基于文件后缀或 URL）。
- 如果输入是本地文件，且属于 视频/文档/音频，会自动调用 Files API 上传并获取 file_id 后再发起推理。
- 对于图片（或较小的其他文件），如果未提供 URL，也可使用 Base64 编码方式传入（本脚本默认优先使用 URL 或 File API 上传，图片直接使用 Base64 兜底）。
"""

import argparse
import base64
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from volcenginesdkarkruntime import Ark


class VolcVLM:
    _IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    _VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    _AUDIO_EXT = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".flac"}
    _DOC_EXT = {".pdf"}

    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_url = (api_url or os.environ.get("VOLC_ARK_API_URL", "https://ark.cn-beijing.volces.com/api/v3")).strip()
        self.api_key = (api_key or os.environ.get("VOLC_ARK_API_KEY", "")).strip()
        self.model = (model or os.environ.get("VOLC_ARK_VLM_MODEL", "")).strip()

        missing_envs = []
        if not self.api_key:
            missing_envs.append("VOLC_ARK_API_KEY")
        if not self.model:
            missing_envs.append("VOLC_ARK_VLM_MODEL")
        if missing_envs:
            raise ValueError(f"请一次性设置以下环境变量: {', '.join(missing_envs)}")

        self.client = Ark(base_url=self.api_url, api_key=self.api_key)

    @classmethod
    def guess_media_type(cls, path_or_url: str) -> str:
        """根据后缀猜测媒体类型"""
        path = urlparse(path_or_url).path or ""
        _, ext = os.path.splitext(path.lower())
        
        if ext in cls._IMAGE_EXT:
            return "image"
        if ext in cls._VIDEO_EXT:
            return "video"
        if ext in cls._AUDIO_EXT:
            return "audio"
        if ext in cls._DOC_EXT:
            return "file"
        
        # 默认回退
        return "image"

    def upload_file_if_needed(self, path: str, media_type: str) -> Optional[str]:
        """
        上传本地文件到 Files API 并返回 file_id。
        对于视频、文档、音频，官方推荐使用 Files API 上传。
        对于图片，可以直接转 Base64，无需 Files API。
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"本地文件不存在: {path}")

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 正在上传本地 {media_type} 到方舟 Files API...", file=sys.stderr)
        
        # 构建预处理配置
        preprocess_configs = None
        if media_type == "video":
            # 官方推荐的视频预处理抽帧 fps 配置，可根据需要调整
            preprocess_configs = {"video": {"fps": 1.0}}
            
        with open(path, "rb") as f:
            file_resp = self.client.files.create(
                file=f,
                purpose="user_data",
                preprocess_configs=preprocess_configs
            )
            
        file_id = file_resp.id
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 文件上传成功，ID: {file_id}，等待云端处理完成...", file=sys.stderr)
        
        # 阻塞等待文件处理完成
        self.client.files.wait_for_processing(file_id)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 文件云端处理完毕，可用于推理。", file=sys.stderr)
        
        return file_id

    @staticmethod
    def encode_image_to_base64(image_path: str) -> str:
        """将本地图片转为 Base64 data URI 格式"""
        with open(image_path, "rb") as image_file:
            b64_data = base64.b64encode(image_file.read()).decode("utf-8")
            
        _, ext = os.path.splitext(image_path.lower())
        mime_type = "image/jpeg"
        if ext == ".png":
            mime_type = "image/png"
        elif ext == ".webp":
            mime_type = "image/webp"
        elif ext == ".gif":
            mime_type = "image/gif"
            
        return f"data:{mime_type};base64,{b64_data}"

    def build_message_content(self, text: str, media_inputs: List[str]) -> List[Dict[str, Any]]:
        """
        根据媒体类型和来源（本地/URL）构建 Responses API 所需的 input content
        """
        content_list: List[Dict[str, Any]] = []
        
        for media in media_inputs:
            is_url = media.startswith("http://") or media.startswith("https://")
            media_type = self.guess_media_type(media)
            
            if media_type == "image":
                if is_url:
                    content_list.append({
                        "type": "input_image",
                        "image_url": media
                    })
                else:
                    b64_url = self.encode_image_to_base64(media)
                    content_list.append({
                        "type": "input_image",
                        "image_url": b64_url
                    })
            else:
                # 视频 / 文档(PDF) / 音频
                type_mapping = {
                    "video": "input_video",
                    "audio": "input_audio",
                    "file": "input_file"
                }
                content_type = type_mapping[media_type]
                
                if is_url:
                    # 官方文档：支持视频/音频 URL 直接传入
                    # 但文档输入仅支持 Files API 和 Base64，不支持直接传 URL，此处为了泛用性统一当 URL 传尝试
                    url_key = "video_url" if media_type == "video" else "audio_url" if media_type == "audio" else "file_url"
                    content_list.append({
                        "type": content_type,
                        url_key: media
                    })
                else:
                    # 本地大文件走 Files API 上传
                    file_id = self.upload_file_if_needed(media, media_type)
                    content_list.append({
                        "type": content_type,
                        "file_id": file_id
                    })

        # 追加文本指令
        if text:
            content_list.append({
                "type": "input_text",
                "text": text
            })
            
        return content_list

    def understand(self, text: str, media_inputs: List[str]) -> str:
        """
        发起 Responses API 推理请求
        """
        if not text and not media_inputs:
            raise ValueError("文本指令和媒体输入不能同时为空")

        contents = self.build_message_content(text, media_inputs)
        
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 正在请求模型 {self.model} 进行理解分析...", file=sys.stderr)
        
        try:
            response = self.client.responses.create(
                model=self.model,
                input=[
                    {
                        "role": "user",
                        "content": contents
                    }
                ]
            )
        except Exception as e:
            raise RuntimeError(f"API 请求失败: {str(e)}")
        
        # 解析 Responses API 新版的输出结构
        # 返回对象通常有一个 output 列表，里面包含推理过程（ResponseReasoningItem）和最终回答（ResponseOutputMessage）
        if hasattr(response, "output") and isinstance(response.output, list):
            for item in response.output:
                # 寻找 type 为 'message' 的对象，通常是 ResponseOutputMessage
                if getattr(item, "type", "") == "message" and hasattr(item, "content"):
                    content_list = item.content
                    if isinstance(content_list, list):
                        texts = []
                        for block in content_list:
                            # 提取 ResponseOutputText 中的 text
                            if getattr(block, "type", "") == "output_text" and hasattr(block, "text"):
                                texts.append(block.text)
                        if texts:
                            return "".join(texts)

        # 兼容普通的 Chat completions 格式 (若存在 choices)
        if hasattr(response, "choices") and response.choices:
            msg = getattr(response.choices[0], "message", None)
            if msg:
                if hasattr(msg, "content"):
                    if hasattr(msg.content, "string_value") and msg.content.string_value:
                        return msg.content.string_value
                    if isinstance(msg.content, str):
                        return msg.content
                    return str(msg.content)
                if hasattr(msg, "text") and msg.text:
                    return msg.text
        
        # 兜底：尝试从顶层的 text 属性取
        if hasattr(response, "text") and response.text:
            return response.text
            
        # 终极兜底直接打印完整的对象
        print(f"[Debug] 未能精准解析返回值内容，原始返回对象：\n{response}", file=sys.stderr)
        return str(response)

    @classmethod
    def build_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="多模态大模型理解 CLI (支持图片/视频/文档/音频)")
        parser.add_argument("--text", "-t", required=True, help="输入的指令/提问文本（如：'请描述图片内容'）")
        parser.add_argument("--media", "-m", action="append", default=[], help="要分析的媒体路径或 URL（可多次指定），自动识别 图片/视频/PDF/音频")
        parser.add_argument("--model", help="指定模型版本（默认读取 VOLC_ARK_VLM_MODEL）")
        return parser

    @classmethod
    def main(cls, argv=None) -> None:
        args = cls.build_parser().parse_args(argv)
        
        try:
            vlm = cls(model=args.model)
            result = vlm.understand(text=args.text, media_inputs=args.media)
            
            # 将模型的回答输出到标准输出
            print(result)
            
        except Exception as e:
            print(f"❌ 运行失败: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    VolcVLM.main()
