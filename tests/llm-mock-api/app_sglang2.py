from fastapi import FastAPI, Response
import uvicorn
import random
import threading
import time

app_sglang2 = FastAPI()

# 动态更新开关：True 启用；False 保持固定
DYNAMIC_UPDATE_ENABLED = True

# 初始指标值（可动态更新）
metrics = {
    "num_requests_waiting": 100.0,
    "gpu_cache_usage_perc": 0.4
}

# 后台线程：每隔 1~10 秒更新一次指标值
def update_metrics():
    while True:
        if DYNAMIC_UPDATE_ENABLED:
            metrics["num_requests_waiting"] = round(random.uniform(100.0, 1000.0), 1)
            metrics["gpu_cache_usage_perc"] = round(random.uniform(0.4, 1.0), 2)
            #time.sleep(random.randint(1, 10))
            time.sleep(300)
        else:
            time.sleep(1)

# 启动后台线程（守护模式）
threading.Thread(target=update_metrics, daemon=True).start()

@app_sglang2.get("/metrics")
def get_sglang_metrics():
    content = f"""
# HELP sglang:num_queue_reqs The number of requests in the waiting queue
# TYPE sglang:num_queue_reqs gauge
sglang:num_queue_reqs{{model_name="meta-llama/Llama-3.1-8B-Instruct"}} {metrics["num_requests_waiting"]}
# HELP sglang:token_usage The token usage
# TYPE sglang:token_usage gauge
sglang:token_usage{{model_name="meta-llama/Llama-3.1-8B-Instruct"}} {metrics["gpu_cache_usage_perc"]}
""".strip()
    return Response(content=content, media_type="text/plain")


@app_sglang2.post("/toggle_update/{state}")
def toggle_update(state: int):
    global DYNAMIC_UPDATE_ENABLED
    DYNAMIC_UPDATE_ENABLED = bool(state)
    return {"dynamic_update": DYNAMIC_UPDATE_ENABLED}

if __name__ == "__main__":
    uvicorn.run("app_sglang2:app_sglang2", host="0.0.0.0", port=8012, reload=True)
