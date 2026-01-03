# XInference API Key同步功能使用指南

## 概述

XInference API Key同步功能是为支持XInference推理引擎而开发的模块，能够自动从XInference集群获取API key并同步到F5 BIG-IP的data group中，供iRule使用。

## 功能特性

- **自动同步**: 定期从XInference的`/v1/cluster/authorizations`端点获取API key
- **F5集成**: 将API key存储到F5 data group中，支持模型级别的key管理
- **故障处理**: 提供多种故障处理策略（preserve/clear/smart）
- **健康监控**: 提供API接口监控同步状态和健康情况
- **配置热重载**: 支持运行时配置更新

## 配置示例

在`scheduler-config.yaml`中为XInference类型的pool添加`model_APIkey`配置：

```yaml
pools:
  - name: xinference_pool_1
    partition: Common
    engine_type: xinference
    model_APIkey:
      path: /v1/cluster/authorizations
      f5datagroup: xinfer-datagroup
      timeout: 4
      api_key_sync_interval: 300  # 同步间隔（秒）
      APIkey: your_xinference_api_key
      apikey_user: user1
      apikey_pwd_env: APIKeyServer_PWD
      # 故障处理配置（可选）
      failure_mode: "preserve"        # preserve/clear/smart
      max_failures_threshold: 10      # 智能模式：连续失败阈值
      failure_timeout_hours: 2.0      # 智能模式：超时小时数
```

## 配置参数说明

### 必需参数
- `path`: XInference API key端点路径
- `f5datagroup`: F5 data group名称

### 可选参数
- `timeout`: HTTP请求超时时间（默认：4秒）
- `api_key_sync_interval`: 同步间隔（默认：300秒）
- `APIkey`: XInference API访问密钥（优先使用）
- `apikey_user`: 用户名（当没有APIkey时使用）
- `apikey_pwd_env`: 密码环境变量名（当没有APIkey时使用）

### 故障处理参数
- `failure_mode`: 故障处理模式
  - `preserve`: 保持现有data group不变（推荐）
  - `clear`: 立即清空data group
  - `smart`: 基于失败次数和时间的智能处理
- `max_failures_threshold`: 智能模式下的连续失败阈值（默认：10）
- `failure_timeout_hours`: 智能模式下的超时时间（默认：2.0小时）

## F5 Data Group格式

API key在F5 data group中的存储格式：

```
Key格式: {model_id}_{ip}_{port}
Value格式: api_key1,api_key2,api_key3...（逗号分隔）

示例:
model-001_192.168.1.132_5001: sha256_sk11111,sha256_sk2222
model-001_192.168.1.132_5002: sha256_sk3333
model-002_192.168.1.132_5001: sha256_sk11111,sha256_sk2222
```

## F5 iRule使用示例

在F5的iRule中使用API key：

```tcl
# 获取特定模型和集群的API keys
set api_keys_string [class lookup "model-001_192.168.1.132_5001" xinfer-datagroup]
# 结果: "sha256_sk11111,sha256_sk2222"

# 分割API keys列表
set api_keys_list [split $api_keys_string ","]
# 结果: {"sha256_sk11111" "sha256_sk2222"}

# 随机选择一个API key
set random_index [expr {int(rand() * [llength $api_keys_list])}]
set selected_api_key [lindex $api_keys_list $random_index]

# 在HTTP请求中使用
HTTP::header replace "Authorization" "Bearer $selected_api_key"
```

## 健康监控

### API接口

调度器提供以下API接口监控API key同步状态：

```bash
# 基础健康检查
curl http://localhost:8080/health

# API key同步健康检查
curl http://localhost:8080/api_key_health
```

### 响应示例

```json
{
  "summary": {
    "total_pools": 2,
    "healthy_pools": 1,
    "unhealthy_pools": 1,
    "overall_status": "degraded",
    "failure_mode": "preserve"
  },
  "pools": {
    "xinference_pool_1_Common": {
      "pool_name": "xinference_pool_1",
      "is_healthy": true,
      "consecutive_failures": 0,
      "total_failures": 0,
      "last_success_hours_ago": 0.1,
      "last_error": "",
      "failure_mode": "preserve"
    }
  }
}
```

## 日志监控

查看API key同步相关的日志：

```bash
# 查看实时日志
tail -f logs/scheduler.log | grep "API key"

# 查看错误日志
grep "ERROR.*API key" logs/scheduler.log

# 查看同步成功的日志
grep "Successfully synced.*API keys" logs/scheduler.log
```

## 故障处理策略

### 1. Preserve模式（推荐）
- 当无法连接XInference时，保持F5 data group现有数据不变
- 适用于生产环境，确保服务连续性

### 2. Clear模式
- 当无法连接XInference时，立即清空F5 data group
- 适用于需要强制刷新的场景

### 3. Smart模式
- 基于连续失败次数和持续时间智能决策
- 达到阈值后才清空data group
- 平衡数据新鲜度和服务稳定性

## 注意事项

1. **引擎类型限制**: `model_APIkey`配置仅对`engine_type: xinference`有效
2. **配置验证**: 系统会在启动时验证配置的完整性
3. **内存管理**: 同步任务会自动管理HTTP连接和会话
4. **并发安全**: 支持多个pool的并发同步
5. **热重载**: 支持运行时修改同步间隔等配置

## 故障排查

### 常见问题

1. **配置无效**
   - 检查`engine_type`是否为`xinference`
   - 验证必需字段`f5datagroup`是否配置

2. **连接失败**
   - 检查XInference服务是否正常运行
   - 验证网络连接和防火墙设置
   - 确认API key和认证信息正确

3. **同步失败**
   - 查看日志中的具体错误信息
   - 检查F5设备连接和权限
   - 验证data group是否存在

### 调试模式

设置日志级别为DEBUG以获取详细信息：

```yaml
global:
  log_level: DEBUG
```

## 升级和兼容性

- 新功能向后兼容，不影响现有的vLLM/SGLang池
- 仅为配置了`model_APIkey`的XInference池启用同步
- 支持从旧版本无缝升级
