# XInference调度器集成指南

本文档详细介绍如何将XInference推理引擎集成到F5 LLM推理网关调度器中。

## 目录

- [概述](#概述)
- [配置文件样例](#配置文件样例)
- [程序基本工作逻辑](#程序基本工作逻辑)
- [API请求示例](#api请求示例)
- [异常处理](#异常处理)
- [最佳实践](#最佳实践)

## 概述

XInference是一个多模态推理引擎，支持多种模型类型（LLM、音频、视频等）。与vLLM/SGLang不同，XInference具有以下特点：

- **模型级别指标**: 每个模型独立维护`throughput_utilization`指标
- **JSON格式响应**: metrics接口返回JSON格式而非Prometheus格式
- **模型特定调度**: API请求必须指定具体的模型名称

## 配置文件样例

### 基础配置

> 与正常配置类似，仅需注意在XInference类型下，系统会忽略member级别的fallback阀值设置，以及忽略modes的算法（无论是否配置为s1，s1_enhanced等算法）

```yaml
# scheduler-config-xinference.yaml
global:
  log_debug: true
  log_level: "INFO"

scheduler:
  metrics_fetch_interval: 5000  # 5秒采集一次metrics

pools:
  - name: xinference_pool_1
    partition: Common
    engine_type: xinference  # 关键：指定为xinference
    fallback:
      pool_fallback: false
      # 注意：XInference忽略以下两个member级别的threshold
      member_running_req_threshold: 100
      member_waiting_queue_threshold: 100.0
    metrics:
      schema: http
      port: 5001  # XInference metrics端口，注释掉表示使用pool member对应端口
      path: /v1/cluster/load-statistics  # XInference metrics路径
      timeout: 4
      APIkey: "your-api-key-here"  # 可选
      metric_user: "metrics_user"  # 可选
      metric_pwd_env: "XINF_METRICS_PWD"  # 可选

modes:
  - name: "s1"  # XInference会忽略算法设置，直接使用throughput_utilization
    w_a: 0.3
    w_b: 0.7
```

## 程序基本工作逻辑

### 1. 系统启动与初始化

```
程序启动
    ↓
加载配置文件 (scheduler-config.yaml)
    ↓
识别engine_type为xinference的Pool
    ↓
初始化调度器、metrics采集器、score计算器
    ↓
启动API服务器 (默认端口8080)
```

### 2. Metrics采集流程

```
定时器触发 (每N秒)
    ↓
并行访问各Pool的metrics接口
    ↓
XInference: GET /v1/cluster/load-statistics
    ↓
解析JSON响应:
{
  "code": 200,
  "data": {
    "model_metrics": [
      {
        "model_name": "qwen-7b",
        "throughput_utilization": 0.3
      },
      {
        "model_name": "stable-diffusion",
        "throughput_utilization": 0.8
      }
    ]
  }
}
    ↓
存储到内存: member.model_metrics[model_name] = utilization
    ↓
立即预计算所有模型分值: member.model_scores[model_name] = 1.0 - utilization
```

### 3. API调度流程

```
接收API请求 (POST /scheduler/select)
    ↓
验证请求参数:
- pool_name, partition, members (必需)
- model (XInference必需)
    ↓
检查Pool类型:
if engine_type == xinference:
    if model字段缺失:
        return "request_has_no_model_name"
    ↓
    过滤拥有该模型的members
    ↓
    if 无member拥有该模型:
        return "no_the_model_name"
    ↓
    读取预计算的模型分值: member.score = member.model_scores[model_name]
    ↓
    执行加权随机选择
    ↓
    return 选中的member地址
```

### 4. 分值计算逻辑

```
XInference分值计算 (预计算模式):

for each member in pool:
    for each model in member.model_metrics:
        utilization = member.model_metrics[model]
        score = max(0.001, 1.0 - utilization)
        member.model_scores[model] = score

特点:
- 利用率越高，分值越低
- 利用率 0.0 → 分值 1.0 (最优)
- 利用率 1.0 → 分值 0.001 (最差)
- 每个模型独立计算，不相互影响
```

## API请求示例

### 正常请求示例

#### 请求

```bash
curl -X POST "http://localhost:8001/scheduler/select" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_name": "xinference_pool_1",
    "partition": "Common",
    "model": "qwen-7b",
    "members": [
      "192.168.1.100:8001",
      "192.168.1.101:8002",
      "192.168.1.102:8003"
    ]
  }'
```

#### 响应

```
192.168.1.100:8001
```

#### 说明
- 返回利用率最低的member地址
- 响应为纯字符串格式

### Python客户端示例

```python
import requests
import json

def select_xinference_member(pool_name, partition, model, members):
    """选择XInference最优member"""
    url = "http://localhost:8001/scheduler/select"
    payload = {
        "pool_name": pool_name,
        "partition": partition,
        "model": model,
        "members": members
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.text.strip('"')  # 移除可能的引号
        else:
            print(f"API错误: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None

# 使用示例
result = select_xinference_member(
    pool_name="xinference_pool_1",
    partition="Common", 
    model="qwen-7b",
    members=["192.168.1.100:8001", "192.168.1.101:8002"]
)

if result:
    print(f"选中的member: {result}")
    # 可以直接用于后续的推理请求
    inference_url = f"http://{result}/v1/chat/completions"
```

## 异常处理

### 1. 缺少model字段

#### 请求

```bash
curl -X POST "http://localhost:8001/scheduler/select" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_name": "xinference_pool_1",
    "partition": "Common",
    "members": ["192.168.1.100:8001", "192.168.1.101:8002"]
  }'
```

#### 响应

```
request_has_no_model_name
```

#### 处理建议

```python
result = select_xinference_member(...)
if result == "request_has_no_model_name":
    print("错误：XInference请求必须包含model字段")
    # 重新构造请求，添加model字段
```

### 2. 模型不存在 或 模型在全部集群里存在但对应的候选member里没有此模型

#### 请求

```bash
curl -X POST "http://localhost:8001/scheduler/select" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_name": "xinference_pool_1",
    "partition": "Common",
    "model": "nonexistent-model",
    "members": ["192.168.1.100:8001", "192.168.1.101:8002"]
  }'
```

#### 响应

```
no_the_model_name
```

#### 处理建议

```python
result = select_xinference_member(...)
if result == "no_the_model_name":
    print("错误：没有member支持请求的模型")
    # 检查模型名称是否正确，或选择其他模型
```

### 3. Pool启用Fallback

#### 配置

```yaml
pools:
  - name: xinference_pool_1
    partition: Common
    engine_type: xinference
    fallback:
      pool_fallback: true  # 启用fallback
```

#### 响应

```
fallback
```

#### 处理建议

```python
result = select_xinference_member(...)
if result == "fallback":
    print("Pool当前不可用，使用备用方案")
    # 切换到备用Pool或返回错误给上游
```

### 4. Pool不存在

#### 请求

```bash
curl -X POST "http://localhost:8001/scheduler/select" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_name": "nonexistent_pool",
    "partition": "Common",
    "model": "qwen-7b",
    "members": ["192.168.1.100:8001"]
  }'
```

#### 响应

```
none
```

### 5. 候选members为空

#### 请求

```bash
curl -X POST "http://localhost:8001/scheduler/select" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_name": "xinference_pool_1",
    "partition": "Common",
    "model": "qwen-7b",
    "members": []
  }'
```

#### 响应

```
none
```

### 6. 无效的member格式

#### 请求

```bash
curl -X POST "http://localhost:8001/scheduler/select" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_name": "xinference_pool_1",
    "partition": "Common",
    "model": "qwen-7b",
    "members": ["invalid-format", "192.168.1.100"]
  }'
```

#### 响应

```
none
```

### 7. HTTP异常情况

#### 请求参数缺失

```bash
curl -X POST "http://localhost:8001/scheduler/select" \
  -H "Content-Type: application/json" \
  -d '{
    "pool_name": "xinference_pool_1"
  }'
```

#### 响应

```http
HTTP/1.1 422 Unprocessable Entity
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "partition"],
      "msg": "Field required"
    }
  ]
}
```

## 异常响应汇总表

| 场景 | 响应值 | HTTP状态码 | 说明 |
|------|--------|------------|------|
| 正常选择 | `"192.168.1.100:8001"` | 200 | 返回最优member地址 |
| Pool fallback | `"fallback"` | 200 | Pool配置了fallback |
| 模型不存在，<br />或候选members里无此模型 | `"no_the_model_name"` | 200 | 无member支持该模型 |
| 缺少model字段 | `"request_has_no_model_name"` | 200 | XInference必需model字段 |
| Pool不存在 | `"none"` | 200 | 指定的Pool不存在 |
| 候选members为空 | `"none"` | 200 | members数组为空或无效 |
| 请求参数缺失 | JSON错误详情 | 422 | 缺少必需的请求字段 |
| 服务器内部错误 | JSON错误详情 | 500 | 服务器异常 |

## 最佳实践

### 1. 错误处理

```python
def robust_xinference_request(pool_name, partition, model, members, retry_count=3):
    """健壮的XInference请求处理"""
    
    for attempt in range(retry_count):
        try:
            result = select_xinference_member(pool_name, partition, model, members)
            
            # 处理不同的响应情况
            if result and result not in ["none", "fallback", "no_the_model_name", "request_has_no_model_name"]:
                return result  # 成功获取member
            
            elif result == "request_has_no_model_name":
                raise ValueError("请求缺少model字段")
            
            elif result == "no_the_model_name":
                raise ValueError(f"没有member支持模型: {model}")
            
            elif result == "fallback":
                # 尝试备用Pool
                backup_result = select_xinference_member(f"{pool_name}_backup", partition, model, members)
                if backup_result and backup_result not in ["none", "fallback", "no_the_model_name"]:
                    return backup_result
            
            elif result == "none":
                if attempt < retry_count - 1:
                    time.sleep(1)  # 等待重试
                    continue
                else:
                    raise RuntimeError("无法获取可用的member")
        
        except requests.RequestException as e:
            if attempt < retry_count - 1:
                time.sleep(2 ** attempt)  # 指数退避
                continue
            else:
                raise RuntimeError(f"网络请求失败: {e}")
    
    raise RuntimeError("重试次数耗尽")
```

### 2. 模型可用性检查

```python
def check_model_availability(pool_name, partition, model):
    """检查模型在指定Pool中的可用性"""
    
    # 获取Pool状态
    url = f"http://localhost:8001/pools/{pool_name}/{partition}/status"
    response = requests.get(url)
    
    if response.status_code != 200:
        return False, "Pool不存在或不可用"
    
    status = response.json()
    members = status.get('members', [])
    
    available_models = set()
    for member in members:
        model_metrics = member.get('model_metrics', {})
        available_models.update(model_metrics.keys())
    
    if model in available_models:
        return True, f"模型 {model} 可用"
    else:
        return False, f"模型 {model} 不可用，可用模型: {list(available_models)}"

# 使用示例
available, message = check_model_availability("xinference_pool_1", "Common", "qwen-7b")
if available:
    result = select_xinference_member(...)
else:
    print(f"模型检查失败: {message}")
```

### 3. 性能监控

```python
import time
from collections import defaultdict

class XInferenceSchedulerMonitor:
    """XInference调度器性能监控"""
    
    def __init__(self):
        self.request_stats = defaultdict(int)
        self.response_times = []
        self.error_counts = defaultdict(int)
    
    def monitor_request(self, pool_name, partition, model, members):
        """监控单次请求"""
        start_time = time.time()
        
        try:
            result = select_xinference_member(pool_name, partition, model, members)
            response_time = time.time() - start_time
            
            self.response_times.append(response_time)
            self.request_stats[f"{pool_name}:{model}"] += 1
            
            # 记录异常响应
            if result in ["none", "fallback", "no_the_model_name", "request_has_no_model_name"]:
                self.error_counts[result] += 1
            
            return result
            
        except Exception as e:
            self.error_counts["exception"] += 1
            raise
    
    def get_stats(self):
        """获取统计信息"""
        if self.response_times:
            avg_response_time = sum(self.response_times) / len(self.response_times)
            max_response_time = max(self.response_times)
        else:
            avg_response_time = max_response_time = 0
        
        return {
            "total_requests": len(self.response_times),
            "avg_response_time": avg_response_time,
            "max_response_time": max_response_time,
            "error_counts": dict(self.error_counts),
            "request_stats": dict(self.request_stats)
        }

# 使用示例
monitor = XInferenceSchedulerMonitor()
result = monitor.monitor_request("xinference_pool_1", "Common", "qwen-7b", ["192.168.1.100:8001"])
print(monitor.get_stats())
```

### 4. 配置验证

```bash
# 验证XInference配置的脚本
#!/bin/bash

echo "验证XInference配置..."

# 1. 检查配置文件语法
python3 -c "
import yaml
try:
    with open('config/scheduler-config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    print('✅ 配置文件语法正确')
except Exception as e:
    print(f'❌ 配置文件语法错误: {e}')
    exit(1)
"

# 2. 检查XInference Pool配置
python3 -c "
import yaml
with open('config/scheduler-config.yaml', 'r') as f:
    config = yaml.safe_load(f)

xinf_pools = [p for p in config.get('pools', []) if p.get('engine_type') == 'xinference']
if not xinf_pools:
    print('⚠️  未找到XInference类型的Pool')
else:
    for pool in xinf_pools:
        name = pool.get('name')
        metrics = pool.get('metrics', {})
        path = metrics.get('path')
        if path != '/v1/cluster/load-statistics':
            print(f'⚠️  Pool {name} metrics path可能不正确: {path}')
        else:
            print(f'✅ Pool {name} 配置正确')
"

# 3. 测试metrics接口连通性
python3 -c "
import yaml, requests
with open('config/scheduler-config.yaml', 'r') as f:
    config = yaml.safe_load(f)

for pool in config.get('pools', []):
    if pool.get('engine_type') == 'xinference':
        name = pool.get('name')
        metrics = pool.get('metrics', {})
        members = pool.get('members', [])
        
        for member in members:
            ip = member.get('ip')
            port = metrics.get('port', 8000)
            schema = metrics.get('schema', 'http')
            path = metrics.get('path', '/v1/cluster/load-statistics')
            
            url = f'{schema}://{ip}:{port}{path}'
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    print(f'✅ {name} - {ip}:{port} 连通正常')
                else:
                    print(f'⚠️  {name} - {ip}:{port} 返回状态码: {response.status_code}')
            except Exception as e:
                print(f'❌ {name} - {ip}:{port} 连接失败: {e}')
"

echo "配置验证完成"
```


