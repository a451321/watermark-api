#!/bin/bash
# ============================================
# 去水印服务 - 一键启动脚本
# ============================================

echo "💧 去水印后端服务启动中..."

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要 Python 3.9+"
    exit 1
fi

# 进入目录
cd "$(dirname "$0")"

# 检查并创建虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null

# 安装依赖
echo "📥 安装依赖..."
pip install -q -r requirements.txt

# 安装 Playwright 浏览器（可选）
if command -v playwright &> /dev/null; then
    echo "🌐 检查 Playwright 浏览器..."
    playwright install chromium 2>/dev/null || echo "⚠️  Playwright 浏览器安装失败（非必需）"
fi

echo ""
echo "✅ 服务启动: http://localhost:8000"
echo "📖 API 文档: http://localhost:8000/docs"
echo ""
echo "按 Ctrl+C 停止服务"
echo "========================================"

# 启动服务
python3 main.py
