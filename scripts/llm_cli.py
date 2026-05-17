#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大型语言模型 (LLM) CLI
基于火山引擎 Ark Runtime Responses API 实现文本生成功能。

特点：
- 所有逻辑封装在 VolcLLM 类内。
- 极简的文本问答接口，适用于文本分析、翻译、摘要、编程等纯文本场景。
- 自动解析最新的 Responses API 输出结构（包括推理过程与最终回答）。
"""

import argparse
import os
import sys
import time
from typing import Any, Dict, List, Optional

from volcenginesdkarkruntime import Ark


class VolcLLM:
    def __init__(
        self,
        *,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self.api_url = (api_url or os.environ.get("VOLC_ARK_API_URL", "https://ark.cn-beijing.volces.com/api/v3")).strip()
        self.api_key = (api_key or os.environ.get("VOLC_ARK_API_KEY", "")).strip()
        self.model = (model or os.environ.get("VOLC_ARK_LLM_MODEL", "")).strip()

        missing_envs = []
        if not self.api_key:
            missing_envs.append("VOLC_ARK_API_KEY")
        if not self.model:
            missing_envs.append("VOLC_ARK_LLM_MODEL")
        if missing_envs:
            raise ValueError(f"请一次性设置以下环境变量: {', '.join(missing_envs)}")

        self.client = Ark(base_url=self.api_url, api_key=self.api_key)

    @staticmethod
    def build_input_list(system_text: Optional[str] = None, user_text: str = "") -> List[Dict[str, Any]]:
        """
        构造标准的 input_list
        :param system_text: 可选的系统级提示词 (System Prompt)
        :param user_text: 用户输入的文本指令
        :return: 组装好的 input_list
        """
        input_list = []
        
        if system_text:
            input_list.append({
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": system_text
                    }
                ]
            })
            
        input_list.append({
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": user_text
                }
            ]
        })
        
        return input_list

    def chat(self, input_list: List[Dict[str, Any]]) -> str:
        """
        发起 Responses API 纯文本推理请求
        :param input_list: 符合 Responses API 规范的消息列表
        """
        if not input_list:
            raise ValueError("输入参数 input_list 不能为空")

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 正在请求模型 {self.model} 进行文本生成...", file=sys.stderr)
        
        try:
            response = self.client.responses.create(
                model=self.model,
                input=input_list
            )
        except Exception as e:
            raise RuntimeError(f"API 请求失败: {str(e)}")

        # 解析 Responses API 新版的输出结构
        # 返回对象通常有一个 output 列表，里面包含推理过程（ResponseReasoningItem）和最终回答（ResponseOutputMessage）
        if hasattr(response, "output") and isinstance(response.output, list) and len(response.output) > 0:
            # 尝试直接按 ve_responses.py 中的快捷取法获取： response.output[0].content[0].text
            try:
                first_output = response.output[0]
                if hasattr(first_output, "content") and isinstance(first_output.content, list) and len(first_output.content) > 0:
                    first_content = first_output.content[0]
                    if hasattr(first_content, "text"):
                        return first_content.text
            except Exception:
                pass
                
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
        parser = argparse.ArgumentParser(description="大型语言模型 (LLM) CLI - 纯文本生成工具")
        parser.add_argument("--system", "-s", help="可选的系统提示词文本（System Prompt），用于设定人设或背景规则")
        parser.add_argument("--system-file", help="可选的系统提示词文件路径（优先级高于 --system）")
        parser.add_argument("--text", "-t", help="输入的指令/提问文本（如：'你好，请写一首诗'）")
        parser.add_argument("--text-file", help="可选的提问文本文件路径（优先级高于 --text）")
        parser.add_argument("--model", help="指定模型版本（默认读取 VOLC_ARK_LLM_MODEL）")
        return parser

    @classmethod
    def main(cls, argv=None) -> None:
        args = cls.build_parser().parse_args(argv)
        
        # 处理 system text
        system_text = args.system
        if args.system_file:
            if not os.path.exists(args.system_file):
                print(f"❌ 错误: 系统提示词文件不存在: {args.system_file}", file=sys.stderr)
                sys.exit(1)
            try:
                with open(args.system_file, "r", encoding="utf-8") as f:
                    system_text = f.read()
            except Exception as e:
                print(f"❌ 错误: 无法读取系统提示词文件: {e}", file=sys.stderr)
                sys.exit(1)

        # 处理 user text
        user_text = args.text
        if args.text_file:
            if not os.path.exists(args.text_file):
                print(f"❌ 错误: 提问文本文件不存在: {args.text_file}", file=sys.stderr)
                sys.exit(1)
            try:
                with open(args.text_file, "r", encoding="utf-8") as f:
                    user_text = f.read()
            except Exception as e:
                print(f"❌ 错误: 无法读取提问文本文件: {e}", file=sys.stderr)
                sys.exit(1)
                
        if not user_text:
            print("❌ 错误: 必须通过 --text 或 --text-file 提供输入指令", file=sys.stderr)
            sys.exit(1)
        
        # 组装默认的单轮对话 input_list
        input_list = cls.build_input_list(system_text=system_text, user_text=user_text)
        
        try:
            llm = cls(model=args.model)
            result = llm.chat(input_list=input_list)
            
            # 将模型的回答输出到标准输出
            print(result)

        except Exception as e:
            print(f"❌ 运行失败: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    VolcLLM.main()
