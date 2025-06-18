from fastapi import FastAPI, Response
import uvicorn
import random
import threading
import time

app_vllm = FastAPI()

# 动态更新开关：True 启用；False 保持固定
# The switch, control dynamic value of metrics
DYNAMIC_UPDATE_ENABLED = True

# 初始指标值（可动态更新）
# initial metrics value
metrics = {
    "num_requests_waiting": 12.0,
    "gpu_cache_usage_perc": 0.1
}

def update_metrics_once():
    metrics["num_requests_waiting"] = round(random.uniform(5.0, 2000.0), 1)
    metrics["gpu_cache_usage_perc"] = round(random.uniform(0.0, 1.0), 2)
# Regually change metrics value according the time sleep
# Or actively change metrics value if triggered by the API  /trigger_update
def update_metrics():
    while True:
        if DYNAMIC_UPDATE_ENABLED:
            update_metrics_once()
            #time.sleep(random.randint(1, 10))
            time.sleep(600)
        else:
            time.sleep(1)

# 启动后台线程（守护模式）
# Start the background thread (daemon mode)
threading.Thread(target=update_metrics, daemon=True).start()

@app_vllm.get("/metrics")
def get_metrics():
    content = f"""
# HELP vllm:num_requests_waiting Number of requests waiting to be processed.
# TYPE vllm:num_requests_waiting gauge
vllm:num_requests_waiting{{model_name="xxx"}} {metrics["num_requests_waiting"]}
# HELP vllm:gpu_cache_usage_perc GPU KV-cache usage.
# TYPE vllm:gpu_cache_usage_perc gauge
vllm:gpu_cache_usage_perc{{model_name="xxx"}} {metrics["gpu_cache_usage_perc"]}
""".strip()
    return Response(content=content, media_type="text/plain")

@app_vllm.post("/trigger_update")
def trigger_update():
    """手动触发立即更新 Manually trigger"""
    update_metrics_once()
    return {"status": "Metrics updated immediately"}

# 设置动态更新开关的接口：POST /toggle_update/1 或 /toggle_update/0
# The API that to set DYNAMIC_UPDATE_ENABLED switch
@app_vllm.post("/toggle_update/{state}")
def toggle_update(state: int):
    global DYNAMIC_UPDATE_ENABLED
    DYNAMIC_UPDATE_ENABLED = bool(state)
    return {"dynamic_update": DYNAMIC_UPDATE_ENABLED}

if __name__ == "__main__":
    uvicorn.run("app_vllm:app_vllm", host="0.0.0.0", port=8001, reload=True)
