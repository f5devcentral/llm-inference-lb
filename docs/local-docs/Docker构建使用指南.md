# F5 LLM推理网关调度器 Docker构建使用指南

## 概述

本项目提供了两个不同的Dockerfile，分别用于开发和生产环境：

- `Dockerfile` - 开发版本，功能简单，适合开发测试
- `Dockerfile.production` - 生产版本，包含日志轮转、健康检查等企业级功能

## Dockerfile对比

### 开发版 (Dockerfile)
- **特点**: 简单轻量，快速构建
- **适用场景**: 开发、测试、快速原型
- **功能**: 基础功能，简单的日志输出
- **大小**: 相对较小

### 生产版 (Dockerfile.production)
- **特点**: 功能完整，企业级特性
- **适用场景**: 生产环境、正式部署
- **功能**: 
  - 日志轮转 (logrotate)
  - Cron服务
  - 详细的启动检查
  - 灵活的日志配置
  - 增强的错误处理
- **大小**: 相对较大

## 构建方式

### 1. 单平台构建

#### 构建开发版镜像
```bash
# 使用默认Dockerfile
./build-and-run.sh build

# 指定标签
./build-and-run.sh build -t dev-v1.0
```

#### 构建生产版镜像
```bash
# 使用生产版Dockerfile
./build-and-run.sh build --production

# 指定标签和生产版
./build-and-run.sh build --production -t prod-v1.0
```

#### 指定特定Dockerfile
```bash
# 自定义Dockerfile路径
./build-and-run.sh build -f Dockerfile.custom
```

### 2. 多平台构建

#### 基本多平台构建
```bash
# 默认构建 linux/amd64,linux/arm64
./build-and-run.sh buildx

# 生产版多平台构建
./build-and-run.sh buildx --production
```

#### 指定构建平台
```bash
# 只构建AMD64
./build-and-run.sh buildx --platforms linux/amd64

# 构建多个平台
./build-and-run.sh buildx --platforms linux/amd64,linux/arm64,linux/arm/v7
```

#### 构建并推送到仓库
```bash
# 构建并推送
./build-and-run.sh buildx --push

# 生产版构建并推送
./build-and-run.sh buildx --production --push

# 指定标签并推送
./build-and-run.sh buildx --production --push -t registry.example.com/f5-scheduler:v1.0
```

## 运行容器

### 开发环境运行
```bash
# 基本运行
./build-and-run.sh run --f5-password your_password

# 指定端口
./build-and-run.sh run --f5-password your_password -p 8090:8080
```

### 生产环境运行
```bash
# 使用生产版镜像运行
./build-and-run.sh build --production
./build-and-run.sh run --f5-password your_password --metric-password metric_pwd
```

## 环境变量配置

### 必需变量
- `F5_PASSWORD`: F5设备访问密码

### 可选变量
- `METRIC_PWD`: 监控指标访问密码
- `LOG_TO_STDOUT`: 是否输出日志到标准输出 (仅生产版)
- `LOG_FILE_PATH`: 日志文件路径 (仅生产版)

### 生产版特有配置
```bash
# 日志输出到标准输出
docker run -e LOG_TO_STDOUT=true ...

# 日志输出到文件
docker run -e LOG_FILE_PATH=/app/logs/scheduler.log ...
```

## Docker Compose使用

项目还提供了`docker-compose.yml`文件：

```bash
# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止服务
docker-compose down
```

## 多平台构建要求

### 前置条件
1. Docker版本 >= 19.03
2. 启用BuildKit: `export DOCKER_BUILDKIT=1`
3. 安装buildx插件 (通常随Docker Desktop自带)

### 验证buildx可用性
```bash
docker buildx version
docker buildx ls
```

### 创建builder实例
脚本会自动创建名为`f5-scheduler-builder`的builder实例，也可以手动创建：

```bash
docker buildx create --name mybuilder --use
docker buildx inspect --bootstrap
```

## 常用命令示例

### 开发流程
```bash
# 1. 构建开发版
./build-and-run.sh build

# 2. 运行测试
./build-and-run.sh run --f5-password test123

# 3. 查看日志
./build-and-run.sh logs

# 4. 停止容器
./build-and-run.sh stop
```

### 生产部署
```bash
# 1. 多平台构建生产版
./build-and-run.sh buildx --production --push -t myregistry/f5-scheduler:v1.0

# 2. 在目标服务器拉取并运行
docker pull myregistry/f5-scheduler:v1.0
./build-and-run.sh run --f5-password prod_password --metric-password metric_password
```

### CI/CD集成
```bash
# 在CI/CD管道中
./build-and-run.sh buildx --production --push --platforms linux/amd64,linux/arm64 -t $CI_REGISTRY_IMAGE:$CI_COMMIT_TAG
```

## 故障排除

### 构建失败
1. 检查Docker版本和buildx可用性
2. 确保网络连接正常
3. 检查Dockerfile语法

### 多平台构建问题
1. 确认目标平台支持
2. 检查builder实例状态: `docker buildx ls`
3. 重新创建builder: `docker buildx rm f5-scheduler-builder`

### 运行时问题
1. 检查配置文件是否正确挂载
2. 验证环境变量设置
3. 查看容器日志: `./build-and-run.sh logs`

## 最佳实践

1. **开发阶段**: 使用开发版Dockerfile，快速迭代
2. **测试阶段**: 使用生产版Dockerfile，验证完整功能
3. **生产部署**: 使用多平台构建，确保兼容性
4. **版本管理**: 使用语义化版本标签
5. **安全考虑**: 不在镜像中包含敏感信息，使用环境变量传递 