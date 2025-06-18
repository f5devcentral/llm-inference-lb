from fastapi import FastAPI, Response
import uvicorn
import random
import threading
import time

app_vllm3 = FastAPI()

# 动态更新开关：True 启用；False 保持固定
DYNAMIC_UPDATE_ENABLED = True

# 初始指标值（可动态更新）
metrics = {
    "num_requests_waiting": 2000.0,
    "gpu_cache_usage_perc": 0.6
}

def update_metrics_once():
    """执行单次指标更新"""
    metrics["num_requests_waiting"] = round(random.uniform(2000.0, 5000.0), 1)
    metrics["gpu_cache_usage_perc"] = round(random.uniform(0.6, 1.0), 2)
# 后台线程：每隔 1~10 秒更新一次指标值
def update_metrics():
    while True:
        if DYNAMIC_UPDATE_ENABLED:
            update_metrics_once()  # 使用独立函数
            #time.sleep(random.randint(1, 10))
            time.sleep(600)
        else:
            time.sleep(1)

# 启动后台线程（守护模式）
threading.Thread(target=update_metrics, daemon=True).start()

@app_vllm3.get("/metrics")
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


@app_vllm3.post("/trigger_update")
def trigger_update():
    """手动触发立即更新"""
    update_metrics_once()
    return {"status": "Metrics updated immediately"}
# 设置动态更新开关的接口：POST /toggle_update/1 或 /toggle_update/0
@app_vllm3.post("/toggle_update/{state}")
def toggle_update(state: int):
    global DYNAMIC_UPDATE_ENABLED
    DYNAMIC_UPDATE_ENABLED = bool(state)
    return {"dynamic_update": DYNAMIC_UPDATE_ENABLED}

if __name__ == "__main__":
    uvicorn.run("app_vllm3:app_vllm3", host="0.0.0.0", port=8003, reload=True)
