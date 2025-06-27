#!/bin/bash

# F5 LLM推理网关调度器 Docker构建和运行脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认配置
IMAGE_NAME="f5-scheduler"
IMAGE_TAG="latest"
CONTAINER_NAME="f5-scheduler-container"
CONFIG_FILE="./config/scheduler-config.yaml"
LOGS_DIR="./logs"
DOCKERFILE="Dockerfile"
PLATFORMS="linux/amd64,linux/arm64"
HTTP_PROXY=""
HTTPS_PROXY=""
NO_PROXY=""

# 帮助信息
show_help() {
    echo -e "${BLUE}F5 LLM推理网关调度器 Docker构建和运行脚本${NC}"
    echo ""
    echo "用法: $0 [选项] [命令]"
    echo ""
    echo "命令:"
    echo "  build       构建Docker镜像"
    echo "  buildx      多平台构建Docker镜像"
    echo "  run         运行容器"
    echo "  stop        停止容器"
    echo "  restart     重启容器"
    echo "  logs        查看容器日志"
    echo "  clean       清理容器和镜像"
    echo "  clean-buildx 清理buildx实例和缓存"
    echo "  help        显示帮助信息"
    echo ""
    echo "选项:"
    echo "  -t, --tag TAG           镜像标签 (默认: latest)"
    echo "  -n, --name NAME         容器名称 (默认: f5-scheduler-container)"
    echo "  -c, --config FILE       配置文件路径 (默认: ./config/scheduler-config.yaml)"
    echo "  -p, --port PORT         API端口映射 (默认: 8080:8080)"
    echo "  -f, --dockerfile FILE   Dockerfile路径 (默认: Dockerfile)"
    echo "  --platforms PLATFORMS   构建平台 (默认: linux/amd64,linux/arm64)"
    echo "  --production           使用生产版Dockerfile"
    echo "  --push                 构建后推送到镜像仓库"
    echo "  --proxy URL            HTTP/HTTPS代理地址"
    echo "  --http-proxy URL       HTTP代理地址"
    echo "  --https-proxy URL      HTTPS代理地址"
    echo "  --no-proxy HOSTS       不使用代理的主机列表"
    echo "  --f5-password PWD       F5设备密码"
    echo "  --metric-password PWD   监控指标密码"
    echo ""
    echo "环境变量:"
    echo "  F5_PASSWORD            F5设备密码"
    echo "  METRIC_PWD             监控指标密码（可选）"
    echo ""
    echo "示例:"
    echo "  $0 build                                    # 构建开发版镜像"
    echo "  $0 build --production                       # 构建生产版镜像"
    echo "  $0 buildx --push                           # 多平台构建并推送"
    echo "  $0 buildx --production --platforms linux/amd64 # 生产版单平台构建"
    echo "  $0 buildx --proxy http://127.0.0.1:8010     # 使用代理构建"
    echo "  $0 run --f5-password mypass --metric-password metricpass"
    echo "  $0 restart"
}

# 构建镜像
build_image() {
    echo -e "${BLUE}正在构建Docker镜像...${NC}"
    echo "使用Dockerfile: $DOCKERFILE"
    echo "镜像标签: ${IMAGE_NAME}:${IMAGE_TAG}"
    
    # 构建命令
    BUILD_CMD="docker build -f $DOCKERFILE -t ${IMAGE_NAME}:${IMAGE_TAG}"
    
    # 添加代理设置
    if [ -n "$HTTP_PROXY" ]; then
        BUILD_CMD="$BUILD_CMD --build-arg HTTP_PROXY=$HTTP_PROXY"
        BUILD_CMD="$BUILD_CMD --build-arg http_proxy=$HTTP_PROXY"
        echo "使用HTTP代理: $HTTP_PROXY"
    fi
    
    if [ -n "$HTTPS_PROXY" ]; then
        BUILD_CMD="$BUILD_CMD --build-arg HTTPS_PROXY=$HTTPS_PROXY"
        BUILD_CMD="$BUILD_CMD --build-arg https_proxy=$HTTPS_PROXY"
        echo "使用HTTPS代理: $HTTPS_PROXY"
    fi
    
    if [ -n "$NO_PROXY" ]; then
        BUILD_CMD="$BUILD_CMD --build-arg NO_PROXY=$NO_PROXY"
        BUILD_CMD="$BUILD_CMD --build-arg no_proxy=$NO_PROXY"
        echo "不使用代理的主机: $NO_PROXY"
    fi
    
    BUILD_CMD="$BUILD_CMD ."
    
    echo "执行命令: $BUILD_CMD"
    eval $BUILD_CMD
    echo -e "${GREEN}镜像构建完成: ${IMAGE_NAME}:${IMAGE_TAG}${NC}"
}

# 多平台构建镜像
buildx_image() {
    echo -e "${BLUE}正在进行多平台构建...${NC}"
    echo "使用Dockerfile: $DOCKERFILE"
    echo "构建平台: $PLATFORMS"
    echo "镜像标签: ${IMAGE_NAME}:${IMAGE_TAG}"
    
    # 检查buildx是否可用
    if ! docker buildx version >/dev/null 2>&1; then
        echo -e "${RED}错误: docker buildx 不可用${NC}"
        echo "请确保Docker版本支持buildx功能"
        exit 1
    fi
    
    # 创建builder实例（如果不存在）
    BUILDER_NAME="f5-scheduler-builder"
    
    # 先尝试清理可能存在的有问题的builder
    echo -e "${YELLOW}检查并清理builder实例...${NC}"
    docker buildx rm "$BUILDER_NAME" >/dev/null 2>&1 || true
    
    # 清理临时配置文件
    rm -f /tmp/buildkitd.toml >/dev/null 2>&1 || true
    
    # 创建新的builder实例
    echo -e "${YELLOW}创建新的builder实例...${NC}"
    
    # 创建builder时传递代理环境变量
    CREATE_CMD="docker buildx create --name $BUILDER_NAME --use"
    
    # 检查是否需要代理设置
    if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ]; then
        echo -e "${BLUE}配置builder代理设置...${NC}"
        CREATE_CMD="$CREATE_CMD --driver docker-container"
        
        # 为builder容器设置代理环境变量
        if [ -n "$HTTP_PROXY" ]; then
            CREATE_CMD="$CREATE_CMD --driver-opt env.HTTP_PROXY=$HTTP_PROXY"
            CREATE_CMD="$CREATE_CMD --driver-opt env.http_proxy=$HTTP_PROXY"
            echo "设置HTTP代理: $HTTP_PROXY"
        fi
        
        if [ -n "$HTTPS_PROXY" ]; then
            CREATE_CMD="$CREATE_CMD --driver-opt env.HTTPS_PROXY=$HTTPS_PROXY"
            CREATE_CMD="$CREATE_CMD --driver-opt env.https_proxy=$HTTPS_PROXY"
            echo "设置HTTPS代理: $HTTPS_PROXY"
        fi
        
        if [ -n "$NO_PROXY" ]; then
            CREATE_CMD="$CREATE_CMD --driver-opt env.NO_PROXY=$NO_PROXY"
            CREATE_CMD="$CREATE_CMD --driver-opt env.no_proxy=$NO_PROXY"
            echo "设置NO_PROXY: $NO_PROXY"
        fi
        
        # 使用host网络模式，让builder容器能访问宿主机的代理
        CREATE_CMD="$CREATE_CMD --driver-opt network=host"
    else
        CREATE_CMD="$CREATE_CMD --driver docker-container"
    fi
    
    echo "执行创建命令: $CREATE_CMD"
    if eval $CREATE_CMD; then
        echo -e "${GREEN}Builder实例创建成功${NC}"
        
        # 启动builder
        echo -e "${YELLOW}启动builder...${NC}"
        if docker buildx inspect --bootstrap; then
            echo -e "${GREEN}Builder启动成功${NC}"
        else
            echo -e "${RED}Builder启动失败，尝试使用默认builder${NC}"
            docker buildx use default
            BUILDER_NAME="default"
        fi
    else
        echo -e "${RED}Builder创建失败，使用默认builder${NC}"
        docker buildx use default
        BUILDER_NAME="default"
    fi
    
    # 构建命令
    BUILD_CMD="docker buildx build"
    BUILD_CMD="$BUILD_CMD --platform $PLATFORMS"
    BUILD_CMD="$BUILD_CMD -f $DOCKERFILE"
    BUILD_CMD="$BUILD_CMD -t ${IMAGE_NAME}:${IMAGE_TAG}"
    
    # 添加代理设置
    if [ -n "$HTTP_PROXY" ]; then
        BUILD_CMD="$BUILD_CMD --build-arg HTTP_PROXY=$HTTP_PROXY"
        BUILD_CMD="$BUILD_CMD --build-arg http_proxy=$HTTP_PROXY"
        echo "使用HTTP代理: $HTTP_PROXY"
    fi
    
    if [ -n "$HTTPS_PROXY" ]; then
        BUILD_CMD="$BUILD_CMD --build-arg HTTPS_PROXY=$HTTPS_PROXY"
        BUILD_CMD="$BUILD_CMD --build-arg https_proxy=$HTTPS_PROXY"
        echo "使用HTTPS代理: $HTTPS_PROXY"
    fi
    
    if [ -n "$NO_PROXY" ]; then
        BUILD_CMD="$BUILD_CMD --build-arg NO_PROXY=$NO_PROXY"
        BUILD_CMD="$BUILD_CMD --build-arg no_proxy=$NO_PROXY"
        echo "不使用代理的主机: $NO_PROXY"
    fi
    
    if [ "$PUSH_IMAGE" = "true" ]; then
        BUILD_CMD="$BUILD_CMD --push"
        echo "将推送到镜像仓库"
    else
        # 检查是否为单平台构建
        if [[ "$PLATFORMS" == *","* ]]; then
            echo "多平台构建，镜像将存储在builder缓存中"
            echo "提示: 如需本地使用，请指定单一平台或使用--push推送到仓库"
        else
            BUILD_CMD="$BUILD_CMD --load"
            echo "单平台构建，将加载到本地Docker"
        fi
    fi
    
    BUILD_CMD="$BUILD_CMD ."
    
    echo "执行命令: $BUILD_CMD"
    eval $BUILD_CMD
    
    echo -e "${GREEN}多平台构建完成: ${IMAGE_NAME}:${IMAGE_TAG}${NC}"
}

# 运行容器
run_container() {
    # 检查配置文件是否存在
    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}错误: 配置文件不存在: $CONFIG_FILE${NC}"
        exit 1
    fi

    # 创建日志目录
    mkdir -p "$LOGS_DIR"

    # 停止已存在的容器
    if docker ps -a --format 'table {{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo -e "${YELLOW}停止已存在的容器...${NC}"
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
        docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi

    # 构建docker run命令
    DOCKER_CMD="docker run -d"
    DOCKER_CMD="$DOCKER_CMD --name $CONTAINER_NAME"
    DOCKER_CMD="$DOCKER_CMD -p ${API_PORT:-8080:8080}"
    DOCKER_CMD="$DOCKER_CMD -v $(realpath $CONFIG_FILE):/app/config/scheduler-config.yaml:ro"
    DOCKER_CMD="$DOCKER_CMD -v $(realpath $LOGS_DIR):/app/logs"
    
    # 添加环境变量
    if [ -n "$F5_PASSWORD" ]; then
        DOCKER_CMD="$DOCKER_CMD -e F5_PASSWORD=$F5_PASSWORD"
    fi
    
    if [ -n "$METRIC_PWD" ]; then
        DOCKER_CMD="$DOCKER_CMD -e METRIC_PWD=$METRIC_PWD"
    fi
    
    DOCKER_CMD="$DOCKER_CMD --restart unless-stopped"
    DOCKER_CMD="$DOCKER_CMD ${IMAGE_NAME}:${IMAGE_TAG}"

    echo -e "${BLUE}正在启动容器...${NC}"
    echo "命令: $DOCKER_CMD"
    
    eval $DOCKER_CMD
    
    echo -e "${GREEN}容器启动成功: $CONTAINER_NAME${NC}"
    echo -e "${BLUE}API端点: http://localhost:${API_PORT:-8080}${NC}"
}

# 停止容器
stop_container() {
    echo -e "${BLUE}正在停止容器...${NC}"
    docker stop "$CONTAINER_NAME" || true
    docker rm "$CONTAINER_NAME" || true
    echo -e "${GREEN}容器已停止${NC}"
}

# 重启容器
restart_container() {
    stop_container
    run_container
}

# 查看日志
show_logs() {
    docker logs -f "$CONTAINER_NAME"
}

# 清理
clean_up() {
    echo -e "${YELLOW}正在清理容器和镜像...${NC}"
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rmi "${IMAGE_NAME}:${IMAGE_TAG}" >/dev/null 2>&1 || true
    echo -e "${GREEN}清理完成${NC}"
}

# 清理buildx
clean_buildx() {
    echo -e "${YELLOW}正在清理buildx实例和缓存...${NC}"
    
    # 清理我们的builder实例
    docker buildx rm f5-scheduler-builder >/dev/null 2>&1 || true
    
    # 清理buildx缓存
    docker buildx prune -f >/dev/null 2>&1 || true
    
    # 清理可能有问题的活动文件
    rm -rf ~/.docker/buildx/activity/f5-scheduler-builder >/dev/null 2>&1 || true
    
    echo -e "${GREEN}Buildx清理完成${NC}"
}

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--tag)
            # 解析完整的镜像名称和标签
            FULL_IMAGE_NAME="$2"
            # 如果包含冒号，分离镜像名和标签
            if [[ "$FULL_IMAGE_NAME" == *":"* ]]; then
                IMAGE_NAME="${FULL_IMAGE_NAME%:*}"
                IMAGE_TAG="${FULL_IMAGE_NAME##*:}"
            else
                IMAGE_NAME="$FULL_IMAGE_NAME"
                IMAGE_TAG="latest"
            fi
            shift 2
            ;;
        -n|--name)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -c|--config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -p|--port)
            API_PORT="$2"
            shift 2
            ;;
        -f|--dockerfile)
            DOCKERFILE="$2"
            shift 2
            ;;
        --platforms)
            PLATFORMS="$2"
            shift 2
            ;;
        --production)
            DOCKERFILE="Dockerfile.production"
            shift
            ;;
        --push)
            PUSH_IMAGE="true"
            shift
            ;;
        --proxy)
            HTTP_PROXY="$2"
            HTTPS_PROXY="$2"
            shift 2
            ;;
        --http-proxy)
            HTTP_PROXY="$2"
            shift 2
            ;;
        --https-proxy)
            HTTPS_PROXY="$2"
            shift 2
            ;;
        --no-proxy)
            NO_PROXY="$2"
            shift 2
            ;;
        --f5-password)
            F5_PASSWORD="$2"
            shift 2
            ;;
        --metric-password)
            METRIC_PWD="$2"
            shift 2
            ;;
        build)
            COMMAND="build"
            shift
            ;;
        buildx)
            COMMAND="buildx"
            shift
            ;;
        run)
            COMMAND="run"
            shift
            ;;
        stop)
            COMMAND="stop"
            shift
            ;;
        restart)
            COMMAND="restart"
            shift
            ;;
        logs)
            COMMAND="logs"
            shift
            ;;
        clean)
            COMMAND="clean"
            shift
            ;;
        clean-buildx)
            COMMAND="clean-buildx"
            shift
            ;;
        help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}未知参数: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 执行命令
case ${COMMAND:-help} in
    build)
        build_image
        ;;
    buildx)
        buildx_image
        ;;
    run)
        run_container
        ;;
    stop)
        stop_container
        ;;
    restart)
        restart_container
        ;;
    logs)
        show_logs
        ;;
    clean)
        clean_up
        ;;
    clean-buildx)
        clean_buildx
        ;;
    *)
        show_help
        ;;
esac 