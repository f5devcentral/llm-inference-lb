import requests
import time
from collections import Counter, defaultdict

SELECT_URL = "http://localhost:8080/scheduler/select"
STATUS_URL = "http://127.0.0.1:8080/pools/status"
TRIGGER_URLS = [
    "http://localhost:8001/trigger_update",
    "http://localhost:8002/trigger_update",
    "http://localhost:8003/trigger_update"
]

HEADERS = {"Content-Type": "application/json"}
POOL_REQUEST_PAYLOAD = {
    "pool_name": "example_pool1",
    "partition": "Common",
    "members": ["127.0.0.1:8001", "127.0.0.1:8002", "127.0.0.1:8003"]
}
MEMBERS = POOL_REQUEST_PAYLOAD["members"]

# Data structures for overall statistics
history_selection = defaultdict(list)  # Selection probability for each member per round
history_percent = defaultdict(list)    # Status percent for each member per round

def run_scheduler_test(num_requests=1000):
    counter = Counter()
    success = 0
    fail = 0

    for _ in range(num_requests):
        try:
            response = requests.post(SELECT_URL, headers=HEADERS, json=POOL_REQUEST_PAYLOAD, timeout=3)
            if response.status_code == 200:
                # New plain text response format
                selected = response.text.strip()
                if selected in MEMBERS:
                    counter[selected] += 1
                    success += 1
                else:
                    fail += 1
            else:
                fail += 1
        except Exception:
            fail += 1

    return counter, success, fail

def get_status_percent():
    try:
        response = requests.get(STATUS_URL, timeout=3)
        if response.status_code == 200:
            data = response.json()
            for pool in data.get("pools", []):
                if pool.get("name") == "example_pool1":
                    member_percents = {}
                    for m in pool.get("members", []):
                        addr = f"{m['ip']}:{m['port']}"
                        percent = m.get("percent", 0.0)
                        member_percents[addr] = percent
                    return member_percents
    except Exception:
        pass
    return {}

def print_round_report(counter, success, fail, percent_from_status, total):
    print("Test results statistics:")
    print("---------------------")
    print(f"Total requests: {total}")
    print(f"Successful requests: {success}")
    print(f"Failed requests: {fail}")
    print("#First column is member, second column is selection probability, third column is percent field from /pools/status interface")
    print("----Member selection probability and score distribution probability----")
    for member in MEMBERS:
        picked_percent = (counter[member] / total) * 100 if total else 0
        status_percent = percent_from_status.get(member, 0.0)
        print(f"{member},{picked_percent:.2f}%,{status_percent:.2f}%")
    print("--------------------------------------------")

def trigger_metrics_update():
    all_success = True
    for url in TRIGGER_URLS:
        try:
            response = requests.post(url, timeout=3)
            if response.status_code != 200:
                all_success = False
                print(f"[Error] Request {url} returned status code: {response.status_code}")
                try:
                    print("Response content:", response.json())
                except Exception:
                    print("Response content is not JSON format:", response.text)
            else:
                json_data = response.json()
                if json_data.get("status") != "Metrics updated immediately":
                    all_success = False
                    print(f"[Error] Request {url} response content abnormal: {json_data}")
        except Exception as e:
            all_success = False
            print(f"[Error] Request {url} failed, exception: {e}")
    return all_success


def print_final_summary():
    print("\n======== Overall Test Statistics Report (All Rounds) ========")
    for member in MEMBERS:
        print(f"\n{member}")
        print("-------------------------")
        print("Selection Probability\tLLM Workload Distribution")
        for sel, perc in zip(history_selection[member], history_percent[member]):
            print(f"{sel:.2f}%\t{perc:.2f}%")
    print("--------------------------------------------\n")


import matplotlib.pyplot as plt
import seaborn as sns

def draw_visual_charts():
    print("\nGenerating visualization charts, please wait...")

    sns.set(style="whitegrid")
    for member in MEMBERS:
        rounds = list(range(1, len(history_selection[member]) + 1))
        sel_values = history_selection[member]
        percent_values = history_percent[member]

        plt.figure(figsize=(10, 5))
        plt.plot(rounds, sel_values, marker='o', label="selective probability", linewidth=2)
        plt.plot(rounds, percent_values, marker='s', label="LLM workload distribution", linewidth=2)

        plt.title(f"{member}: selective probability vs. LLM workload distribution")
        plt.xlabel("Rounds")
        plt.ylabel("Percentage (%)")
        plt.xticks(rounds)
        plt.ylim(0, 100)
        plt.legend()
        plt.grid(True)
        plt.tight_layout()

        # Optional: save as file, or display directly
        plt.savefig(f"{member.replace(':', '_')}_trend.png")
        plt.show()  # If running locally, you can also uncomment to view in real time

    print("Charts generated, files saved in current directory.")


def main():
    try:
        loop_times = int(input("Enter the number of loops: "))
    except ValueError:
        print("Please enter a valid number")
        return

    for i in range(loop_times):
        print(f"\n=== Round {i+1} test begins ===")
        counter, success, fail = run_scheduler_test()
        status_percent = get_status_percent()

        # Record current round data
        total = 1000
        for member in MEMBERS:
            picked_percent = (counter[member] / total) * 100 if total else 0
            status_val = status_percent.get(member, 0.0)
            history_selection[member].append(picked_percent)
            history_percent[member].append(status_val)

        # Display current round test report
        print_round_report(counter, success, fail, status_percent, total)

        print("Pausing 1 second, preparing to trigger metrics update...")
        time.sleep(1)

        if trigger_metrics_update():
            print("All metrics update requests executed successfully. Delaying 2 second for make sure metrics are fetched and updated.")
            time.sleep(2)
        else:
            print("Some metrics update requests failed, please check service status.")

    # Output summary table after all rounds completed
    print_final_summary()

     # Draw line charts
    draw_visual_charts()

if __name__ == "__main__":
    main()
