#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seedance2-cli - Seedance-2 视频生成流水线 (Pipeline)。

执行逻辑概览：
1. 环境检查：一次性检查 TOS、Assets、Ark API 相关的全部环境变量是否齐全。
2. 参数校验与标准化：通过 validate_and_normalize.py 统一处理时长、分辨率、种子等关键参数，
   并根据环境变量应用稳定性护栏（超时上限等）。
3. 多模态输入解析与模式选择：使用 select_mode.py 解析文本与多模态素材，自动判定细分模式
   （t2v / i2v / fl2v / multi_i2v / multimodal_ref2v），同时给出置信度与告警信息。
4. 自动 TOS 上传：识别本地文件路径，调用 tos_cli.py 上传至 TOS，并替换为签名 URL。
5. 直接生成：调用 seedance_cli.py 封装的 VolcSeeDanceAPI 尝试生成视频。
6. 自动 Assets 兜底：若生成失败且错误信息中包含人脸/肖像限制，则调用 assets_cli.py 将 URL
   上传至私域素材库，再使用 asset:// 重新发起生成请求。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional

from assets_cli import VolcAssetsAPI
from seedance_cli import VolcSeeDanceAPI
from tos_cli import VolcTOSAPI
from select_mode import (
    Material,
    ModeDecision,
    build_materials_from_args,
    kind_from_path as _kind_from_path,
    select_mode_from_materials,
    simple_select_mode as _select_mode,
)
from validate_and_normalize import normalize_and_validate_args

# 在程序启动阶段启用行缓冲与直写，确保实时输出
try:
    import sys
    sys.stdout.reconfigure(line_buffering=True, write_through=True)
    sys.stderr.reconfigure(line_buffering=True, write_through=True)
except Exception:
    pass


def check_and_guide_envs() -> None:

    """检查所有的环境变量并给出一次性指导。"""

    required_envs = {
        "ARK API Key (控制台获取: https://www.volcengine.com/docs/82379/1399008)": [
            "VOLC_ARK_API_URL",
            "VOLC_ARK_API_KEY",
            "VOLC_ARK_SEEDANCE_MODEL",
        ],
        "Access Key (用于 TOS/Assets: https://www.volcengine.com/docs/6291/65568)": [
            "VOLC_ACCESS_KEY",
            "VOLC_SECRET_KEY",
        ],
        "Assets 参数 (私域素材库: https://www.volcengine.com/docs/82379/2333565)": [
            "VOLC_ASSETS_HOST",
            "VOLC_ASSETS_REGION",
            "VOLC_ASSETS_SERVICE",
            "VOLC_ASSETS_VERSION",
            "VOLC_ASSETS_GROUP",
            "VOLC_ASSETS_PROJECT",
        ],
        "TOS 参数 (对象存储: https://www.volcengine.com/docs/6349/107356)": [
            "VOLC_TOS_REGION",
            "VOLC_TOS_ENDPOINT",
            "VOLC_TOS_BUCKET",
        ],
    }

    missing_info: List[str] = []
    for category, envs in required_envs.items():
        missing_in_category = [env for env in envs if not os.environ.get(env)]
        if missing_in_category:
            missing_info.append(f"  - {category}: {', '.join(missing_in_category)}")

    if missing_info:
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        print(
            f"[CHANNEL] [{now}] ❌ 缺少必要环境变量！",
            file=sys.stderr,
        )
        for info in missing_info:
            print(f"[CHANNEL] [{now}] {info}", file=sys.stderr)
        print(
            f"[CHANNEL] [{now}] 请将以下命令复制粘贴到会话，替换敏感信息（AK/SK、Bucket、API key、Model 等）后发回给我进行校验。",
            file=sys.stderr,
        )

        # 国内环境一键配置
        print(
            f"[CHANNEL] [{now}] 💡 国内环境一键配置示例（可直接复制整块命令）：",
            file=sys.stderr,
        )
        cn_lines = [
            "```bash",
            "# AK/SK (用于 TOS/Assets 鉴权)",
            "# 获取文档: https://www.volcengine.com/docs/6291/65568?lang=zh",
            'export VOLC_ACCESS_KEY="xxxx"',
            'export VOLC_SECRET_KEY="xxxxxx=="',
            "",
            "# Assets 参数 (私域素材库)",
            "# 接口文档: https://www.volcengine.com/docs/82379/2333565?lang=zh",
            'export VOLC_ASSETS_HOST="ark.cn-beijing.volcengineapi.com"',
            'export VOLC_ASSETS_REGION="cn-beijing"',
            'export VOLC_ASSETS_SERVICE="ark"',
            'export VOLC_ASSETS_VERSION="2024-01-01"',
            'export VOLC_ASSETS_GROUP="seedance-pipeline-group"',
            'export VOLC_ASSETS_PROJECT="default"',
            "",
            "# TOS 参数 (对象存储)",
            "# 获取文档: https://www.volcengine.com/docs/6349/107356?lang=zh",
            'export VOLC_TOS_REGION="cn-beijing"',
            'export VOLC_TOS_ENDPOINT="tos-cn-beijing.volces.com"',
            'export VOLC_TOS_BUCKET="xxx"',
            "",
            "# Ark API (模型推理服务)",
            "# 获取文档: https://www.volcengine.com/docs/82379/1399008?lang=zh#f97e77a7",
            'export VOLC_ARK_API_URL="https://ark.cn-beijing.volces.com/api/v3"',
            'export VOLC_ARK_API_KEY="xxxxxx"',
            'export VOLC_ARK_SEEDANCE_MODEL="doubao-seedance-2-0-pro-260215"',
            "```",
        ]
        for line in cn_lines:
            print(f"[CHANNEL] [{now}] {line}", file=sys.stderr)

        # BytePlus 环境一键配置
        print(
            f"[CHANNEL] [{now}] 💡 BytePlus 环境一键配置示例（可直接复制整块命令）：",
            file=sys.stderr,
        )
        bp_lines = [
            "```bash",
            "# AK/SK ENV",
            'export VOLC_ACCESS_KEY="xxxx"',
            'export VOLC_SECRET_KEY="xxxxxxx=="',
            "",
            "# ASSETS ENV",
            'export VOLC_ASSETS_HOST="ark.ap-southeast-1.byteplusapi.com"',
            'export VOLC_ASSETS_REGION="ap-southeast-1"',
            'export VOLC_ASSETS_SERVICE="ark"',
            'export VOLC_ASSETS_VERSION="2024-01-01"',
            'export VOLC_ASSETS_GROUP="seedance-pipeline-group"',
            'export VOLC_ASSETS_PROJECT="default"',
            "",
            "# TOS ENV",
            'export VOLC_TOS_REGION="ap-southeast-1"',
            'export VOLC_TOS_ENDPOINT="tos-ap-southeast-1.bytepluses.com"',
            'export VOLC_TOS_BUCKET="xxx"',
            "",
            "### ARK",
            'export VOLC_ARK_API_URL="https://ark.ap-southeast.bytepluses.com/api/v3"',
            'export VOLC_ARK_API_KEY="xxxxx"',
            'export VOLC_ARK_SEEDANCE_MODEL="dreamina-seedance-2-0-260128"',
            "```",
        ]
        for line in bp_lines:
            print(f"[CHANNEL] [{now}] {line}", file=sys.stderr)

        sys.exit(1)

    print(
        f"[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ 环境检查通过，所有必需环境变量已配置（日志已发送到频道）。",
        file=sys.stderr,
    )


def is_local_file(path_or_url: str) -> bool:
    """简单判断是否为本地文件路径。"""

    if path_or_url.startswith("http://") or path_or_url.startswith("https://") or path_or_url.startswith(
        "asset://"
    ):
        return False
    return True


def upload_locals_to_tos(paths: List[str]) -> Dict[str, str]:
    """将本地文件上传至 TOS，并返回 mapping (local_path -> tos_url)。"""

    if not paths:
        return {}

    print(
        f"\n[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ⏳ 步骤 1/3: 发现 {len(paths)} 个本地文件，正在上传至 TOS...",
        file=sys.stderr,
    )
    mapping: Dict[str, str] = {}
    try:
        items = VolcTOSAPI.upload_files_and_get_urls(paths, expires_in=3600 * 24)
        for item in items:
            mapping[item["file"]] = item["url"]
            print(
                f"[CHANNEL]   ✅ 上传成功: {item['file']} -> {item['url'][:60]}...",
                file=sys.stderr,
            )
        print(
            f"[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ 步骤 1/3: TOS 上传完成，共 {len(items)} 个文件（日志已发送到频道）。",
            file=sys.stderr,
        )
        return mapping
    except Exception as e:  # noqa: BLE001
        print(f"[CHANNEL]   ❌ TOS 上传失败: {e}", file=sys.stderr)
        sys.exit(1)


def upload_urls_to_assets(urls: List[str]) -> Dict[str, str]:
    """将 URL 上传至 Assets，并返回 mapping (url -> asset_uri)。"""

    if not urls:
        return {}

    print(
        f"\n[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ⏳ 触发人脸/肖像限制兜底: 正在将 {len(urls)} 个素材上传至私域人像库...",
        file=sys.stderr,
    )
    mapping: Dict[str, str] = {}
    try:
        api = VolcAssetsAPI()
        items = api.upload_urls_to_assets(
            urls=urls,
            group_name=os.environ.get("VOLC_ASSETS_GROUP", "seedance-pipeline-group"),
            project_name=os.environ.get("VOLC_ASSETS_PROJECT", "default"),
            on_exists="auto",
        )
        for item in items:
            asset_uri = f"asset://{item['asset_id']}"
            mapping[item["url"]] = asset_uri
            print(
                f"[CHANNEL]   ✅ 资产入库成功: {item['url'][:60]}... -> {asset_uri}",
                file=sys.stderr,
            )
        print(
            f"[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Assets 入库完成，共 {len(items)} 条素材（日志已发送到频道）。",
            file=sys.stderr,
        )
        return mapping
    except Exception as e:  # noqa: BLE001
        print(f"[CHANNEL]   ❌ Assets 入库失败: {e}", file=sys.stderr)
        sys.exit(1)


def auto_select_mode(args: argparse.Namespace) -> ModeDecision:
    """使用 select_mode 模块根据输入参数自动选择模式。"""

    materials = build_materials_from_args(args)
    decision = select_mode_from_materials(materials, text_present=bool(getattr(args, "text", None)))
    return decision


def determine_mode(args: argparse.Namespace) -> str:
    """向后兼容的模式判定接口，返回 Seedance API 使用的模式字符串。"""

    decision = auto_select_mode(args)
    return decision.seedance_mode


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="seedance2-cli - Seedance-2 视频生成一键流水线 (自动 Mode, 参数校验, 自动 TOS, 自动 Assets 兜底)",
    )

    # 核心内容参数
    parser.add_argument("--text", help="输入的提示词文本（t2v 模式可选，但强烈推荐提供）")
    parser.add_argument("--first-frame", help="首帧图片路径 / URL / 素材 ID")
    parser.add_argument("--last-frame", help="尾帧图片路径 / URL / 素材 ID")
    parser.add_argument("--reference-image", action="append", default=[], help="参考图片路径 / URL / 素材 ID")
    parser.add_argument("--reference-video", action="append", default=[], help="参考视频路径 / URL / 素材 ID")
    parser.add_argument("--reference-audio", action="append", default=[], help="参考音频路径 / URL / 素材 ID")

    # 基础生成控制参数
    parser.add_argument("--duration", type=int, default=15, help="视频时长（秒），支持 4~15 或 -1，默认 15")
    parser.add_argument(
        "--ratio",
        default="9:16",
        choices=["16:9", "4:3", "1:1", "3:4", "9:16", "21:9", "adaptive"],
        help="视频宽高比",
    )
    parser.add_argument(
        "--resolution",
        default="720p",
        choices=["480p", "720p", "1080p"],
        help="输出分辨率",
    )
    parser.add_argument(
        "--generate-audio",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="是否生成音频",
    )
    parser.add_argument("--return-last-frame", action="store_true", help="返回生成视频的尾帧图像")
    parser.add_argument("--watermark", action="store_true", help="生成视频是否包含水印")
    parser.add_argument(
        "--seed",
        type=int,
        default=-1,
        help="种子整数，默认 -1（-1 时由服务端采样随机种子，如需确定性结果请显式设置具体整数值）",
    )

    # 高级控制与安全参数
    parser.add_argument("--safety-identifier", help="终端用户的唯一标识符")
    parser.add_argument("--web-search", action="store_true", help="开启联网搜索工具（可被环境变量关闭）")

    # CLI 执行控制与输出参数
    parser.add_argument("--download", action="store_true", help="等待完成后自动下载视频到本地")
    parser.add_argument("--output-path", help="指定下载视频的保存路径（仅在启用 --download 时有效）")

    return parser


def main() -> None:
    start = time.time()
    try:
        check_and_guide_envs()
        parser = build_parser()
        args = parser.parse_args()

        # 1. 参数校验与标准化（时长、分辨率、随机种子、特性开关、超时等）
        args, normalize_messages = normalize_and_validate_args(args)
        for msg in normalize_messages:
            print(f"[CHANNEL] [参数规范化] {msg}", file=sys.stderr)
        print(
            f"[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ 参数规范化完成，共 {len(normalize_messages)} 条调整（日志已发送到频道）。",
            file=sys.stderr,
        )

        # 2. 自动判定 Mode（细分模式 + Seedance API 模式）
        decision = auto_select_mode(args)
        args.mode = decision.seedance_mode
        print(
            f"\n[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] 🤖 自动识别视频生成模式: {decision.mode}"
            f"（Seedance API 模式: {decision.seedance_mode}, 置信度 {decision.confidence:.2f}）",
            file=sys.stderr,
        )
        for warn in decision.warnings:
            print(f"[CHANNEL] [模式告警] {warn}", file=sys.stderr)

        # 3. 收集所有传入的素材路径
        all_media_inputs: List[str] = []
        if args.first_frame:
            all_media_inputs.append(args.first_frame)
        if args.last_frame:
            all_media_inputs.append(args.last_frame)
        all_media_inputs.extend(args.reference_image)
        all_media_inputs.extend(args.reference_video)
        all_media_inputs.extend(args.reference_audio)

        # 4. 过滤出本地文件，统一上传 TOS
        local_files = list({p for p in all_media_inputs if is_local_file(p)})
        tos_mapping = upload_locals_to_tos(local_files)

        # 替换参数中的本地路径为 TOS URL
        def replace_with_tos(val: Optional[str]) -> Optional[str]:
            if val in tos_mapping:
                return tos_mapping[val]
            return val

        args.first_frame = replace_with_tos(args.first_frame)
        args.last_frame = replace_with_tos(args.last_frame)
        args.reference_image = [replace_with_tos(x) for x in args.reference_image]
        args.reference_video = [replace_with_tos(x) for x in args.reference_video]
        args.reference_audio = [replace_with_tos(x) for x in args.reference_audio]

        # 5. 构建内容并尝试直接生成
        print(
            f"\n[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ⏳ 步骤 2/3: 正在请求 Seedance-2 API 生成视频...",
            file=sys.stderr,
        )
        content = VolcSeeDanceAPI.build_content_from_args(args)
        tools = [{"type": "web_search"}] if getattr(args, "web_search", False) else None

        seedance_api = VolcSeeDanceAPI()

        def do_generate(current_content: List[Dict[str, Any]]) -> Dict[str, Any]:
            return seedance_api.generate_video(
                content=current_content,
                duration=args.duration,
                ratio=args.ratio,
                resolution=args.resolution,
                generate_audio=args.generate_audio,
                return_last_frame=args.return_last_frame,
                watermark=args.watermark,
                seed=args.seed,
                safety_identifier=args.safety_identifier,
                tools=tools,
                timeout=getattr(args, "_wait_timeout", 3600),
                interval=getattr(args, "_poll_interval", 30),
                poll_timeout=getattr(args, "_poll_timeout", 60),
            )

        try:
            result = do_generate(content)
        except Exception as e:  # noqa: BLE001
            err_str = str(e).lower()
            # 6. 若报错为人脸相关，则兜底 Assets 上传
            if any(key in err_str for key in ["face", "人脸", "肖像", "portrait", "人像"]):
                print(
                    f"\n[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ⚠️ 拦截到人脸审核限制: {e}",
                    file=sys.stderr,
                )

                # 收集需要上传的 URL（此时所有的本地文件已经变成了 TOS URL，普通的 HTTP URL 也可以直接上传 Assets）
                urls_to_assets = list(
                    {
                        p
                        for p in (
                            [args.first_frame, args.last_frame]
                            + args.reference_image
                            + args.reference_video
                            + args.reference_audio
                        )
                        if p and not p.startswith("asset://")
                    }
                )

                assets_mapping = upload_urls_to_assets(urls_to_assets)

                def replace_with_asset(val: Optional[str]) -> Optional[str]:
                    if val in assets_mapping:
                        return assets_mapping[val]
                    return val

                args.first_frame = replace_with_asset(args.first_frame)
                args.last_frame = replace_with_asset(args.last_frame)
                args.reference_image = [replace_with_asset(x) for x in args.reference_image]
                args.reference_video = [replace_with_asset(x) for x in args.reference_video]
                args.reference_audio = [replace_with_asset(x) for x in args.reference_audio]

                print(
                    f"\n[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ⏳ 步骤 3/3: 使用入库后的资产重新请求生成视频...",
                    file=sys.stderr,
                )
                new_content = VolcSeeDanceAPI.build_content_from_args(args)
                try:
                    result = do_generate(new_content)
                    print(
                        f"[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ Assets 兜底生成成功（已使用 asset:// 重新发起生成，日志已发送到频道）。",
                        file=sys.stderr,
                    )
                except Exception as final_e:  # noqa: BLE001
                    print(f"[CHANNEL] ❌ 视频生成最终失败（Assets 兜底后仍失败）: {final_e}", file=sys.stderr)
                    sys.exit(1)
            else:
                print(f"[CHANNEL] ❌ 首次视频生成失败: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print(
                f"[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] ✅ 首次视频生成请求成功（未触发 Assets 兜底，日志已发送到频道）。",
                file=sys.stderr,
            )

        # 7. 输出结果 & 自动下载
        print(
            f"\n[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] 🎉 视频生成成功！（结果信息已发送到频道）",
            file=sys.stderr,
        )
        if result.get("video_url"):
            video_url = result["video_url"]
            print(video_url)

            if args.download:
                try:
                    import download_cli

                    download_cli.download_file(video_url, args.output_path)
                except ImportError:
                    print(
                        "[CHANNEL] 警告: 未找到 download_cli.py 模块，无法自动下载视频。",
                        file=sys.stderr,
                    )
        else:
            print(result.get("task_id", ""))
    finally:
        try:
            elapsed = max(0.0, time.time() - start)
            print(
                f"\n[CHANNEL] [{time.strftime('%Y-%m-%d %H:%M:%S')}] 本次任务总耗时: {elapsed:.1f} 秒（该信息已发送到频道）。",
                file=sys.stderr,
            )
        except Exception:
            pass


if __name__ == "__main__":
    main()
