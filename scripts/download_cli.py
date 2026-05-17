#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用文件下载 CLI 工具
"""

import argparse
import os
import sys
import time
from urllib.parse import urlparse
from typing import Optional

import requests


def download_file(url: str, output_path: Optional[str] = None) -> str:
    """
    下载单个文件到本地。
    如果未指定 output_path，则默认保存到脚本同级目录下的 runtime/ 文件夹内，
    文件名尝试从 URL 提取，提取失败则使用生成的时间戳。
    """
    if not output_path:
        # 获取当前脚本所在目录，并拼接 runtime 文件夹
        base_dir = os.path.dirname(os.path.abspath(__file__))
        runtime_dir = os.path.join(base_dir, "runtime")
        os.makedirs(runtime_dir, exist_ok=True)

        path = urlparse(url).path
        filename = os.path.basename(path)

        if not filename:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            filename = f"download_{timestamp}"

        output_path = os.path.join(runtime_dir, filename)
    else:
        # 如果用户指定了路径，但路径中包含目录，则尝试创建父目录
        parent_dir = os.path.dirname(output_path)

        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    try:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始下载: {url}", file=sys.stderr)

        with requests.get(url, stream=True, timeout=600, headers={"User-Agent": "Mozilla/5.0"}) as response:
            response.raise_for_status()

            file_total_size = int(response.headers.get("Content-Length", 0))
            downloaded_size = 0

            with open(output_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        if file_total_size > 0:
                            progress = (downloaded_size / file_total_size) * 100
                            print(f"\r下载进度: {progress:.1f}%", end="", file=sys.stderr)

                if file_total_size > 0:
                    print(file=sys.stderr)

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 文件已成功下载至: {output_path}", file=sys.stderr)

        return output_path

    except Exception as e:
        if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
            os.remove(output_path)

        raise RuntimeError(f"下载失败: {str(e)}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="通用文件下载工具")
    parser.add_argument("url", help="要下载的文件的 URL")
    parser.add_argument("-o", "--output", dest="output_path", help="指定保存的本地路径")

    args = parser.parse_args(argv)

    try:
        download_file(args.url, args.output_path)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
