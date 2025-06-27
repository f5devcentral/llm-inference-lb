# Docker Run Examples

## 🚀 Production Deployment (Recommended)

### Standard Output Logging - Simplest Approach
```bash
# Run container with stdout logging (recommended)
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
  f5-scheduler:latest #container image Will be provided by offline. Here is just an example.

# View logs
docker logs -f f5-scheduler

# Export logs
docker logs f5-scheduler > scheduler-$(date +%Y%m%d).log
```

### File Logging Mode (If Host Persistence Required)
```bash
# Run container with file logging
docker run -d \
  --name f5-scheduler-file \
  -p 8080:8080 \
  -v $(pwd)/config/scheduler-config.yaml:/app/config/scheduler-config.yaml:ro \
  -v $(pwd)/logs:/app/logs \
  -e F5_PASSWORD=your-password \
  -e METRIC_PWD=your-metric-password \
  -e LOG_TO_STDOUT=false \
  -e LOG_FILE_PATH=/app/logs/scheduler.log \
  --restart unless-stopped \
  f5-scheduler:latest

# View log file
tail -f logs/scheduler.log
```

## 🔧 Development Environment

### Development Version (Simplified Configuration)
```bash
# Run development container
docker run -d \
  --name f5-scheduler-dev \
  -p 8080:8080 \
  -v $(pwd)/config/scheduler-config.yaml:/app/config/scheduler-config.yaml:ro \
  -e F5_PASSWORD=dev-password \
  -e METRIC_PWD=dev-metric-pwd \
  -e LOG_TO_STDOUT=true \
  f5-scheduler:dev
```

## 📋 Environment Variables Reference

### Required Variables
```bash
-e F5_PASSWORD="your-f5-password"     # F5 device password
```

### Optional Variables
```bash
-e METRIC_PWD="your-metric-password"  # Metrics service password (optional)
-e LOG_TO_STDOUT="true"               # Log output method (default: true)
-e LOG_FILE_PATH="/app/logs/scheduler.log"  # Log file path (only when LOG_TO_STDOUT=false)
```

## 🔍 Container Management

### View Container Status
```bash
docker ps -a | grep f5-scheduler
```

### View Container Logs
```bash
# Real-time logs
docker logs -f f5-scheduler

# Last 100 lines
docker logs --tail 100 f5-scheduler

# Logs with timestamps
docker logs -t f5-scheduler
```

### Container Operations
```bash
# Stop container
docker stop f5-scheduler

# Restart container
docker restart f5-scheduler

# Remove container
docker stop f5-scheduler && docker rm f5-scheduler
```

## 🔧 Configuration Validation

### Check Environment Variables
```bash
docker inspect f5-scheduler | grep -A 10 "Env"
```

### Verify Mount Points
```bash
docker inspect f5-scheduler | grep -A 10 "Mounts"
```

### Test Configuration
```bash
# Health check
curl http://localhost:8080/health

# Expected response
{"status": "healthy", "message": "Scheduler is running normally"}
```

## 🎯 Best Practices

### 1. Logging Configuration
- **Production**: Use `LOG_TO_STDOUT=true` with log aggregation systems
- **Development**: Use `LOG_TO_STDOUT=true` for simplicity
- **Legacy Systems**: Use `LOG_TO_STDOUT=false` only if required

### 2. Security
- Use Docker Secrets or environment files for sensitive data
- Never hardcode passwords in commands

### 3. Resource Management
- Set appropriate log rotation limits (`--log-opt max-size`, `--log-opt max-file`)
- Use `--restart unless-stopped` for production deployments

### 4. Monitoring
- Implement health checks in orchestration systems
- Monitor container resource usage
- Set up log-based alerting

## ⚠️ Troubleshooting

### Common Issues

#### Container Fails to Start
```bash
# Check container logs
docker logs container-name

# Common causes:
# - Missing required environment variables
# - Configuration file not properly mounted
# - Log directory permission issues
```

#### Log Configuration Problems
```bash
# Verify environment variables
docker inspect container-name | grep LOG_TO_STDOUT

# Check file permissions
ls -la config/scheduler-config.yaml
ls -la logs/
```

#### Permission Issues
```bash
# Fix configuration file permissions
chmod 644 config/scheduler-config.yaml

# Fix log directory permissions
chmod 755 logs/
```
