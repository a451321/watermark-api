"""
抖音解析器
支持格式:
  - https://v.douyin.com/xxxxx/
  - https://www.douyin.com/video/123456789
  - https://www.iesdouyin.com/share/video/123456789/
"""

import re
import json
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from parsers.base import BaseParser
from utils.fetcher import fetcher, get_headers


class DouyinParser(BaseParser):
    name = "douyin"
    domains = ["douyin.com", "iesdouyin.com", "v.douyin.com"]

    async def parse(self, url: str) -> Dict[str, Any]:
        """解析抖音分享链接"""

        # Step 1: 解析短链接
        if "v.douyin.com" in url:
            url = await self.resolve_short_link(url)

        # Step 2: 提取视频 ID
        video_id = self.extract_id(url)
        if not video_id:
            raise ValueError("无法从链接中提取视频 ID")

        # Step 3: 获取视频页面数据
        result = await self._fetch_video_data(video_id, url)

        return result

    def extract_id(self, url: str) -> Optional[str]:
        """提取视频 ID"""
        patterns = [
            r'/video/(\d+)',
            r'/share/video/(\d+)',
            r'modal_id=(\d+)',
            r'video/(\d+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _fetch_video_data(self, video_id: str, url: str) -> Dict[str, Any]:
        """
        获取视频数据
        方法: 请求 douyin.com 的 SSG API (服务端渲染时的接口)
        """
        headers = get_headers(platform="douyin")

        # 方法1: 请求视频页面 HTML，提取 RENDER_DATA
        try:
            video_url = f"https://www.douyin.com/video/{video_id}"
            resp = await fetcher.get(video_url, headers=headers)

            result = self._parse_html(resp.text, video_id)
            if result and result.get("videoUrl"):
                return result
        except Exception as e:
            print(f"[Douyin] HTML 解析失败: {e}")

        # 方法2: 使用 douyin.com 的 API 接口
        try:
            result = await self._fetch_via_api(video_id)
            if result and result.get("videoUrl"):
                return result
        except Exception as e:
            print(f"[Douyin] API 解析失败: {e}")

        # 返回基本信息
        return {
            "title": f"抖音视频 {video_id}",
            "description": "",
            "cover": f"https://p3-pc.douyinpic.com/aweme/100x100/{video_id}.jpeg",
            "author": "",
            "avatar": "",
            "type": "video",
            "videoUrl": "",
            "images": [],
            "musicUrl": "",
            "platform": "douyin",
            "duration": 0,
            "likes": 0,
            "comment_count": 0,
            "share_count": 0,
            "originalUrl": url,
            "error": "解析失败，请确认链接有效或稍后重试"
        }

    def _parse_html(self, html: str, video_id: str) -> Optional[Dict[str, Any]]:
        """从 HTML 中提取视频数据"""
        soup = BeautifulSoup(html, 'lxml')

        # 尝试提取 RENDER_DATA (抖音 SSG 渲染数据)
        render_match = re.search(
            r'<script[^>]*id="RENDER_DATA"[^>]*>(.*?)</script>',
            html, re.DOTALL
        )
        if render_match:
            try:
                from urllib.parse import unquote
                render_text = unquote(render_match.group(1))
                render_data = json.loads(render_text)

                # 遍历查找视频数据
                video_data = self._find_video_in_render(render_data)
                if video_data:
                    return video_data
            except Exception:
                pass

        # 尝试从普通 script 标签提取
        script_patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*</script>',
            r'<script[^>]*>\s*window\._ROUTER_DATA\s*=\s*({.*?});?\s*</script>',
        ]
        for pattern in script_patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    video_data = self._extract_from_initial_state(data)
                    if video_data:
                        return video_data
                except json.JSONDecodeError:
                    continue

        # 从 meta 标签提取基本信息
        title = ""
        desc = ""
        cover = ""

        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content', '')

        og_desc = soup.find('meta', property='og:description')
        if og_desc:
            desc = og_desc.get('content', '')

        og_image = soup.find('meta', property='og:image')
        if og_image:
            cover = og_image.get('content', '')

        return {
            "title": self.clean_text(title) or f"抖音视频 {video_id}",
            "description": self.clean_text(desc),
            "cover": cover,
            "author": "",
            "avatar": "",
            "type": "video",
            "videoUrl": "",
            "images": [],
            "musicUrl": "",
            "platform": "douyin",
            "duration": 0,
            "likes": 0,
            "comment_count": 0,
            "share_count": 0,
        }

    def _find_video_in_render(self, data: dict, depth: int = 0) -> Optional[Dict]:
        """递归查找视频数据"""
        if depth > 10 or not isinstance(data, dict):
            return None

        # 查找包含 video/play_addr 的节点
        if "video" in data and isinstance(data["video"], dict):
            v = data["video"]
            play_addr = v.get("play_addr") or v.get("playAddr") or {}
            url_list = play_addr.get("url_list") or play_addr.get("urlList") or []

            if url_list:
                # 无水印地址（替换 watermark=1 为 watermark=0）
                video_url = url_list[0]
                video_url = video_url.replace("watermark=1", "watermark=0")
                video_url = video_url.replace("watermark%3D1", "watermark%3D0")

                author_info = data.get("author", {})
                music_info = data.get("music", {})

                return {
                    "title": self.clean_text(data.get("desc", "")),
                    "description": "",
                    "cover": (v.get("cover") or v.get("origin_cover") or {}).get("url_list", [""])[0] if isinstance(v.get("cover"), dict) else "",
                    "author": author_info.get("nickname", ""),
                    "avatar": (author_info.get("avatar_thumb") or author_info.get("avatar_medium") or {}).get("url_list", [""])[0] if isinstance(author_info.get("avatar_thumb"), dict) else "",
                    "type": "video",
                    "videoUrl": video_url,
                    "images": [],
                    "musicUrl": (music_info.get("play_url") or {}).get("url_list", [""])[0] if isinstance(music_info.get("play_url"), dict) else "",
                    "platform": "douyin",
                    "duration": v.get("duration", 0),
                    "likes": data.get("statistics", {}).get("digg_count", 0),
                    "comment_count": data.get("statistics", {}).get("comment_count", 0),
                    "share_count": data.get("statistics", {}).get("share_count", 0),
                }

        # 递归搜索子节点
        for key, value in data.items():
            if isinstance(value, dict):
                result = self._find_video_in_render(value, depth + 1)
                if result:
                    return result
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        result = self._find_video_in_render(item, depth + 1)
                        if result:
                            return result

        return None

    def _extract_from_initial_state(self, data: dict) -> Optional[Dict]:
        """从 __INITIAL_STATE__ 提取视频数据"""
        return self._find_video_in_render(data)

    async def _fetch_via_api(self, video_id: str) -> Optional[Dict[str, Any]]:
        """通过 API 接口获取视频数据"""
        try:
            api_url = f"https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/?item_ids={video_id}"
            headers = get_headers(platform="douyin")
            headers["Referer"] = f"https://www.douyin.com/video/{video_id}"

            resp = await fetcher.get(api_url, headers=headers)
            data = resp.json()

            if data.get("status_code") == 0 and data.get("item_list"):
                item = data["item_list"][0]
                return self._parse_api_item(item)

        except Exception as e:
            print(f"[Douyin] API 请求失败: {e}")

        return None

    def _parse_api_item(self, item: dict) -> Dict[str, Any]:
        """解析 API 返回的视频条目"""
        video = item.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])

        # 无水印地址
        video_url = url_list[0] if url_list else ""
        video_url = video_url.replace("watermark=1", "watermark=0")

        author = item.get("author", {})
        music = item.get("music", {})
        statistics = item.get("statistics", {})

        return {
            "title": self.clean_text(item.get("desc", "")),
            "description": "",
            "cover": (video.get("origin_cover", {}) or video.get("cover", {})).get("url_list", [""])[0],
            "author": author.get("nickname", ""),
            "avatar": (author.get("avatar_thumb", {}) or author.get("avatar_medium", {})).get("url_list", [""])[0],
            "type": "video",
            "videoUrl": video_url,
            "images": [],
            "musicUrl": (music.get("play_url", {})).get("url_list", [""])[0],
            "platform": "douyin",
            "duration": video.get("duration", 0),
            "likes": statistics.get("digg_count", 0),
            "comment_count": statistics.get("comment_count", 0),
            "share_count": statistics.get("share_count", 0),
        }
