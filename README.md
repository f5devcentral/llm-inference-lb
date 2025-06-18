[[中文Readme]](./docs/README-zh.md)   [[模块关系-中文]](./docs/模块关系-zh.md)  [[程序有效性评估-中文]](./docs/Program-effectiveness-Evaluation-zh.md)

[[Modules relationships]](./docs/Module-Relationships.md)   [[Program effectiveness evaluation-EN]](./docs/Program-effectiveness-Evaluation.md)  [[LLM Performance improvement test]](./docs/Inference-performance-improvement-test.md)

# F5 LLM Inference Gateway Scheduler

An intelligent scheduler for LLM inference gateway, designed to work with F5 LTM for optimal load balancing based on real-time performance metrics from inference engines.

## Features

- **Intelligent Scheduling Algorithm**: S1 algorithm based on waiting queue and GPU cache usage
- **Multi-Engine Support**: Supports vLLM and SGLang inference engines
- **Real-time Monitoring**: Automatically fetches F5 Pool members and inference engine performance metrics
- **High Availability Design**: Asynchronous architecture with concurrent processing support
- **RESTful API**: Provides standard HTTP interfaces
- **Configuration Hot Reload**: Supports runtime configuration updates
- **Comprehensive Logging**: Detailed debugging and runtime logs
- **Weighted Random Selection**: Score-based probabilistic selection algorithm
- **Performance Analysis**: Provides selection process simulation and probability analysis interfaces

## Project Structure

```
scheduler-project/
├── main.py                 # Main program entry point
├── config/
│   ├── __init__.py
│   ├── config_loader.py    # Configuration file loader module
│   └── scheduler-config.yaml  # Configuration file
├── core/
│   ├── __init__.py
│   ├── models.py           # Data model definitions
│   ├── f5_client.py        # F5 API client
│   ├── metrics_collector.py # Metrics collection module
│   ├── score_calculator.py  # Score calculation module
│   └── scheduler.py        # Scheduler core logic
├── api/
│   ├── __init__.py
│   └── server.py           # API server
├── utils/
│   ├── __init__.py
│   ├── logger.py           # Logging utilities
│   └── exceptions.py       # Custom exceptions
├── tests/                  # Test files
├── requirements.txt        # Project dependencies
└── README.md              # Project documentation
```

## Modules Relationships

[Check here](./docs/Module-Relationships.md) for detailed architecture.

## Installation and Deployment

### 1. Environment Requirements

- Python 3.8+
- F5 LTM device access permissions
- Inference engine services (vLLM or SGLang)

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configuration File

Configuration file:

```bash
config/scheduler-config.yaml
```

Edit the configuration file to set F5 connection information and Pool configuration:

```yaml
global:
  interval: 5                    # Configuration hot reload check interval (seconds)
  api_port: 8080                # API service port
  api_host: 0.0.0.0             # API service listening address
  log_level: INFO               # Log level

f5:
  host: 192.168.1.100           # F5 device IP (required)
  port: 443                     # F5 management port
  username: admin               # F5 username
  password_env: F5_PASSWORD     # F5 password environment variable

scheduler:
  pool_fetch_interval: 10       # Pool member fetch interval (seconds)
  metrics_fetch_interval: 3000  # Metrics collection interval (milliseconds)

modes:
  - name: s1                    # Algorithm mode name
    w_a: 0.5                    # Waiting queue weight
    w_b: 0.5                    # Cache usage weight

pools:
  - name: llm-pool-1            # Pool name (required)
    partition: Common           # Partition name
    engine_type: vllm           # Engine type (required)
    metrics:
      schema: http              # Protocol type
      path: /metrics            # Metrics path
      timeout: 4                # Request timeout
```

### 4. Set Environment Variables

```bash
export F5_PASSWORD="your_f5_password"
export METRIC_PWD="your_metrics_password"  # If needed
```

### 5. Start the Scheduler

```bash
python main.py
```

## API Interfaces

### 1. Select Optimal Member

**POST** `/scheduler/select`

**Function**: Select the optimal member based on real-time performance metrics of Pool members

**Request Body**:
```json
{
  "pool_name": "llm-pool-1",
  "partition": "Common", 
  "members": ["10.10.10.10:8001", "10.10.10.10:8002"]
}
```

**Response**:

Successfully selected optimal member:
```
10.10.10.10:8001
```

Unable to select optimal member (Pool doesn't exist, empty member list, all members have Score of 0, etc.):
```
none
```

**Status Codes**:
- `200`: Success (includes both successful selection and unable to select scenarios)
- `400`: Bad request parameters
- `500`: Internal server error

**Common scenarios when unable to select**:
- Pool does not exist in the scheduler
- No intersection between requested member list and actual Pool members
- All candidate members have Score values of 0
- No members in the Pool
- Metrics data collection failure preventing Score calculation

### 2. Get Single Pool Status

**GET** `/pools/{pool_name}/{partition}/status`

**Function**: Get detailed status information for a specific Pool

**Parameters**:
- `pool_name`: Pool name
- `partition`: Partition name

**Response**:
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

### 3. Get All Pools Status

**GET** `/pools/status`

**Function**: Get status information for all Pools

**Response**:
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

### 4. Health Check

**GET** `/health`

**Function**: Check scheduler service health status

**Response**:
```json
{
  "status": "healthy",
  "message": "Scheduler is running normally"
}
```

### 5. Simulate Selection Process

**POST** `/pools/{pool_name}/{partition}/simulate`

**Function**: Simulate multiple selection processes for testing and analysis (test interface)

**Parameters**:
- `pool_name`: Pool name
- `partition`: Partition name
- `iterations`: Number of simulations (query parameter, default 100)

**Request Body**:
```json
{
  "pool_name": "llm-pool-1",
  "partition": "Common",
  "members": ["10.10.10.10:8001", "10.10.10.10:8002"]
}
```

**Response**:
```json
{
  "results": {
    "10.10.10.10:8001": 45,
    "10.10.10.10:8002": 55
  },
  "iterations": 100
}
```

### 6. Advanced Probability Analysis

**POST** `/pools/{pool_name}/{partition}/analyze`

**Function**: Detailed analysis of selection accuracy and probability bias (test interface)

**Parameters**:
- `pool_name`: Pool name
- `partition`: Partition name
- `iterations`: Number of analyses (query parameter, default 1000)

**Request Body**:
```json
{
  "pool_name": "llm-pool-1",
  "partition": "Common",
  "members": ["10.10.10.10:8001", "10.10.10.10:8002"]
}
```

**Response**:
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

## Complete Configuration Documentation

### Global Configuration (global)

| Config Item | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| `interval` | Integer | No | 60 | Configuration file hot reload check interval (seconds) |
| `api_port` | Integer | No | 8080 | API service listening port |
| `api_host` | String | No | "0.0.0.0" | API service listening address (0.0.0.0 means all interfaces) |
| `log_level` | String | No | "INFO" | Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `log_debug` | Boolean | No | false | Backward compatible debug switch (used when log_level is not configured) |

### F5 Configuration (f5)

| Config Item | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| `host` | String | **Yes** | None | F5 device IP address or hostname |
| `port` | Integer | No | 443 | F5 iControl REST API port |
| `username` | String | No | "admin" | F5 device login username. The guest role or high. |
| `password_env` | String | No | None | Environment variable name for F5 password |

### Scheduler Configuration (scheduler)

| Config Item | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| `pool_fetch_interval` | Integer | No | 10 | Interval to fetch Pool members from F5 (seconds) |
| `metrics_fetch_interval` | Integer | No | 1000 | Interval to collect Metrics from inference engines (milliseconds) |

### Algorithm Mode Configuration (modes)

| Config Item | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| `name` | String | No | "s1" | Algorithm mode name (currently only supports s1) |
| `w_a` | Float | No | 0.5 | Waiting queue weight (between 0-1) |
| `w_b` | Float | No | 0.5 | Cache usage weight (between 0-1) |
| `w_g` | Float | No | 0.0 | Reserved weight (currently unused) |

### Pool Configuration (pools)

| Config Item | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| `name` | String | **Yes** | None | Pool name, must match Pool name on F5 |
| `partition` | String | No | "Common" | Partition name on F5 |
| `engine_type` | String | **Yes** | None | Inference engine type (vllm/sglang) |

### Metrics Configuration (pools[].metrics)

| Config Item | Type | Required | Default | Description |
|-------------|------|----------|---------|-------------|
| `schema` | String | No | "http" | Protocol type (http/https) |
| `port` | Integer | No | null | Metrics service port, null means use Pool member's own port |
| `path` | String | No | "/metrics" | URL path for Metrics service |
| `timeout` | Integer | No | 3 | HTTP request timeout (seconds) |
| `APIkey` | String | No | null | API key for Metrics service |
| `metric_user` | String | No | null | Username for Metrics service |
| `metric_pwd_env` | String | No | null | Environment variable name for Metrics service password |

### Configuration Example

```yaml
# Complete configuration example
global:
  interval: 5
  api_port: 8080
  api_host: 0.0.0.0
  log_level: INFO

f5:
  host: 192.168.1.100          # Required: F5 device address
  port: 443
  username: admin
  password_env: F5_PASSWORD

scheduler:
  pool_fetch_interval: 10
  metrics_fetch_interval: 3000

modes:
  - name: s1
    w_a: 0.8 # In practice, w_a has greater impact on TTFT
    w_b: 0.2

pools:
  - name: llm-pool-1           # Required: Pool name
    partition: Common
    engine_type: vllm          # Required: Engine type
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
      port: 9090               # Use unified metrics port
      path: /custom/metrics
      timeout: 5
```

## Algorithm Description

### S1 Algorithm

Score calculation formula:
```
score = w_a × (1 - normalized_waiting_queue) + w_b × (1 - cache_usage)
```

Where:
- `w_a`: Waiting queue weight (usually w_a + w_b = 1)
- `w_b`: Cache usage weight
- `normalized_waiting_queue`: Normalized waiting queue length (0-1)
- `cache_usage`: GPU cache usage ratio (0-1)

Higher Score values indicate better member performance with higher selection probability.

### Weighted Random Selection

Weighted random selection based on each member's Score value:
1. Calculate the sum of all members' Scores
2. Generate a random number between 0 and the total sum
3. Select the corresponding member based on which interval the random number falls into
4. Members with higher Scores occupy larger intervals and have higher selection probability

### Supported Metrics by Inference Engine

**vLLM Engine**:
- `vllm:num_requests_waiting`: Number of requests waiting in queue
- `vllm:gpu_cache_usage_perc`: GPU cache usage percentage

**SGLang Engine**:
- `sglang:num_queue_reqs`: Number of requests in queue
- `sglang:token_usage`: Token cache usage rate

## Runtime Monitoring

### Log Files

The scheduler generates detailed log files `scheduler.log`, including:
- Configuration loading and hot reload records
- Pool member fetch and update records
- Metrics collection status and results
- Score calculation process and results
- API request and response records
- Scheduling selection decision process
- Error and exception information

### Performance Metrics

Through API interfaces you can view:
- Number and status of members in each Pool
- Real-time Metrics data of members
- Score distribution and trend changes
- Selection result statistics and probability analysis
- System runtime health status

### Log Level Description

- **DEBUG**: Shows all detailed information, including detailed process of each selection
- **INFO**: Shows key operations and status changes
- **WARNING**: Shows warning information such as missing configuration, connection issues, etc.
- **ERROR**: Shows error information such as configuration errors, network failures, etc.
- **CRITICAL**: Shows critical errors that may prevent the program from running

## Troubleshooting

### Common Issues

1. **F5 Connection Failure**
   - Check F5 device network connectivity: `ping <f5_host>`
   - Verify username and password are correct
   - Confirm F5 device has iControl REST functionality enabled
   - Check if F5 device ports are open (usually 443 or 8443)

2. **Metrics Collection Failure**
   - Check if inference engine services are running normally
   - Verify Metrics interface configuration is correct
   - Confirm network firewall settings allow access
   - Check inference engine's Metrics port and path

3. **Score Calculation Anomaly**
   - Check if algorithm mode configuration is correct
   - Verify weight parameter settings (w_a + w_b recommended to equal 1)
   - Review Metrics data completeness
   - Confirm inference engine type configuration is correct

4. **Pool Member Fetch Failure**
   - Verify Pool name and Partition match F5 configuration
   - Check Pool status on F5 device
   - Confirm F5 client connection and authentication are normal

### Debug Mode

Enable detailed debug logging:

```yaml
global:
  log_level: DEBUG
```

Or use backward compatible method:

```yaml
global:
  log_debug: true
```

### Health Check

Use health check interface to monitor service status:

```bash
curl http://localhost:8080/health
```

Normal response:
```json
{"status": "healthy", "message": "Scheduler is running normally"}
```

## Development Guide

### Extending Support for New Inference Engines

1. Add new engine type in `core/models.py`:
```python
class EngineType(Enum):
    VLLM = "vllm"
    SGLANG = "sglang"
    NEW_ENGINE = "new_engine"  # Add new engine
```

2. Define key metrics in `ENGINE_METRICS`:
```python
ENGINE_METRICS = {
    EngineType.NEW_ENGINE: {
        "waiting_queue": "new_engine:queue_length",
        "cache_usage": "new_engine:cache_usage"
    }
}
```

3. Update parsing logic in `metrics_collector.py` (if metric format is different)

### Implementing New Scheduling Algorithms

1. Add new mode in configuration:
```yaml
modes:
  - name: s2
    w_a: 0.4
    w_b: 0.3
    w_g: 0.3
```

2. Implement algorithm logic in `core/score_calculator.py`:
```python
def _s2_algorithm(self, member: PoolMember, mode: ModeConfig) -> float:
    # Implement S2 algorithm
    pass
```

### Adding New API Interfaces

1. Add new route handler functions in `api/server.py`
2. Implement corresponding business logic in `core/scheduler.py`
3. Update API documentation

## License

This project is for internal use, please comply with relevant usage terms. 