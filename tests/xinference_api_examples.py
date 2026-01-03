#!/usr/bin/env python3
"""
XInference API Usage Examples
Demonstrates how to use the enhanced API with XInference support
"""

import requests
import json

# API Base URL
API_BASE = "http://localhost:8080"

def example_xinference_request():
    """Example: XInference pool request with model parameter"""
    print("🔥 XInference API Request Example")
    
    # XInference request payload (model parameter is required)
    xinference_payload = {
        "pool_name": "xinference-pool-1",
        "partition": "Common",
        "model": "qwen-7b-chat",  # Required for XInference
        "members": ["192.168.1.100:8001", "192.168.1.101:8002", "192.168.1.102:8003"]
    }
    
    print(f"📝 Request payload:")
    print(json.dumps(xinference_payload, indent=2))
    
    try:
        response = requests.post(f"{API_BASE}/scheduler/select", json=xinference_payload)
        print(f"📊 Response status: {response.status_code}")
        print(f"🎯 Selected member: {response.text}")
        
        # Possible responses:
        # - "192.168.1.100:8001" (selected member with the best score for this model)
        # - "fallback" (if pool_fallback is enabled)
        # - "no_the_model_name" (if no member has the requested model)
        # - "request_has_no_model_name" (if model field is missing in request)
        # - "none" (if other errors occur)
        
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")

def example_vllm_request():
    """Example: Regular vLLM request (backward compatible)"""
    print("🔥 vLLM API Request Example (Backward Compatible)")
    
    # vLLM request payload (model parameter is optional and ignored)
    vllm_payload = {
        "pool_name": "vllm-pool-1", 
        "partition": "Common",
        "members": ["192.168.1.200:8001", "192.168.1.201:8002"]
        # No model parameter needed for vLLM/SGLang
    }
    
    print(f"📝 Request payload:")
    print(json.dumps(vllm_payload, indent=2))
    
    try:
        response = requests.post(f"{API_BASE}/scheduler/select", json=vllm_payload)
        print(f"📊 Response status: {response.status_code}")
        print(f"🎯 Selected member: {response.text}")
        
    except requests.RequestException as e:
        print(f"❌ Request failed: {e}")

def example_xinference_simulation():
    """Example: XInference simulation testing"""
    print("🔥 XInference Simulation Example")
    
    simulation_payload = {
        "pool_name": "xinference-pool-1",
        "partition": "Common", 
        "model": "qwen-7b-chat",
        "members": ["192.168.1.100:8001", "192.168.1.101:8002"]
    }
    
    # Run 100 simulations to test selection distribution
    try:
        response = requests.post(
            f"{API_BASE}/pools/xinference-pool-1/Common/simulate?iterations=100",
            json=simulation_payload
        )
        
        print(f"📊 Response status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"🎯 Simulation results ({result['iterations']} iterations):")
            for member, count in result['results'].items():
                percentage = (count / result['iterations']) * 100
                print(f"   {member}: {count} times ({percentage:.1f}%)")
        
    except requests.RequestException as e:
        print(f"❌ Simulation failed: {e}")

def example_error_handling():
    """Example: Error handling scenarios"""
    print("🔥 Error Handling Examples")
    
    # 1. XInference without model parameter
    print("❌ Testing XInference without model parameter...")
    invalid_payload = {
        "pool_name": "xinference-pool-1",
        "partition": "Common",
        "members": ["192.168.1.100:8001"]
        # Missing required model parameter
    }
    
    try:
        response = requests.post(f"{API_BASE}/scheduler/select", json=invalid_payload)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        # Should return 400 Bad Request
        
    except requests.RequestException as e:
        print(f"   Request exception: {e}")
    
    # 2. Non-existent pool
    print("❌ Testing non-existent pool...")
    nonexistent_payload = {
        "pool_name": "non-existent-pool",
        "partition": "Common",
        "model": "any-model",
        "members": ["192.168.1.100:8001"]
    }
    
    try:
        response = requests.post(f"{API_BASE}/scheduler/select", json=nonexistent_payload)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        # Should return "none"
        
    except requests.RequestException as e:
        print(f"   Request exception: {e}")

def example_pool_status():
    """Example: Get pool status for XInference"""
    print("🔥 XInference Pool Status Example")
    
    try:
        # Get specific pool status
        response = requests.get(f"{API_BASE}/pools/xinference-pool-1/Common/status")
        print(f"📊 Response status: {response.status_code}")
        
        if response.status_code == 200:
            status = response.json()
            print(f"🏊 Pool: {status['name']} ({status['engine_type']})")
            print(f"   Members: {status['member_count']}")
            for member in status['members']:
                print(f"   📍 {member['ip']}:{member['port']} - Score: {member['score']:.3f}")
                # For XInference, metrics will show model-level data
                if member['metrics']:
                    print(f"      Metrics: {member['metrics']}")
        
        # Get all pools status
        response_all = requests.get(f"{API_BASE}/pools/status")
        if response_all.status_code == 200:
            all_pools = response_all.json()
            print(f"🌊 Total pools: {len(all_pools['pools'])}")
            for pool in all_pools['pools']:
                print(f"   - {pool['name']} ({pool['engine_type']}): {pool['member_count']} members")
        
    except requests.RequestException as e:
        print(f"❌ Status request failed: {e}")

def main():
    """Run all examples"""
    print("🚀 XInference API Usage Examples")
    print("=" * 60)
    print("⚠️  Note: These examples assume the scheduler is running on localhost:8080")
    print("⚠️  Make sure to configure your F5 and XInference endpoints correctly")
    print()
    
    try:
        example_xinference_request()
        print()
        example_vllm_request()
        print()
        example_xinference_simulation()
        print()
        example_error_handling()
        print()
        example_pool_status()
        
    except Exception as e:
        print(f"❌ Example execution failed: {e}")
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 60)
    print("📚 Key Points for XInference Integration:")
    print("   ✅ XInference pools require 'model' parameter in API requests")
    print("   ✅ vLLM/SGLang pools work as before (model parameter ignored)")
    print("   ✅ XInference uses throughput_utilization directly (no algorithm weights)")
    print("   ✅ XInference ignores member threshold filtering")
    print("   ✅ Each model maintains separate scores (no averaging)")
    print("   ✅ Returns 'no_the_model_name' when requested model not found")
    print("   ✅ Returns 'request_has_no_model_name' when model field is missing")
    print("   ✅ Higher utilization = lower score = less likely to be selected")
    print("   ✅ All existing APIs are backward compatible")

if __name__ == "__main__":
    main()
