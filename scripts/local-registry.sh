#!/bin/bash

# 本地Docker Registry管理脚本
# 用于支持多平台镜像的本地存储和测试

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

REGISTRY_NAME="local-registry"
REGISTRY_PORT="6000"
REGISTRY_IMAGE="registry:2"

# 启动本地registry
start_registry() {
    echo -e "${BLUE}启动本地Docker Registry...${NC}"
    
    # 检查是否已经运行
    if docker ps | grep -q "$REGISTRY_NAME"; then
        echo -e "${YELLOW}本地Registry已在运行${NC}"
        return 0
    fi
    
    # 启动registry容器
    docker run -d \
        --name "$REGISTRY_NAME" \
        --restart=unless-stopped \
        -p "$REGISTRY_PORT:5000" \
        "$REGISTRY_IMAGE"
    
    echo -e "${GREEN}本地Registry启动成功${NC}"
    echo -e "${BLUE}Registry地址: localhost:$REGISTRY_PORT${NC}"
}

# 停止本地registry
stop_registry() {
    echo -e "${BLUE}停止本地Docker Registry...${NC}"
    docker stop "$REGISTRY_NAME" >/dev/null 2>&1 || true
    docker rm "$REGISTRY_NAME" >/dev/null 2>&1 || true
    echo -e "${GREEN}本地Registry已停止${NC}"
}

# 重启本地registry
restart_registry() {
    stop_registry
    start_registry
}

# 查看registry状态
status_registry() {
    echo -e "${BLUE}检查本地Registry状态...${NC}"
    
    if docker ps | grep -q "$REGISTRY_NAME"; then
        echo -e "${GREEN}✅ 本地Registry正在运行${NC}"
        echo -e "${BLUE}地址: localhost:$REGISTRY_PORT${NC}"
        
        # 列出存储的镜像
        echo -e "${BLUE}存储的镜像:${NC}"
        curl -s http://localhost:$REGISTRY_PORT/v2/_catalog | jq -r '.repositories[]' 2>/dev/null || echo "无镜像或jq未安装"
    else
        echo -e "${RED}❌ 本地Registry未运行${NC}"
    fi
}

# 推送镜像到本地registry
push_to_local() {
    local image_name="$1"
    local image_tag="${2:-latest}"
    
    if [ -z "$image_name" ]; then
        echo -e "${RED}错误: 请指定镜像名称${NC}"
        echo "用法: $0 push <镜像名称> [标签]"
        exit 1
    fi
    
    echo -e "${BLUE}推送镜像到本地Registry...${NC}"
    
    # 确保registry运行
    start_registry
    
    # 重新标记镜像
    local local_tag="localhost:$REGISTRY_PORT/$image_name:$image_tag"
    docker tag "$image_name:$image_tag" "$local_tag"
    
    # 推送到本地registry
    docker push "$local_tag"
    
    echo -e "${GREEN}推送完成: $local_tag${NC}"
}

# 从本地registry拉取镜像
pull_from_local() {
    local image_name="$1"
    local image_tag="${2:-latest}"
    
    if [ -z "$image_name" ]; then
        echo -e "${RED}错误: 请指定镜像名称${NC}"
        echo "用法: $0 pull <镜像名称> [标签]"
        exit 1
    fi
    
    echo -e "${BLUE}从本地Registry拉取镜像...${NC}"
    
    local local_tag="localhost:$REGISTRY_PORT/$image_name:$image_tag"
    docker pull "$local_tag"
    
    echo -e "${GREEN}拉取完成: $local_tag${NC}"
}

# 显示帮助信息
show_help() {
    echo -e "${BLUE}本地Docker Registry管理脚本${NC}"
    echo ""
    echo "用法: $0 [命令] [参数]"
    echo ""
    echo "命令:"
    echo "  start               启动本地Registry"
    echo "  stop                停止本地Registry"
    echo "  restart             重启本地Registry"
    echo "  status              查看Registry状态"
    echo "  push <镜像> [标签]   推送镜像到本地Registry"
    echo "  pull <镜像> [标签]   从本地Registry拉取镜像"
    echo "  help                显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start"
    echo "  $0 push f5-scheduler v1.0"
    echo "  $0 pull f5-scheduler v1.0"
    echo ""
    echo "配合多平台构建使用:"
    echo "  # 1. 启动本地registry"
    echo "  $0 start"
    echo "  # 2. 多平台构建并推送到本地registry"
    echo "  ../build-and-run.sh buildx --production --push -t localhost:6000/f5-scheduler:v1.0"
    echo "  # 3. 从本地registry拉取使用"
    echo "  docker run localhost:6000/f5-scheduler:v1.0"
}

# 主函数
case "${1:-help}" in
    start)
        start_registry
        ;;
    stop)
        stop_registry
        ;;
    restart)
        restart_registry
        ;;
    status)
        status_registry
        ;;
    push)
        push_to_local "$2" "$3"
        ;;
    pull)
        pull_from_local "$2" "$3"
        ;;
    help|*)
        show_help
        ;;
esac 