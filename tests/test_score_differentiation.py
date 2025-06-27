#!/usr/bin/env python3
"""
Score区分度测试脚本
用于比较不同算法在相似指标情况下的区分效果
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.models import Pool, PoolMember, EngineType
from core.score_calculator import ScoreCalculator
from config.config_loader import ModeConfig


def test_score_differentiation():
    """测试不同算法的区分度"""
    print("测试Score区分度...")
    
    # 创建类似您实际情况的测试数据
    members = [
        PoolMember("10.0.20.128", 8000, "Common"),
        PoolMember("10.0.20.133", 8000, "Common")
    ] 
    
    # 设置与您的实际情况相似的metrics
    # waiting_queue都是0，cache_usage有差异，running_req添加一些差异
    members[0].metrics = {"waiting_queue": 0.0, "cache_usage": 0.118, "running_req": 2.0}
    members[1].metrics = {"waiting_queue": 0.0, "cache_usage": 0.009, "running_req": 1.5}
    
    pool = Pool("test-pool", "Common", EngineType.VLLM, members)
    calculator = ScoreCalculator()
    
    print("\n=== 原始指标 ===")
    for i, member in enumerate(members):
        print(f"Member {i+1} ({member.address}): waiting={member.metrics['waiting_queue']:.3f}, "
              f"cache={member.metrics['cache_usage']:.3f}, running={member.metrics['running_req']:.3f}")
    
    # 测试不同算法
    algorithms = [
        ("s2", "原始S2算法", ModeConfig(name="s2", w_a=0.6, w_b=0.2, w_g=0.2)),
        ("s2_enhanced", "S2增强算法(cache归一化)", ModeConfig(name="s2_enhanced", w_a=0.6, w_b=0.2, w_g=0.2)),
        ("s2_enhanced_balanced", "S2增强算法(平衡权重)", ModeConfig(name="s2_enhanced", w_a=0.4, w_b=0.4, w_g=0.2)),
        ("s2_nonlinear", "S2非线性算法", ModeConfig(name="s2_nonlinear", w_a=0.6, w_b=0.2, w_g=0.2)),
        ("s2_adaptive", "S2自适应算法", ModeConfig(name="s2_adaptive", w_a=0.6, w_b=0.2, w_g=0.2)),
    ]
    
    results = []
    
    for algo_name, algo_desc, mode_config in algorithms:
        print(f"\n=== {algo_desc} ===")
        print(f"权重配置: w_a={mode_config.w_a}, w_b={mode_config.w_b}, w_g={mode_config.w_g}")
        
        # 重置scores
        for member in members:
            member.score = 0.5
        
        calculator.calculate_pool_scores(pool, mode_config)
        
        scores = [member.score for member in members]
        score_diff = abs(scores[0] - scores[1])
        score_ratio = max(scores) / min(scores) if min(scores) > 0 else float('inf')
        
        print(f"Score结果: {scores[0]:.6f} vs {scores[1]:.6f}")
        print(f"绝对差异: {score_diff:.6f}")
        print(f"比值: {score_ratio:.3f}")
        
        results.append({
            'name': algo_desc,
            'scores': scores.copy(),
            'diff': score_diff,
            'ratio': score_ratio
        })
    
    # 比较结果
    print("\n=== 算法比较总结 ===")
    print(f"{'算法':<20} {'Score1':<12} {'Score2':<12} {'绝对差异':<12} {'比值':<8}")
    print("-" * 70)
    
    for result in results:
        print(f"{result['name']:<20} {result['scores'][0]:<12.6f} {result['scores'][1]:<12.6f} "
              f"{result['diff']:<12.6f} {result['ratio']:<8.3f}")
    
    # 推荐最佳算法
    best_diff = max(results, key=lambda x: x['diff'])
    print(f"\n推荐算法: {best_diff['name']} (差异最大: {best_diff['diff']:.6f})")


def test_extreme_cache_difference():
    """测试极端cache差异情况"""
    print("\n\n测试极端cache差异情况...")
    
    members = [
        PoolMember("10.0.10.1", 8000, "Common"),
        PoolMember("10.0.10.2", 8000, "Common"),
        PoolMember("10.0.10.3", 8000, "Common")
    ]
    
    # 设置极端差异的cache使用率
    members[0].metrics = {"waiting_queue": 0.0, "cache_usage": 0.05, "running_req": 1.0}   # 很低
    members[1].metrics = {"waiting_queue": 0.0, "cache_usage": 0.50, "running_req": 2.0}   # 中等
    members[2].metrics = {"waiting_queue": 0.0, "cache_usage": 0.95, "running_req": 3.0}   # 很高
    
    pool = Pool("extreme-test-pool", "Common", EngineType.VLLM, members)
    calculator = ScoreCalculator()
    
    print("\n原始指标:")
    for i, member in enumerate(members):
        print(f"Member {i+1}: cache={member.metrics['cache_usage']:.3f}")
    
    # 测试S2 Enhanced算法
    mode_config = ModeConfig(name="s2_enhanced", w_a=0.3, w_b=0.5, w_g=0.2)
    calculator.calculate_pool_scores(pool, mode_config)
    
    print(f"\nS2 Enhanced算法结果:")
    total_score = sum(member.score for member in members)
    for i, member in enumerate(members):
        percentage = (member.score / total_score * 100) if total_score > 0 else 0
        print(f"Member {i+1}: score={member.score:.6f} ({percentage:.1f}%)")


def test_weight_sensitivity():
    """测试权重敏感性"""
    print("\n\n测试权重敏感性...")
    
    members = [
        PoolMember("10.0.20.128", 8000, "Common"),
        PoolMember("10.0.20.133", 8000, "Common")
    ]
    
    # 使用您的实际数据
    members[0].metrics = {"waiting_queue": 0.0, "cache_usage": 0.118, "running_req": 2.0}
    members[1].metrics = {"waiting_queue": 0.0, "cache_usage": 0.009, "running_req": 1.5}
    
    pool = Pool("weight-test-pool", "Common", EngineType.VLLM, members)
    calculator = ScoreCalculator()
    
    # 测试不同的权重配置
    weight_configs = [
        (0.6, 0.2, 0.2, "原始配置"),
        (0.4, 0.4, 0.2, "提高cache权重"),
        (0.3, 0.5, 0.2, "进一步提高cache权重"),
        (0.2, 0.6, 0.2, "cache权重最高"),
    ]
    
    print(f"{'权重配置':<20} {'Score差异':<12} {'比值':<8}")
    print("-" * 45)
    
    for w_a, w_b, w_g, desc in weight_configs:
        # 重置scores
        for member in members:
            member.score = 0.5
            
        mode_config = ModeConfig(name="s2_enhanced", w_a=w_a, w_b=w_b, w_g=w_g)
        calculator.calculate_pool_scores(pool, mode_config)
        
        scores = [member.score for member in members]
        score_diff = abs(scores[0] - scores[1])
        score_ratio = max(scores) / min(scores) if min(scores) > 0 else float('inf')
        
        print(f"{desc:<20} {score_diff:<12.6f} {score_ratio:<8.3f}")


if __name__ == "__main__":
    test_score_differentiation()
    test_extreme_cache_difference()  
    test_weight_sensitivity() 