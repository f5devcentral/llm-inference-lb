# API Key热重载测试指南

## 测试场景

本指南说明如何测试XInference API Key配置的热重载功能。

## 准备工作

1. 确保调度器正在运行
2. 监控日志输出：`tail -f logs/scheduler.log`

## 测试步骤

### 1. 基础配置测试

**初始配置** (`scheduler-config.yaml`):
```yaml
pools:
  - name: xinference_pool_1
    partition: Common
    engine_type: xinference
    model_APIkey:
      path: /v1/cluster/authorizations
      f5datagroup: xinfer-datagroup
      timeout: 4
      api_key_sync_interval: 300
      APIkey: old_api_key_123
      apikey_user: user1
      apikey_pwd_env: APIKeyServer_PWD
      failure_mode: "preserve"
```

**预期行为**:
- 调度器应启动API key同步任务
- 每300秒同步一次
- 使用APIkey认证（因为APIkey存在）

### 2. 认证方式切换测试

**修改配置** - 移除APIkey，使用用户密码认证:
```yaml
pools:
  - name: xinference_pool_1
    partition: Common
    engine_type: xinference
    model_APIkey:
      path: /v1/cluster/authorizations
      f5datagroup: xinfer-datagroup
      timeout: 4
      api_key_sync_interval: 300
      # APIkey: old_api_key_123  # 注释掉
      apikey_user: user1
      apikey_pwd_env: APIKeyServer_PWD
      failure_mode: "preserve"
```

**预期行为**:
```
[INFO] Configuration file changes detected, starting hot reload...
[INFO] Updated Pool xinference_pool_1_Common model_APIkey configuration
[INFO] API key sync task restarted with updated configuration
[DEBUG] Using basic authentication for 192.168.1.100:8080 with user: user1
```

### 3. 同步间隔修改测试

**修改配置** - 将同步间隔从300秒改为60秒:
```yaml
pools:
  - name: xinference_pool_1
    partition: Common
    engine_type: xinference
    model_APIkey:
      path: /v1/cluster/authorizations
      f5datagroup: xinfer-datagroup
      timeout: 4
      api_key_sync_interval: 60  # 从300改为60
      apikey_user: user1
      apikey_pwd_env: APIKeyServer_PWD
      failure_mode: "preserve"
```

**预期行为**:
```
[INFO] Updated Pool xinference_pool_1_Common model_APIkey configuration
[INFO] API key sync task restarted with updated configuration
[INFO] Starting API key sync for pool xinference_pool_1, interval: 60s
```

### 4. 故障处理模式测试

**修改配置** - 将故障处理模式从preserve改为smart:
```yaml
pools:
  - name: xinference_pool_1
    partition: Common
    engine_type: xinference
    model_APIkey:
      path: /v1/cluster/authorizations
      f5datagroup: xinfer-datagroup
      timeout: 4
      api_key_sync_interval: 60
      apikey_user: user1
      apikey_pwd_env: APIKeyServer_PWD
      failure_mode: "smart"  # 从preserve改为smart
      max_failures_threshold: 5  # 从10改为5
```

**预期行为**:
```
[INFO] Updated Pool xinference_pool_1_Common model_APIkey configuration
[INFO] API key sync task restarted with updated configuration
```

### 5. 添加新的XInference Pool测试

**修改配置** - 添加第二个XInference pool:
```yaml
pools:
  - name: xinference_pool_1
    partition: Common
    engine_type: xinference
    model_APIkey:
      # ... 现有配置 ...
      
  - name: xinference_pool_2  # 新增pool
    partition: Common
    engine_type: xinference
    model_APIkey:
      path: /v1/cluster/authorizations
      f5datagroup: xinfer-datagroup-2
      timeout: 4
      api_key_sync_interval: 180
      APIkey: new_pool_api_key_456
      failure_mode: "preserve"
```

**预期行为**:
```
[INFO] Configuration added Pool: xinference_pool_2:Common
[INFO] API key sync task restarted with updated configuration
[INFO] Started 2 API key sync loops
[INFO] Starting API key sync for pool xinference_pool_2, interval: 180s
```

## 监控检查点

### 1. 日志关键词监控

```bash
# 监控配置变更
tail -f logs/scheduler.log | grep "model_APIkey configuration"

# 监控任务重启
tail -f logs/scheduler.log | grep "API key sync task restarted"

# 监控认证模式
tail -f logs/scheduler.log | grep "Using.*authentication"

# 监控同步成功
tail -f logs/scheduler.log | grep "Successfully synced.*API keys"
```

### 2. API健康检查

在配置变更后，检查API健康状态：

```bash
curl http://localhost:8080/api_key_health | jq
```

预期响应应显示更新后的配置和状态。

### 3. F5 Data Group验证

如果可以访问F5设备，验证data group的更新：

```bash
# 检查data group是否存在并包含新数据
curl -u admin:password -k \
  https://f5.example.com:8443/mgmt/tm/ltm/data-group/internal/xinfer-datagroup
```

## 常见问题排查

### 1. 配置没有生效

**检查项**:
- 配置文件语法是否正确（YAML格式）
- 是否在global.interval时间内
- 日志中是否有错误信息

### 2. 认证方式没有切换

**检查项**:
- APIkey字段是否完全移除（不只是注释）
- apikey_user和apikey_pwd_env是否正确配置
- 环境变量是否设置

### 3. 同步间隔没有改变

**检查项**:
- 是否触发了任务重启
- 新的同步循环是否开始
- 检查具体的日志时间戳

## 测试验证标准

✅ **成功标准**:
1. 配置变更后5秒内检测到更改
2. API key同步任务成功重启
3. 新配置立即生效
4. 认证方式正确切换
5. 同步间隔按新配置执行
6. API健康检查反映新状态

❌ **失败情况**:
1. 配置变更未被检测
2. 任务重启失败
3. 认证方式没有切换
4. 同步间隔未更新
5. 出现错误日志

## 回滚测试

在完成测试后，验证回滚到原始配置也能正常工作：

1. 恢复原始配置
2. 等待配置重新加载
3. 确认所有设置回到初始状态
4. 验证功能正常

这样可以确保热重载功能在两个方向都工作正常。
