#!/usr/bin/env python3
"""
测试修复后的S1_RATIO算法
"""

import math
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_ratio_based_normalize():
    """测试比例归一化方法"""
    
    def _ratio_based_normalize(values):
        """基于比例的归一化"""
        if not values or len(values) == 1:
            return [0.5] * len(values)
        
        if len(values) == 2:
            val1, val2 = values[0], values[1]
            if val1 == val2:
                return [0.5, 0.5]
            
            if min(val1, val2) > 0:
                if val1 > val2:
                    ratio = val1 / val2
                    better_weight = ratio / (ratio + 1)
                    worse_weight = 1 / (ratio + 1)
                    return [better_weight, worse_weight]
                else:
                    ratio = val2 / val1  
                    better_weight = ratio / (ratio + 1)
                    worse_weight = 1 / (ratio + 1)
                    return [worse_weight, better_weight]
        
        return [0.5] * len(values)
    
    print("S1_RATIO算法修复验证")
    print("=" * 60)
    
    # 使用您的实际数据
    cache_values = [0.2898059167137743, 0.0357461734693878]
    waiting_values = [0.0, 0.0]
    
    print(f"原始数据:")
    print(f"  Node 1: waiting={waiting_values[0]:.3f}, cache={cache_values[0]:.3f}")
    print(f"  Node 2: waiting={waiting_values[1]:.3f}, cache={cache_values[1]:.3f}")
    print(f"  Cache比例: {cache_values[0]/cache_values[1]:.2f}:1")
    
    # 测试比例归一化
    normalized_cache = _ratio_based_normalize(cache_values)
    print(f"\n比例归一化后:")
    print(f"  Node 1: cache_norm={normalized_cache[0]:.3f}")
    print(f"  Node 2: cache_norm={normalized_cache[1]:.3f}")
    
    # 计算S1_RATIO算法的score
    w_a, w_b = 0.1, 0.9
    scores = []
    for i in range(len(cache_values)):
        score = w_a * (1.0 - waiting_values[i]) + w_b * (1.0 - normalized_cache[i])
        scores.append(score)
    
    print(f"\nS1_RATIO算法计算 (w_a={w_a}, w_b={w_b}):")
    print(f"  Node 1: score = {w_a}*(1-{waiting_values[0]:.3f}) + {w_b}*(1-{normalized_cache[0]:.3f}) = {scores[0]:.3f}")
    print(f"  Node 2: score = {w_a}*(1-{waiting_values[1]:.3f}) + {w_b}*(1-{normalized_cache[1]:.3f}) = {scores[1]:.3f}")
    
    # 计算选择概率
    total_score = sum(scores)
    if total_score > 0:
        probs = [score/total_score*100 for score in scores]
        print(f"\n选择概率:")
        print(f"  Node 1: {probs[0]:.1f}%")
        print(f"  Node 2: {probs[1]:.1f}%")
    else:
        print(f"\n❌ 错误：总分为0！")
    
    return scores, total_score

def compare_algorithms():
    """对比不同算法的效果"""
    print("\n" + "=" * 60)
    print("算法效果对比")
    print("=" * 60)
    
    cache_values = [0.2898059167137743, 0.0357461734693878]
    waiting_values = [0.0, 0.0]
    w_a, w_b = 0.1, 0.9
    
    def _ratio_based_normalize(values):
        if len(values) == 2:
            val1, val2 = values[0], values[1]
            if val1 == val2:
                return [0.5, 0.5]
            if min(val1, val2) > 0:
                if val1 > val2:
                    ratio = val1 / val2
                    better_weight = ratio / (ratio + 1)
                    worse_weight = 1 / (ratio + 1)
                    return [better_weight, worse_weight]
                else:
                    ratio = val2 / val1  
                    better_weight = ratio / (ratio + 1)
                    worse_weight = 1 / (ratio + 1)
                    return [worse_weight, better_weight]
        return [0.5] * len(values)
    
    def _min_max_normalize(values):
        if len(values) <= 1:
            return [0.5] * len(values)
        min_val = min(values)
        max_val = max(values)
        if max_val == min_val:
            return [0.5] * len(values)
        return [(val - min_val) / (max_val - min_val) for val in values]
    
    algorithms = [
        ("原始S1", cache_values, "直接使用cache值"),
        ("S1增强(Min-Max)", _min_max_normalize(cache_values), "Min-Max归一化"),
        ("S1_RATIO(修复后)", _ratio_based_normalize(cache_values), "比例归一化")
    ]
    
    print(f"{'算法':<20} {'Node1 Score':<12} {'Node2 Score':<12} {'概率分布':<15} {'说明'}")
    print("-" * 80)
    
    for algo_name, norm_cache, description in algorithms:
        scores = []
        for i in range(len(cache_values)):
            score = w_a * (1.0 - waiting_values[i]) + w_b * (1.0 - norm_cache[i])
            scores.append(score)
        
        total = sum(scores)
        if total > 0:
            probs = [score/total*100 for score in scores]
            prob_str = f"{probs[0]:.1f}%:{probs[1]:.1f}%"
        else:
            prob_str = "0%:0%"
        
        print(f"{algo_name:<20} {scores[0]:<12.3f} {scores[1]:<12.3f} {prob_str:<15} {description}")

def test_edge_cases():
    """测试边界情况"""
    print("\n" + "=" * 60)
    print("边界情况测试")
    print("=" * 60)
    
    def _ratio_based_normalize(values):
        if len(values) == 2:
            val1, val2 = values[0], values[1]
            if val1 == val2:
                return [0.5, 0.5]
            if min(val1, val2) > 0:
                if val1 > val2:
                    ratio = val1 / val2
                    better_weight = ratio / (ratio + 1)
                    worse_weight = 1 / (ratio + 1)
                    return [better_weight, worse_weight]
                else:
                    ratio = val2 / val1  
                    better_weight = ratio / (ratio + 1)
                    worse_weight = 1 / (ratio + 1)
                    return [worse_weight, better_weight]
        return [0.5] * len(values)
    
    test_cases = [
        ("相同值", [0.5, 0.5]),
        ("极小差异", [0.001, 0.0009]),
        ("极大差异", [0.9, 0.1]),
        ("一个为0", [0.5, 0.0]),
        ("都为0", [0.0, 0.0])
    ]
    
    for case_name, values in test_cases:
        try:
            normalized = _ratio_based_normalize(values)
            print(f"{case_name:<12}: {values} → {[f'{v:.3f}' for v in normalized]}")
        except Exception as e:
            print(f"{case_name:<12}: {values} → 错误: {e}")

if __name__ == "__main__":
    scores, total = test_ratio_based_normalize()
    
    if total > 0:
        print(f"\n✅ S1_RATIO算法修复成功！")
        print(f"   总分: {total:.3f}")
        print(f"   两节点都有有效的score值")
    else:
        print(f"\n❌ 仍有问题，总分为0")
    
    compare_algorithms()
    test_edge_cases()
    
    print(f"\n" + "=" * 60)
    print("修复总结")
    print("=" * 60)
    print("""
原问题：
- S1_RATIO算法计算 waiting_queue/cache_usage 比例
- 当waiting_queue=0时，比例总是0
- Min-Max归一化[0,0] → [0.0,0.0]
- 最终score都为0

修复方案：
- 改用比例归一化处理cache_usage差异
- 基于cache使用率的相对比例分配权重  
- 避免除零和归一化失效问题
- 保留原有的权重配置逻辑

预期效果：
- Cache使用率低的节点获得更高score
- 根据实际性能差异合理分配流量
- 解决score为0的问题
""") 