# F5 LLM Inference Gateway 调度器

LLM推理网关智能调度器，用于与F5 LTM配合，实现基于推理引擎的实时性能指标进行最优成员进行负载平衡。

## 功能特性

- **智能调度算法**: S1，S2算法
- **多引擎支持**: 支持vLLM和SGLang推理引擎
- **实时监控**: 自动获取F5 Pool成员和推理引擎性能指标
- **高可用设计**: 异步架构，支持并发处理
- **RESTful API**: 提供标准HTTP接口
- **配置热重载**: 支持运行时配置更新
- **完善日志**: 详细的调试和运行日志
- **加权随机选择**: 基于Score值的概率选择算法
- **性能分析**: 提供选择过程模拟和概率分析接口

## 项目结构

```
scheduler-project/
├── main.py                 # 主程序入口
├── config/
│   ├── __init__.py
│   ├── config_loader.py    # 配置文件读取模块
│   └── scheduler-config.yaml  # 配置文件
├── core/
│   ├── __init__.py
│   ├── models.py           # 数据模型定义
│   ├── f5_client.py        # F5 API客户端
│   ├── metrics_collector.py # Metrics收集模块
│   ├── score_calculator.py  # Score计算模块
│   └── scheduler.py        # 调度器核心逻辑
├── api/
│   ├── __init__.py
│   └── server.py           # API服务器
├── utils/
│   ├── __init__.py
│   ├── logger.py           # 日志工具
│   └── exceptions.py       # 自定义异常
├── tests/                  # 测试文件
├── requirements.txt        # 项目依赖
└── README.md              # 项目说明
```

## 模块关系

[详细架构请查看](./模块关系-zh.md)

## 安装部署

### 1. 环境要求

- Python 3.8+
- F5 LTM设备访问权限
- 推理引擎服务（vLLM或SGLang）

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置文件

配置文件：

```bash
config/scheduler-config.yaml
```

编辑配置文件，设置F5连接信息和Pool配置：

```yaml
global:
  interval: 5                    # 配置热更新检查间隔（秒）
  api_port: 8080                # API服务端口
  api_host: 0.0.0.0             # API服务监听地址
  log_level: INFO               # 日志级别

f5:
  host: 192.168.1.100           # F5设备IP（必配）
  port: 443                     # F5管理端口
  username: admin               # F5用户名
  password_env: F5_PASSWORD     # F5密码环境变量

scheduler:
  pool_fetch_interval: 10       # Pool成员获取间隔（秒）
  metrics_fetch_interval: 3000  # Metrics收集间隔（毫秒）

modes:
  - name: s1                    # 算法模式名称
    w_a: 0.5                    # 等待队列权重
    w_b: 0.5                    # 缓存使用率权重

pools:
  - name: llm-pool-1            # Pool名称（必配）
    partition: Common           # Partition名称
    engine_type: vllm           # 引擎类型（必配）
    metrics:
      schema: http              # 协议类型
      path: /metrics            # Metrics路径
      timeout: 4                # 请求超时时间
```

### 4. 设置环境变量

```bash
export F5_PASSWORD="your_f5_password"
export METRIC_PWD="your_metrics_password"  # 如果需要

# 可选：日志文件路径配置（用于非Docker部署）
export LOG_FILE_PATH="/var/log/f5-scheduler/scheduler.log"  # 自定义日志文件路径
```

#### 日志文件路径配置

**可选环境变量**: `LOG_FILE_PATH`

- **如果设置**: 调度器将日志写入指定的文件路径
  ```bash
  export LOG_FILE_PATH="/var/log/f5-scheduler/scheduler.log"
  # 日志将写入到: /var/log/f5-scheduler/scheduler.log
  ```

- **如果不设置**: 调度器将使用默认的日志文件路径
  ```bash
  # 默认日志文件: scheduler.log（在当前工作目录下）
  # 例如：如果从 /opt/f5-scheduler/ 目录运行调度器，
  # 日志文件将创建在 /opt/f5-scheduler/scheduler.log
  ```

**注意**: 此环境变量主要用于非Docker部署。对于Docker部署，请使用Docker部署章节中描述的 `LOG_TO_STDOUT` 和 `LOG_FILE_PATH` 环境变量。

### 5. 启动调度器

```bash
python main.py
```

## Docker 部署

### 生产环境部署示例（推荐）

```bash
# 构建生产版镜像
docker build -f Dockerfile.production -t f5-scheduler:latest .

# 运行生产配置（标准输出日志 - 推荐）
docker run -d \
  --name f5-scheduler \
  -p 8080:8080 \
  -v $(pwd)/config/scheduler-config.yaml:/app/config/scheduler-config.yaml:ro \
  -e F5_PASSWORD=your-password \
  -e METRIC_PWD=your-metric-password \
  -e LOG_TO_STDOUT=true \
  --log-driver json-file \
  --log-opt max-size=100m \
  --log-opt max-file=3 \
  --restart unless-stopped \
  f5-scheduler:latest
```

### 备选方案：文件日志

```bash
# 运行文件日志模式（如果环境需要）
docker run -d \
  --name f5-scheduler-container \
  -p 8080:8080 \
  -v $(pwd)/config/scheduler-config.yaml:/app/config/scheduler-config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -e F5_PASSWORD="your_f5_password" \
  -e METRIC_PWD="your_metrics_password" \
  -e LOG_TO_STDOUT="false" \
  -e LOG_FILE_PATH="/app/logs/scheduler.log" \
  --restart unless-stopped \
  f5-scheduler:latest
```

### 环境变量

```bash
# 必需
-e F5_PASSWORD="your_f5_password"                    # F5设备密码

# 可选
-e METRIC_PWD="your_metrics_password"                # 监控指标密码（可选）
-e LOG_TO_STDOUT="true"                              # 日志输出方式（可选，仅生产版，默认：推荐true）
-e LOG_FILE_PATH="/app/logs/scheduler.log"           # 日志文件路径（可选，仅当LOG_TO_STDOUT=false时使用）
```

### 日志记录最佳实践

**推荐**: 对于容器部署使用 `LOG_TO_STDOUT="true"`（默认），因为：
- 遵循12-Factor App原则和容器最佳实践
- 更好地与Docker/Kubernetes日志系统集成
- 便于集中式日志收集解决方案（ELK、Fluentd等）收集
- 使用 `docker logs -f f5-scheduler-container` 查看日志
- 更好的性能（无文件I/O开销）

**文件日志** 仅在特定企业环境或传统日志收集系统需要时使用。

## API接口

### 1. 选择最优成员

**POST** `/scheduler/select`

**功能**: 根据Pool成员的实时性能指标选择最优成员

**请求体**:
```json
{
  "pool_name": "llm-pool-1",
  "partition": "Common", 
  "members": ["10.10.10.10:8001", "10.10.10.10:8002"]
}
```

**响应**:

成功选择到最优成员：
```
10.10.10.10:8001
```

无法选择最优成员（Pool不存在、成员列表为空、所有成员Score为0等情况）：
```
none
```

**状态码**:
- `200`: 成功（包括成功选择和无法选择两种情况）
- `400`: 请求参数错误
- `500`: 内部服务器错误

**无法选择的常见情况**:
- Pool在调度器中不存在
- 请求的成员列表与Pool中的实际成员没有交集
- Pool中没有任何成员

### 2. 获取单个Pool状态

**GET** `/pools/{pool_name}/{partition}/status`

**功能**: 获取指定Pool的详细状态信息

**参数**:
- `pool_name`: Pool名称
- `partition`: Partition名称

**响应**:
```json
{
  "name": "llm-pool-1",
  "partition": "Common",
  "engine_type": "vllm",
  "member_count": 2,
  "members": [
    {
      "ip": "10.10.10.10",
      "port": 8001,
      "score": 0.75,
      "metrics": {
        "waiting_queue": 2.0,
        "cache_usage": 0.3
      }
    },
    {
      "ip": "10.10.10.10",
      "port": 8002,
      "score": 0.82,
      "metrics": {
        "waiting_queue": 1.5,
        "cache_usage": 0.25
      }
    }
  ]
}
```

**GET** `/pools/{pool_name}/{partition}/status?simple`

**功能**: 获取指定Pool的member score分值的简单输出

**参数**:

- `pool_name`: Pool名称
- `partition`: Partition名称
- `simple`:查询参数

**响应**:

```
127.0.0.1:8001 0.5404
127.0.0.1:8002 0.0000
127.0.0.1:8003 0.2846
```

### 3. 获取所有Pool状态

**GET** `/pools/status`

**功能**: 获取所有Pool的状态信息

**响应**:
```json
{
  "pools": [
    {
      "name": "llm-pool-1",
      "partition": "Common",
      "engine_type": "vllm",
      "member_count": 2,
      "members": [...]
    },
    {
      "name": "llm-pool-2",
      "partition": "Common",
      "engine_type": "sglang",
      "member_count": 3,
      "members": [...]
    }
  ]
}
```

### 4. 健康检查

**GET** `/health`

**功能**: 检查调度器服务健康状态

**响应**:
```json
{
  "status": "healthy",
  "message": "调度器运行正常"
}
```

### 5. 模拟选择过程

**POST** `/pools/{pool_name}/{partition}/simulate`

**功能**: 模拟多次选择过程，用于测试和分析（测试接口）

**参数**:
- `pool_name`: Pool名称
- `partition`: Partition名称
- `iterations`: 模拟次数（查询参数，默认100）

**请求体**:
```json
{
  "pool_name": "llm-pool-1",
  "partition": "Common",
  "members": ["10.10.10.10:8001", "10.10.10.10:8002"]
}
```

**响应**:
```json
{
  "results": {
    "10.10.10.10:8001": 45,
    "10.10.10.10:8002": 55
  },
  "iterations": 100
}
```

### 6. 高级概率分析

**POST** `/pools/{pool_name}/{partition}/analyze`

**功能**: 详细分析选择精度和概率偏差（测试接口）

**参数**:
- `pool_name`: Pool名称
- `partition`: Partition名称
- `iterations`: 分析次数（查询参数，默认1000）

**请求体**:
```json
{
  "pool_name": "llm-pool-1",
  "partition": "Common",
  "members": ["10.10.10.10:8001", "10.10.10.10:8002"]
}
```

**响应**:
```json
{
  "member_analysis": {
    "10.10.10.10:8001": {
      "theoretical_probability": 0.4286,
      "actual_probability": 0.4310,
      "selection_count": 431,
      "deviation": 0.0024,
      "deviation_percentage": 0.56
    },
    "10.10.10.10:8002": {
      "theoretical_probability": 0.5714,
      "actual_probability": 0.5690,
      "selection_count": 569,
      "deviation": -0.0024,
      "deviation_percentage": -0.42
    }
  },
  "overall_stats": {
    "total_iterations": 1000,
    "avg_deviation": 0.0024,
    "max_deviation": 0.0024,
    "quality_score": 99.44
  }
}
```

## 配置文件完整说明

### 全局配置 (global)

| 配置项 | 类型 | 必配 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `interval` | 整数 | 否 | 60 | 配置文件热更新检查间隔（秒） |
| `api_port` | 整数 | 否 | 8080 | API服务监听端口 |
| `api_host` | 字符串 | 否 | "0.0.0.0" | API服务监听地址（0.0.0.0表示所有接口） |
| `log_level` | 字符串 | 否 | "INFO" | 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL） |
| `log_debug` | 布尔值 | 否 | false | 向后兼容的调试开关（当log_level未配置时使用） |

### F5配置 (f5)

| 配置项 | 类型 | 必配 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `host` | 字符串 | **是** | 无 | F5设备IP地址或主机名 |
| `port` | 整数 | 否 | 443 | F5 iControl REST API端口 |
| `username` | 字符串 | 否 | "admin" | F5设备登录用户名，需要Guest角色或更高权限 |
| `password_env` | 字符串 | 否 | 无 | F5密码的环境变量名 |

### 调度器配置 (scheduler)

| 配置项 | 类型 | 必配 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `pool_fetch_interval` | 整数 | 否 | 10 | 从F5获取Pool成员的间隔（秒） |
| `metrics_fetch_interval` | 整数 | 否 | 1000 | 从推理引擎收集Metrics的间隔（毫秒） |

### 算法模式配置 (modes)

| 配置项 | 类型 | 必配 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `name` | 字符串 | 否 | "s1" | 算法模式名称（支持s1和s2） |
| `w_a` | 浮点数 | 否 | 0.5 | 等待队列权重（0-1之间） |
| `w_b` | 浮点数 | 否 | 0.5 | 缓存使用率权重（0-1之间） |
| `w_g` | 浮点数 | 否 | 0.0 | 运行请求权重（在S2算法中使用） |

### Pool配置 (pools)

| 配置项 | 类型 | 必配 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `name` | 字符串 | **是** | 无 | Pool名称，必须与F5上的Pool名称一致 |
| `partition` | 字符串 | 否 | "Common" | F5上的Partition名称 |
| `engine_type` | 字符串 | **是** | 无 | 推理引擎类型（vllm/sglang） |

### Metrics配置 (pools[].metrics)

| 配置项 | 类型 | 必配 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `schema` | 字符串 | 否 | "http" | 协议类型（http/https） |
| `port` | 整数 | 否 | null | Metrics服务端口，null表示使用Pool成员自己的端口 |
| `path` | 字符串 | 否 | "/metrics" | Metrics服务的URL路径 |
| `timeout` | 整数 | 否 | 3 | HTTP请求超时时间（秒） |
| `APIkey` | 字符串 | 否 | null | Metrics服务的API密钥 |
| `metric_user` | 字符串 | 否 | null | Metrics服务的用户名 |
| `metric_pwd_env` | 字符串 | 否 | null | Metrics服务密码的环境变量名 |

### 配置示例

```yaml
# 完整配置示例
global:
  interval: 5
  api_port: 8080
  api_host: 0.0.0.0
  log_level: INFO

f5:
  host: 192.168.1.100          # 必配：F5设备地址
  port: 443
  username: admin
  password_env: F5_PASSWORD

scheduler:
  pool_fetch_interval: 10
  metrics_fetch_interval: 3000

modes:
# 目前支持s1和s2算法。s1使用2个指标，s2使用3个指标
# 您需要在实际环境中测试它们，看看哪个效果更好
  #- name: s1
    #w_a: 0.8 # 在实际中，w_a对TTFT影响更大
    #w_b: 0.2
  - name: s2
    w_a: 0.4 # 等待队列指标权重
    w_b: 0.3 # 缓存使用率指标权重
    w_g: 0.3 # 运行请求指标权重

pools:
  - name: llm-pool-1           # 必配：Pool名称
    partition: Common
    engine_type: vllm          # 必配：引擎类型
    metrics:
      schema: http
      path: /metrics
      timeout: 4
      APIkey: your-api-key
      metric_user: metrics_user
      metric_pwd_env: METRIC_PWD

  - name: llm-pool-2
    partition: tenant-1
    engine_type: sglang
    metrics:
      schema: https
      port: 9090               # 使用统一的metrics端口
      path: /custom/metrics
      timeout: 5
```

## 算法说明

Please refer to [LLM推理网关调度器算法对比分析](./LLM推理网关调度器算法对比分析.md)

### 加权随机选择

基于每个成员的Score值进行加权随机选择：
1. 计算所有成员的Score总和
2. 生成0到总和之间的随机数
3. 根据随机数落在的区间选择对应成员
4. Score越高的成员占据的区间越大，被选中概率越高

### 推理引擎支持的指标

**vLLM引擎**:
- `vllm:num_requests_waiting`: 等待队列中的请求数量
- `vllm:gpu_cache_usage_perc`: GPU缓存使用百分比
- `vllm:num_requests_running`: 当前运行中的请求数量（用于S2算法）

**SGLang引擎**:
- `sglang:num_queue_reqs`: 队列中的请求数量
- `sglang:token_usage`: Token缓存使用率
- `sglang:num_running_reqs`: 当前运行中的请求数量（用于S2算法）

## 运行监控

### 日志文件

调度器会生成详细的日志文件 `scheduler.log`，包含：
- 配置加载和热更新记录
- Pool成员获取和更新记录
- Metrics收集状态和结果
- Score计算过程和结果
- API请求和响应记录
- 调度选择决策过程
- 错误和异常信息

### 性能指标

通过API接口可以查看：
- 每个Pool的成员数量和状态
- 成员的实时Metrics数据
- Score分值分布和变化趋势
- 选择结果统计和概率分析
- 系统运行健康状态

### 日志级别说明

- **DEBUG**: 显示所有详细信息，包括每次选择的详细过程
- **INFO**: 显示关键操作和状态变化
- **WARNING**: 显示警告信息，如配置缺失、连接问题等
- **ERROR**: 显示错误信息，如配置错误、网络故障等
- **CRITICAL**: 显示严重错误，可能导致程序无法运行

## 故障排除

### 常见问题

1. **F5连接失败**
   - 检查F5设备网络连通性：`ping <f5_host>`
   - 验证用户名和密码是否正确
   - 确认F5设备开启iControl REST功能
   - 检查用户是否因多次失败登录而被锁定
   - 设置log level为debug，查看详细日志
   
2. **Metrics收集失败**
   - 检查推理引擎服务是否正常运行
   - 验证Metrics接口配置是否正确
   - 确认网络防火墙设置允许访问
   - 检查推理引擎的Metrics端口和路径
   - 设置log level为debug，查看详细日志
   
3. **Score计算异常**
   - 检查算法模式配置是否正确
   - 验证权重参数设置（w_a + w_b建议等于1）
   - 查看Metrics数据完整性
   - 确认推理引擎类型配置正确
   - 设置log level为debug，查看详细日志
   
4. **Pool成员获取失败**
   - 验证Pool名称和Partition是否与F5配置一致
   - 检查F5设备上Pool的状态
   - 确认F5客户端连接和认证正常
   - 设置log level为debug，查看详细日志

### 调试模式

启用详细调试日志：

```yaml
global:
  log_level: DEBUG
```

或使用向后兼容方式：

```yaml
global:
  log_debug: true
```

### 健康检查

使用健康检查接口监控服务状态：

```bash
curl http://localhost:8080/health
```

正常响应：
```json
{"status": "healthy", "message": "调度器运行正常"}
```

## 开发指南

### 扩展支持新的推理引擎

1. 在 `core/models.py` 中添加新的引擎类型：
```python
class EngineType(Enum):
    VLLM = "vllm"
    SGLANG = "sglang"
    NEW_ENGINE = "new_engine"  # 添加新引擎
```

2. 在 `ENGINE_METRICS` 中定义关键指标：
```python
ENGINE_METRICS = {
    EngineType.NEW_ENGINE: {
        "waiting_queue": "new_engine:queue_length",
        "cache_usage": "new_engine:cache_usage"
    }
}
```

3. 更新 `metrics_collector.py` 的解析逻辑（如果指标格式不同）

### 实现新的调度算法

项目目前支持两种算法：S1和S2。要实现额外的算法：

1. 在配置中添加新模式：
```yaml
modes:
  - name: s3
    w_a: 0.3
    w_b: 0.3
    w_g: 0.2
    w_h: 0.2  # 根据需要添加新的权重参数
```

2. 如果需要新指标，在 `core/models.py` 中添加指标支持：
```python
ENGINE_METRICS = {
    EngineType.VLLM: {
        "waiting_queue": "vllm:num_requests_waiting",
        "cache_usage": "vllm:gpu_cache_usage_perc",
        "running_req": "vllm:num_requests_running",
        "new_metric": "vllm:new_metric_name"  # 添加新指标
    }
}
```

3. 在 `core/score_calculator.py` 中实现算法逻辑：
```python
def _calculate_s3_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
    # 实现S3算法
    pass
```

4. 更新主计算方法以支持新算法：
```python
elif mode_config.name == "s3":
    self._calculate_s3_scores(pool, mode_config)
```

## 许可证

本项目为内部使用，请遵守相关使用条款。 