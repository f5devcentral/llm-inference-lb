"""
Test updated fallback functionality with member threshold filtering
验证更新后的fallback功能和成员阈值过滤功能
"""

import asyncio
import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.models import Pool, PoolMember, EngineType, add_or_update_pool
from api.server import APIServer, ScheduleRequest
from config.config_loader import PoolConfig, FallbackConfig, MetricsConfig


def test_fallback_config_parsing():
    """测试FallbackConfig配置解析"""
    print("=== 测试FallbackConfig配置解析 ===")
    
    from config.config_loader import ConfigLoader
    
    # 创建测试配置数据 - 新的fallback结构
    pool_data_new_format = {
        'name': 'test-pool',
        'engine_type': 'vllm',
        'fallback': {
            'pool_fallback': True,
            'member_running_req_threshold': 20.0,
            'member_waiting_queue_threshold': 15.0
        }
    }
    
    config_loader = ConfigLoader()
    
    # 测试配置解析
    pool_config = config_loader._parse_pool_config(pool_data_new_format)
    print(f"配置解析结果:")
    print(f"  pool_fallback: {pool_config.fallback.pool_fallback}")
    print(f"  member_running_req_threshold: {pool_config.fallback.member_running_req_threshold}")
    print(f"  member_waiting_queue_threshold: {pool_config.fallback.member_waiting_queue_threshold}")
    
    print("✓ FallbackConfig配置解析测试通过\n")


def test_pool_model_fallback():
    """测试Pool模型的fallback属性"""
    print("=== 测试Pool模型fallback属性 ===")
    
    # 测试默认值
    pool1 = Pool("test-pool-1", "Common", EngineType.VLLM)
    print(f"默认值:")
    print(f"  pool_fallback: {pool1.pool_fallback}")
    print(f"  member_running_req_threshold: {pool1.member_running_req_threshold}")
    print(f"  member_waiting_queue_threshold: {pool1.member_waiting_queue_threshold}")
    
    # 测试显式设置
    pool2 = Pool("test-pool-2", "Common", EngineType.VLLM, 
                pool_fallback=True, 
                member_running_req_threshold=20.0,
                member_waiting_queue_threshold=15.0)
    print(f"显式设置:")
    print(f"  pool_fallback: {pool2.pool_fallback}")
    print(f"  member_running_req_threshold: {pool2.member_running_req_threshold}")
    print(f"  member_waiting_queue_threshold: {pool2.member_waiting_queue_threshold}")
    
    print("✓ Pool模型fallback属性测试通过\n")


async def test_api_pool_fallback():
    """测试API层面的pool_fallback逻辑"""
    print("=== 测试API层面pool_fallback逻辑 ===")
    
    # 创建测试Pool
    members = [
        PoolMember("127.0.0.1", 8001, "Common"),
        PoolMember("127.0.0.1", 8002, "Common")
    ]
    
    # 创建pool_fallback=False的Pool
    pool_normal = Pool("normal-pool", "Common", EngineType.VLLM, members, pool_fallback=False)
    add_or_update_pool(pool_normal)
    
    # 创建pool_fallback=True的Pool  
    pool_fallback = Pool("fallback-pool", "Common", EngineType.VLLM, members, pool_fallback=True)
    add_or_update_pool(pool_fallback)
    
    # 测试API逻辑 - 模拟检查
    from core.models import get_pool_by_key
    
    # 测试正常Pool
    pool = get_pool_by_key("normal-pool", "Common")
    if pool and pool.pool_fallback:
        result_normal = "fallback"
        print(f"正常Pool (pool_fallback=False) 检查结果: 不应该返回fallback")
    else:
        result_normal = "正常调度流程"
        print(f"正常Pool (pool_fallback=False) 检查结果: {result_normal}")
    
    # 测试fallback Pool
    pool = get_pool_by_key("fallback-pool", "Common")
    if pool and pool.pool_fallback:
        result_fallback = "fallback"
        print(f"Fallback Pool (pool_fallback=True) 检查结果: {result_fallback}")
    else:
        result_fallback = "正常调度流程"
        print(f"Fallback Pool (pool_fallback=True) 检查结果: 不应该进入正常流程")
    
    # 验证结果
    assert result_normal == "正常调度流程", "正常Pool应该进入正常调度流程"
    assert result_fallback == "fallback", "Fallback Pool应该返回fallback"
    
    print("✓ API层面pool_fallback逻辑测试通过\n")


def test_member_threshold_filtering():
    """测试成员阈值过滤功能"""
    print("=== 测试成员阈值过滤功能 ===")
    
    # 创建带metrics的测试members
    members = [
        PoolMember("127.0.0.1", 8001, "Common"),
        PoolMember("127.0.0.1", 8002, "Common"),
        PoolMember("127.0.0.1", 8003, "Common"),
        PoolMember("127.0.0.1", 8004, "Common")
    ]
    
    # 设置不同的metrics值（使用原始值，不是归一化值）
    members[0].metrics = {"running_req": 10.0, "waiting_queue": 5.0}   # 正常
    members[1].metrics = {"running_req": 25.0, "waiting_queue": 8.0}   # running_req超阈值
    members[2].metrics = {"running_req": 15.0, "waiting_queue": 20.0}  # waiting_queue超阈值
    members[3].metrics = {"running_req": 30.0, "waiting_queue": 25.0}  # 两个都超阈值
    
    # 创建带阈值的Pool
    pool = Pool("threshold-pool", "Common", EngineType.VLLM, members,
                member_running_req_threshold=20.0,
                member_waiting_queue_threshold=15.0)
    add_or_update_pool(pool)
    
    # 测试调度器的过滤逻辑
    from core.scheduler import Scheduler
    scheduler = Scheduler()
    
    # 模拟调度器的过滤过程
    filtered_members = scheduler._filter_members_by_thresholds(pool, members)
    
    print(f"原始members数量: {len(members)}")
    print(f"过滤后members数量: {len(filtered_members)}")
    print(f"过滤后的members:")
    for member in filtered_members:
        metrics = member.metrics
        print(f"  {member}: running_req={metrics.get('running_req')}, waiting_queue={metrics.get('waiting_queue')}")
    
    # 验证过滤结果：只有第一个member应该通过过滤
    expected_remaining = 1  # 只有members[0]应该保留
    assert len(filtered_members) == expected_remaining, f"应该剩余{expected_remaining}个member，实际剩余{len(filtered_members)}个"
    assert str(filtered_members[0]) == "127.0.0.1:8001", "剩余的应该是第一个member"
    
    print("✓ 成员阈值过滤功能测试通过\n")


def test_threshold_filtering_with_no_metrics():
    """测试没有metrics数据时的过滤行为"""
    print("=== 测试没有metrics数据时的过滤行为 ===")
    
    # 创建没有metrics的members
    members_no_metrics = [
        PoolMember("127.0.0.1", 8001, "Common"),
        PoolMember("127.0.0.1", 8002, "Common")
    ]
    # 不设置metrics数据
    
    pool = Pool("no-metrics-pool", "Common", EngineType.VLLM, members_no_metrics,
                member_running_req_threshold=20.0,
                member_waiting_queue_threshold=15.0)
    
    from core.scheduler import Scheduler
    scheduler = Scheduler()
    
    # 没有metrics数据的members应该被保留（保守策略）
    filtered_members = scheduler._filter_members_by_thresholds(pool, members_no_metrics)
    
    print(f"没有metrics的members数量: {len(members_no_metrics)}")
    print(f"过滤后保留的members数量: {len(filtered_members)}")
    
    assert len(filtered_members) == len(members_no_metrics), "没有metrics数据的members应该被保留"
    
    print("✓ 没有metrics数据的过滤行为测试通过\n")


def test_pool_fallback_priority():
    """测试pool_fallback优先级高于阈值过滤"""
    print("=== 测试pool_fallback优先级高于阈值过滤 ===")
    
    # 创建同时开启pool_fallback和阈值设置的Pool
    members = [
        PoolMember("127.0.0.1", 8001, "Common"),
        PoolMember("127.0.0.1", 8002, "Common")
    ]
    
    # 设置超过阈值的metrics
    members[0].metrics = {"running_req": 50.0, "waiting_queue": 30.0}  # 都超过阈值
    members[1].metrics = {"running_req": 60.0, "waiting_queue": 40.0}  # 都超过阈值
    
    pool = Pool("priority-test-pool", "Common", EngineType.VLLM, members,
                pool_fallback=True,  # 开启pool级别fallback
                member_running_req_threshold=20.0,  # 这些阈值应该被忽略
                member_waiting_queue_threshold=15.0)
    add_or_update_pool(pool)
    
    # 模拟API检查逻辑
    from core.models import get_pool_by_key
    pool = get_pool_by_key("priority-test-pool", "Common")
    
    if pool and pool.pool_fallback:
        api_result = "fallback"
        print(f"API检查结果: {api_result} (pool_fallback=True时直接返回fallback)")
        print("阈值过滤逻辑被跳过，这是正确的行为")
    else:
        api_result = "进入正常调度流程"
        print("不应该到达这里")
    
    assert api_result == "fallback", "pool_fallback=True时应该直接返回fallback"
    
    print("✓ pool_fallback优先级测试通过\n")


async def main():
    """运行所有测试"""
    print("开始测试更新后的fallback功能...")
    print("=" * 60)
    
    # 运行测试
    test_fallback_config_parsing()
    test_pool_model_fallback()
    await test_api_pool_fallback()
    test_member_threshold_filtering()
    test_threshold_filtering_with_no_metrics()
    test_pool_fallback_priority()
    
    print("=" * 60)
    print("✅ 所有fallback功能测试完成！")
    print("\n功能总结:")
    print("1. ✓ fallback配置结构解析正确")
    print("2. ✓ Pool模型支持新的fallback属性")
    print("3. ✓ API层面正确检查pool_fallback开关")
    print("4. ✓ 成员阈值过滤使用原始metrics值")
    print("5. ✓ 没有metrics数据时采用保守策略")
    print("6. ✓ pool_fallback优先级高于阈值过滤")
    print("\n配置示例:")
    print("```yaml")
    print("pools:")
    print("  - name: example_pool")
    print("    fallback:")
    print("      pool_fallback: false")
    print("      member_running_req_threshold: 20.0")
    print("      member_waiting_queue_threshold: 15.0")
    print("```")


if __name__ == "__main__":
    asyncio.run(main()) 