# F5 LLM Inference Gateway Scheduler Dockerfile
# 使用官方Python 3.11 slim镜像作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt并安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目源代码
COPY . .

# 创建配置文件目录（用于外部挂载）
RUN mkdir -p /app/config

# 创建日志目录
RUN mkdir -p /app/logs

# 设置环境变量
ENV CONFIG_FILE=/app/config/scheduler-config.yaml
ENV LOG_FILE_PATH=/app/logs/scheduler.log

# 创建启动脚本
COPY <<EOF /app/entrypoint.sh
#!/bin/bash
set -e

# 检查配置文件
if [ ! -f "\${CONFIG_FILE:-/app/config/scheduler-config.yaml}" ]; then
    echo "错误: 配置文件不存在: \${CONFIG_FILE}"
    echo "请确保配置文件已正确挂载到容器中"
    exit 1
fi

# 检查必需的环境变量
missing_vars=""
if [ -z "\$F5_PASSWORD" ]; then
    missing_vars="\${missing_vars} F5_PASSWORD"
fi

if [ -n "\$missing_vars" ]; then
    echo "错误: 缺少必需的环境变量:\$missing_vars"
    echo "请设置这些环境变量后重新启动容器"
    exit 1
fi

# 检查可选的环境变量
if [ -z "\$METRIC_PWD" ]; then
    echo "提示: METRIC_PWD未设置，如果需要监控指标功能，请设置此环境变量"
fi

# 确保日志目录存在
if [ -n "\$LOG_FILE_PATH" ] && [ "\$LOG_FILE_PATH" != "" ]; then
    mkdir -p \$(dirname "\$LOG_FILE_PATH")
fi

echo "F5 Scheduler 启动中..."
echo "配置文件: \${CONFIG_FILE}"
echo "日志文件: \${LOG_FILE_PATH:-'stdout'}"

# 启动主程序
exec python main.py
EOF

RUN chmod +x /app/entrypoint.sh

# 创建非root用户
RUN groupadd -r scheduler && useradd -r -g scheduler scheduler
RUN chown -R scheduler:scheduler /app
USER scheduler

# 暴露API端口（默认8080，可通过配置文件修改）
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# 使用启动脚本
ENTRYPOINT ["/app/entrypoint.sh"] 