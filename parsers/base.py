"""
基础解析器 - 定义通用接口
"""

import re
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from utils.fetcher import fetcher


class BaseParser(ABC):
    """平台解析器基类"""

    name: str = "base"
    domains: list = []

    @abstractmethod
    async def parse(self, url: str) -> Dict[str, Any]:
        """解析分享链接，返回结构化数据"""
        pass

    def extract_id(self, url: str) -> Optional[str]:
        """从 URL 中提取内容 ID"""
        return None

    def match(self, url: str) -> bool:
        """判断 URL 是否属于该平台"""
        for domain in self.domains:
            if domain in url.lower():
                return True
        return False

    async def resolve_short_link(self, url: str) -> str:
        """解析短链接，获取完整 URL"""
        return await fetcher.get_final_url(url)

    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本中的特殊字符"""
        if not text:
            return ""
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        text = text.replace('\n', ' ').replace('\r', '')
        return text.strip()

    @staticmethod
    def safe_json_extract(html: str, key: str) -> Optional[dict]:
        """从 HTML 中安全提取 JSON 数据"""
        patterns = [
            rf'{key}\s*=\s*(\{{.*?\}})',
            rf'"{key}"\s*:\s*({{.*?}})',
            rf'{key}:\s*({{.*?}})',
            rf'window\._{key}\s*=\s*(\{{.*?\}})',
        ]
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue
        return None
