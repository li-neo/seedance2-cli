#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 URL 上传到方舟 Assets 素材库并返回 asset_id。

特点：
- 自包含：所有逻辑封装在 VolcAssetsAPI 内（含签名、请求、去重、CLI）
- 默认 name：按素材内容 MD5(digest) -> urlsafe base64（无 padding）生成，长度稳定可控
- 重名处理（默认 auto）：
  - 若同名素材存在：GetAsset 拿 URL -> 下载算 MD5
  - MD5 相同：直接复用
  - MD5 不同：直接创建新素材（不覆盖）

依赖：
  pip install -U requests
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import requests


class VolcAssetsAPI:
    _IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
    _VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi"}
    _AUDIO_EXT = {".mp3", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".flac"}

    class AssetsAPIError(Exception):
        def __init__(
            self,
            message: str,
            status_code: Optional[int] = None,
            error_code: Optional[str] = None,
            details: Optional[Any] = None,
        ) -> None:
            super().__init__(message)
            self.message = message
            self.status_code = status_code
            self.error_code = error_code
            self.details = details

        def __str__(self) -> str:
            base = self.message
            if self.status_code is not None:
                base += f" (status={self.status_code}"
                if self.error_code:
                    base += f", code={self.error_code}"
                base += ")"
            return base

    @dataclass(frozen=True)
    class ExistingDecision:
        action: str  # upload / use / overwrite / new-group
        group_id_or_name: str
        asset_id: Optional[str] = None

    def __init__(
        self,
        *,
        ak: Optional[str] = None,
        sk: Optional[str] = None,
        service: Optional[str] = None,
        region: Optional[str] = None,
        host: Optional[str] = None,
        content_type: str = "application/json",
        path: str = "/",
        version: Optional[str] = None,
        timeout: int = 10,
    ) -> None:
        if not ak:
            ak = os.environ.get("VOLC_ACCESS_KEY", "")
        if not sk:
            sk = os.environ.get("VOLC_SECRET_KEY", "")
        if not host:
            host = os.environ.get("VOLC_ASSETS_HOST", "")
        if not region:
            region = os.environ.get("VOLC_ASSETS_REGION", "")
        if not service:
            service = os.environ.get("VOLC_ASSETS_SERVICE", "")
        if not version:
            version = os.environ.get("VOLC_ASSETS_VERSION", "")

        self.ak = ak
        self.sk = sk
        self.service = service
        self.region = region
        self.host = host
        self.content_type = content_type
        self.path = path
        self.version = version
        self.timeout = timeout

        missing_envs: List[str] = []
        if not self.ak:
            missing_envs.append("VOLC_ACCESS_KEY")
        if not self.sk:
            missing_envs.append("VOLC_SECRET_KEY")
        if not self.host:
            missing_envs.append("VOLC_ASSETS_HOST")
        if not self.region:
            missing_envs.append("VOLC_ASSETS_REGION")
        if not self.service:
            missing_envs.append("VOLC_ASSETS_SERVICE")
        if not self.version:
            missing_envs.append("VOLC_ASSETS_VERSION")
        if missing_envs:
            raise self.AssetsAPIError(f"请一次性设置以下环境变量: {', '.join(missing_envs)}")

    # ---------------------------
    # Utilities
    # ---------------------------

    @staticmethod
    def _norm_query(params: Dict[str, Any]) -> str:
        if not params:
            return ""
        query = ""
        for key in sorted(params.keys()):
            value = params[key]
            if isinstance(value, list):
                for item in value:
                    query += quote(str(key), safe="-_.~") + "=" + quote(str(item), safe="-_.~") + "&"
            else:
                query += quote(str(key), safe="-_.~") + "=" + quote(str(value), safe="-_.~") + "&"
        return query[:-1].replace("+", "%20")

    @staticmethod
    def _hmac_sha256(key: bytes, content: str) -> bytes:
        return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()

    @staticmethod
    def _hash_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _extract_id(resp: Dict[str, Any]) -> Optional[str]:
        result = resp.get("Result")
        if isinstance(result, dict) and result.get("Id"):
            return result["Id"]
        if resp.get("Id"):
            return resp["Id"]
        return None

    @staticmethod
    def _extract_items(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = resp.get("Result")
        if isinstance(result, dict) and isinstance(result.get("Items"), list):
            return [x for x in result["Items"] if isinstance(x, dict)]
        if isinstance(resp.get("Items"), list):
            return [x for x in resp["Items"] if isinstance(x, dict)]
        return []

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
    def normalize_urls(cls, raw_values: List[str]) -> List[str]:
        """
        宽容解析 URL 输入，支持：
        - 多个独立参数：["https://a", "https://b"]
        - 单个 JSON 数组字符串：['["https://a","https://b"]']
        - 带方括号/引号/反引号的字符串
        - 逗号分隔字符串（在明显多 URL 文本时）
        """

        urls: List[str] = []

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

            if "," in value and "http" in value:
                parts = [p.strip() for p in value.split(",")]
                if sum(1 for p in parts if "http://" in p or "https://" in p) >= 2:
                    for part in parts:
                        add_candidate(part)
                    return

            cleaned = cls._strip_wrapping_quotes(value)
            if cleaned:
                urls.append(cleaned)

        for raw in raw_values:
            add_candidate(raw)
        return [u for u in urls if u]

    @classmethod
    def guess_asset_type_from_url(cls, url: str) -> str:
        path = urlparse(url).path or ""
        _, ext = os.path.splitext(path.lower())
        if ext in cls._IMAGE_EXT:
            return "Image"
        if ext in cls._VIDEO_EXT:
            return "Video"
        if ext in cls._AUDIO_EXT:
            return "Audio"
        return "Image"

    @staticmethod
    def md5_of_url_content(url: str, timeout: int = 60) -> bytes:
        h = hashlib.md5()  # noqa: S324 (identity only)
        with requests.get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    h.update(chunk)
        return h.digest()

    @staticmethod
    def md5_digest_to_b64(digest: bytes) -> str:
        # 16 bytes -> urlsafe base64 without '=' padding => stable length 22
        return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    # ---------------------------
    # Core API request
    # ---------------------------

    def _request_api(
        self,
        method: str,
        action: str,
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        if body is None:
            body_str = ""
        else:
            body_str = json.dumps(body, ensure_ascii=False, separators=(",", ":"))

        final_query: Dict[str, Any] = {"Action": action, "Version": self.version}
        if query:
            final_query.update(query)

        now = datetime.datetime.now(datetime.timezone.utc)
        x_date = now.strftime("%Y%m%dT%H%M%SZ")
        short_x_date = x_date[:8]
        x_content_sha256 = self._hash_sha256(body_str)

        signed_headers_str = ";".join(["content-type", "host", "x-content-sha256", "x-date"])
        canonical_request = "\n".join(
            [
                method.upper(),
                self.path,
                self._norm_query(final_query),
                "\n".join(
                    [
                        f"content-type:{self.content_type}",
                        f"host:{self.host}",
                        f"x-content-sha256:{x_content_sha256}",
                        f"x-date:{x_date}",
                    ]
                ),
                "",
                signed_headers_str,
                x_content_sha256,
            ]
        )

        hashed_canonical_request = self._hash_sha256(canonical_request)
        credential_scope = "/".join([short_x_date, self.region, self.service, "request"])
        string_to_sign = "\n".join(["HMAC-SHA256", x_date, credential_scope, hashed_canonical_request])

        k_date = self._hmac_sha256(self.sk.encode("utf-8"), short_x_date)
        k_region = self._hmac_sha256(k_date, self.region)
        k_service = self._hmac_sha256(k_region, self.service)
        k_signing = self._hmac_sha256(k_service, "request")
        signature = self._hmac_sha256(k_signing, string_to_sign).hex()

        signed_headers: Dict[str, str] = {
            "Host": self.host,
            "X-Content-Sha256": x_content_sha256,
            "X-Date": x_date,
            "Content-Type": self.content_type,
            "Authorization": (
                "HMAC-SHA256 "
                f"Credential={self.ak}/{credential_scope}, "
                f"SignedHeaders={signed_headers_str}, "
                f"Signature={signature}"
            ),
        }

        final_headers: Dict[str, str] = {}
        if headers:
            final_headers.update(headers)
        final_headers.update(signed_headers)

        url = f"https://{self.host}{self.path}"
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=final_headers,
            params=final_query,
            data=body_str,
            timeout=self.timeout,
        )

        status = resp.status_code
        if 200 <= status < 300:
            try:
                return resp.json()
            except json.JSONDecodeError as exc:
                raise self.AssetsAPIError("响应 JSON 解析失败", status_code=status, details=resp.text) from exc

        parsed: Optional[Dict[str, Any]] = None
        error_code: Optional[str] = None
        error_message: Optional[str] = None
        try:
            parsed = resp.json()
            if isinstance(parsed, dict):
                meta = parsed.get("ResponseMetadata")
                if isinstance(meta, dict):
                    err = meta.get("Error")
                    if isinstance(err, dict):
                        error_code = err.get("Code")
                        error_message = err.get("Message")
        except json.JSONDecodeError:
            parsed = None

        if not error_message:
            error_message = resp.text or "请求失败"
        raise self.AssetsAPIError(
            f"请求失败 (HTTP {status}): {error_message}",
            status_code=status,
            error_code=error_code,
            details=parsed,
        )

    # ---------------------------
    # Assets API methods
    # ---------------------------

    def create_asset_group(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        group_type: str = "AIGC",
        project_name: str = "default",
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"Name": name, "GroupType": group_type, "ProjectName": project_name}
        if description is not None:
            payload["Description"] = description
        return self._request_api(method="POST", action="CreateAssetGroup", body=payload)

    def list_asset_groups(
        self,
        *,
        group_type: str,
        name: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 50,
        project_name: str = "default",
    ) -> Dict[str, Any]:
        filter_obj: Dict[str, Any] = {"GroupType": group_type}
        if name is not None:
            filter_obj["name"] = name
        payload: Dict[str, Any] = {
            "Filter": filter_obj,
            "PageNumber": page_number,
            "PageSize": page_size,
            "SortBy": "CreateTime",
            "SortOrder": "Desc",
            "ProjectName": project_name,
        }
        return self._request_api(method="POST", action="ListAssetGroups", body=payload)

    def create_asset(
        self,
        *,
        group_id: str,
        url: str,
        asset_type: str,
        project_name: str = "default",
        name: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "GroupId": group_id,
            "URL": url,
            "AssetType": asset_type,
            "ProjectName": project_name,
            # "Moderation": {
            #     "Strategy": "Skip"
            # },
        }
        if name is not None:
            payload["Name"] = name
        return self._request_api(method="POST", action="CreateAsset", body=payload)

    def list_assets(
        self,
        *,
        group_type: str,
        group_ids: Optional[list[str]] = None,
        statuses: Optional[list[str]] = None,
        name: Optional[str] = None,
        page_number: int = 1,
        page_size: int = 20,
        project_name: str = "default",
    ) -> Dict[str, Any]:
        filter_obj: Dict[str, Any] = {"GroupType": group_type}
        if group_ids is not None:
            filter_obj["GroupIds"] = group_ids
        if statuses is not None:
            filter_obj["Statuses"] = statuses
        if name is not None:
            filter_obj["Name"] = name
        payload: Dict[str, Any] = {
            "Filter": filter_obj,
            "PageNumber": page_number,
            "PageSize": page_size,
            "SortBy": "CreateTime",
            "SortOrder": "Desc",
            "ProjectName": project_name,
        }
        return self._request_api(method="POST", action="ListAssets", body=payload)

    def get_asset(self, *, asset_id: str, project_name: str = "default") -> Dict[str, Any]:
        payload = {"Id": asset_id, "ProjectName": project_name}
        return self._request_api(method="POST", action="GetAsset", body=payload)

    def delete_asset(self, *, asset_id: str, project_name: str = "default") -> Dict[str, Any]:
        payload = {"Id": asset_id, "ProjectName": project_name}
        return self._request_api(method="POST", action="DeleteAsset", body=payload)

    def wait_for_asset_active(
        self,
        *,
        asset_id: str,
        project_name: str = "default",
        interval: float = 5.0,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        start = time.time()
        last: Optional[Dict[str, Any]] = None
        while True:
            last = self.get_asset(asset_id=asset_id, project_name=project_name)
            result = last.get("Result") if isinstance(last, dict) else None
            status = result.get("Status") if isinstance(result, dict) else None
            if status == "Active":
                return last
            if status == "Failed":
                raise self.AssetsAPIError(f"素材处理失败 (asset_id={asset_id})", details=last)
            if time.time() - start > timeout:
                raise self.AssetsAPIError(f"等待素材变为 Active 超时 (asset_id={asset_id})", details=last)
            time.sleep(interval)

    # ---------------------------
    # Higher-level helpers
    # ---------------------------

    def ensure_asset_group(self, *, group_name: str, project_name: str, group_type: str = "AIGC") -> str:
        resp = self.list_asset_groups(
            group_type=group_type,
            name=group_name,
            page_number=1,
            page_size=50,
            project_name=project_name,
        )
        items = self._extract_items(resp)
        for it in items:
            if it.get("Name") == group_name and it.get("Id"):
                return it["Id"]
        create_resp = self.create_asset_group(
            name=group_name,
            description="created by seedance pipeline",
            group_type=group_type,
            project_name=project_name,
        )
        group_id = self._extract_id(create_resp)
        if not group_id:
            raise self.AssetsAPIError("CreateAssetGroup 响应中未找到 Id", details=create_resp)
        return group_id

    def find_assets_by_name(
        self,
        *,
        group_id: str,
        project_name: str,
        name: str,
        group_type: str = "AIGC",
    ) -> List[Dict[str, Any]]:
        resp = self.list_assets(
            group_type=group_type,
            group_ids=[group_id],
            name=name,
            page_number=1,
            page_size=50,
            project_name=project_name,
        )
        items = self._extract_items(resp)
        return [it for it in items if it.get("Name") == name]

    @staticmethod
    def _extract_result_obj(resp: Dict[str, Any]) -> Dict[str, Any]:
        result = resp.get("Result")
        if isinstance(result, dict):
            return result
        return {}

    def get_asset_url(self, *, asset_id: str, project_name: str) -> Optional[str]:
        resp = self.get_asset(asset_id=asset_id, project_name=project_name)
        result = self._extract_result_obj(resp)
        url = result.get("URL")
        if isinstance(url, str) and url:
            return url
        url = result.get("Url")
        if isinstance(url, str) and url:
            return url
        return None

    def find_matching_asset_by_md5(
        self,
        *,
        project_name: str,
        existing_items: List[Dict[str, Any]],
        new_digest: bytes,
        timeout: int,
    ) -> Optional[str]:
        for it in existing_items:
            asset_id = it.get("Id")
            if not isinstance(asset_id, str) or not asset_id:
                continue
            url = self.get_asset_url(asset_id=asset_id, project_name=project_name)
            if not url:
                continue
            try:
                digest = self.md5_of_url_content(url, timeout=timeout)
            except Exception:  # noqa: BLE001
                continue
            if digest == new_digest:
                return asset_id
        return None

    def _choose_action_interactive(self, *, asset_name: str, existing_items: List[Dict[str, Any]]) -> str:
        if not sys.stdin.isatty():
            raise SystemExit("检测到同名素材，但当前非交互环境。请使用 --on-exists 指定处理策略。")
        print(f"发现同名素材: name={asset_name} (count={len(existing_items)})", file=sys.stderr)
        for it in existing_items[:5]:
            print(f"  - asset_id={it.get('Id')} status={it.get('Status')} url={it.get('URL')}", file=sys.stderr)
        print("请选择处理方式：", file=sys.stderr)
        print("1) 直接使用已有素材", file=sys.stderr)
        print("2) 覆盖上传（删除同名素材后重新创建）", file=sys.stderr)
        print("3) 新建 assets group 后新上传", file=sys.stderr)
        while True:
            s = input("请输入 1/2/3: ").strip()
            if s == "1":
                return "use"
            if s == "2":
                return "overwrite"
            if s == "3":
                return "new-group"

    def decide_when_exists(
        self,
        *,
        on_exists: str,
        group_name: str,
        group_id: str,
        project_name: str,
        asset_name: str,
        existing_items: List[Dict[str, Any]],
        new_digest: bytes,
        md5_timeout: int,
    ) -> "VolcAssetsAPI.ExistingDecision":
        if not existing_items:
            return self.ExistingDecision(action="upload", group_id_or_name=group_id)

        # auto: verify by content; match -> use; mismatch -> upload new
        if on_exists == "auto":
            matched_id = self.find_matching_asset_by_md5(
                project_name=project_name,
                existing_items=existing_items,
                new_digest=new_digest,
                timeout=md5_timeout,
            )
            if matched_id:
                return self.ExistingDecision(action="use", group_id_or_name=group_id, asset_id=matched_id)
            return self.ExistingDecision(action="upload", group_id_or_name=group_id)

        action = on_exists
        if action == "prompt":
            action = self._choose_action_interactive(asset_name=asset_name, existing_items=existing_items)

        if action == "use":
            asset_id = existing_items[0].get("Id")
            if not isinstance(asset_id, str) or not asset_id:
                raise SystemExit("存在同名素材但无法解析 asset_id")
            return self.ExistingDecision(action="use", group_id_or_name=group_id, asset_id=asset_id)

        if action == "overwrite":
            return self.ExistingDecision(action="overwrite", group_id_or_name=group_id)

        if action == "new-group":
            suffix = asset_name[:16]
            new_group_name = f"{group_name}-{suffix}"
            return self.ExistingDecision(action="new-group", group_id_or_name=new_group_name)

        raise SystemExit(f"未知 --on-exists: {on_exists}")

    def upload_urls_to_assets(
        self,
        *,
        urls: List[str],
        group_name: str,
        project_name: str,
        asset_type: Optional[str] = None,
        name_prefix: str = "md5_",
        on_exists: str = "auto",  # auto/use/overwrite/new-group/prompt
        md5_timeout: int = 60,
    ) -> List[Dict[str, str]]:
        group_id = self.ensure_asset_group(group_name=group_name, project_name=project_name)

        out: List[Dict[str, str]] = []
        for u in urls:
            at = asset_type or self.guess_asset_type_from_url(u)
            new_digest = self.md5_of_url_content(u, timeout=md5_timeout)
            asset_name = f"{name_prefix}{self.md5_digest_to_b64(new_digest)}"

            existing = self.find_assets_by_name(group_id=group_id, project_name=project_name, name=asset_name)
            decision = self.decide_when_exists(
                on_exists=on_exists,
                group_name=group_name,
                group_id=group_id,
                project_name=project_name,
                asset_name=asset_name,
                existing_items=existing,
                new_digest=new_digest,
                md5_timeout=md5_timeout,
            )

            if decision.action == "use":
                self.wait_for_asset_active(asset_id=decision.asset_id, project_name=project_name)
                out.append({"url": u, "asset_id": decision.asset_id, "asset_type": at})
                continue

            target_group_id = group_id
            if decision.action == "new-group":
                target_group_id = self.ensure_asset_group(group_name=decision.group_id_or_name, project_name=project_name)

            if decision.action == "overwrite":
                # delete existing same-name in current group, then create
                for it in existing:
                    asset_id0 = it.get("Id")
                    if isinstance(asset_id0, str) and asset_id0:
                        self.delete_asset(asset_id=asset_id0, project_name=project_name)

            resp = self.create_asset(
                group_id=target_group_id,
                url=u,
                asset_type=at,
                name=asset_name,
                project_name=project_name,
            )
            asset_id = self._extract_id(resp)
            if not asset_id:
                raise self.AssetsAPIError("CreateAsset 响应中未找到 Id", details=resp)

            self.wait_for_asset_active(asset_id=asset_id, project_name=project_name)
            out.append({"url": u, "asset_id": asset_id, "asset_type": at})

        return out

    # ---------------------------
    # CLI
    # ---------------------------

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(description="Upload URLs to Assets library and print asset_id.")
        parser.add_argument("--urls", nargs="*", help="一个或多个可访问 URL")
        parser.add_argument("--url-file", help="URL 列表文件（每行一个 URL）")
        parser.add_argument("--group", default=os.environ.get("VOLC_ASSETS_GROUP", "volc-assets-group"), help="素材库 group 名称")
        parser.add_argument("--project", default=os.environ.get("VOLC_ASSETS_PROJECT", "default"), help="ProjectName，默认 default")
        parser.add_argument("--asset-type", choices=["Image", "Video", "Audio"], help="强制指定素材类型（默认按 URL 后缀猜测）")
        parser.add_argument("--host", default=os.environ.get("VOLC_ASSETS_HOST"), help="Assets API host（默认读 VOLC_ASSETS_HOST）")
        parser.add_argument("--region", default=os.environ.get("VOLC_ASSETS_REGION"), help="Assets region（默认读 VOLC_ASSETS_REGION）")
        parser.add_argument("--service", default=os.environ.get("VOLC_ASSETS_SERVICE"), help="Assets service（默认读 VOLC_ASSETS_SERVICE）")
        parser.add_argument("--version", default=os.environ.get("VOLC_ASSETS_VERSION"), help="Assets API version（默认读 VOLC_ASSETS_VERSION）")
        parser.add_argument(
            "--on-exists",
            choices=["auto", "use", "overwrite", "new-group", "prompt"],
            default="auto",
            help="同名素材已存在时策略：auto=同MD5复用，否则新建（默认 auto）",
        )
        parser.add_argument("--name-prefix", default="md5_", help="素材 Name 前缀（默认 md5_）")
        parser.add_argument("--md5-timeout", type=int, default=60, help="下载计算 MD5 的超时（秒），默认 60")
        parser.add_argument("--json", action="store_true", help="以 JSON 输出（用于脚本串联）")
        return parser

    @classmethod
    def main(cls, argv=None) -> None:
        args = cls.build_parser().parse_args(argv)

        raw_urls: List[str] = []
        if args.urls:
            raw_urls.extend([u for u in args.urls if u])
        if args.url_file:
            with open(args.url_file, "r", encoding="utf-8") as f:
                for line in f:
                    u = line.strip()
                    if u:
                        raw_urls.append(u)

        urls = cls.normalize_urls(raw_urls)
        if not urls:
            raise SystemExit("请传入 --urls 或 --url-file")

        api = cls(
            host=args.host,
            region=args.region,
            service=args.service,
            version=args.version,
        )

        try:
            items = api.upload_urls_to_assets(
                urls=urls,
                group_name=args.group,
                project_name=args.project,
                asset_type=args.asset_type,
                name_prefix=args.name_prefix,
                on_exists=args.on_exists,
                md5_timeout=args.md5_timeout,
            )
        except cls.AssetsAPIError as e:
            print(str(e), file=sys.stderr)
            raise SystemExit(1)

        if args.json:
            print(json.dumps({"items": items, "asset_ids": [x["asset_id"] for x in items]}, ensure_ascii=False))
            return

        for x in items:
            print(x["asset_id"])


if __name__ == "__main__":
    VolcAssetsAPI.main()
