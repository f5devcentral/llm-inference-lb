# Docker Buildx 代理问题解决方案

## 问题描述

使用 `docker buildx` 进行多平台构建时，即使设置了 `--build-arg` 代理参数，buildx 仍然无法通过代理访问外部资源（如 Docker Hub），出现类似错误：

```
ERROR: failed to solve: DeadlineExceeded: python:3.11-slim: failed to resolve source metadata for docker.io/library/python:3.11-slim: failed to do request: Head "https://registry-1.docker.io/v2/library/python/manifests/3.11-slim": dial tcp 108.160.167.148:443: i/o timeout
```

## 根本原因

`docker buildx` 使用独立的 BuildKit 容器进行构建，该容器需要单独配置代理设置。仅仅传递 `--build-arg` 是不够的，因为这只影响构建过程中的环境变量，不影响 BuildKit 容器本身的网络连接。

## 解决方案

### 方案1：环境变量方式（推荐）实际测试，此方法成功！

在运行构建命令前设置环境变量：

```bash
# 设置代理环境变量
export HTTP_PROXY=http://127.0.0.1:8010
export HTTPS_PROXY=http://127.0.0.1:8010
export NO_PROXY=localhost,127.0.0.1

# 然后运行构建
./build-and-run.sh buildx --production --proxy http://127.0.0.1:8010
```

### 方案2：Docker Daemon 配置

配置 Docker Desktop 的代理设置：

1. 打开 Docker Desktop
2. 进入 Settings (设置)
3. 选择 Resources > Proxies
4. 启用 Manual proxy configuration
5. 设置：
   - HTTP proxy: `http://127.0.0.1:8010`
   - HTTPS proxy: `http://127.0.0.1:8010`
   - No proxy: `localhost,127.0.0.1`
6. 点击 Apply & Restart

### 方案3：使用 Docker 网络模式

我们的脚本已经包含这个解决方案，它会：

1. 为 BuildKit 容器设置代理环境变量
2. 使用 host 网络模式让容器访问宿主机代理
3. 自动配置所有必要的代理参数

```bash
# 脚本会自动处理
./build-and-run.sh buildx --proxy http://127.0.0.1:8010 --production
```

### 方案4：手动创建 Builder

如果自动方案不工作，可以手动创建：

```bash
# 清理现有builder
docker buildx rm f5-scheduler-builder

# 手动创建带代理的builder
docker buildx create \
  --name f5-scheduler-builder \
  --driver docker-container \
  --driver-opt network=host \
  --driver-opt env.HTTP_PROXY=http://127.0.0.1:8010 \
  --driver-opt env.HTTPS_PROXY=http://127.0.0.1:8010 \
  --use

# 启动builder
docker buildx inspect --bootstrap

# 然后进行构建
./build-and-run.sh buildx --proxy http://127.0.0.1:8010 --production
```

## 验证代理是否生效

### 检查 Builder 状态
```bash
docker buildx ls
docker buildx inspect f5-scheduler-builder
```

### 测试网络连接
```bash
# 进入builder容器测试网络
docker exec -it buildx_buildkit_f5-scheduler-builder0 sh
# 在容器内测试
curl -v https://registry-1.docker.io/v2/
```

### 查看环境变量
```bash
# 检查builder容器的环境变量
docker exec buildx_buildkit_f5-scheduler-builder0 env | grep -i proxy
```

## 常见问题排查

### 1. 代理服务器不可访问
```bash
# 测试代理连接
curl -x http://127.0.0.1:8010 https://www.google.com
```

### 2. Builder 容器网络问题
```bash
# 重新创建builder使用host网络
docker buildx rm f5-scheduler-builder
./build-and-run.sh clean-buildx
./build-and-run.sh buildx --proxy http://127.0.0.1:8010 --production
```

### 3. Docker Desktop 代理冲突
有时 Docker Desktop 的代理设置会与 buildx 冲突，尝试：
- 临时禁用 Docker Desktop 的代理设置
- 或者只使用 Docker Desktop 的代理，不在命令行设置

### 4. 防火墙问题
确保：
- 代理端口 8010 可以访问
- Docker 容器可以访问宿主机网络
- 防火墙允许相关连接

## 推荐的完整工作流

```bash
# 1. 设置环境变量（可选但推荐）
export HTTP_PROXY=http://127.0.0.1:8010
export HTTPS_PROXY=http://127.0.0.1:8010

# 2. 清理可能有问题的builder
./build-and-run.sh clean-buildx

# 3. 使用代理进行构建
./build-and-run.sh buildx --production \
  --proxy http://127.0.0.1:8010 \
  --platforms linux/amd64,linux/arm64 \
  --push -t localhost:6000/f5-scheduler:v1.0

# 4. 如果仍然失败，尝试单平台构建
./build-and-run.sh buildx \
  --proxy http://127.0.0.1:8010 \
  --platforms linux/amd64 \
  -t f5-scheduler:test
```

## 备用方案

如果 buildx 代理仍然有问题，可以：

1. **使用普通 docker build**：
   ```bash
   ./build-and-run.sh build --proxy http://127.0.0.1:8010 --production
   ```

2. **预先拉取基础镜像**：
   ```bash
   # 使用代理预先拉取镜像
   docker pull python:3.11-slim
   # 然后再构建
   ./build-and-run.sh buildx --production
   ```

3. **使用本地镜像仓库**：
   ```bash
   # 启动本地registry
   ./scripts/local-registry.sh start
   # 推送到本地仓库
   ./build-and-run.sh buildx --push -t localhost:6000/f5-scheduler:v1.0
   ```

通过这些方案，应该能够解决 buildx 的代理问题！ 