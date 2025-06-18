import requests
import time
from collections import defaultdict
import sys

def send_request():
    url = "http://localhost:8080/scheduler/select"
    headers = {"Content-Type": "application/json"}
    data = {
        "pool_name": "example_pool1",
        "partition": "Common",
        "members": ["127.0.0.1:8001", "127.0.0.1:8002", "127.0.0.1:8003"]
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            # New plain text response format
            selected_member = response.text.strip()
            if selected_member and selected_member != "none":
                return selected_member
            else:
                return "none_response"
        else:
            return f"error_{response.status_code}"
    except Exception as e:
        return f"exception_{str(e)}"

def run_test(duration_sec=5):
    results = defaultdict(int)
    total_requests = 0
    success_requests = 0
    failed_requests = 0
    end_time = time.time() + duration_sec
    
    print(f"\nStarting test for {duration_sec} seconds...")
    
    while time.time() < end_time:
        result = send_request()
        results[result] += 1
        total_requests += 1
        
        if result.startswith("127.0.0.1"):
            success_requests += 1
        else:
            failed_requests += 1
        
        # Add a small delay to avoid excessive CPU usage
        #time.sleep(0.01)
    
    print("\nTest results statistics:")
    print("---------------------")
    print(f"Total requests: {total_requests}")
    print(f"Successful requests: {success_requests}")
    print(f"Failed requests: {failed_requests}")
    print("----Member selection probability----")
    
    if success_requests > 0:
        for member in ["127.0.0.1:8001", "127.0.0.1:8002", "127.0.0.1:8003"]:
            count = results.get(member, 0)
            percentage = (count / success_requests) * 100
            print(f"{member},{percentage:.1f}%")
    
    # Print error statistics
    error_items = {k: v for k, v in results.items() if not k.startswith("127.0.0.1")}
    if error_items:
        print("----Error statistics----")
        for error, count in error_items.items():
            percentage = (count / total_requests) * 100
            print(f"{error},{percentage:.1f}%")
    
    print("---------------------")

def main():
    while True:
        run_test()
        
        while True:
            user_input = input("\nContinue testing? (y/n): ").strip().lower()
            if user_input in ('y', 'n'):
                break
            print("Please enter 'y' or 'n'.")
        
        if user_input == 'n':
            print("Program exit.")
            break

if __name__ == "__main__":
    main()