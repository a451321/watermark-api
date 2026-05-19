"""
小红书解析器
支持格式:
  - https://www.xiaohongshu.com/discovery/item/xxxxxxxxx
  - https://www.xiaohongshu.com/explore/xxxxxxxxx
  - https://xhslink.com/xxxxx
  - https://www.xiaohongshu.com/note/xxxxxxxxx (新版)
"""

import re
import json
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from parsers.base import BaseParser
from utils.fetcher import fetcher, get_headers


class XiaohongshuParser(BaseParser):
    name = "xiaohongshu"
    domains = ["xiaohongshu.com", "xhslink.com"]

    async def parse(self, url: str) -> Dict[str, Any]:
        """解析小红书链接"""

        # Step 1: 解析短链接
        if "xhslink.com" in url:
            url = await self.resolve_short_link(url)

        # Step 2: 提取笔记 ID
        note_id = self.extract_id(url)
        if not note_id:
            raise ValueError("无法提取笔记 ID")

        # Step 3: 获取笔记详情
        result = await self._fetch_note_data(note_id, url)
        return result

    def extract_id(self, url: str) -> Optional[str]:
        """提取笔记 ID"""
        patterns = [
            r'/explore/([a-zA-Z0-9]+)',
            r'/discovery/item/([a-zA-Z0-9]+)',
            r'/note/([a-zA-Z0-9]+)',
            r'/a/([a-zA-Z0-9]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    async def _fetch_note_data(self, note_id: str, url: str) -> Dict[str, Any]:
        """获取笔记数据"""
        headers = get_headers(platform="xiaohongshu")
        # 小红书需要 Cookie 才能访问详情
        headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "zh-CN,zh;q=0.9",
        })

        try:
            note_url = f"https://www.xiaohongshu.com/explore/{note_id}"
            resp = await fetcher.get(note_url, headers=headers)

            # 尝试从 __INITIAL_STATE__ 提取
            result = self._parse_initial_state(resp.text)
            if result:
                return result

            # 尝试从 meta 标签提取
            soup = BeautifulSoup(resp.text, 'html.parser')
            result = self._parse_meta(soup, url, note_id)
            return result

        except Exception as e:
            print(f"[XHS] 请求失败: {e}")

        return {
            "title": f"小红书笔记 {note_id}",
            "description": "",
            "cover": "",
            "author": "",
            "avatar": "",
            "type": "image",
            "videoUrl": "",
            "images": [],
            "musicUrl": "",
            "platform": "xiaohongshu",
            "duration": 0,
            "likes": 0,
            "comment_count": 0,
            "share_count": 0,
            "originalUrl": url,
            "error": "解析失败，小红书需要登录态Cookie才能获取详情。请确认链接有效。"
        }

    def _parse_initial_state(self, html: str) -> Optional[Dict[str, Any]]:
        """解析 __INITIAL_STATE__"""
        pattern = r'window\.__INITIAL_STATE__\s*=\s*({.*?});?\s*</script>'

        match = re.search(pattern, html, re.DOTALL)
        if match:
            try:
                # 小红书的数据可能包含未转义的特殊字符
                data_str = match.group(1)
                # 替换可能出问题的 undefined
                data_str = data_str.replace('undefined', 'null')
                data = json.loads(data_str)
                return self._extract_note(data)
            except json.JSONDecodeError as e:
                print(f"[XHS] JSON 解析失败: {e}")

        # 尝试提取 serverData
        server_pattern = r'<script[^>]*>\s*window\.__INITIAL_SSR_DATA__\s*=\s*({.*?});?\s*</script>'
        match = re.search(server_pattern, html, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1).replace('undefined', 'null'))
                return self._extract_note(data)
            except json.JSONDecodeError:
                pass

        return None

    def _extract_note(self, data: dict) -> Optional[Dict[str, Any]]:
        """从小红书状态数据中提取笔记信息"""
        try:
            note = None

            # 路径1: note.noteDetailMap
            if "note" in data:
                note_data = data["note"]
                if "noteDetailMap" in note_data:
                    note_map = note_data["noteDetailMap"]
                    # 获取第一个笔记
                    for nid, detail in note_map.items():
                        if isinstance(detail, dict) and "note" in detail:
                            note = detail["note"]
                            break
                elif "noteDetail" in note_data:
                    note = note_data["noteDetail"]
                elif "currentNote" in note_data:
                    note = note_data["currentNote"]

            # 路径2: noteDetail
            if not note and "noteDetail" in data:
                note = data["noteDetail"]

            # 路径3: 递归搜索
            if not note:
                note = self._recursive_find_note(data)

            if not note:
                return None

            # 判断类型
            note_type = note.get("type", "")
            is_video = note_type == "video"

            # 提取图片
            images = []
            if "imageList" in note:
                for img in note["imageList"]:
                    if isinstance(img, dict):
                        # 优先使用原图
                        url = img.get("urlDefault") or img.get("url") or img.get("traceId") or ""
                        # 构建完整图片 URL
                        if url:
                            images.append(url)

            # 提取视频
            video_url = ""
            if is_video and "video" in note:
                video_info = note["video"]
                if isinstance(video_info, dict):
                    video_url = video_info.get("media", {}).get("stream", {}).get("h264", [{}])[0].get("masterUrl", "")

            # 作者信息
            author = ""
            avatar = ""
            if "user" in note:
                user = note["user"]
                author = user.get("nickname", "") or user.get("nickName", "")
                avatar = user.get("avatar", "") or user.get("images", "")

            # 封面
            cover = ""
            if images:
                cover = images[0]
            elif "cover" in note:
                cover_info = note["cover"]
                if isinstance(cover_info, dict):
                    cover = cover_info.get("urlDefault", "") or cover_info.get("url", "")

            return {
                "title": self.clean_text(note.get("title", "") or note.get("desc", "")),
                "description": self.clean_text(note.get("desc", "")),
                "cover": cover,
                "author": self.clean_text(author),
                "avatar": avatar,
                "type": "video" if is_video else "image",
                "videoUrl": video_url,
                "images": images,
                "musicUrl": "",
                "platform": "xiaohongshu",
                "duration": note.get("video", {}).get("duration", 0) if isinstance(note.get("video"), dict) else 0,
                "likes": note.get("interactInfo", {}).get("likedCount", 0),
                "comment_count": note.get("interactInfo", {}).get("commentCount", 0),
                "share_count": note.get("interactInfo", {}).get("shareCount", 0),
            }

        except Exception as e:
            print(f"[XHS] 笔记提取失败: {e}")
            return None

    def _recursive_find_note(self, data, depth=0, max_depth=8):
        """递归查找包含 note 的节点"""
        if depth > max_depth:
            return None
        if not isinstance(data, dict):
            return None

        # 如果同时有 imageList 和 title，很可能是笔记
        if "imageList" in data and ("title" in data or "desc" in data):
            return data
        if "video" in data and "title" in data:
            return data

        for key, value in data.items():
            if isinstance(value, dict):
                result = self._recursive_find_note(value, depth + 1, max_depth)
                if result:
                    return result
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        result = self._recursive_find_note(item, depth + 1, max_depth)
                        if result:
                            return result
        return None

    def _parse_meta(self, soup: BeautifulSoup, url: str, note_id: str) -> Dict[str, Any]:
        """从 meta 标签提取信息"""
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

        # 检查是否有图片
        images = []
        img_tags = soup.find_all('img', class_=re.compile(r'note-image|swiper|image'))
        for img in img_tags:
            src = img.get('src') or img.get('data-src', '')
            if src and 'xhscdn' in src or 'sns-webpic' in src:
                images.append(src)

        return {
            "title": self.clean_text(title) or f"小红书笔记 {note_id}",
            "description": self.clean_text(desc),
            "cover": cover,
            "author": "",
            "avatar": "",
            "type": "image" if images else "image",
            "videoUrl": "",
            "images": images,
            "musicUrl": "",
            "platform": "xiaohongshu",
            "duration": 0,
            "likes": 0,
            "comment_count": 0,
            "share_count": 0,
        }
