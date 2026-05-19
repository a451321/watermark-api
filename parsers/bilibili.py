"""
哔哩哔哩解析器
支持格式:
  - https://www.bilibili.com/video/BV1xx411c7mD
  - https://b23.tv/xxxxx
  - https://www.bilibili.com/video/av123456
"""

import re
import json
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from parsers.base import BaseParser
from utils.fetcher import fetcher, get_headers


class BilibiliParser(BaseParser):
    name = "bilibili"
    domains = ["bilibili.com", "b23.tv"]

    async def parse(self, url: str) -> Dict[str, Any]:
        """解析B站视频链接"""

        # Step 1: 解析短链接 b23.tv
        if "b23.tv" in url or "b23.tv" in url.lower():
            url = await self.resolve_short_link(url)

        # Step 2: 提取 BV/AV 号
        video_id = self.extract_id(url)
        if not video_id:
            raise ValueError("无法从链接中提取视频ID，请使用 BV 或 AV 号链接")

        # Step 3: 调用B站API获取详情
        result = await self._fetch_video_info(video_id, url)
        return result

    def extract_id(self, url: str) -> Optional[Dict[str, str]]:
        """提取 BV 或 AV 号"""
        # BV号: BV开头，10位字母数字
        bv_match = re.search(r'(BV[a-zA-Z0-9]{10})', url)
        if bv_match:
            return {"bvid": bv_match.group(1)}

        # AV号
        av_match = re.search(r'av(\d+)', url, re.IGNORECASE)
        if av_match:
            return {"aid": int(av_match.group(1))}

        return None

    async def _fetch_video_info(self, video_id: Dict[str, str], url: str) -> Dict[str, Any]:
        """调用B站公开API获取视频信息"""
        headers = get_headers(platform="bilibili")
        headers.update({
            "Referer": "https://www.bilibili.com/",
            "Origin": "https://www.bilibili.com",
        })

        try:
            # API 1: 获取视频基本信息
            if "bvid" in video_id:
                info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={video_id['bvid']}"
            else:
                info_url = f"https://api.bilibili.com/x/web-interface/view?aid={video_id['aid']}"

            resp = await fetcher.get(info_url, headers=headers)
            data = resp.json()

            if data.get("code") != 0:
                raise ValueError(f"B站API返回错误: {data.get('message', '未知错误')}")

            video_data = data["data"]

            # 提取基本信息
            title = self.clean_text(video_data.get("title", ""))
            desc = self.clean_text(video_data.get("desc", ""))
            cover = video_data.get("pic", "")
            author = video_data.get("owner", {}).get("name", "")
            avatar = video_data.get("owner", {}).get("face", "")
            duration = video_data.get("duration", 0)
            cid = video_data.get("cid", 0)

            # 统计
            stat = video_data.get("stat", {})
            likes = stat.get("like", 0)
            comments = stat.get("reply", 0)
            shares = stat.get("share", 0)
            views = stat.get("view", 0)

            # API 2: 获取视频播放地址
            bvid = video_id.get("bvid") or video_data.get("bvid", "")
            if not bvid:
                bvid = video_data.get("bvid", "")

            play_url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=80&fnval=1&fourk=1"
            play_resp = await fetcher.get(play_url, headers=headers)
            play_data = play_resp.json()

            video_url = ""
            if play_data.get("code") == 0:
                durl = play_data.get("data", {}).get("durl", [])
                if durl and len(durl) > 0:
                    video_url = durl[0].get("url", "")
                    # B站视频URL可能带有参数，直接可用
                # 备用：dash 格式
                if not video_url:
                    dash = play_data.get("data", {}).get("dash", {})
                    if dash:
                        video_list = dash.get("video", [])
                        if video_list:
                            # 选最高画质
                            video_url = video_list[-1].get("baseUrl", "") or video_list[-1].get("base_url", "")

            return {
                "title": title or f"B站视频",
                "description": desc,
                "cover": cover,
                "author": author,
                "avatar": avatar,
                "type": "video",
                "videoUrl": video_url,
                "images": [],
                "musicUrl": "",
                "platform": "bilibili",
                "duration": duration,
                "likes": likes,
                "comment_count": comments,
                "share_count": shares,
                "views": views,
                "originalUrl": url,
                "bvid": bvid,
            }

        except Exception as e:
            print(f"[Bilibili] 解析失败: {e}")
            return {
                "title": f"B站视频",
                "description": "",
                "cover": "",
                "author": "",
                "avatar": "",
                "type": "video",
                "videoUrl": "",
                "images": [],
                "musicUrl": "",
                "platform": "bilibili",
                "duration": 0,
                "likes": 0,
                "comment_count": 0,
                "share_count": 0,
                "originalUrl": url,
                "error": f"解析失败: {str(e)}"
            }
