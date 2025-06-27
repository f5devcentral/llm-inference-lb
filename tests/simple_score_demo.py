#!/usr/bin/env python3
"""
简化的Score区分度演示
"""

def min_max_normalize(values):
    if not values or len(values) == 1:
        return [0.0] * len(values)
    
    min_val = min(values)
    max_val = max(values)
    
    if max_val == min_val:
        return [0.0] * len(values)
    
    return [(val - min_val) / (max_val - min_val) for val in values]

def demo_score_algorithms():
    print("Score算法区分度演示")
    print("="*50)
    
    # 您的实际数据
    waiting_queue_values = [0.0, 0.0]  # 两台机器等待队列都是0
    cache_usage_values = [0.118, 0.009]  # cache使用率差异
    running_req_values = [2.0, 1.5]  # 运行请求数
    
    print("原始指标:")
    print(f"Member 1: waiting={waiting_queue_values[0]:.3f}, cache={cache_usage_values[0]:.3f}, running={running_req_values[0]:.3f}")
    print(f"Member 2: waiting={waiting_queue_values[1]:.3f}, cache={cache_usage_values[1]:.3f}, running={running_req_values[1]:.3f}")
    print()
    
    # 当前S2算法 (w_a=0.6, w_b=0.2, w_g=0.2)
    print("1. 当前S2算法 (w_a=0.6, w_b=0.2, w_g=0.2)")
    normalized_waiting = min_max_normalize(waiting_queue_values)  # [0.0, 0.0]
    normalized_running = min_max_normalize(running_req_values)   # [1.0, 0.0]
    
    scores = []
    for i in range(2):
        score = (
            0.6 * (1.0 - normalized_waiting[i]) +
            0.2 * (1.0 - cache_usage_values[i]) +
            0.2 * (1.0 - normalized_running[i])
        )
        scores.append(score)
    
    print(f"  Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
    print(f"  绝对差异: {abs(scores[0] - scores[1]):.6f}")
    print()
    
    # S2增强算法 - cache也归一化
    print("2. S2增强算法 - cache归一化 (w_a=0.6, w_b=0.2, w_g=0.2)")
    normalized_cache = min_max_normalize(cache_usage_values)  # [1.0, 0.0]
    
    scores = []
    for i in range(2):
        score = (
            0.6 * (1.0 - normalized_waiting[i]) +
            0.2 * (1.0 - normalized_cache[i]) +
            0.2 * (1.0 - normalized_running[i])
        )
        scores.append(score)
    
    print(f"  Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
    print(f"  绝对差异: {abs(scores[0] - scores[1]):.6f}")
    print()
    
    # 提高cache权重
    print("3. 提高cache权重 - cache归一化 (w_a=0.4, w_b=0.4, w_g=0.2)")
    scores = []
    for i in range(2):
        score = (
            0.4 * (1.0 - normalized_waiting[i]) +
            0.4 * (1.0 - normalized_cache[i]) +
            0.2 * (1.0 - normalized_running[i])
        )
        scores.append(score)
    
    print(f"  Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
    print(f"  绝对差异: {abs(scores[0] - scores[1]):.6f}")
    print()
    
    # 非线性增强
    print("4. 非线性算法 - 指数放大 (exp_factor=2.0)")
    exp_factor = 2.0
    scores = []
    for i in range(2):
        score = (
            0.4 * ((1.0 - normalized_waiting[i]) ** exp_factor) +
            0.4 * ((1.0 - normalized_cache[i]) ** exp_factor) +
            0.2 * ((1.0 - normalized_running[i]) ** exp_factor)
        )
        scores.append(score)
    
    print(f"  Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
    print(f"  绝对差异: {abs(scores[0] - scores[1]):.6f}")
    print()
    
    # 极端情况测试
    print("5. 极端cache权重测试 (w_a=0.2, w_b=0.6, w_g=0.2)")
    scores = []
    for i in range(2):
        score = (
            0.2 * (1.0 - normalized_waiting[i]) +
            0.6 * (1.0 - normalized_cache[i]) +
            0.2 * (1.0 - normalized_running[i])
        )
        scores.append(score)
    
    print(f"  Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
    print(f"  绝对差异: {abs(scores[0] - scores[1]):.6f}")
    print()
    
    print("总结:")
    print("- 对cache_usage进行归一化可以显著放大差异")
    print("- 提高cache权重可以进一步增强区分度") 
    print("- 非线性变换可以更好地突出性能差异")
    print("- 建议使用S2增强算法并调整权重配置")

if __name__ == "__main__":
    demo_score_algorithms() 