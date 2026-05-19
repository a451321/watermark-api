# 🔧 去水印后端 API

支持抖音、快手、小红书的视频/图片去水印解析服务。

## 🚀 快速部署

### 方式一：本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动服务
python main.py
# 或: uvicorn main:app --host 0.0.0.0 --port 8000

# 3. 访问文档
# http://localhost:8000/docs
```

### 方式二：Docker 部署

```bash
# 启动
docker-compose up -d

# 查看日志
docker-compose logs -f api

# 停止
docker-compose down
```

## 📡 API 接口

### POST /api/parse

解析分享链接，返回无水印媒体地址。

**请求:**
```json
{
  "url": "https://v.douyin.com/xxxxx/"
}
```

**成功响应:**
```json
{
  "success": true,
  "data": {
    "title": "视频标题",
    "description": "视频描述",
    "cover": "https://...",
    "author": "作者昵称",
    "avatar": "https://...",
    "type": "video",
    "videoUrl": "https://...无水印地址",
    "images": [],
    "musicUrl": "https://...",
    "platform": "douyin",
    "duration": 15,
    "likes": 1234,
    "comment_count": 56,
    "share_count": 78
  }
}
```

### POST /api/parse/batch

批量解析（最多10个链接）

### GET /api/health

健康检查

## 🔗 对接小程序

在小程序 `utils/api.js` 中修改：

```javascript
const BASE_URL = 'https://你的服务器地址';
```

### ⚠️ 微信小程序要求

微信小程序要求后端使用 **HTTPS** 且域名已备案。开发调试时可以：

1. 在「微信开发者工具」→ 详情 → 本地设置 → 勾选「不校验合法域名」
2. 使用 **ngrok** 或 **frp** 做内网穿透测试

推荐方案：
```bash
# 使用 ngrok 暴露本地服务
ngrok http 8000
# 将生成的 https 地址填入小程序
```

## 📁 项目结构

```
watermark-api/
├── main.py                 # FastAPI 主入口
├── parsers/
│   ├── base.py             # 基础解析器
│   ├── douyin.py           # 抖音解析器
│   ├── kuaishou.py         # 快手解析器
│   └── xiaohongshu.py      # 小红书解析器
├── utils/
│   └── fetcher.py          # HTTP 请求工具
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🛠️ 技术原理

### 抖音 (Douyin)
1. 解析 `v.douyin.com` 短链接 → 获取完整视频页 URL
2. 提取页面内的 `RENDER_DATA` (SSR 渲染数据)
3. 从 JSON 中提取 `play_addr.url_list[0]`
4. 将 `watermark=1` 替换为 `watermark=0` 获得无水印地址
5. 备用：调用 `iesdouyin.com/web/api/v2/aweme/iteminfo/` API

### 快手 (Kuaishou)
1. 解析 `v.kuaishou.com` 短链接
2. 提取 `window.__INITIAL_STATE__` 
3. 递归搜索 `photoUrl` / `mainMvUrls` 字段
4. 提取视频地址和作品信息

### 小红书 (Xiaohongshu)
1. 解析 `xhslink.com` 短链接
2. 提取笔记 ID
3. 访问笔记页面，提取 `__INITIAL_STATE__`
4. 解析 `noteDetailMap` 获取图片/视频
5. ⚠️ 小红书部分接口需要登录态 Cookie

## ⚠️ 注意事项

- 平台接口可能随时变化，解析器需要定期维护
- 频繁请求可能触发反爬机制，建议加请求间隔
- 仅用于学习交流，请尊重原创作者版权
