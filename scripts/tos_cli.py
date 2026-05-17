#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上传本地素材到 TOS，并返回可读 URL。

特点：
- 自包含：所有逻辑封装在 VolcTOSAPI 内
- 先检查目录前缀是否可用；若为空则创建 0-byte 占位对象
- 默认对象名：md5_<urlsafe_base64(md5_digest)>
- 若对象已存在且 MD5 一致：直接重新生成签名 URL 返回
- 若不存在：上传后再生成 1 小时签名 URL
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import sys
import tempfile
from typing import Dict, List

import tos
from dotenv import load_dotenv


load_dotenv()


class VolcTOSAPI:
    def __init__(self) -> None:
        self.ak = os.getenv("VOLC_ACCESS_KEY")
        self.sk = os.getenv("VOLC_SECRET_KEY")
        self.bucket = os.getenv("VOLC_TOS_BUCKET")
        self.endpoint = os.getenv("VOLC_TOS_ENDPOINT")
        self.region = os.getenv("VOLC_TOS_REGION")

        missing_envs = []
        if not self.ak:
            missing_envs.append("VOLC_ACCESS_KEY")
        if not self.sk:
            missing_envs.append("VOLC_SECRET_KEY")
        if not self.bucket:
            missing_envs.append("VOLC_TOS_BUCKET")
        if not self.endpoint:
            missing_envs.append("VOLC_TOS_ENDPOINT")
        if not self.region:
            missing_envs.append("VOLC_TOS_REGION")
        if missing_envs:
            raise ValueError(f"请一次性设置以下环境变量: {', '.join(missing_envs)}")

        self.client = tos.TosClientV2(self.ak, self.sk, self.endpoint, self.region)

    @staticmethod
    def _md5_of_file(path: str) -> bytes:
        h = hashlib.md5()  # noqa: S324
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.digest()

    @staticmethod
    def _md5_digest_to_b64(digest: bytes) -> str:
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    @staticmethod
    def _md5_digest_to_hex(digest: bytes) -> str:
        return digest.hex()

    @staticmethod
    def _normalize_dir(dir_key: str) -> str:
        dir_key = (dir_key or "").strip().lstrip("/")
        if not dir_key:
            return ""
        if not dir_key.endswith("/"):
            dir_key += "/"
        return dir_key

    @staticmethod
    def _strip_wrapping_quotes(text: str) -> str:
        text = text.strip()
        while len(text) >= 2 and (
            (text[0] == text[-1] and text[0] in {"'", '"', "`"})
            or (text[0] == "[" and text[-1] == "]")
            or (text[0] == "(" and text[-1] == ")")
        ):
            text = text[1:-1].strip()
        return text

    @classmethod
    def normalize_files(cls, raw_values: List[str]) -> List[str]:
        """
        宽容解析 --files 输入，支持：
        - 正常多个参数：--files /a.jpg /b.jpg
        - 单个 JSON 数组字符串：--files '["/a.jpg","/b.jpg"]'
        - 带引号/反引号/方括号包裹：--files '["`/a.jpg`"]'
        """
        files: List[str] = []

        def add_candidate(value: str) -> None:
            value = value.strip()
            if not value:
                return

            if value.startswith("[") and value.endswith("]"):
                try:
                    parsed = json.loads(value)
                except json.JSONDecodeError:
                    pass
                else:
                    if isinstance(parsed, list):
                        for item in parsed:
                            if isinstance(item, str):
                                add_candidate(item)
                        return

            cleaned = cls._strip_wrapping_quotes(value)
            if cleaned:
                files.append(cleaned)

        for raw in raw_values:
            add_candidate(raw)
        return [p for p in files if p]

    def close(self) -> None:
        try:
            self.client.close()
        except Exception as e:  # noqa: BLE001
            print(f"关闭客户端失败: {e}", file=sys.stderr)

    def _list_objects_any(self, prefix: str, max_keys: int = 1) -> bool:
        """
        Best-effort 判断前缀下是否已有对象。
        """
        if hasattr(self.client, "list_objects"):
            try:
                resp = self.client.list_objects(self.bucket, prefix=prefix, max_keys=max_keys, delimiter="/")
                contents = getattr(resp, "contents", None) or getattr(resp, "Contents", None)
                if contents is not None:
                    return len(contents) > 0
                common = getattr(resp, "common_prefixes", None) or getattr(resp, "CommonPrefixes", None)
                if common is not None:
                    return len(common) > 0
                return True
            except Exception:
                pass

        if hasattr(self.client, "list_objects_type2"):
            try:
                resp = self.client.list_objects_type2(self.bucket, prefix=prefix, max_keys=max_keys, delimiter="/")
                contents = getattr(resp, "contents", None) or getattr(resp, "Contents", None)
                if contents is not None:
                    return len(contents) > 0
                common = getattr(resp, "common_prefixes", None) or getattr(resp, "CommonPrefixes", None)
                if common is not None:
                    return len(common) > 0
                return True
            except Exception:
                pass

        return False

    def ensure_directory(self, dir_key: str) -> str:
        """
        对象存储里的“目录”本质是前缀。若前缀无对象，则创建一个 0-byte 占位对象 `<dir>/`。
        """
        dir_key = self._normalize_dir(dir_key)
        if not dir_key:
            return ""
        if self._list_objects_any(prefix=dir_key, max_keys=1):
            return dir_key

        try:
            if hasattr(self.client, "put_object"):
                self.client.put_object(self.bucket, dir_key, content=b"")
            else:
                with tempfile.NamedTemporaryFile("wb", delete=True) as tf:
                    tf.write(b"")
                    tf.flush()
                    self.client.put_object_from_file(self.bucket, dir_key, tf.name)
        except Exception as e:  # noqa: BLE001
            print(f"创建目录占位对象失败: {e}", file=sys.stderr)
        return dir_key

    def _head_object(self, key: str):
        if hasattr(self.client, "head_object"):
            return self.client.head_object(self.bucket, key)
        if hasattr(self.client, "head_object_v2"):
            return self.client.head_object_v2(self.bucket, key)
        raise AttributeError("当前 TOS SDK 不支持 head_object")

    def object_exists_and_matches_md5(self, *, key: str, md5_digest: bytes) -> bool:
        """
        若对象存在且（最好情况下）ETag 等于本地 MD5，则认为匹配。
        由于 key 本身已由 MD5 生成，若对象存在通常也可视为匹配；这里只额外尝试比对 ETag。
        """
        try:
            resp = self._head_object(key)
        except Exception:
            return False

        etag = getattr(resp, "etag", None) or getattr(resp, "ETag", None)
        if isinstance(etag, str) and etag:
            return etag.strip('"') == self._md5_digest_to_hex(md5_digest)

        # 无法拿到 ETag 时，保守按“存在即匹配”处理，因为 key 已绑定 md5
        return True

    def upload_file(self, *, local_file_path: str, key: str) -> None:
        self.client.put_object_from_file(self.bucket, key, local_file_path)

    def generate_presigned_url(self, *, key: str, expires_in: int = 3600 * 24) -> str:
        method = tos.HttpMethodType.Http_Method_Get
        out = self.client.pre_signed_url(method, bucket=self.bucket, key=key, expires=expires_in)
        return out.signed_url

    def build_object_key(self, *, local_file_path: str, dir_key: str, name_prefix: str = "md5_") -> tuple[str, bytes]:
        dir_key = self.ensure_directory(dir_key)
        md5_digest = self._md5_of_file(local_file_path)
        _, ext = os.path.splitext(local_file_path)
        object_name = f"{name_prefix}{self._md5_digest_to_b64(md5_digest)}{ext}"
        object_key = f"{dir_key}{object_name}" if dir_key else object_name
        return object_key, md5_digest

    def upload_or_resign(
        self,
        *,
        local_file_path: str,
        dir_key: str,
        expires_in: int = 3600,
        name_prefix: str = "md5_",
    ) -> Dict[str, str]:
        object_key, md5_digest = self.build_object_key(
            local_file_path=local_file_path,
            dir_key=dir_key,
            name_prefix=name_prefix,
        )

        reused = "0"
        if self.object_exists_and_matches_md5(key=object_key, md5_digest=md5_digest):
            reused = "1"
        else:
            self.upload_file(local_file_path=local_file_path, key=object_key)

        url = self.generate_presigned_url(key=object_key, expires_in=expires_in)
        return {"file": local_file_path, "key": object_key, "url": url, "reused": reused}

    @classmethod
    def upload_files_and_get_urls(cls, local_files: List[str], expires_in: int, dir_key: str = "") -> List[Dict[str, str]]:
        api = cls()
        try:
            items: List[Dict[str, str]] = []
            for p in local_files:
                if not os.path.exists(p):
                    raise FileNotFoundError(p)
                items.append(api.upload_or_resign(local_file_path=p, dir_key=dir_key, expires_in=expires_in))
            return items
        finally:
            api.close()

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Upload local files to TOS and print presigned URLs.")
        parser.add_argument("--files", "-f", nargs="+", required=True, help="一个或多个本地文件路径")
        parser.add_argument("--dir", default=os.environ.get("TOS_DIR", "volc-assets/"), help="对象前缀目录（默认 TOS_DIR 或 volc-assets/）")
        parser.add_argument("--expires", type=int, default=3600 * 24, help="URL 有效期（秒），默认 24 小时")
        parser.add_argument("--json", action="store_true", help="以 JSON 输出（用于脚本串联）")
        return parser

    @classmethod
    def main(cls, argv=None) -> None:
        args = cls.build_parser().parse_args(argv)
        if args.expires <= 0:
            raise SystemExit("--expires 必须是正整数")

        files = cls.normalize_files(args.files)
        items = cls.upload_files_and_get_urls(files, args.expires, dir_key=args.dir)

        if args.json:
            print(json.dumps({"items": items, "urls": [x["url"] for x in items]}, ensure_ascii=False))
            return

        for x in items:
            print(x["url"])


if __name__ == "__main__":
    VolcTOSAPI.main()
