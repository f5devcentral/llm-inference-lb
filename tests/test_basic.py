"""
Basic functionality tests
"""

import sys
import asyncio
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.models import PoolMember, Pool, EngineType
from core.score_calculator import ScoreCalculator
from core.scheduler import Scheduler
from config.config_loader import ModeConfig


async def test_score_calculation():
    """Test score calculation functionality"""
    print("Testing score calculation functionality...")
    
    # Create test data
    members = [
        PoolMember("10.10.10.10", 8001, "Common"),
        PoolMember("10.10.10.11", 8001, "Common"),
        PoolMember("10.10.10.12", 8001, "Common")
    ]
    
    # Set test metrics
    members[0].metrics = {"waiting_queue": 5.0, "cache_usage": 0.3, "running_req": 2.0}
    members[1].metrics = {"waiting_queue": 2.0, "cache_usage": 0.6, "running_req": 4.0}
    members[2].metrics = {"waiting_queue": 8.0, "cache_usage": 0.1, "running_req": 1.0}
    
    pool = Pool("test-pool", "Common", EngineType.VLLM, members)
    
    # Test S1 algorithm
    mode_config_s1 = ModeConfig(name="s1", w_a=0.3, w_b=0.7)
    calculator = ScoreCalculator()
    calculator.calculate_pool_scores(pool, mode_config_s1)
    
    print("S1 algorithm results:")
    for member in members:
        print(f"  {member}: score={member.score:.3f}, metrics={member.metrics}")
    
    # Test S2 algorithm
    mode_config_s2 = ModeConfig(name="s2", w_a=0.3, w_b=0.4, w_g=0.3)
    calculator.calculate_pool_scores(pool, mode_config_s2)
    
    print("S2 algorithm results:")
    for member in members:
        print(f"  {member}: score={member.score:.3f}, metrics={member.metrics}")
    
    return pool


async def test_scheduler():
    """Test scheduler functionality"""
    print("\nTesting scheduler functionality...")
    
    # Use previously calculated pool
    pool = await test_score_calculation()
    
    # Add pool to global storage
    from core.models import add_or_update_pool
    add_or_update_pool(pool)
    
    # Create scheduler
    scheduler = Scheduler()
    
    # Test optimal member selection
    candidates = ["10.10.10.10:8001", "10.10.10.11:8001", "10.10.10.12:8001"]
    
    print(f"\nCandidate members: {candidates}")
    
    # Multiple selections to test weighted random algorithm
    results = {}
    for i in range(20):
        selected = scheduler.select_optimal_member("test-pool", "Common", candidates)
        if selected:
            results[selected] = results.get(selected, 0) + 1
    
    print("\nSelection results statistics (20 times):")
    for member, count in results.items():
        probability = count / 20
        print(f"  {member}: {count} times ({probability:.1%})")


async def test_config_loading():
    """Test configuration loading functionality"""
    print("\nTesting configuration loading functionality...")
    
    try:
        from config.config_loader import load_config
        config = load_config()
        
        print("Configuration loaded successfully:")
        print(f"  F5 host: {config.f5.host}")
        print(f"  Pool count: {len(config.pools)}")
        for pool in config.pools:
            print(f"    - {pool.name} ({pool.engine_type})")
        
        return True
    except Exception as e:
        print(f"Configuration loading failed: {e}")
        return False


async def main():
    """Main test function"""
    print("=" * 50)
    print("F5 LLM Inference Gateway Scheduler Basic Functionality Tests")
    print("=" * 50)
    
    try:
        # Test configuration loading
        await test_config_loading()
        
        # Test score calculation
        await test_score_calculation()
        
        # Test scheduler
        await test_scheduler()
        
        print("\n" + "=" * 50)
        print("All tests completed!")
        print("=" * 50)
        
    except Exception as e:
        print(f"\nException occurred during testing: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main()) 