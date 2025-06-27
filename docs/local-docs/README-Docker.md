# F5 LLM推理网关调度器 Docker快速入门

## 快速开始

### 1. 构建镜像

#### 开发版本（推荐用于测试）
```bash
# 基本构建
./build-and-run.sh build

# 指定标签
./build-and-run.sh build -t f5-scheduler:dev
```

#### 生产版本（推荐用于部署）
```bash
# 构建生产版
./build-and-run.sh build --production

# 指定标签
./build-and-run.sh build --production -t f5-scheduler:prod
```

### 2. 多平台构建

```bash
# 多平台构建（AMD64 + ARM64）
./build-and-run.sh buildx --production

# 只构建AMD64
./build-and-run.sh buildx --platforms linux/amd64

# 构建并推送到仓库
./build-and-run.sh buildx --production --push -t your-registry/f5-scheduler:v1.0
```

### 3. 运行容器

```bash
# 基本运行
./build-and-run.sh run --f5-password your_f5_password

# 完整配置运行
./build-and-run.sh run \
  --f5-password your_f5_password \
  --metric-password your_metric_password \
  -p 8090:8080 \
  -n my-scheduler
```

### 4. 管理容器

```bash
# 查看日志
./build-and-run.sh logs

# 重启容器
./build-and-run.sh restart

# 停止容器
./build-and-run.sh stop

# 清理容器和镜像
./build-and-run.sh clean
```

## 两个Dockerfile的使用场景

### 开发版 (Dockerfile)
- ✅ 快速构建和测试
- ✅ 开发环境调试
- ✅ 功能验证
- ❌ 不适合生产环境

### 生产版 (Dockerfile.production)
- ✅ 生产环境部署
- ✅ 日志管理和轮转
- ✅ 健康检查
- ✅ 企业级特性
- ❌ 构建时间较长

## 常见使用模式

### 开发流程
```bash
# 1. 开发阶段 - 使用开发版
./build-and-run.sh build
./build-and-run.sh run --f5-password test123

# 2. 测试修改
./build-and-run.sh restart

# 3. 查看日志
./build-and-run.sh logs
```

### 生产部署
```bash
# 1. 构建生产版镜像
./build-and-run.sh buildx --production --push -t registry.company.com/f5-scheduler:v1.0

# 2. 在生产服务器运行
docker pull registry.company.com/f5-scheduler:v1.0
./build-and-run.sh run \
  --f5-password $F5_PROD_PASSWORD \
  --metric-password $METRIC_PROD_PASSWORD \
  -t v1.0
```

## 环境变量说明

| 变量名 | 必需 | 说明 | 示例 |
|--------|------|------|------|
| F5_PASSWORD | ✅ | F5设备密码 | `mypassword` |
| METRIC_PWD | ❌ | 监控指标密码 | `metricpass` |
| LOG_TO_STDOUT | ❌ | 日志输出方式(仅生产版) | `true/false` |
| LOG_FILE_PATH | ❌ | 日志文件路径(仅生产版) | `/app/logs/app.log` |

## 故障排除

### 构建失败
```bash
# 检查Docker版本
docker --version

# 检查buildx支持
docker buildx version
```

### 运行失败
```bash
# 检查配置文件
ls -la config/scheduler-config.yaml

# 查看容器状态
docker ps -a

# 查看详细日志
./build-and-run.sh logs
```

### 多平台构建问题
```bash
# 检查builder状态
docker buildx ls

# 重新创建builder
docker buildx rm f5-scheduler-builder
docker buildx create --name f5-scheduler-builder --use
```

## 完整示例

### 从零开始的完整流程
```bash
# 1. 克隆项目
git clone <repository-url>
cd Scheduler-project-en

# 2. 准备配置文件
cp config/scheduler-config.yaml.example config/scheduler-config.yaml
# 编辑配置文件...

# 3. 构建开发版测试
./build-and-run.sh build
./build-and-run.sh run --f5-password test123

# 4. 验证功能
curl http://localhost:8080/health

# 5. 构建生产版
./build-and-run.sh stop
./build-and-run.sh build --production
./build-and-run.sh run --f5-password prod123 --metric-password metric123

# 6. 多平台构建并推送
./build-and-run.sh buildx --production --push -t myregistry/f5-scheduler:v1.0
```

更多详细信息请参考 [Docker构建使用指南](./Docker构建使用指南.md)。 