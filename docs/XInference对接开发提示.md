本文档描述当engine_type设置为xinference时候，程序的工作行为与机制。



由于XInference（简称xinf或xinfer）的metrics接口与vLLM以及SGlang都不同，因此针对xinf的metrics接口内容的提取需要单独处理。

我们继续利用scheduler-config.yaml配置文件中的pools来配置，当engine_type为xinference时，需要忽略fallback下的`member_running_req_threshold`和`member_waiting_queue_threshold`这两个参数，即fallback功能此时仅考虑pool_fallback的设置。

```yaml
pools:
  - name: example_pool1
    partition: Common
    engine_type: xinference
    fallback:
      pool_fallback: false  # Pool level fallback switch, default is false. If true, API will return "fallback" directly
      member_running_req_threshold: 100  # Running request threshold for member filtering (optional)，it is the any one logic between member_running_req_threshold and member_waiting_queue_threshold
      member_waiting_queue_threshold: 100.0  # Waiting queue threshold for member filtering (optional)，it is the any one logic between member_running_req_threshold and member_waiting_queue_threshold
    metrics:
      schema: http
      port: 5001 #Assume xinf uses dedicate port for metrics API
      path: /v1/cluster/load-statistics
      timeout: 4  # HTTP request timeout (seconds)
      APIkey: abcdefdfdsfds
      metric_user: user1
      metric_pwd_env: METRIC_PWD
```

#### metrics 采集

XInference的metrics接口列出了本集群内的所有模型及其对应的`throughput_utilization`值，Scheduler调度器的metrics采集模块需读取各个模型（model_name)对应的该值，并存储到内存数据结构中，在内存中形成`model_name--pool_member--throughput_utilization`的映射关系。

以下是XInference集群1响应示例（XInference集群1对应了pool下的一个member）：

```json
{
  "code": 200,
  "message": "Success",
  "timestamp": "2025-08-15T14:25:30.000Z",
  "data": {
    "count": 2,
    "model_metrics": [
      {
        "model_id": "model-001",
        "model_name": "name1",
        "model_type": "llm",
        "throughput_utilization": 0.8,
        "model_ability": ["chat"],
        "last_updated": "2025-08-15T14:20:01Z"
      },
      {
        "model_id": "model-002",
        "model_name": "name2",
        "model_type": "audio",
        "throughput_utilization": 0.7,
        "model_ability": ["text2audio"],
        "last_updated": "2025-08-15T14:20:05Z"
      }
    ]
  }
}
```



以下是xinference集群2响应示例（XInference集群2对应了pool下的另一个member）：

```json
{
  "code": 200,
  "message": "Success",
  "timestamp": "2025-08-15T14:25:30.000Z",
  "data": {
    "count": 3,
    "model_metrics": [
      {
        "model_id": "model-001",
        "model_name": "name1",
        "model_type": "llm",
        "throughput_utilization": 0.6,
        "model_ability": ["chat"],
        "last_updated": "2025-08-15T14:20:01Z"
      },
      {
        "model_id": "model-002",
        "model_name": "name2",
        "model_type": "audio",
        "throughput_utilization": 0.2,
        "model_ability": ["text2audio"],
        "last_updated": "2025-08-15T14:20:05Z"
      },
      {
        "model_id": "model-003",
        "model_name": "name3",
        "model_type": "video",
        "throughput_utilization": 0.4,
        "model_ability": ["text2video"],
        "last_updated": "2025-08-15T14:20:05Z"
      }
    ]
  }
}
```



#### score计算与member优选

在engine_type为xInference时，metrics采集模块采集到的是`throughput_utilization`这个指标，这与当engine_type为vllm或sglang时都不一样，为vllm或sglang所定义的`w_a`,`w_b`,`w_g`这些权重值都不再需要。无论用户配置哪种score算法（如s1,s1_enhanced等等)，此时都直接按照`throughput_utilization`原始值来进行加权随机选择，从而选择出最合适的member。

在 engine_type为xInference时，意味着向调度器API接口查询的请求内容包含了model name字段，payload内容举例如下:

```
{
  "pool_name": "example_pool1",
  "partition": "Common", 
  "model": "name1",
  "members": ["10.10.10.10:8001", "10.10.10.10:8002"]
}
```



### 注意点

你需要仔细分析已有程序在数据结构设计、模块采集、分值计算、优选等逻辑处理，在保持已有功能正常基础上，增加对XInference推理引擎类型的支持。

如果在本文中有未考虑到的地方，你需要考虑并提出解决方案
