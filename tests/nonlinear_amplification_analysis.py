#!/usr/bin/env python3
"""
非线性放大方案分析
对比ChatGPT建议的非线性放大与现有算法的效果
"""

import math
import numpy as np
import matplotlib.pyplot as plt

def analyze_nonlinear_amplification():
    """分析非线性放大的数学效果"""
    print("非线性放大方案分析")
    print("=" * 80)
    
    # 测试不同的cache差异场景
    test_scenarios = [
        {
            'name': '微小差异',
            'cache_values': [0.12, 0.10],
            'description': '仅1.2倍差异，传统方法难以区分'
        },
        {
            'name': '小差异',
            'cache_values': [0.15, 0.08],
            'description': '1.9倍差异'
        },
        {
            'name': '中等差异',
            'cache_values': [0.30, 0.10],
            'description': '3倍差异'
        },
        {
            'name': '您的实际场景',
            'cache_values': [0.290, 0.036],
            'description': '8.1倍差异'
        }
    ]
    
    waiting_values = [0.0, 0.0]  # 假设waiting都为0
    epsilon = 1e-6  # 防零处理
    
    def chatgpt_method(cache_vals, waiting_vals, w_waiting=0.6, w_cache=0.4):
        """ChatGPT建议的方法"""
        min_w, max_w = min(waiting_vals), max(waiting_vals)
        min_c, max_c = min(cache_vals), max(cache_vals)
        
        # 归一化 + ε防零
        norm_waiting = [(w - min_w) / (max_w - min_w + epsilon) for w in waiting_vals]
        norm_cache = [(c - min_c) / (max_c - min_c + epsilon) for c in cache_vals]
        
        # 非线性放大
        scores = [w_waiting * nw + w_cache * (nc ** 2) for nw, nc in zip(norm_waiting, norm_cache)]
        return scores, norm_waiting, norm_cache
    
    def traditional_minmax(cache_vals, waiting_vals, w_a=0.2, w_b=0.8):
        """传统Min-Max方法"""
        min_w, max_w = min(waiting_vals), max(waiting_vals)
        min_c, max_c = min(cache_vals), max(cache_vals)
        
        if max_w == min_w:
            norm_waiting = [0.0] * len(waiting_vals)
        else:
            norm_waiting = [(w - min_w) / (max_w - min_w) for w in waiting_vals]
            
        if max_c == min_c:
            norm_cache = [0.5] * len(cache_vals)
        else:
            norm_cache = [(c - min_c) / (max_c - min_c) for c in cache_vals]
        
        scores = [w_a * (1 - nw) + w_b * (1 - nc) for nw, nc in zip(norm_waiting, norm_cache)]
        return scores, norm_waiting, norm_cache
    
    def enhanced_method(cache_vals, waiting_vals, w_a=0.2, w_b=0.8, power=2):
        """改进的非线性放大方法"""
        min_w, max_w = min(waiting_vals), max(waiting_vals)
        min_c, max_c = min(cache_vals), max(cache_vals)
        
        # 归一化 + ε防零
        if max_w == min_w:
            norm_waiting = [0.0] * len(waiting_vals)
        else:
            norm_waiting = [(w - min_w) / (max_w - min_w + epsilon) for w in waiting_vals]
            
        if max_c == min_c:
            norm_cache = [0.5] * len(cache_vals)
        else:
            norm_cache = [(c - min_c) / (max_c - min_c + epsilon) for c in cache_vals]
        
        # 非线性放大cache差异
        amplified_cache = [nc ** power for nc in norm_cache]
        
        # 重新归一化放大后的值到[0,1]
        if max(amplified_cache) > min(amplified_cache):
            min_amp, max_amp = min(amplified_cache), max(amplified_cache)
            amplified_cache = [(ac - min_amp) / (max_amp - min_amp) for ac in amplified_cache]
        
        scores = [w_a * (1 - nw) + w_b * (1 - ac) for nw, ac in zip(norm_waiting, amplified_cache)]
        return scores, norm_waiting, amplified_cache
    
    print(f"{'场景':<15} {'方法':<15} {'Node1 Score':<12} {'Node2 Score':<12} {'差异':<10} {'概率分布':<15}")
    print("-" * 85)
    
    for scenario in test_scenarios:
        cache_vals = scenario['cache_values']
        
        # ChatGPT方法
        chatgpt_scores, _, _ = chatgpt_method(cache_vals, waiting_values)
        chatgpt_diff = abs(chatgpt_scores[0] - chatgpt_scores[1])
        chatgpt_total = sum(chatgpt_scores)
        chatgpt_probs = [s/chatgpt_total*100 for s in chatgpt_scores] if chatgpt_total > 0 else [0, 0]
        
        # 传统方法
        trad_scores, _, _ = traditional_minmax(cache_vals, waiting_values)
        trad_diff = abs(trad_scores[0] - trad_scores[1])
        trad_total = sum(trad_scores)
        trad_probs = [s/trad_total*100 for s in trad_scores] if trad_total > 0 else [0, 0]
        
        # 改进方法
        enh_scores, _, _ = enhanced_method(cache_vals, waiting_values)
        enh_diff = abs(enh_scores[0] - enh_scores[1])
        enh_total = sum(enh_scores)
        enh_probs = [s/enh_total*100 for s in enh_scores] if enh_total > 0 else [0, 0]
        
        print(f"{scenario['name']:<15} {'ChatGPT':<15} {chatgpt_scores[0]:<12.3f} {chatgpt_scores[1]:<12.3f} {chatgpt_diff:<10.3f} {chatgpt_probs[0]:.1f}%:{chatgpt_probs[1]:.1f}%")
        print(f"{'':15} {'传统Min-Max':<15} {trad_scores[0]:<12.3f} {trad_scores[1]:<12.3f} {trad_diff:<10.3f} {trad_probs[0]:.1f}%:{trad_probs[1]:.1f}%")
        print(f"{'':15} {'改进非线性':<15} {enh_scores[0]:<12.3f} {enh_scores[1]:<12.3f} {enh_diff:<10.3f} {enh_probs[0]:.1f}%:{enh_probs[1]:.1f}%")
        print("-" * 85)

def analyze_power_effects():
    """分析不同幂次的放大效果"""
    print("\n非线性幂次效果分析")
    print("=" * 60)
    
    # 使用微小差异场景
    cache_values = [0.12, 0.10]  # 仅1.2倍差异
    
    def calculate_amplification_effect(power):
        """计算指定幂次的放大效果"""
        min_c, max_c = min(cache_values), max(cache_values)
        epsilon = 1e-6
        
        # 归一化
        norm_cache = [(c - min_c) / (max_c - min_c + epsilon) for c in cache_values]
        
        # 非线性放大
        amplified = [nc ** power for nc in norm_cache]
        
        # 重新归一化
        if max(amplified) > min(amplified):
            min_amp, max_amp = min(amplified), max(amplified)
            final_norm = [(ac - min_amp) / (max_amp - min_amp) for ac in amplified]
        else:
            final_norm = amplified
        
        return norm_cache, amplified, final_norm
    
    powers = [1, 1.5, 2, 2.5, 3, 4]
    
    print(f"原始cache值: {cache_values}")
    print(f"{'幂次':<8} {'归一化后':<20} {'放大后':<20} {'最终归一化':<20} {'差异放大倍数'}")
    print("-" * 80)
    
    for power in powers:
        norm, amp, final = calculate_amplification_effect(power)
        
        orig_diff = abs(norm[0] - norm[1])
        final_diff = abs(final[0] - final[1])
        amplification = final_diff / orig_diff if orig_diff > 0 else 0
        
        print(f"{power:<8} {norm[0]:.3f}, {norm[1]:.3f}      {amp[0]:.3f}, {amp[1]:.3f}      {final[0]:.3f}, {final[1]:.3f}      {amplification:.1f}x")

def implementation_suggestion():
    """实现建议"""
    print("\n" + "=" * 80)
    print("实现建议和价值评估")
    print("=" * 80)
    
    print("""
ChatGPT方案的价值评估:

✅ 【核心优势】
1. 非线性放大: 通过平方运算拉开微小差异
2. ε防零处理: 避免除零错误，提高数值稳定性  
3. 数学合理: 保持归一化的数学性质
4. 参数可调: 可以调整幂次来控制放大程度

✅ 【适用场景】
- cache差异很小(<1.5倍)但需要区分
- 数值都在相近范围内
- 需要突出微小性能差异

⚠️ 【注意事项】
1. 幂次选择: 过高可能导致过度放大
2. 权重平衡: 需要重新调整w_a和w_b
3. 边界情况: 需要处理极值情况

🔧 【实现建议】
在现有框架中添加s1_nonlinear算法:
- 支持可配置的幂次参数
- 保持与现有算法的一致性
- 提供调试日志查看放大效果
""")

def create_nonlinear_algorithm():
    """生成非线性算法的实现代码"""
    print("\n实现代码建议:")
    print("-" * 40)
    
    code = '''
def _calculate_s1_nonlinear_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
    """Calculate scores using S1 Nonlinear algorithm with amplification"""
    
    # 收集指标
    waiting_queue_values = []
    cache_usage_values = []
    valid_members = []
    
    for member in pool.members:
        # ... 收集数据逻辑 ...
        pass
    
    if not valid_members:
        return
    
    # 非线性放大参数
    power = getattr(mode_config, 'power', 2.0)  # 默认平方
    epsilon = 1e-6  # 防零处理
    
    # 归一化 + ε防零
    min_w, max_w = min(waiting_queue_values), max(waiting_queue_values)
    min_c, max_c = min(cache_usage_values), max(cache_usage_values)
    
    if max_w == min_w:
        normalized_waiting = [0.0] * len(waiting_queue_values)
    else:
        normalized_waiting = [(w - min_w) / (max_w - min_w + epsilon) 
                             for w in waiting_queue_values]
    
    if max_c == min_c:
        normalized_cache = [0.5] * len(cache_usage_values)
    else:
        normalized_cache = [(c - min_c) / (max_c - min_c + epsilon) 
                           for c in cache_usage_values]
    
    # 非线性放大cache差异
    amplified_cache = [nc ** power for nc in normalized_cache]
    
    # 重新归一化到[0,1]
    if max(amplified_cache) > min(amplified_cache):
        min_amp, max_amp = min(amplified_cache), max(amplified_cache)
        amplified_cache = [(ac - min_amp) / (max_amp - min_amp) 
                          for ac in amplified_cache]
    
    # 计算最终score
    new_scores = []
    for i, member in enumerate(valid_members):
        score = (mode_config.w_a * (1.0 - normalized_waiting[i]) + 
                mode_config.w_b * (1.0 - amplified_cache[i]))
        new_scores.append(max(0.0, min(1.0, score)))
        member.score = new_scores[-1]
    
    # 日志输出
    self.logger.debug(f"Nonlinear amplification: power={power}")
    # ... 其他日志 ...
'''
    
    print(code)

if __name__ == "__main__":
    analyze_nonlinear_amplification()
    analyze_power_effects()
    implementation_suggestion()
    create_nonlinear_algorithm() 