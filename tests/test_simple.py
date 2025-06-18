"""
Simplified functional tests - no dependency on external network packages
"""

import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_models():
    """Test data models"""
    print("Testing data models...")
    
    # Import models directly, avoiding modules that depend on external packages
    sys.path.insert(0, str(project_root / "core"))
    import models
    PoolMember = models.PoolMember
    Pool = models.Pool
    EngineType = models.EngineType
    
    # Create test members
    member1 = PoolMember("10.10.10.10", 8001, "Common")
    member2 = PoolMember("10.10.10.11", 8001, "Common")
    
    # Set metrics
    member1.metrics = {"waiting_queue": 5.0, "cache_usage": 0.3}
    member2.metrics = {"waiting_queue": 2.0, "cache_usage": 0.6}
    
    # Create Pool
    pool = Pool("test-pool", "Common", EngineType.VLLM, [member1, member2])
    
    print(f"  Pool: {pool.name}, member count: {len(pool.members)}")
    for member in pool.members:
        print(f"    Member: {member}, metrics: {member.metrics}")
    
    return pool


def test_score_calculation():
    """Test score calculation"""
    print("\nTesting score calculation...")
    
    # Import modules directly
    sys.path.insert(0, str(project_root / "core"))
    sys.path.insert(0, str(project_root / "config"))
    import score_calculator
    import config_loader
    ScoreCalculator = score_calculator.ScoreCalculator
    ModeConfig = config_loader.ModeConfig
    
    # Get test Pool
    pool = test_models()
    
    # Create algorithm configuration
    mode_config = ModeConfig(name="s1", w_a=0.3, w_b=0.7)
    
    # Calculate scores
    calculator = ScoreCalculator()
    calculator.calculate_pool_scores(pool, mode_config)
    
    print("  Score calculation results:")
    for member in pool.members:
        print(f"    {member}: score={member.score:.3f}")
    
    return pool


def test_weighted_random():
    """Test weighted random selection"""
    print("\nTesting weighted random selection...")
    
    # Import modules directly
    sys.path.insert(0, str(project_root / "core"))
    import scheduler
    WeightedRandomSelector = scheduler.WeightedRandomSelector
    
    # Get Pool with scores
    pool = test_score_calculation()
    
    # Create selector
    selector = WeightedRandomSelector()
    
    # Multiple selection tests
    results = {}
    for i in range(20):
        selected = selector.select(pool.members)
        if selected:
            key = str(selected)
            results[key] = results.get(key, 0) + 1
    
    print("  Selection results statistics (20 times):")
    for member, count in results.items():
        probability = count / 20
        print(f"    {member}: {count} times ({probability:.1%})")


def test_config_parsing():
    """Test configuration parsing (without loading files)"""
    print("\nTesting configuration parsing...")
    
    # Import modules directly
    sys.path.insert(0, str(project_root / "config"))
    import config_loader
    GlobalConfig = config_loader.GlobalConfig
    F5Config = config_loader.F5Config
    SchedulerConfig = config_loader.SchedulerConfig
    ModeConfig = config_loader.ModeConfig
    
    # Create test configurations
    global_config = GlobalConfig(interval=60, log_debug=True)
    f5_config = F5Config(host="192.168.1.100", port=443, username="admin", password="admin")
    scheduler_config = SchedulerConfig(pool_fetch_interval=30, metrics_fetch_interval=1000)
    mode_config = ModeConfig(name="s1", w_a=0.3, w_b=0.7)
    
    print(f"  Global config: interval={global_config.interval}, debug={global_config.log_debug}")
    print(f"  F5 config: host={f5_config.host}, port={f5_config.port}")
    print(f"  Scheduler config: pool_interval={scheduler_config.pool_fetch_interval}s")
    print(f"  Algorithm config: mode={mode_config.name}, w_a={mode_config.w_a}, w_b={mode_config.w_b}")


def main():
    """Main test function"""
    print("=" * 60)
    print("F5 LLM Inference Gateway Scheduler - Simplified Functional Tests")
    print("=" * 60)
    
    try:
        # Test data models
        test_models()
        
        # Test score calculation
        test_score_calculation()
        
        # Test weighted random selection
        test_weighted_random()
        
        # Test configuration parsing
        test_config_parsing()
        
        print("\n" + "=" * 60)
        print("All tests completed! ✅")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Exception occurred during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 