"""
HTTP 请求工具
- 自动处理重定向
- User-Agent 轮换
- 错误重试
"""

import httpx
import random
import asyncio
from typing import Optional
from urllib.parse import urlparse

# User-Agent 池
UA_POOL = [
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    # Android Chrome
    "Mozilla/5.0 (Linux; Android 13; SM-S9080) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    # iPad
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    # Desktop Chrome
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
]

# 默认请求头
def get_headers(referer: str = "", platform: str = "") -> dict:
    """生成请求头"""
    headers = {
        "User-Agent": random.choice(UA_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer

    # 平台特定头
    if platform == "douyin":
        headers["Referer"] = "https://www.douyin.com/"
    elif platform == "kuaishou":
        headers["Referer"] = "https://www.kuaishou.com/"
    elif platform == "xiaohongshu":
        headers["Referer"] = "https://www.xiaohongshu.com/"

    return headers


class Fetcher:
    """HTTP 请求客户端"""

    def __init__(self, timeout: int = 8, max_retries: int = 1):
        self.timeout = timeout
        self.max_retries = max_retries

    async def get(self, url: str, headers: dict = None, follow_redirects: bool = True, platform: str = "") -> httpx.Response:
        """GET 请求"""
        if headers is None:
            headers = get_headers(platform=platform)

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=follow_redirects,
            http2=True,
        ) as client:
            for attempt in range(self.max_retries):
                try:
                    resp = await client.get(url, headers=headers)
                    resp.raise_for_status()
                    return resp
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (429, 503):
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                except (httpx.ConnectError, httpx.TimeoutException) as e:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    raise

    async def post(self, url: str, headers: dict = None, json_data: dict = None, data: dict = None) -> httpx.Response:
        """POST 请求"""
        if headers is None:
            headers = get_headers()

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for attempt in range(self.max_retries):
                try:
                    resp = await client.post(url, headers=headers, json=json_data, data=data)
                    resp.raise_for_status()
                    return resp
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (429, 503):
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                except (httpx.ConnectError, httpx.TimeoutException):
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                    raise

    async def resolve_redirect(self, url: str) -> str:
        """解析短链接，返回最终 URL"""
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            try:
                resp = await client.get(url, headers=get_headers())
                if resp.status_code in (301, 302, 303, 307, 308):
                    location = resp.headers.get("Location", "")
                    if location:
                        return location
                return url
            except Exception:
                return url

    async def get_final_url(self, url: str) -> str:
        """获取最终重定向后的 URL"""
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            try:
                resp = await client.get(url, headers=get_headers())
                return str(resp.url)
            except Exception:
                return url


# 全局实例
fetcher = Fetcher()
