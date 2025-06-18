import subprocess
import time

processes = []

def start_service(script):
    p = subprocess.Popen(["python3", script])
    processes.append(p)

if __name__ == "__main__":
    start_service("app_sglang.py")
    time.sleep(1)  # 给每个服务一点启动时间
    start_service("app_sglang2.py")
    time.sleep(1)  # 给每个服务一点启动时间
    start_service("app_sglang3.py")

    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        print("Shutting down...")
        for p in processes:
            p.terminate()
