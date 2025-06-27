#!/usr/bin/env python3
"""
S1算法区分度改进演示
基于用户实际配置：S1算法，w_a=0.2, w_b=0.8
"""

def min_max_normalize(values):
    if not values or len(values) == 1:
        return [0.0] * len(values)
    
    min_val = min(values)
    max_val = max(values)
    
    if max_val == min_val:
        return [0.0] * len(values)
    
    return [(val - min_val) / (max_val - min_val) for val in values]

def demo_s1_improvements():
    print("S1算法区分度改进演示")
    print("="*60)
    print("基于您的实际配置：S1算法，w_a=0.2, w_b=0.8")
    print()
    
    # 您的实际数据
    waiting_queue_values = [0.0, 0.0]  # 两台机器等待队列都是0
    cache_usage_values = [0.118, 0.009]  # cache使用率差异
    
    print("原始指标:")
    print(f"Member 1 (10.0.20.128): waiting={waiting_queue_values[0]:.3f}, cache={cache_usage_values[0]:.3f}")
    print(f"Member 2 (10.0.20.133): waiting={waiting_queue_values[1]:.3f}, cache={cache_usage_values[1]:.3f}")
    print(f"Cache差异: {cache_usage_values[0] - cache_usage_values[1]:.3f}")
    print()
    
    # 1. 当前S1算法
    print("1. 当前S1算法 (w_a=0.2, w_b=0.8)")
    print("   公式: score = w_a × (1 - normalized_waiting) + w_b × (1 - cache_usage)")
    
    normalized_waiting = min_max_normalize(waiting_queue_values)  # [0.0, 0.0]
    print(f"   normalized_waiting: {normalized_waiting}")
    print(f"   cache_usage直接使用: {cache_usage_values}")
    
    scores = []
    for i in range(2):
        score = (
            0.2 * (1.0 - normalized_waiting[i]) +
            0.8 * (1.0 - cache_usage_values[i])
        )
        scores.append(score)
    
    print(f"   详细计算:")
    print(f"     Member 1: 0.2×(1-0.0) + 0.8×(1-0.118) = 0.2 + 0.8×0.882 = 0.2 + 0.706 = {scores[0]:.6f}")
    print(f"     Member 2: 0.2×(1-0.0) + 0.8×(1-0.009) = 0.2 + 0.8×0.991 = 0.2 + 0.793 = {scores[1]:.6f}")
    print(f"   Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
    print(f"   绝对差异: {abs(scores[0] - scores[1]):.6f}")
    print(f"   比值: {max(scores)/min(scores):.3f}")
    print()
    
    # 2. S1增强算法 - cache归一化
    print("2. S1增强算法 - cache归一化 (w_a=0.2, w_b=0.8)")
    print("   改进: 对cache_usage也进行归一化处理")
    
    normalized_cache = min_max_normalize(cache_usage_values)  # [1.0, 0.0]
    print(f"   normalized_cache: {normalized_cache}")
    
    scores = []
    for i in range(2):
        score = (
            0.2 * (1.0 - normalized_waiting[i]) +
            0.8 * (1.0 - normalized_cache[i])
        )
        scores.append(score)
    
    print(f"   详细计算:")
    print(f"     Member 1: 0.2×(1-0.0) + 0.8×(1-1.0) = 0.2 + 0.8×0.0 = 0.2 + 0.0 = {scores[0]:.6f}")
    print(f"     Member 2: 0.2×(1-0.0) + 0.8×(1-0.0) = 0.2 + 0.8×1.0 = 0.2 + 0.8 = {scores[1]:.6f}")
    print(f"   Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
    print(f"   绝对差异: {abs(scores[0] - scores[1]):.6f}")
    print(f"   比值: {max(scores)/min(scores):.3f}")
    print(f"   相比原算法差异提升: {abs(scores[0] - scores[1]) / 0.087:.1f}倍")
    print()
    
    # 3. 非线性增强
    print("3. S1非线性增强算法 (指数因子=2.0)")
    print("   进一步改进: 使用平方函数放大差异")
    
    exp_factor = 2.0
    scores = []
    for i in range(2):
        score = (
            0.2 * ((1.0 - normalized_waiting[i]) ** exp_factor) +
            0.8 * ((1.0 - normalized_cache[i]) ** exp_factor)
        )
        scores.append(score)
    
    print(f"   详细计算:")
    print(f"     Member 1: 0.2×(1-0.0)² + 0.8×(1-1.0)² = 0.2×1.0 + 0.8×0.0 = {scores[0]:.6f}")
    print(f"     Member 2: 0.2×(1-0.0)² + 0.8×(1-0.0)² = 0.2×1.0 + 0.8×1.0 = {scores[1]:.6f}")
    print(f"   Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
    print(f"   绝对差异: {abs(scores[0] - scores[1]):.6f}")
    print(f"   比值: {max(scores)/min(scores):.3f}")
    print()
    
    # 4. 权重调整建议
    print("4. 权重调整建议")
    print("   在cache归一化基础上，可以进一步优化权重配置")
    print()
    
    weight_configs = [
        (0.2, 0.8, "原始权重"),
        (0.1, 0.9, "进一步提高cache权重"),
        (0.0, 1.0, "完全依赖cache"),
    ]
    
    for w_a, w_b, desc in weight_configs:
        scores = []
        for i in range(2):
            score = (
                w_a * (1.0 - normalized_waiting[i]) +
                w_b * (1.0 - normalized_cache[i])
            )
            scores.append(score)
        
        diff = abs(scores[0] - scores[1])
        ratio = max(scores) / min(scores) if min(scores) > 0 else float('inf')
        
        print(f"   {desc} (w_a={w_a}, w_b={w_b}): 差异={diff:.6f}, 比值={ratio:.3f}")
    
    print()
    print("=" * 60)
    print("总结和建议:")
    print("1. 核心问题: cache_usage没有归一化，导致0.118 vs 0.009的差异被稀释")
    print("2. 最佳方案: 使用S1增强算法，对cache_usage归一化")
    print("3. 效果提升: 差异从0.087提升到0.8，提升约9.2倍")
    print("4. 配置建议: 使用s1_enhanced模式，保持当前权重w_a=0.2, w_b=0.8")
    print("5. 实施方式: 只需修改配置文件中的mode名称即可")

def demo_percentage_impact():
    print("\n\n加权随机选择概率影响分析")
    print("=" * 50)
    
    # 原始S1算法的score
    original_scores = [0.906, 0.993]
    original_total = sum(original_scores)
    
    print("原始S1算法:")
    print(f"  Member 1: score={original_scores[0]:.3f}, 选择概率={(original_scores[0]/original_total)*100:.1f}%")
    print(f"  Member 2: score={original_scores[1]:.3f}, 选择概率={(original_scores[1]/original_total)*100:.1f}%")
    print(f"  概率比: {(original_scores[1]/original_total)/(original_scores[0]/original_total):.2f}:1")
    print()
    
    # S1增强算法的score
    enhanced_scores = [0.2, 1.0]
    enhanced_total = sum(enhanced_scores)
    
    print("S1增强算法:")
    print(f"  Member 1: score={enhanced_scores[0]:.3f}, 选择概率={(enhanced_scores[0]/enhanced_total)*100:.1f}%")
    print(f"  Member 2: score={enhanced_scores[1]:.3f}, 选择概率={(enhanced_scores[1]/enhanced_total)*100:.1f}%")
    print(f"  概率比: {(enhanced_scores[1]/enhanced_total)/(enhanced_scores[0]/enhanced_total):.2f}:1")
    print()
    
    print("改进效果:")
    print(f"  原始算法: 性能好的机器被选中概率仅比差的机器高 {((original_scores[1]/original_total)/(original_scores[0]/original_total)-1)*100:.1f}%")
    print(f"  增强算法: 性能好的机器被选中概率比差的机器高 {((enhanced_scores[1]/enhanced_total)/(enhanced_scores[0]/enhanced_total)-1)*100:.1f}%")
    print(f"  调度倾向性提升: {((enhanced_scores[1]/enhanced_total)/(enhanced_scores[0]/enhanced_total)) / ((original_scores[1]/original_total)/(original_scores[0]/original_total)):.1f}倍")

if __name__ == "__main__":
    demo_s1_improvements()
    demo_percentage_impact() 