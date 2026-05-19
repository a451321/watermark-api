"""
快手解析器
支持格式:
  - https://v.kuaishou.com/xxxxx
  - https://www.kuaishou.com/short-video/xxxxxxxxx
  - https://live.kuaishou.com/u/xxx/xxxxxxxxx
"""

import re
import json
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from parsers.base import BaseParser
from utils.fetcher import fetcher, get_headers


class KuaishouParser(BaseParser):
    name = "kuaishou"
    domains = ["kuaishou.com", "gifshow.com", "chenzhongtech.com"]

    async def parse(self, url: str) -> Dict[str, Any]:
        """解析快手分享链接"""

        # Step 1: 解析短链接
        if "v.kuaishou.com" in url:
            url = await self.resolve_short_link(url)

        # Step 2: 获取视频页面
        result = await self._fetch_video_data(url)

        return result

    async def _fetch_video_data(self, url: str) -> Dict[str, Any]:
        """获取视频数据"""
        headers = get_headers(platform="kuaishou")

        try:
            resp = await fetcher.get(url, headers=headers)
            html = resp.text

            # 尝试从 HTML 中提取 window.__INITIAL_STATE__
            result = self._parse_initial_state(html)
            if result and result.get("videoUrl"):
                return result

            # 尝试从 meta 标签获取
            soup = BeautifulSoup(html, 'html.parser')
            result = self._parse_meta(soup, url)
            return result

        except Exception as e:
            print(f"[Kuaishou] 请求失败: {e}")

        return {
            "title": "快手视频",
            "description": "",
            "cover": "",
            "author": "",
            "avatar": "",
            "type": "video",
            "videoUrl": "",
            "images": [],
            "musicUrl": "",
            "platform": "kuaishou",
            "duration": 0,
            "likes": 0,
            "comment_count": 0,
            "share_count": 0,
            "originalUrl": url,
            "error": "解析失败，请确认链接有效或稍后重试"
        }

    def _parse_initial_state(self, html: str) -> Optional[Dict[str, Any]]:
        """解析 __INITIAL_STATE__"""
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*</script>',
            r'<script[^>]*>\s*window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*</script>',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return self._extract_from_state(data)
                except json.JSONDecodeError:
                    continue
        return None

    def _extract_from_state(self, data: dict) -> Optional[Dict[str, Any]]:
        """从状态数据中提取视频信息"""
        try:
            # 快手的数据结构可能在多个路径
            video_info = None

            # 路径1: feeds
            if "feeds" in data:
                feeds = data["feeds"]
                if isinstance(feeds, list) and feeds:
                    video_info = feeds[0]
                elif isinstance(feeds, dict):
                    video_info = feeds

            # 路径2: videoDetail
            if not video_info and "videoDetail" in data:
                video_info = data["videoDetail"]

            # 路径3: currentVideo
            if not video_info and "currentVideo" in data:
                video_info = data["currentVideo"]

            # 路径4: 递归搜索
            if not video_info:
                video_info = self._recursive_search(data)

            if not video_info:
                return None

            # 提取字段
            title = video_info.get("caption", "") or video_info.get("desc", "")
            author = video_info.get("userName", "") or video_info.get("authorName", "")

            if "author" in video_info:
                author = video_info["author"].get("name", "") or video_info["author"].get("userName", "")
            if "user" in video_info:
                author = video_info["user"].get("name", "") or author

            # 视频地址
            video_url = ""
            if "photoUrl" in video_info:
                video_url = video_info["photoUrl"]
            elif "videoUrl" in video_info:
                video_url = video_info["videoUrl"]
            elif "mainMvUrls" in video_info:
                urls = video_info["mainMvUrls"]
                if isinstance(urls, list) and urls:
                    video_url = urls[0].get("url", "")
                elif isinstance(urls, dict):
                    video_url = urls.get("url", "")

            # 封面
            cover = video_info.get("coverUrl", "") or video_info.get("poster", "")
            if not cover and "coverUrls" in video_info:
                covers = video_info["coverUrls"]
                if isinstance(covers, list) and covers:
                    cover = covers[0].get("url", "") if isinstance(covers[0], dict) else str(covers[0])

            # 作者头像
            avatar = ""
            if "headUrl" in video_info:
                avatar = video_info["headUrl"]
            elif "author" in video_info:
                avatar = video_info["author"].get("headUrl", "")

            return {
                "title": self.clean_text(title) or "快手视频",
                "description": "",
                "cover": cover,
                "author": self.clean_text(author),
                "avatar": avatar,
                "type": "video",
                "videoUrl": video_url,
                "images": [],
                "musicUrl": "",
                "platform": "kuaishou",
                "duration": video_info.get("duration", 0),
                "likes": video_info.get("likeCount", 0) or video_info.get("like", 0),
                "comment_count": video_info.get("commentCount", 0),
                "share_count": video_info.get("shareCount", 0),
            }
        except Exception as e:
            print(f"[Kuaishou] 状态提取失败: {e}")
            return None

    def _recursive_search(self, data, depth=0, max_depth=8):
        """递归搜索包含视频 URL 的节点"""
        if depth > max_depth:
            return None
        if not isinstance(data, dict):
            return None

        # 如果节点包含视频 URL 字段
        if any(k in data for k in ["photoUrl", "videoUrl", "mainMvUrls"]):
            return data

        for key, value in data.items():
            if isinstance(value, dict):
                result = self._recursive_search(value, depth + 1, max_depth)
                if result:
                    return result
            elif isinstance(value, list) and value:
                for item in value:
                    if isinstance(item, dict):
                        result = self._recursive_search(item, depth + 1, max_depth)
                        if result:
                            return result
        return None

    def _parse_meta(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """从 meta 标签提取信息"""
        title = ""
        cover = ""

        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content', '')

        og_image = soup.find('meta', property='og:image')
        if og_image:
            cover = og_image.get('content', '')

        # 尝试从 video 标签提取
        video_tag = soup.find('video')
        video_url = ""
        if video_tag:
            video_url = video_tag.get('src', '')
            if not video_url:
                source = video_tag.find('source')
                if source:
                    video_url = source.get('src', '')

        return {
            "title": self.clean_text(title) or "快手视频",
            "description": "",
            "cover": cover,
            "author": "",
            "avatar": "",
            "type": "video",
            "videoUrl": video_url,
            "images": [],
            "musicUrl": "",
            "platform": "kuaishou",
            "duration": 0,
            "likes": 0,
            "comment_count": 0,
            "share_count": 0,
        }
