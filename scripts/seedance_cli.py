#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
seedance2-cli - Seedance-2 视频生成 CLI（env 配置版）。

特点：
- 所有功能封装在 `VolcSeeDanceAPI` 内
- 环境变量：
  - `VOLC_ARK_API_URL`（必需）
  - `VOLC_ARK_API_KEY`（必需）
  - `VOLC_ARK_SEEDANCE_MODEL`（必需）

成功输出：
- 默认仅输出 video_url
- 可选 `--json` 输出完整结果
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Literal, Optional

from volcenginesdkarkruntime import Ark


class VolcSeeDanceAPI:
    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_url = (api_url or os.environ.get("VOLC_ARK_API_URL", "")).strip()
        self.api_key = (api_key or os.environ.get("VOLC_ARK_API_KEY", "")).strip()
        self.model = (model or os.environ.get("VOLC_ARK_SEEDANCE_MODEL", "")).strip()

        missing_envs: List[str] = []

        if not self.api_url:
            missing_envs.append("VOLC_ARK_API_URL")
        if not self.api_key:
            missing_envs.append("VOLC_ARK_API_KEY")
        if not self.model:
            missing_envs.append("VOLC_ARK_SEEDANCE_MODEL")
        if missing_envs:
            raise ValueError(f"请一次性设置以下环境变量: {', '.join(missing_envs)}")

    @staticmethod
    def make_text_item(text: str) -> Dict[str, Any]:
        return {"type": "text", "text": text}

    @staticmethod
    def make_image_item(url: str, role: Optional[str] = None) -> Dict[str, Any]:
        item: Dict[str, Any] = {"type": "image_url", "image_url": {"url": url}}

        if role:
            item["role"] = role

        return item

    @staticmethod
    def make_video_item(url: str, role: Optional[str] = "reference_video") -> Dict[str, Any]:
        item: Dict[str, Any] = {"type": "video_url", "video_url": {"url": url}}

        if role:
            item["role"] = role

        return item

    @staticmethod
    def make_audio_item(url: str, role: Optional[str] = "reference_audio") -> Dict[str, Any]:
        item: Dict[str, Any] = {"type": "audio_url", "audio_url": {"url": url}}

        if role:
            item["role"] = role

        return item

    def _client(self, timeout: int) -> Ark:
        return Ark(base_url=self.api_url, api_key=self.api_key, timeout=timeout)

    def create_task(
        self,
        *,
        content: Optional[List[Dict[str, Any]]] = None,
        duration: int = 15,
        ratio: Literal["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"] = "9:16",
        resolution: Literal["480p", "720p", "1080p"] = "720p",
        generate_audio: bool = True,
        return_last_frame: bool = False,
        watermark: bool = False,
        seed: int = -1,
        safety_identifier: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        execution_expires_after: int = 172800,
        callback_url: Optional[str] = None,
        timeout: int = 60,
    ) -> str:
        if not content:
            raise ValueError("content 不能为空")

        client = self._client(timeout=timeout)
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "content": content,
            "duration": duration,
            "ratio": ratio,
            "resolution": resolution,
            "generate_audio": generate_audio,
            "return_last_frame": return_last_frame,
            "watermark": watermark,
            "seed": seed,
            "execution_expires_after": execution_expires_after,
        }

        if callback_url is not None:
            kwargs["callback_url"] = callback_url

        if tools is not None:
            kwargs["tools"] = tools

        if safety_identifier is not None:
            kwargs["safety_identifier"] = safety_identifier

        resp = client.content_generation.tasks.create(**kwargs)

        return resp.id

    def wait_task(self, *, task_id: str, interval: int, timeout: int, poll_timeout: int) -> Dict[str, Any]:
        client = self._client(timeout=poll_timeout)
        start = time.time()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 任务已提交，Task ID: {task_id}", file=sys.stderr)

        while True:
            elapsed = int(time.time() - start)

            if elapsed > timeout:
                raise TimeoutError(f"任务等待超时: {timeout}s")

            resp = client.content_generation.tasks.get(task_id=task_id)
            status = resp.status
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 任务状态: {status} | 已运行: {elapsed}s", file=sys.stderr)

            if status == "succeeded":
                video_url = None

                if hasattr(resp, "content") and resp.content:
                    content = resp.content

                    if hasattr(content, "video_url"):
                        video_url = content.video_url
                    elif isinstance(content, dict):
                        video_url = content.get("video_url")

                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 任务成功完成！", file=sys.stderr)

                return {"task_id": task_id, "status": status, "video_url": video_url}

            if status == "failed":
                err = getattr(resp, "error", None) or "Unknown error"
                raise RuntimeError(f"任务失败: {err}")

            time.sleep(interval)

    def generate_video(
        self,
        *,
        content: Optional[List[Dict[str, Any]]] = None,
        duration: int = 15,
        ratio: Literal["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"] = "9:16",
        resolution: Literal["480p", "720p", "1080p"] = "720p",
        generate_audio: bool = True,
        return_last_frame: bool = False,
        watermark: bool = False,
        seed: int = -1,
        safety_identifier: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        execution_expires_after: int = 172800,
        callback_url: Optional[str] = None,
        wait: bool = True,
        interval: int = 30,
        timeout: int = 3600,
        poll_timeout: int = 60,
    ) -> Dict[str, Any]:
        if not content:
            raise ValueError("content 不能为空")

        task_id = self.create_task(
            content=content,
            duration=duration,
            ratio=ratio,
            resolution=resolution,
            generate_audio=generate_audio,
            return_last_frame=return_last_frame,
            watermark=watermark,
            seed=seed,
            safety_identifier=safety_identifier,
            tools=tools,
            execution_expires_after=execution_expires_after,
            callback_url=callback_url,
            timeout=poll_timeout,
        )

        if not wait:
            return {"task_id": task_id, "status": "submitted"}

        return self.wait_task(task_id=task_id, interval=interval, timeout=timeout, poll_timeout=poll_timeout)

    @classmethod
    def build_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Seedance-2 video generation (env based).")

        # 核心内容参数
        parser.add_argument(
            "--mode",
            choices=["t2v", "i2v", "fl2v", "multimodal_ref2v"],
            required=True,
            help="生成模式：t2v (文生视频) / i2v (图生视频-首帧) / fl2v (图生视频-首尾帧) / multimodal_ref2v (多模态参考生视频)",
        )

        parser.add_argument("--text", help="输入的提示词文本（t2v 模式必填，其他模式可选）")
        parser.add_argument("--first-frame", help="首帧图片 URL / Base64 / 素材 ID（i2v / fl2v）")
        parser.add_argument("--last-frame", help="尾帧图片 URL / Base64 / 素材 ID（fl2v）")
        parser.add_argument("--reference-image", action="append", default=[], help="参考图片 URL / Base64 / 素材 ID（multimodal_ref2v 支持 0~9 个）")
        parser.add_argument("--reference-video", action="append", default=[], help="参考视频 URL / 素材 ID（multimodal_ref2v 支持 0~3 个）")
        parser.add_argument("--reference-audio", action="append", default=[], help="参考音频 URL / Base64 / 素材 ID（multimodal_ref2v 支持 0~3 个）")

        # 基础生成控制参数
        parser.add_argument("--duration", type=int, default=15, help="视频时长（秒），支持 4~15 或 -1（模型智能选择），默认 15")
        parser.add_argument(
            "--ratio",
            default="9:16",
            choices=["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"],
            help="视频宽高比，默认 9:16",
        )
        parser.add_argument(
            "--resolution",
            default="720p",
            choices=["480p", "720p", "1080p"],
            help="输出分辨率，默认 720p",
        )
        parser.add_argument(
            "--generate-audio",
            action=argparse.BooleanOptionalAction,
            default=True,
            help="是否生成音频，默认开启；可用 --no-generate-audio 关闭",
        )
        parser.add_argument("--return-last-frame", action="store_true", help="返回生成视频的尾帧图像")
        parser.add_argument("--watermark", action="store_true", help="生成视频是否包含水印")
        parser.add_argument("--seed", type=int, default=-1, help="种子整数，默认 -1")

        # 高级控制与安全参数
        parser.add_argument("--model", help="指定模型版本（默认读取 VOLC_ARK_SEEDANCE_MODEL）")
        parser.add_argument("--safety-identifier", help="终端用户的唯一标识符")
        parser.add_argument("--web-search", action="store_true", help="开启联网搜索工具")
        parser.add_argument("--execution-expires-after", type=int, default=172800, help="任务超时阈值（秒），默认 172800")
        parser.add_argument("--callback-url", help="回调通知地址")

        # CLI 执行控制与输出参数
        parser.add_argument("--wait", action="store_true", default=True, help="等待任务完成并输出 video_url")
        parser.add_argument("--download", action="store_true", help="等待完成后自动下载视频到本地")
        parser.add_argument("--output-path", help="指定下载视频的保存路径（仅在启用 --download 时有效，默认保存至脚本同级目录下的 runtime/ 文件夹内）")
        parser.add_argument("--interval", type=int, default=30, help="轮询间隔（秒）")
        parser.add_argument("--timeout", type=int, default=3600, help="等待超时（秒）")
        parser.add_argument("--poll-timeout", type=int, default=60, help="单次轮询请求超时（秒）")
        parser.add_argument("--json", action="store_true", help="输出 JSON")

        return parser

    @classmethod
    def build_content_from_args(cls, args: argparse.Namespace) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = []
        mode = args.mode

        if args.duration <= 0:
            raise SystemExit("--duration 必须是正整数")

        if args.text:
            content.append(cls.make_text_item(args.text))

        if mode == "t2v":
            if not args.text:
                raise SystemExit("t2v 模式必须提供 --text")

            return content

        if mode == "i2v":
            if not args.first_frame:
                raise SystemExit("i2v 模式需要提供 --first-frame")

            content.append(cls.make_image_item(args.first_frame))

            return content

        if mode == "fl2v":
            if not args.first_frame or not args.last_frame:
                raise SystemExit("fl2v 模式需要 --first-frame 和 --last-frame")

            content.append(cls.make_image_item(args.first_frame, role="first_frame"))
            content.append(cls.make_image_item(args.last_frame, role="last_frame"))

            return content

        if mode == "multimodal_ref2v":
            img_cnt = len(args.reference_image)
            vid_cnt = len(args.reference_video)
            aud_cnt = len(args.reference_audio)

            if img_cnt == 0 and vid_cnt == 0:
                raise SystemExit("multimodal_ref2v 模式不支持“文本+音频”或“纯音频”输入，至少需要 1 个参考图片或参考视频")

            if img_cnt > 9:
                raise SystemExit(f"multimodal_ref2v 模式最多支持 9 个参考图片，当前 {img_cnt} 个")

            if vid_cnt > 3:
                raise SystemExit(f"multimodal_ref2v 模式最多支持 3 个参考视频，当前 {vid_cnt} 个")

            if aud_cnt > 3:
                raise SystemExit(f"multimodal_ref2v 模式最多支持 3 个参考音频，当前 {aud_cnt} 个")

            for u in args.reference_image:
                content.append(cls.make_image_item(u, role="reference_image"))

            for v in args.reference_video:
                content.append(cls.make_video_item(v, role="reference_video"))

            for a in args.reference_audio:
                content.append(cls.make_audio_item(a, role="reference_audio"))

            return content

        raise SystemExit(f"未知 mode: {mode}")

    @classmethod
    def main(cls, argv=None) -> None:
        args = cls.build_parser().parse_args(argv)
        content = cls.build_content_from_args(args)
        tools = [{"type": "web_search"}] if getattr(args, "web_search", False) else None

        try:
            api = cls()
            result = api.generate_video(
                content=content,
                duration=args.duration,
                ratio=args.ratio,
                resolution=args.resolution,
                generate_audio=args.generate_audio,
                return_last_frame=args.return_last_frame,
                watermark=args.watermark,
                seed=args.seed,
                safety_identifier=args.safety_identifier,
                tools=tools,
                execution_expires_after=args.execution_expires_after,
                callback_url=args.callback_url,
                wait=args.wait,
                interval=args.interval,
                timeout=args.timeout,
                poll_timeout=args.poll_timeout,
            )
        except Exception as e:
            print(str(e), file=sys.stderr)
            raise SystemExit(1)

        if args.json:
            print(json.dumps(result, ensure_ascii=False))
            return

        if result.get("video_url"):
            video_url = result["video_url"]
            print(video_url)
            
            # 如果启用了下载，则下载到本地
            if getattr(args, "download", False):
                try:
                    import download_cli
                    download_cli.download_file(video_url, getattr(args, "output_path", None))
                except ImportError:
                    print("警告: 未找到 download_cli.py 模块，无法自动下载视频。", file=sys.stderr)
        else:
            print(result.get("task_id", ""))


if __name__ == "__main__":
    VolcSeeDanceAPI.main()
