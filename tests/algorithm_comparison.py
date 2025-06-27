#!/usr/bin/env python3
"""
S1系列算法详细对比分析
"""

import math
import sys
from pathlib import Path

def analyze_algorithms():
    """分析各算法的核心差异"""
    print("S1系列算法核心差异分析")
    print("=" * 80)
    
    algorithms = {
        's1': {
            'name': '原始S1算法',
            'cache_processing': '直接使用原始cache值，不进行归一化',
            'formula': 'score = w_a * (1 - waiting) + w_b * (1 - cache_raw)',
            'pros': ['计算简单', '直接反映原始差异', '无额外处理开销'],
            'cons': ['小差异区分度不足', '受cache数值范围影响大', '权重效果有限'],
            'best_for': '当cache差异很大(>0.3)且数值范围合理时'
        },
        
        's1_enhanced': {
            'name': 'S1增强算法',
            'cache_processing': '对cache使用精确归一化(对数缩放)',
            'formula': 'score = w_a * (1 - waiting_norm) + w_b * (1 - cache_precise_norm)',
            'pros': ['保留差异程度信息', '避免极端值[1,0]', '数学上更合理'],
            'cons': ['计算稍复杂', '对数变换可能过度平滑'],
            'best_for': '当cache差异中等(2-10倍)且需要精确区分时'
        },
        
        's1_adaptive': {
            'name': 'S1自适应算法',
            'cache_processing': 'Min-Max归一化 + 动态权重调整',
            'formula': '根据指标变异系数动态调整w_a和w_b权重',
            'pros': ['自动适应数据特征', '动态优化权重', '适应性强'],
            'cons': ['逻辑复杂', '权重变化不可预测', '调试困难'],
            'best_for': '多指标变异程度差异很大时'
        },
        
        's1_ratio': {
            'name': 'S1比例算法',
            'cache_processing': '基于相对比例的直接权重分配',
            'formula': 'cache_norm = ratio/(ratio+1), score = w_a * (1-waiting) + w_b * (1-cache_norm)',
            'pros': ['最直观反映比例关系', '计算简单', '结果可预测'],
            'cons': ['只适合两个节点', '极端差异时可能过于极端'],
            'best_for': '两节点场景且需要直观的比例分配'
        },
        
        's1_precise': {
            'name': 'S1精确算法',
            'cache_processing': '直接使用原始值，无归一化',
            'formula': 'score = w_a * (1 - waiting) + w_b * (1 - cache_raw)',
            'pros': ['保持原始数值特征', '计算最简单', '完全可控'],
            'cons': ['与s1算法基本相同', '小差异区分度不足'],
            'best_for': '当原始cache值已经在合理范围内时'
        }
    }
    
    for algo_key, algo_info in algorithms.items():
        print(f"\n【{algo_info['name']}】")
        print(f"  Cache处理方式: {algo_info['cache_processing']}")
        print(f"  计算公式: {algo_info['formula']}")
        print(f"  优点: {', '.join(algo_info['pros'])}")
        print(f"  缺点: {', '.join(algo_info['cons'])}")
        print(f"  最适合: {algo_info['best_for']}")

def test_scenario_comparison():
    """测试您的具体场景下各算法效果"""
    print("\n" + "=" * 80)
    print("您的场景测试: waiting=0, cache差异较小")
    print("=" * 80)
    
    # 模拟几种cache差异情况
    test_scenarios = [
        {
            'name': '小差异场景',
            'cache_values': [0.12, 0.08],
            'description': '1.5倍差异'
        },
        {
            'name': '中等差异场景',
            'cache_values': [0.30, 0.10],
            'description': '3倍差异'
        },
        {
            'name': '您的实际场景',
            'cache_values': [0.290, 0.036],
            'description': '8.1倍差异'
        }
    ]
    
    waiting_values = [0.0, 0.0]
    w_a, w_b = 0.1, 0.9
    
    def _min_max_normalize(values):
        if len(values) <= 1:
            return values
        min_val, max_val = min(values), max(values)
        if max_val == min_val:
            return [0.5] * len(values)
        return [(val - min_val) / (max_val - min_val) for val in values]
    
    def _precise_cache_normalize(values):
        if len(values) != 2 or min(values) <= 0:
            return _min_max_normalize(values)
        
        ratios = [val / min(values) for val in values]
        log_ratios = [math.log2(ratio) for ratio in ratios]
        max_log_ratio = max(log_ratios)
        
        if max_log_ratio > 0:
            return [0.2 + 0.8 * (log_ratio / max_log_ratio) for log_ratio in log_ratios]
        return [0.5] * len(values)
    
    def _ratio_based_normalize(values):
        if len(values) != 2:
            return values
        val1, val2 = values[0], values[1]
        if val1 == val2:
            return [0.5, 0.5]
        if min(val1, val2) > 0:
            if val1 > val2:
                ratio = val1 / val2
                return [ratio / (ratio + 1), 1 / (ratio + 1)]
            else:
                ratio = val2 / val1
                return [1 / (ratio + 1), ratio / (ratio + 1)]
        return values
    
    for scenario in test_scenarios:
        print(f"\n{scenario['name']} - {scenario['description']}")
        print(f"Cache原始值: {scenario['cache_values']}")
        
        cache_values = scenario['cache_values']
        
        # 测试各算法
        algorithms_test = [
            ('s1', cache_values, '原始值'),
            ('s1_enhanced', _precise_cache_normalize(cache_values), '精确归一化'),
            ('s1_ratio', _ratio_based_normalize(cache_values), '比例归一化'),
            ('s1_precise', cache_values, '原始值')
        ]
        
        print(f"{'算法':<15} {'Node1 Score':<12} {'Node2 Score':<12} {'差异':<10} {'概率分布':<15}")
        print("-" * 70)
        
        for algo_name, norm_cache, description in algorithms_test:
            scores = []
            for i in range(len(cache_values)):
                score = w_a * (1.0 - waiting_values[i]) + w_b * (1.0 - norm_cache[i])
                scores.append(score)
            
            diff = abs(scores[0] - scores[1])
            total = sum(scores)
            if total > 0:
                probs = [score/total*100 for score in scores]
                prob_str = f"{probs[0]:.1f}%:{probs[1]:.1f}%"
            else:
                prob_str = "0%:0%"
            
            print(f"{algo_name:<15} {scores[0]:<12.3f} {scores[1]:<12.3f} {diff:<10.3f} {prob_str}")

def recommendation_analysis():
    """针对用户场景的推荐分析"""
    print("\n" + "=" * 80)
    print("针对您场景的算法推荐")
    print("=" * 80)
    
    print("""
场景特征分析:
✓ waiting_queue = 0 (两节点负载相同)
✓ cache差异较小但有区分价值
✓ 需要根据性能差异合理分配流量
✓ 希望算法行为可预测和可控

推荐排序:

🥇 【首选】s1_ratio - 比例算法
  理由:
  - 最直观地反映cache使用率的相对差异
  - 计算结果可预测: ratio/(ratio+1) 的权重分配
  - 适合两节点场景
  - 不会因为差异"太小"而失效
  - 性能好的节点获得更多流量，符合预期

🥈 【备选】s1_enhanced - 增强算法  
  理由:
  - 使用对数缩放保留差异程度信息
  - 避免极端值，数学上更合理
  - 适合各种差异程度的场景
  - 但对数变换可能让小差异变得更小

🥉 【保守】s1 - 原始算法
  理由:
  - 计算最简单，完全可控
  - 当cache值本身就在合理范围时效果不错
  - 但小差异时区分度可能不够

❌ 【不推荐】s1_adaptive - 自适应算法
  理由:
  - 权重会动态变化，行为不可预测
  - 在waiting=0的场景下可能过度复杂
  - 调试和理解困难

❌ 【不推荐】s1_precise - 精确算法
  理由:
  - 与s1算法基本相同
  - 没有解决小差异区分度问题
""")

def practical_configuration():
    """实用配置建议"""
    print("\n" + "=" * 80)
    print("实用配置建议")
    print("=" * 80)
    
    print("""
配置建议:

1. 【推荐配置】
   算法: s1_ratio
   权重: w_a=0.1, w_b=0.9
   理由: waiting经常为0时，主要依靠cache差异区分

2. 【测试配置】
   算法: s1_enhanced  
   权重: w_a=0.1, w_b=0.9
   理由: 作为对比测试，验证效果差异

3. 【权重调优】
   - 如果cache差异很小(<2倍): 考虑w_b=0.95
   - 如果cache差异较大(>5倍): w_b=0.8即可
   - waiting不为0时: 适当提高w_a到0.2

4. 【监控指标】
   - 观察两节点的实际流量分配比例
   - 监控cache使用率变化趋势
   - 确认性能好的节点确实获得更多流量

5. 【调试技巧】
   - 开启DEBUG日志查看归一化后的值
   - 对比不同算法的score分布
   - 记录一段时间的选择概率统计
""")

if __name__ == "__main__":
    analyze_algorithms()
    test_scenario_comparison()
    recommendation_analysis()
    practical_configuration() 