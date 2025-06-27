#!/usr/bin/env python3
"""
Cache归一化方法演示
展示不同数学方法如何更精确地区分cache_usage差异
"""

import math
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.models import Pool, PoolMember, EngineType
from core.score_calculator import ScoreCalculator
from config.config_loader import ModeConfig

def demo_normalization_methods():
    """演示不同归一化方法的效果"""
    print("Cache Usage归一化方法对比演示")
    print("=" * 80)
    
    # 测试数据集 - 两种真实场景
    test_cases = [
        {
            "name": "场景1：低缓存使用率差异",
            "cache_values": [0.06576220086677975, 0.014158163265306167],
            "description": "缓存使用率都比较低，但有4.6倍差异"
        },
        {
            "name": "场景2：高缓存使用率差异", 
            "cache_values": [0.9225551158846806, 0.19043367346938778],
            "description": "缓存使用率较高，有4.9倍差异"
        },
        {
            "name": "场景3：中等缓存使用率差异",
            "cache_values": [0.45, 0.15],
            "description": "中等缓存使用率，有3倍差异"
        }
    ]
    
    calculator = ScoreCalculator()
    
    for test_case in test_cases:
        print(f"\n{test_case['name']}")
        print(f"描述: {test_case['description']}")
        print(f"原始值: {test_case['cache_values']}")
        
        cache_values = test_case['cache_values']
        ratio = max(cache_values) / min(cache_values)
        print(f"原始比值: {ratio:.2f}:1")
        
        # 测试不同归一化方法
        methods = [
            ("Min-Max归一化", calculator._min_max_normalize),
            ("自适应归一化", calculator._adaptive_cache_normalize),
            ("比例归一化", calculator._relative_ratio_normalize),
            ("指数差异归一化", calculator._exponential_difference_normalize),
            ("Sigmoid归一化", calculator._sigmoid_difference_normalize)
        ]
        
        print("\n  归一化结果对比:")
        print(f"  {'方法':<15} {'值1':<10} {'值2':<10} {'差异':<10} {'比值':<8}")
        print("  " + "-" * 55)
        
        for method_name, method_func in methods:
            try:
                normalized = method_func(cache_values)
                if len(normalized) >= 2:
                    diff = abs(normalized[0] - normalized[1])
                    ratio = max(normalized) / min(normalized) if min(normalized) > 0 else float('inf')
                    print(f"  {method_name:<15} {normalized[0]:<10.3f} {normalized[1]:<10.3f} {diff:<10.3f} {ratio:<8.2f}")
                else:
                    print(f"  {method_name:<15} {'Error':<10} {'Error':<10} {'Error':<10} {'Error':<8}")
            except Exception as e:
                print(f"  {method_name:<15} Error: {str(e)[:30]}")

def demo_score_impact():
    """演示不同归一化方法对最终score的影响"""
    print("\n\n" + "=" * 80)
    print("Score计算影响分析")
    print("=" * 80)
    
    # 使用真实数据创建测试
    members = [
        PoolMember("10.0.20.128", 8000, "Common"),
        PoolMember("10.0.20.133", 8000, "Common")
    ]
    
    # 场景1：低cache使用率
    members[0].metrics = {"waiting_queue": 0.0, "cache_usage": 0.06576220086677975}
    members[1].metrics = {"waiting_queue": 0.0, "cache_usage": 0.014158163265306167}
    
    pool = Pool("test-pool", "Common", EngineType.VLLM, members)
    calculator = ScoreCalculator()
    
    print("\n测试场景: 低cache使用率差异 (0.066 vs 0.014)")
    print("原始cache比值: 4.6:1")
    
    # 测试不同算法
    algorithms = [
        ("s1", "原始S1算法", "cache不归一化"),
        ("s1_enhanced", "S1增强算法", "cache最小最大归一化"),
        # ("s1_adaptive", "S1自适应算法", "cache自适应归一化")
    ]
    
    print(f"\n{'算法':<15} {'描述':<20} {'Score1':<10} {'Score2':<10} {'差异':<10} {'概率1':<8} {'概率2':<8}")
    print("-" * 95)
    
    for algo_name, algo_desc, norm_desc in algorithms:
        # 重置scores
        for member in members:
            member.score = 0.5
        
        mode_config = ModeConfig(name=algo_name, w_a=0.2, w_b=0.8)
        calculator.calculate_pool_scores(pool, mode_config)
        
        scores = [member.score for member in members]
        diff = abs(scores[0] - scores[1])
        total = sum(scores)
        prob1 = (scores[0] / total * 100) if total > 0 else 0
        prob2 = (scores[1] / total * 100) if total > 0 else 0
        
        print(f"{algo_name:<15} {norm_desc:<20} {scores[0]:<10.3f} {scores[1]:<10.3f} {diff:<10.3f} {prob1:<8.1f}% {prob2:<8.1f}%")

def demo_mathematical_analysis():
    """数学分析不同方法的特点"""
    print("\n\n" + "=" * 80) 
    print("数学方法特点分析")
    print("=" * 80)
    
    methods_analysis = [
        {
            "name": "Min-Max归一化",
            "formula": "(x - min) / (max - min)",
            "特点": ["两值情况下总是产生[1,0]", "丢失原始比例信息", "适合多值情况"],
            "推荐": "❌ 不适合两值差异比较"
        },
        {
            "name": "自适应归一化", 
            "formula": "基于平方根比例调整",
            "特点": ["保留相对比例信息", "避免极端值", "范围[0.1,1.0]"],
            "推荐": "✅ 推荐用于cache差异"
        },
        {
            "name": "比例归一化",
            "formula": "log(x/min) / log(max/min)",
            "特点": ["基于对数缩放", "压缩大差异", "保留比例关系"],
            "推荐": "✅ 适合大差异场景"
        },
        {
            "name": "指数差异归一化",
            "formula": "base^((x-mean)/mean)",
            "特点": ["放大相对差异", "基于均值偏差", "可调节敏感度"],
            "推荐": "⚠️ 需要调参"
        }
    ]
    
    for method in methods_analysis:
        print(f"\n{method['name']}:")
        print(f"  公式: {method['formula']}")
        print(f"  特点: {', '.join(method['特点'])}")
        print(f"  推荐: {method['推荐']}")

def demo_recommended_solution():
    """推荐的解决方案"""
    print("\n\n" + "=" * 80)
    print("推荐解决方案")
    print("=" * 80)
    
    print("""
基于数学分析和实际效果，推荐以下方案来精确区分cache_usage差异：

1. 【立即可用】修改当前S1增强算法:
   - 使用自适应归一化替代min-max归一化
   - 保留原始比例信息，避免极端值[1,0]
   - 代码已更新，重新部署即可

2. 【配置调整】优化权重分配:
   - 当waiting_queue经常为0时，增加cache权重
   - 建议配置: w_a=0.1, w_b=0.9

3. 【进阶选项】新增算法模式:
   - s1_adaptive: 根据指标变异程度动态调整权重
   - s1_ratio: 基于waiting/cache比值进行评分

4. 【预期效果】:
   场景1 (0.066 vs 0.014): 
     - 原始S1: score差异0.043, 概率52.3%:47.7%
     - S1增强(自适应): score差异0.xxx, 概率xx%:xx%
     
   场景2 (0.923 vs 0.190):
     - 原始S1: score差异0.586, 概率xx%:xx%  
     - S1增强(自适应): score差异0.xxx, 概率xx%:xx%
""")

if __name__ == "__main__":
    demo_normalization_methods()
    demo_score_impact()
    demo_mathematical_analysis()
    demo_recommended_solution() 