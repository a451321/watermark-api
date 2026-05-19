"""
去水印 API 服务
FastAPI 后端，提供抖音/快手/小红书的解析接口
"""

import time
import re
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, HttpUrl

from parsers.douyin import DouyinParser
from parsers.kuaishou import KuaishouParser
from parsers.xiaohongshu import XiaohongshuParser
from parsers.bilibili import BilibiliParser

# ============================================================
# 初始化
# ============================================================

app = FastAPI(
    title="去水印 API",
    description="支持抖音、快手、小红书等平台的视频/图片去水印解析",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 中间件 - 允许小程序和前端调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 解析器注册表
PARSERS = {
    "douyin": DouyinParser(),
    "kuaishou": KuaishouParser(),
    "xiaohongshu": XiaohongshuParser(),
    "bilibili": BilibiliParser(),
}

# 日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    print(f"[API] {request.method} {request.url.path} - {response.status_code} - {duration:.2f}s")
    return response


# ============================================================
# 数据模型
# ============================================================

class ParseRequest(BaseModel):
    url: str

class ParseResponse(BaseModel):
    success: bool = True
    data: dict = {}
    error: Optional[str] = None

class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    parsers: list = ["douyin", "kuaishou", "xiaohongshu", "bilibili"]


# ============================================================
# 路由
# ============================================================

@app.get("/", response_model=HealthResponse)
async def root():
    """服务健康检查"""
    return HealthResponse()


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """健康检查接口"""
    return HealthResponse()


@app.post("/api/parse")
async def parse_url(request: ParseRequest):
    """
    解析分享链接
    
    输入: { "url": "https://v.douyin.com/xxxxx/" }
    
    返回: 
    {
        "success": true,
        "data": {
            "title": "视频标题",
            "type": "video",
            "videoUrl": "无水印视频地址",
            "images": [],
            "author": "作者",
            "platform": "douyin",
            ...
        }
    }
    """
    url = request.url.strip()
    
    if not url:
        raise HTTPException(status_code=400, detail="请输入有效的链接")
    
    # 自动补全协议
    if not url.startswith("http"):
        url = "https://" + url
    
    # 检测平台
    platform = detect_platform(url)
    if not platform:
        raise HTTPException(
            status_code=400, 
            detail="未识别的平台链接，目前支持：抖音、快手、小红书"
        )
    
    # 调用对应解析器
    parser = PARSERS.get(platform)
    if not parser:
        raise HTTPException(status_code=500, detail="解析器未就绪")
    
    try:
        data = await parser.parse(url)
        data["platform"] = data.get("platform") or platform
        data["originalUrl"] = url
        
        # 检查是否有实际内容
        if not data.get("videoUrl") and not data.get("images"):
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "data": data,
                    "warning": "未能提取到媒体资源，部分平台可能需要登录态"
                }
            )
        
        return {"success": True, "data": data}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"[API] 解析异常: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@app.post("/api/parse/batch")
async def parse_batch(request: Request):
    """批量解析（最多10个链接）"""
    try:
        body = await request.json()
        urls = body.get("urls", [])
    except Exception:
        raise HTTPException(status_code=400, detail="请求格式错误")
    
    if not urls or len(urls) > 10:
        raise HTTPException(status_code=400, detail="请提供 1-10 个链接")
    
    results = []
    for url in urls:
        try:
            platform = detect_platform(url)
            if platform and platform in PARSERS:
                data = await PARSERS[platform].parse(url)
                results.append({"success": True, "url": url, "data": data})
            else:
                results.append({"success": False, "url": url, "error": "未识别的平台"})
        except Exception as e:
            results.append({"success": False, "url": url, "error": str(e)})
    
    return {"success": True, "results": results}


# ============================================================
# 工具函数
# ============================================================

def detect_platform(url: str) -> Optional[str]:
    """根据 URL 自动检测平台"""
    url_lower = url.lower()
    
    if any(d in url_lower for d in ["douyin.com", "iesdouyin.com"]):
        return "douyin"
    if any(d in url_lower for d in ["kuaishou.com", "gifshow.com"]):
        return "kuaishou"
    if any(d in url_lower for d in ["xiaohongshu.com", "xhslink.com"]):
        return "xiaohongshu"
    if any(d in url_lower for d in ["bilibili.com", "b23.tv"]):
        return "bilibili"
    
    return None


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
    )
