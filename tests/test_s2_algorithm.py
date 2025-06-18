"""
Test S2 algorithm functionality
"""

import sys
import asyncio
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.models import PoolMember, Pool, EngineType
from core.score_calculator import ScoreCalculator
from config.config_loader import ModeConfig


def test_s2_algorithm_basic():
    """Test basic S2 algorithm functionality"""
    print("Testing S2 algorithm basic functionality...")
    
    # Create test data with different metrics values
    members = [
        PoolMember("10.10.10.10", 8001, "Common"),
        PoolMember("10.10.10.11", 8001, "Common"), 
        PoolMember("10.10.10.12", 8001, "Common")
    ]
    
    # Set metrics including the new running_req metric
    # Member 1: High waiting queue, low cache usage, low running requests (should get medium score)
    members[0].metrics = {"waiting_queue": 10.0, "cache_usage": 0.2, "running_req": 1.0}
    
    # Member 2: Medium waiting queue, medium cache usage, high running requests (should get medium score)
    members[1].metrics = {"waiting_queue": 5.0, "cache_usage": 0.5, "running_req": 8.0}
    
    # Member 3: Low waiting queue, low cache usage, low running requests (should get high score)
    members[2].metrics = {"waiting_queue": 1.0, "cache_usage": 0.1, "running_req": 2.0}
    
    pool = Pool("test-s2-pool", "Common", EngineType.VLLM, members)
    
    # Test S2 algorithm with balanced weights
    mode_config = ModeConfig(name="s2", w_a=0.4, w_b=0.3, w_g=0.3)
    calculator = ScoreCalculator()
    
    print(f"Algorithm configuration: {mode_config.name}, w_a={mode_config.w_a}, w_b={mode_config.w_b}, w_g={mode_config.w_g}")
    
    calculator.calculate_pool_scores(pool, mode_config)
    
    print("S2 algorithm results:")
    total_score = sum(member.score for member in members)
    for i, member in enumerate(members, 1):
        percentage = (member.score / total_score * 100) if total_score > 0 else 0
        print(f"  Member {i} ({member}): score={member.score:.4f} ({percentage:.1f}%)")
        print(f"    Metrics: waiting_queue={member.metrics['waiting_queue']:.1f}, "
              f"cache_usage={member.metrics['cache_usage']:.2f}, "
              f"running_req={member.metrics['running_req']:.1f}")
    
    # Validate results
    # Member 3 should have highest score (best overall metrics)
    # Member 1 vs Member 2: Member 1 has higher waiting_queue but better cache_usage and running_req
    # With weights w_a=0.4, w_b=0.3, w_g=0.3, Member 1 should score higher than Member 2
    assert members[2].score > members[0].score > members[1].score, \
        f"Expected Member 3 > Member 1 > Member 2 based on metrics, got scores: " \
        f"Member 1={members[0].score:.4f}, Member 2={members[1].score:.4f}, Member 3={members[2].score:.4f}"
    
    print("✓ S2 algorithm basic test passed")
    return pool


def test_s2_vs_s1_comparison():
    """Compare S2 algorithm results with S1 algorithm"""
    print("\nComparing S2 vs S1 algorithm results...")
    
    # Create test data
    members = [
        PoolMember("192.168.1.10", 8001, "Common"),
        PoolMember("192.168.1.11", 8001, "Common")
    ]
    
    # Set metrics where running_req makes a difference
    members[0].metrics = {"waiting_queue": 5.0, "cache_usage": 0.4, "running_req": 1.0}  # Low running requests
    members[1].metrics = {"waiting_queue": 5.0, "cache_usage": 0.4, "running_req": 9.0}  # High running requests
    
    pool = Pool("comparison-pool", "Common", EngineType.SGLANG, members)
    calculator = ScoreCalculator()
    
    # Test S1 algorithm (should give similar scores since waiting_queue and cache_usage are same)
    mode_config_s1 = ModeConfig(name="s1", w_a=0.5, w_b=0.5)
    calculator.calculate_pool_scores(pool, mode_config_s1)
    
    s1_scores = [member.score for member in members]
    print(f"S1 results: Member1={s1_scores[0]:.4f}, Member2={s1_scores[1]:.4f}")
    
    # Test S2 algorithm (should differentiate based on running_req)
    mode_config_s2 = ModeConfig(name="s2", w_a=0.3, w_b=0.3, w_g=0.4)
    calculator.calculate_pool_scores(pool, mode_config_s2)
    
    s2_scores = [member.score for member in members]
    print(f"S2 results: Member1={s2_scores[0]:.4f}, Member2={s2_scores[1]:.4f}")
    
    # S2 should show more difference due to running_req metric
    s1_diff = abs(s1_scores[0] - s1_scores[1])
    s2_diff = abs(s2_scores[0] - s2_scores[1])
    
    print(f"Score difference - S1: {s1_diff:.4f}, S2: {s2_diff:.4f}")
    
    # With the given metrics and weights, S2 should show larger difference
    assert s2_diff > s1_diff, "S2 algorithm should show larger score difference due to running_req metric"
    
    # Member 1 (low running_req) should have higher score than Member 2 (high running_req) in S2
    assert s2_scores[0] > s2_scores[1], "Member with lower running_req should have higher score in S2"
    
    print("✓ S2 vs S1 comparison test passed")


def test_s2_edge_cases():
    """Test S2 algorithm edge cases"""
    print("\nTesting S2 algorithm edge cases...")
    
    # Test with missing running_req metric
    members_missing = [PoolMember("10.0.0.1", 8001, "Common")]
    members_missing[0].metrics = {"waiting_queue": 5.0, "cache_usage": 0.3}  # Missing running_req
    
    pool_missing = Pool("missing-metric-pool", "Common", EngineType.VLLM, members_missing)
    calculator = ScoreCalculator()
    mode_config_s2 = ModeConfig(name="s2", w_a=0.4, w_b=0.3, w_g=0.3)
    
    original_score = members_missing[0].score
    calculator.calculate_pool_scores(pool_missing, mode_config_s2)
    
    # Score should remain unchanged when metric is missing
    assert members_missing[0].score == original_score, "Score should remain unchanged when running_req metric is missing"
    
    print("✓ S2 edge cases test passed")


if __name__ == "__main__":
    test_s2_algorithm_basic()
    test_s2_vs_s1_comparison()
    test_s2_edge_cases()
    print("\n✅ All S2 algorithm tests passed successfully!") 