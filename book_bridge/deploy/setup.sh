#!/bin/bash
set -e

echo "============================================================"
echo "  书桥 BOOKBRIDGE 一键部署脚本"
echo "============================================================"

if [ "$EUID" -ne 0 ]; then
  echo "请使用 root 或 sudo 运行：sudo bash setup.sh"
  exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "[1/2] 安装 Docker..."
    curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
    systemctl enable docker && systemctl start docker
    echo "✅ Docker 安装完成"
else
    echo "[1/2] Docker 已安装"
fi

echo "[2/2] 构建并启动服务..."
cd "$(dirname "$0")/.."
docker compose down 2>/dev/null || true
docker compose build
docker compose up -d

sleep 3
IP=$(curl -s ifconfig.me 2>/dev/null || echo "服务器公网IP")
echo ""
echo "============================================================"
echo "  ✅ 部署完成！"
echo "============================================================"
echo "  访问地址: http://$IP/"
echo "  接口文档: http://$IP/docs"
echo ""
echo "  常用命令:"
echo "    查看日志: docker compose logs -f"
echo "    停止服务: docker compose down"
echo "    重启服务: docker compose restart"
echo "============================================================"