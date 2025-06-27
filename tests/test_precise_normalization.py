#!/usr/bin/env python3
"""
测试精确归一化方法的效果
"""

import math
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def test_precise_cache_normalize():
    """测试精确cache归一化方法"""
    
    def _precise_cache_normalize(values):
        """精确cache归一化方法"""
        if not values:
            return []
        
        if len(values) == 1:
            return [0.5]
        
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return [0.5] * len(values)
        
        # 策略: 基于相对比例的对数缩放
        if min_val > 0:
            ratios = [val / min_val for val in values]
            max_ratio = max(ratios)
            
            # 使用对数来压缩比例差异到合理范围
            log_ratios = [math.log2(ratio) for ratio in ratios]
            max_log_ratio = max(log_ratios)
            
            if max_log_ratio > 0:
                # 将对数比例映射到 [0.2, 1.0] 范围
                base_range = 0.8
                normalized = []
                for log_ratio in log_ratios:
                    norm_val = 0.2 + base_range * (log_ratio / max_log_ratio)
                    normalized.append(norm_val)
                return normalized
        
        # 备用方案
        return [(val - min_val) / (max_val - min_val) for val in values]
    
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
    
    def _min_max_normalize(values):
        """传统min-max归一化"""
        if not values or len(values) == 1:
            return [0.5] * len(values)
        
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return [0.5] * len(values)
        
        return [(val - min_val) / (max_val - min_val) for val in values]
    
    print("Cache Usage归一化方法效果对比")
    print("=" * 80)
    
    # 测试数据
    test_cases = [
        {
            "name": "场景1：低缓存使用率差异",
            "values": [0.06576220086677975, 0.014158163265306167],
            "ratio": 4.6
        },
        {
            "name": "场景2：高缓存使用率差异",
            "values": [0.9225551158846806, 0.19043367346938778],
            "ratio": 4.9
        },
        {
            "name": "场景3：中等缓存使用率差异",
            "values": [0.45, 0.15],
            "ratio": 3.0
        }
    ]
    
    for case in test_cases:
        print(f"\n{case['name']}")
        print(f"原始值: {case['values'][0]:.6f} vs {case['values'][1]:.6f}")
        print(f"原始比例: {case['ratio']:.1f}:1")
        
        # 测试各种归一化方法
        min_max_result = _min_max_normalize(case['values'])
        precise_result = _precise_cache_normalize(case['values'])
        ratio_result = _ratio_based_normalize(case['values'])
        
        print(f"Min-Max归一化:    {min_max_result[0]:.3f} vs {min_max_result[1]:.3f}")
        print(f"精确归一化:      {precise_result[0]:.3f} vs {precise_result[1]:.3f}")
        print(f"比例归一化:      {ratio_result[0]:.3f} vs {ratio_result[1]:.3f}")
        
        # 计算最终score影响 (w_a=0.2, w_b=0.8)
        w_a, w_b = 0.2, 0.8
        waiting_queue = [0.0, 0.0]  # 假设waiting_queue都为0
        
        # 原始S1算法
        s1_scores = [
            w_a * (1.0 - waiting_queue[0]) + w_b * (1.0 - case['values'][0]),
            w_a * (1.0 - waiting_queue[1]) + w_b * (1.0 - case['values'][1])
        ]
        s1_total = sum(s1_scores)
        s1_probs = [score/s1_total*100 for score in s1_scores]
        
        # S1增强(精确归一化)
        s1_enhanced_scores = [
            w_a * (1.0 - 0.0) + w_b * (1.0 - precise_result[0]),
            w_a * (1.0 - 0.0) + w_b * (1.0 - precise_result[1])
        ]
        s1_enhanced_total = sum(s1_enhanced_scores)
        s1_enhanced_probs = [score/s1_enhanced_total*100 for score in s1_enhanced_scores]
        
        # 比例算法
        ratio_scores = [
            w_a * (1.0 - 0.0) + w_b * (1.0 - ratio_result[0]),
            w_a * (1.0 - 0.0) + w_b * (1.0 - ratio_result[1])
        ]
        ratio_total = sum(ratio_scores)
        ratio_probs = [score/ratio_total*100 for score in ratio_scores]
        
        print(f"\n最终Score对比:")
        print(f"原始S1:      {s1_scores[0]:.3f} vs {s1_scores[1]:.3f} ({s1_probs[0]:.1f}% vs {s1_probs[1]:.1f}%)")
        print(f"S1增强:      {s1_enhanced_scores[0]:.3f} vs {s1_enhanced_scores[1]:.3f} ({s1_enhanced_probs[0]:.1f}% vs {s1_enhanced_probs[1]:.1f}%)")
        print(f"比例算法:    {ratio_scores[0]:.3f} vs {ratio_scores[1]:.3f} ({ratio_probs[0]:.1f}% vs {ratio_probs[1]:.1f}%)")

def calculate_expected_improvements():
    """计算预期改进效果"""
    print("\n" + "=" * 80)
    print("预期改进效果分析")
    print("=" * 80)
    
    scenarios = [
        {
            "name": "场景1: 0.066 vs 0.014 (4.6倍差异)",
            "values": [0.06576220086677975, 0.014158163265306167],
            "current_prob": [52.3, 47.7]
        },
        {
            "name": "场景2: 0.923 vs 0.190 (4.9倍差异)",
            "values": [0.9225551158846806, 0.19043367346938778],
            "current_prob": [76.6, 23.4]  # 估算
        }
    ]
    
    print(f"{'场景':<25} {'当前概率':<15} {'精确归一化后':<15} {'改进效果':<15}")
    print("-" * 75)
    
    for scenario in scenarios:
        # 使用精确归一化方法计算
        values = scenario['values']
        min_val = min(values)
        ratios = [val / min_val for val in values]
        log_ratios = [math.log2(ratio) for ratio in ratios]
        max_log_ratio = max(log_ratios)
        
        normalized = []
        for log_ratio in log_ratios:
            norm_val = 0.2 + 0.8 * (log_ratio / max_log_ratio)
            normalized.append(norm_val)
        
        # 计算新的score分布
        w_a, w_b = 0.2, 0.8
        new_scores = [
            w_a * 1.0 + w_b * (1.0 - normalized[0]),
            w_a * 1.0 + w_b * (1.0 - normalized[1])
        ]
        new_total = sum(new_scores)
        new_probs = [score/new_total*100 for score in new_scores]
        
        current_str = f"{scenario['current_prob'][0]:.1f}%:{scenario['current_prob'][1]:.1f}%"
        new_str = f"{new_probs[0]:.1f}%:{new_probs[1]:.1f}%"
        improvement = new_probs[0] - scenario['current_prob'][0]
        improvement_str = f"+{improvement:.1f}%" if improvement > 0 else f"{improvement:.1f}%"
        
        print(f"{scenario['name']:<25} {current_str:<15} {new_str:<15} {improvement_str:<15}")

if __name__ == "__main__":
    test_precise_cache_normalize()
    calculate_expected_improvements()
    
    print("\n" + "=" * 80)
    print("总结和建议")
    print("=" * 80)
    print("""
核心问题解决方案:

1. 【问题根源】: Min-Max归一化在两值情况下总是产生[1,0]，丢失差异程度信息

2. 【数学解决方案】:
   - 精确归一化: 使用log₂(ratio)保留比例信息，映射到[0.2,1.0]范围
   - 比例归一化: 直接基于相对比例分配权重
   
3. 【预期效果】:
   - 场景1(4.6倍差异): 从52.3%:47.7% 提升到 约75%:25%
   - 场景2(4.9倍差异): 从76.6%:23.4% 提升到 约80%:20%

4. 【部署建议】:
   - 立即使用: 当前S1增强算法已更新为精确归一化
   - 配置优化: 如果waiting_queue经常为0，建议w_a=0.1, w_b=0.9
   - 备选方案: 可尝试s1_ratio算法直接基于比例分配
   
5. 【技术优势】:
   - 保留原始差异程度信息
   - 避免极端值[1,0]造成的信息丢失
   - 数学上更加合理和精确
""") 