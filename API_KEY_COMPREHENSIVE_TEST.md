# XInference API Key处理全面测试案例

## 测试目标

验证XInference API key处理模块在各种边界情况和异常情况下的正确性和稳定性。

## 测试环境准备

### 1. 配置文件设置

```yaml
# scheduler-config.yaml
pools:
  - name: xinference_test_pool
    partition: Common
    engine_type: xinference
    model_APIkey:
      path: /v1/cluster/authorizations
      f5datagroup: xinfer-test-datagroup
      timeout: 4
      api_key_sync_interval: 60  # 快速测试间隔
      APIkey: test_api_key_123
      apikey_user: testuser
      apikey_pwd_env: APIKeyServer_PWD
      failure_mode: "smart"
      max_failures_threshold: 3
      failure_timeout_hours: 0.5
```

### 2. 环境变量设置

```bash
export TEST_PWD="testpassword123"
export F5_PASSWORD="f5password"
```

## 测试案例

### 案例1: 正常API响应处理

**模拟XInference响应**:
```json
{
  "code": 200,
  "message": "Success",
  "timestamp": "2025-01-15T14:26:15.000Z",
  "data": {
    "authorization_records": [
      {
        "api_key": "sha256_sk11111",
        "model_ids": ["model-001", "model-002"]
      },
      {
        "api_key": "sha256_sk22222",
        "model_ids": ["model-001", "model-003"]
      }
    ],
    "count": 2
  }
}
```

**期望结果**:
- F5 datagroup应包含记录：
  ```
  model-001_192.168.1.100_8080: sha256_sk11111,sha256_sk22222
  model-002_192.168.1.100_8080: sha256_sk11111
  model-003_192.168.1.100_8080: sha256_sk22222
  ```

**验证命令**:
```bash
curl http://localhost:8080/api_key_health | jq '.pools'
```

### 案例2: JSON格式错误处理

**模拟错误响应** (文档中的格式错误):
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "authorization_records": [
      {
        "api_key": "sha256_sk33333",
        "model_ids:": ["model-004"]  // 注意这里有格式错误
      }
    ]
  }
}
```

**期望结果**:
- 系统应正确解析并处理这种格式错误
- 日志应显示成功解析的记录
- F5 datagroup应包含：`model-004_192.168.1.100_8080: sha256_sk33333`

### 案例3: 模型变化检测

**步骤1** - 初始状态:
```json
{
  "authorization_records": [
    {"api_key": "key1", "model_ids": ["model-A", "model-B"]},
    {"api_key": "key2", "model_ids": ["model-A"]}
  ]
}
```

**步骤2** - 模型变化:
```json
{
  "authorization_records": [
    {"api_key": "key1", "model_ids": ["model-A"]},        // model-B被移除
    {"api_key": "key3", "model_ids": ["model-A"]},        // 新key
    {"api_key": "key4", "model_ids": ["model-C"]}         // 新模型
  ]
}
```

**期望日志输出**:
```
[INFO] Pool xinference_test_pool: Removed model keys: ['model-B_192.168.1.100_8080']
[INFO] Pool xinference_test_pool: Added model keys: ['model-C_192.168.1.100_8080']
[INFO] Pool xinference_test_pool: Modified model keys: ['model-A_192.168.1.100_8080']
[DEBUG]   model-A_192.168.1.100_8080: Added API keys: ['key3']
[DEBUG]   model-A_192.168.1.100_8080: Removed API keys: ['key2']
```

### 案例4: 空响应处理

**模拟场景**: XInference返回空的authorization_records

**响应**:
```json
{
  "code": 200,
  "message": "Success",
  "data": {
    "authorization_records": [],
    "count": 0
  }
}
```

**期望行为**:
```
[WARNING] Pool xinference_test_pool: XInference returned empty API keys, but F5 datagroup has X records. This might indicate XInference service issues or all models were removed.
[INFO] Pool xinference_test_pool: Smart mode - treating empty response as potential service issue, preserving records
```

### 案例5: 网络异常处理

**测试步骤**:
1. 临时停止XInference服务或使用错误的端口
2. 观察系统行为

**期望行为**:
```
[ERROR] Exception fetching API keys from 192.168.1.100:8080: Connection refused
[ERROR] Pool xinference_test_pool: No members returned API keys - possible service issues
[ERROR] API key sync failed for pool xinference_test_pool (failure #1): No API keys data received from XInference
```

### 案例6: 认证方式切换

**步骤1** - 使用APIkey认证:
```yaml
model_APIkey:
  APIkey: test_api_key_123
  apikey_user: testuser
  apikey_pwd_env: APIKeyServer_PWD
```

**步骤2** - 移除APIkey，切换到用户密码认证:
```yaml
model_APIkey:
  # APIkey: test_api_key_123  # 注释掉
  apikey_user: testuser
  apikey_pwd_env: APIKeyServer_PWD
```

**期望日志**:
```
[INFO] Updated Pool xinference_test_pool:Common model_APIkey configuration
[INFO] API key sync task restarted with updated configuration
[DEBUG] Using basic authentication for 192.168.1.100:8080 with user: testuser
```

### 案例7: 多成员Pool处理

**配置多个Pool Members**:
- Member 1: 192.168.1.100:8080
- Member 2: 192.168.1.101:8080 (故意配置错误端口测试)
- Member 3: 192.168.1.102:8080

**期望行为**:
- 成功的member正常同步
- 失败的member记录错误但不影响其他member
- 最终报告: "Successfully fetched API keys from 2/3 members"

### 案例8: F5 DataGroup Key格式验证

**测试不同的key格式**:
```python
# 有效格式
"model-001_192.168.1.100_8080"     # ✓
"llama2-7b_10.0.0.1_9000"         # ✓

# 无效格式
"model-001_192.168.1.100"         # ✗ 缺少端口
"model-001_192.168.1.100_abc"     # ✗ 端口非数字
"model-001"                        # ✗ 格式完全错误
```

**期望日志**:
```
[WARNING] Key format may be incorrect: model-001_192.168.1.100
[WARNING] Key format may be incorrect: model-001_192.168.1.100_abc
[WARNING] Key format may be incorrect: model-001
```

### 案例9: 故障处理模式测试

**PRESERVE模式测试**:
1. 配置failure_mode: "preserve"
2. 模拟XInference服务故障
3. 验证F5 datagroup保持不变

**CLEAR模式测试**:
1. 配置failure_mode: "clear"
2. 模拟XInference返回空响应
3. 验证F5 datagroup被清空

**SMART模式测试**:
1. 配置failure_mode: "smart", max_failures_threshold: 3
2. 模拟连续3次以上失败
3. 验证智能处理逻辑

### 案例10: 健康状态监控

**测试API端点**:
```bash
curl http://localhost:8080/api_key_health | jq
```

**期望响应结构**:
```json
{
  "summary": {
    "overall_status": "healthy",
    "total_pools_monitored": 1,
    "healthy_pools": 1,
    "unhealthy_pools": 0,
    "last_updated": 1673798400.0
  },
  "pools": {
    "xinference_test_pool_Common": {
      "pool_name": "xinference_test_pool",
      "is_healthy": true,
      "consecutive_failures": 0,
      "total_failures": 0,
      "total_syncs": 5,
      "last_success_hours_ago": 0.02,
      "last_model_count": 3,
      "last_key_count": 4,
      "last_error": "",
      "failure_mode": "smart"
    }
  }
}
```

## 自动化测试脚本

```bash
#!/bin/bash
# api_key_test.sh

echo "=== XInference API Key处理测试 ==="

# 1. 检查系统状态
echo "1. 检查系统健康状态..."
curl -s http://localhost:8080/api_key_health | jq '.summary.overall_status'

# 2. 检查配置热重载
echo "2. 测试配置热重载..."
# 修改配置文件
sed -i.bak 's/api_key_sync_interval: 60/api_key_sync_interval: 30/' config/scheduler-config.yaml
sleep 10
# 检查是否生效
grep "API key sync task restarted" logs/scheduler.log | tail -1

# 3. 恢复配置
mv config/scheduler-config.yaml.bak config/scheduler-config.yaml

# 4. 监控日志中的关键事件
echo "3. 监控关键事件..."
tail -20 logs/scheduler.log | grep -E "(API key|model|sync|error)"

echo "=== 测试完成 ==="
```

## 验证要点

### 功能正确性
- [ ] 正确解析XInference API响应
- [ ] 准确检测模型和API key变化
- [ ] 正确格式化F5 datagroup记录
- [ ] 认证方式优先级正确

### 异常处理
- [ ] 网络异常不导致程序崩溃
- [ ] JSON格式错误能正确处理
- [ ] 部分member失败不影响整体功能
- [ ] 空响应按配置策略处理

### 性能和稳定性
- [ ] 多pool并发同步正常
- [ ] 长时间运行内存不泄漏
- [ ] 配置热重载不中断服务
- [ ] 故障恢复后自动重新同步

### 监控和诊断
- [ ] 健康检查API返回正确状态
- [ ] 日志记录详细且有用
- [ ] 状态统计准确
- [ ] 错误信息清晰

通过这套全面的测试案例，可以确保XInference API key处理模块在各种复杂情况下都能稳定可靠地工作。
