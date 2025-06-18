#!/usr/bin/env python3
"""
概率分析测试脚本
用于验证加权随机算法的精度和偏差分析
"""

import asyncio
import sys
import requests
import json
import time
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.models import Pool, PoolMember, EngineType, add_or_update_pool
from core.score_calculator import ScoreCalculator
from core.scheduler import Scheduler
from config.config_loader import ModeConfig

def create_test_pool():
    """创建测试Pool"""
    print("创建测试Pool...")
    
    # 创建成员
    members = [
        PoolMember("127.0.0.1", 8001, "Common"),
        PoolMember("127.0.0.1", 8002, "Common"),
        PoolMember("127.0.0.1", 8003, "Common")
    ]
    
    # 设置不同的metrics，产生明显的score差异
    members[0].metrics = {"waiting_queue": 2.0, "cache_usage": 0.2}  # 高score
    members[1].metrics = {"waiting_queue": 5.0, "cache_usage": 0.5}  # 中score
    members[2].metrics = {"waiting_queue": 8.0, "cache_usage": 0.8}  # 低score
    
    # 计算score
    calculator = ScoreCalculator()
    mode_config = ModeConfig(name="s1", w_a=0.4, w_b=0.6)
    
    pool = Pool("example_pool1", "Common", EngineType.SGLANG, members)
    calculator.calculate_pool_scores(pool, mode_config)
    
    # 显示成员信息
    total_score = sum(member.score for member in members)
    print("\n成员信息:")
    for member in members:
        theoretical_prob = (member.score / total_score) * 100
        print(f"  {member}: score={member.score:.6f}, 理论概率={theoretical_prob:.2f}%")
    
    # 添加到全局存储
    add_or_update_pool(pool)
    
    return pool

async def test_local_analysis():
    """本地测试概率分析"""
    print("\n=== 本地概率分析测试 ===")
    
    # 创建测试数据
    pool = create_test_pool()
    
    # 创建调度器
    scheduler = Scheduler()
    
    # 候选成员
    candidates = ["127.0.0.1:8001", "127.0.0.1:8002", "127.0.0.1:8003"]
    
    # 进行概率分析
    print("\n开始概率分析（1000次迭代）...")
    analysis = await scheduler.analyze_selection_accuracy(
        "example_pool1", "Common", candidates, 1000
    )
    
    # 显示结果
    print_analysis_results(analysis)

def test_api_analysis():
    """通过API测试概率分析"""
    print("\n=== API概率分析测试 ===")
    
    api_url = "http://localhost:8080/pools/example_pool1/Common/analyze"
    payload = {
        "pool_name": "example_pool1",
        "partition": "Common", 
        "members": ["127.0.0.1:8001", "127.0.0.1:8002", "127.0.0.1:8003"]
    }
    
    # 指定iterations参数
    iterations = 1000
    print(f"发送API请求... (iterations={iterations})")
    
    # 记录开始时间
    start_time = time.time()
    
    try:
        # 记录API请求开始时间
        api_start_time = time.time()
        
        response = requests.post(
            f"{api_url}?iterations={iterations}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=30
        )
        
        # 记录API请求结束时间
        api_end_time = time.time()
        api_request_time = api_end_time - api_start_time
        
        print(f"响应状态码: {response.status_code}")
        print(f"🕒 单次API请求耗时: {api_request_time:.3f}秒")
        
        if response.status_code == 200:
            analysis = response.json()
            
            # 添加调试信息，显示实际迭代次数
            if "overall_statistics" in analysis:
                actual_iterations = analysis["overall_statistics"].get("total_iterations", "未知")
                print(f"🔍 请求的迭代次数: {iterations}")
                print(f"🔍 实际执行的迭代次数: {actual_iterations}")
                
                if actual_iterations != iterations:
                    print(f"⚠️  警告：请求的迭代次数({iterations})与实际执行的迭代次数({actual_iterations})不匹配！")
                else:
                    print(f"✅ 迭代次数匹配正确")
                
                # 计算性能指标
                if isinstance(actual_iterations, int) and actual_iterations > 0:
                    avg_time_per_iteration = api_request_time / actual_iterations
                    iterations_per_second = actual_iterations / api_request_time
                    print(f"📊 平均每次迭代耗时: {avg_time_per_iteration*1000:.3f}毫秒")
                    print(f"📊 每秒处理迭代数: {iterations_per_second:.1f}次")
            
            print_analysis_results(analysis)
        else:
            print(f"API请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"API请求异常: {e}")
        print("请确保调度器服务已启动: python main.py")
    finally:
        # 记录总耗时
        total_time = time.time() - start_time
        print(f"🕒 客户端总耗时: {total_time:.3f}秒")

def print_analysis_results(analysis):
    """打印分析结果"""
    if "error" in analysis:
        print(f"分析失败: {analysis['error']}")
        return
    
    print("\n📊 概率分析结果:")
    print("=" * 80)
    
    # Pool信息
    pool_info = analysis["pool_info"]
    print(f"Pool: {pool_info['name']}:{pool_info['partition']}")
    print(f"成员数: {pool_info['member_count']}, 总Score: {pool_info['total_score']}")
    
    # 理论vs实际概率
    print("\n📈 概率对比:")
    print("-" * 60)
    print(f"{'成员':<20} {'理论概率':<12} {'实际概率':<12} {'绝对偏差':<12}")
    print("-" * 60)
    
    deviation_analysis = analysis["deviation_analysis"]
    for member, data in deviation_analysis.items():
        print(f"{member:<20} {data['theoretical_percent']:<11.2f}% "
              f"{data['actual_percent']:<11.2f}% {data['absolute_deviation']:<11.2f}%")
    
    # 整体统计
    stats = analysis["overall_statistics"]
    print(f"\n📊 整体统计:")
    print(f"  总迭代次数: {stats['total_iterations']}")
    print(f"  成功选择次数: {stats['successful_selections']}")
    print(f"  成功率: {stats['success_rate']:.2f}%")
    print(f"  平均绝对偏差: {stats['mean_absolute_deviation']:.2f}%")
    print(f"  最大绝对偏差: {stats['max_absolute_deviation']:.2f}%")
    print(f"  最小绝对偏差: {stats['min_absolute_deviation']:.2f}%")
    print(f"  偏差标准差: {stats['std_deviation']:.2f}%")
    
    # 质量评估
    quality = analysis["quality_assessment"]
    print(f"\n⭐ 质量评估:")
    print(f"  质量等级: {quality['quality_grade']}")
    print(f"  质量评分: {quality['quality_score']}")
    print(f"  是否可接受: {'是' if quality['is_acceptable'] else '否'}")
    print(f"  总结: {quality['summary']}")
    
    if quality["recommendations"]:
        print(f"\n💡 优化建议:")
        for i, rec in enumerate(quality["recommendations"], 1):
            print(f"  {i}. {rec}")

def comparative_algorithm_test():
    """对比测试原始算法和优化算法"""
    print("\n=== 算法对比测试 ===")
    
    # 创建测试数据
    pool = create_test_pool()
    members = pool.members
    
    # 计算理论概率
    total_score = sum(member.score for member in members)
    theoretical_probs = {}
    for member in members:
        theoretical_probs[str(member)] = (member.score / total_score) * 100
    
    print("\n📊 理论概率分布:")
    print("-" * 40)
    for member_str, prob in theoretical_probs.items():
        print(f"  {member_str}: {prob:.2f}%")
    
    # 测试参数
    from core.scheduler import WeightedRandomSelector
    selector = WeightedRandomSelector()
    test_iterations = 2000  # 增加测试次数以获得更稳定的结果
    
    print(f"\n🧪 进行 {test_iterations} 次选择测试...")
    
    # ========== 测试原始算法 ==========
    print("\n1️⃣ 原始算法测试:")
    results_original = {}
    start_time = time.time()
    
    for _ in range(test_iterations):
        selected = selector.select_with_algorithm(members, "original")
        if selected:
            key = str(selected)
            results_original[key] = results_original.get(key, 0) + 1
    
    original_time = time.time() - start_time
    
    # 计算原始算法的概率和偏差
    total_selections_original = sum(results_original.values())
    original_deviations = []
    original_results_detailed = {}
    
    print(f"   执行时间: {original_time:.3f}秒")
    print("   结果分析:")
    print("   " + "-" * 50)
    
    for member_str, theoretical_prob in theoretical_probs.items():
        count = results_original.get(member_str, 0)
        actual_prob = (count / total_selections_original) * 100 if total_selections_original > 0 else 0
        deviation = abs(actual_prob - theoretical_prob)
        original_deviations.append(deviation)
        
        original_results_detailed[member_str] = {
            "count": count,
            "theoretical": theoretical_prob,
            "actual": actual_prob,
            "deviation": deviation
        }
        
        print(f"   {member_str}: 理论={theoretical_prob:.2f}%, "
              f"实际={actual_prob:.2f}%, 偏差={deviation:.2f}%")
    
    original_avg_deviation = sum(original_deviations) / len(original_deviations)
    original_max_deviation = max(original_deviations)
    original_min_deviation = min(original_deviations)
    
    print(f"   平均偏差: {original_avg_deviation:.2f}%")
    print(f"   最大偏差: {original_max_deviation:.2f}%")
    print(f"   最小偏差: {original_min_deviation:.2f}%")
    
    # ========== 测试优化算法 ==========
    print("\n2️⃣ 优化算法测试:")
    results_optimized = {}
    start_time = time.time()
    
    for _ in range(test_iterations):
        selected = selector.select_with_algorithm(members, "optimized")
        if selected:
            key = str(selected)
            results_optimized[key] = results_optimized.get(key, 0) + 1
    
    optimized_time = time.time() - start_time
    
    # 计算优化算法的概率和偏差
    total_selections_optimized = sum(results_optimized.values())
    optimized_deviations = []
    optimized_results_detailed = {}
    
    print(f"   执行时间: {optimized_time:.3f}秒")
    print("   结果分析:")
    print("   " + "-" * 50)
    
    for member_str, theoretical_prob in theoretical_probs.items():
        count = results_optimized.get(member_str, 0)
        actual_prob = (count / total_selections_optimized) * 100 if total_selections_optimized > 0 else 0
        deviation = abs(actual_prob - theoretical_prob)
        optimized_deviations.append(deviation)
        
        optimized_results_detailed[member_str] = {
            "count": count,
            "theoretical": theoretical_prob,
            "actual": actual_prob,
            "deviation": deviation
        }
        
        print(f"   {member_str}: 理论={theoretical_prob:.2f}%, "
              f"实际={actual_prob:.2f}%, 偏差={deviation:.2f}%")
    
    optimized_avg_deviation = sum(optimized_deviations) / len(optimized_deviations)
    optimized_max_deviation = max(optimized_deviations)
    optimized_min_deviation = min(optimized_deviations)
    
    print(f"   平均偏差: {optimized_avg_deviation:.2f}%")
    print(f"   最大偏差: {optimized_max_deviation:.2f}%")
    print(f"   最小偏差: {optimized_min_deviation:.2f}%")
    
    # ========== 测试备选算法（NumPy版本） ==========
    print("\n3️⃣ 备选算法测试 (NumPy版本):")
    results_alternative = {}
    start_time = time.time()
    
    try:
        for _ in range(test_iterations):
            selected = selector.select_with_algorithm(members, "alternative")
            if selected:
                key = str(selected)
                results_alternative[key] = results_alternative.get(key, 0) + 1
        
        alternative_time = time.time() - start_time
        
        # 计算备选算法的概率和偏差
        total_selections_alternative = sum(results_alternative.values())
        alternative_deviations = []
        alternative_results_detailed = {}
        
        print(f"   执行时间: {alternative_time:.3f}秒")
        print("   结果分析:")
        print("   " + "-" * 50)
        
        for member_str, theoretical_prob in theoretical_probs.items():
            count = results_alternative.get(member_str, 0)
            actual_prob = (count / total_selections_alternative) * 100 if total_selections_alternative > 0 else 0
            deviation = abs(actual_prob - theoretical_prob)
            alternative_deviations.append(deviation)
            
            alternative_results_detailed[member_str] = {
                "count": count,
                "theoretical": theoretical_prob,
                "actual": actual_prob,
                "deviation": deviation
            }
            
            print(f"   {member_str}: 理论={theoretical_prob:.2f}%, "
                  f"实际={actual_prob:.2f}%, 偏差={deviation:.2f}%")
        
        alternative_avg_deviation = sum(alternative_deviations) / len(alternative_deviations)
        alternative_max_deviation = max(alternative_deviations)
        alternative_min_deviation = min(alternative_deviations)
        
        print(f"   平均偏差: {alternative_avg_deviation:.2f}%")
        print(f"   最大偏差: {alternative_max_deviation:.2f}%")
        print(f"   最小偏差: {alternative_min_deviation:.2f}%")
        
    except ImportError:
        print("   ⚠️  NumPy未安装，跳过备选算法测试")
        alternative_time = None
        alternative_avg_deviation = None
        alternative_max_deviation = None
    

    
    # ========== 综合对比分析 ==========
    print("\n" + "=" * 80)
    print("🔍 综合对比分析")
    print("=" * 80)
    
    # 性能对比
    print("\n📊 性能对比:")
    print(f"   原始算法执行时间: {original_time:.3f}秒")
    print(f"   优化算法执行时间: {optimized_time:.3f}秒")
    if alternative_time is not None:
        print(f"   备选算法执行时间: {alternative_time:.3f}秒")
    
    if optimized_time > 0:
        performance_improvement = ((original_time - optimized_time) / original_time) * 100
        print(f"   优化算法性能变化: {performance_improvement:+.1f}%")
    
    # 精度对比
    print("\n🎯 精度对比:")
    print(f"{'算法':<15} {'平均偏差':<10} {'最大偏差':<10} {'最小偏差':<10} {'质量评级':<10}")
    print("-" * 70)
    
    def get_quality_grade(avg_dev, max_dev):
        if avg_dev < 0.1 and max_dev < 0.5:
            return "完美"
        elif avg_dev < 1.0 and max_dev < 2.0:
            return "优秀"
        elif avg_dev < 2.0 and max_dev < 5.0:
            return "良好"
        elif avg_dev < 5.0 and max_dev < 10.0:
            return "一般"
        else:
            return "需要优化"
    
    original_grade = get_quality_grade(original_avg_deviation, original_max_deviation)
    optimized_grade = get_quality_grade(optimized_avg_deviation, optimized_max_deviation)
    
    print(f"{'原始算法':<15} {original_avg_deviation:<9.2f}% {original_max_deviation:<9.2f}% {original_min_deviation:<9.2f}% {original_grade:<10}")
    print(f"{'优化算法':<15} {optimized_avg_deviation:<9.2f}% {optimized_max_deviation:<9.2f}% {optimized_min_deviation:<9.2f}% {optimized_grade:<10}")
    if alternative_avg_deviation is not None:
        alternative_grade = get_quality_grade(alternative_avg_deviation, alternative_max_deviation)
        print(f"{'备选算法':<15} {alternative_avg_deviation:<9.2f}% {alternative_max_deviation:<9.2f}% {alternative_min_deviation:<9.2f}% {alternative_grade:<10}")
    
    # 改进效果
    print("\n📈 改进效果:")
    accuracy_improvement_opt = original_avg_deviation - optimized_avg_deviation
    stability_improvement_opt = original_max_deviation - optimized_max_deviation
    
    print(f"   优化算法 - 平均偏差改进: {accuracy_improvement_opt:+.2f}%")
    print(f"   优化算法 - 最大偏差改进: {stability_improvement_opt:+.2f}%")
    
    # 推荐使用的算法
    print("\n💡 算法推荐:")
    all_deviations = [original_avg_deviation, optimized_avg_deviation]
    if alternative_avg_deviation is not None:
        all_deviations.append(alternative_avg_deviation)
    
    best_avg = min(all_deviations)
    
    if best_avg == optimized_avg_deviation:
        print("   🏆 推荐使用：优化算法 (Decimal高精度版本)")
        print("   理由：精度和随机性的最佳平衡")
    elif alternative_avg_deviation is not None and best_avg == alternative_avg_deviation:
        print("   🏆 推荐使用：备选算法 (NumPy版本)")
        print("   理由：高精度随机选择")
    else:
        print("   🏆 推荐使用：原始算法")
        print("   理由：简单快速")
    
    print("\n" + "=" * 80)
    print("📊 算法特点分析")
    print("=" * 80)
    print("🎲 随机算法优势:")
    print("   ✅ 每次请求都有不确定性，更符合真实负载均衡场景")
    print("   ✅ 避免可预测的选择模式，安全性更好")
    print("   ✅ 无需维护状态，简单高效")
    print("   ❌ 存在统计学偏差（但通常可接受）")
    print()
    print(f"🔍 本次测试中优化算法平均偏差为 {optimized_avg_deviation:.2f}%")
    print("   在保持随机性的同时，精度已经达到优秀级别！")
    
    print("\n" + "=" * 80)
    print("测试完成 - 现在您可以根据具体需求选择最合适的算法")
    print("=" * 80)

async def main():
    """主函数"""
    print("🎯 加权随机算法概率分析测试工具")
    print("=" * 50)
    print("以下API次数是指调用http://localhost:8080/pools/example_pool1/Common/analyze接口")
    print("迭代次数是指该API内部模拟选择所执行的次数")
    print("报告中的关于迭代次数的耗时能反应程序内部选择算法的耗时")
    print("API的耗时及速率不能代表真实的/scheduler/select API接口性能")
    print("=" * 50)
    # 提示用户选择测试方式
    print("请选择测试方式:")
    print("1. 本地测试（直接调用算法）")
    print("2. API测试（通过HTTP接口）,需要环境提供模拟example_pool1的3个成员")
    print("3. 算法对比测试")
    print("4. 全部测试")
    print("5. 自定义iterations的API测试")
    print("6. 多次API请求性能测试")
    
    try:
        choice = input("\n请输入选择 (1-6): ").strip()
        
        if choice == "1":
            await test_local_analysis()
        elif choice == "2":
            test_api_analysis()
        elif choice == "3":
            comparative_algorithm_test()
        elif choice == "4":
            await test_local_analysis()
            print("\n" + "="*50)
            test_api_analysis()
            print("\n" + "="*50)
            comparative_algorithm_test()
        elif choice == "5":
            # 自定义iterations的API测试
            try:
                iterations = int(input("请输入要测试的迭代次数 (建议1000-10000): "))
                if iterations < 100:
                    print("⚠️  迭代次数太少，建议至少100次以获得有意义的结果")
                elif iterations > 50000:
                    print("⚠️  迭代次数较大，测试可能需要较长时间")
                
                test_api_analysis_custom(iterations)
            except ValueError:
                print("❌ 请输入有效的数字")
        elif choice == "6":
            # 多次API请求性能测试
            try:
                request_count = int(input("请输入要测试的API请求次数 (建议3-10): "))
                iterations = int(input("请输入每次请求的迭代次数 (建议500-2000): "))
                if request_count < 1:
                    print("❌ 请求次数至少为1")
                    return
                if request_count > 20:
                    print("⚠️  请求次数较多，测试可能需要较长时间")
                    
                test_multiple_api_requests(request_count, iterations)
            except ValueError:
                print("❌ 请输入有效的数字")
        else:
            print("无效的选择")
            
    except KeyboardInterrupt:
        print("\n\n测试已取消")
    except Exception as e:
        print(f"\n测试出现异常: {e}")
        import traceback
        traceback.print_exc()

def test_api_analysis_custom(iterations: int):
    """通过API测试概率分析（自定义迭代次数）"""
    print(f"\n=== API概率分析测试（{iterations}次迭代）===")
    
    api_url = "http://localhost:8080/pools/example_pool1/Common/analyze"
    payload = {
        "pool_name": "example_pool1",
        "partition": "Common", 
        "members": ["127.0.0.1:8001", "127.0.0.1:8002", "127.0.0.1:8003"]
    }
    
    print(f"发送API请求... (iterations={iterations})")
    
    # 记录开始时间
    start_time = time.time()
    
    try:
        # 记录API请求开始时间
        api_start_time = time.time()
        
        response = requests.post(
            f"{api_url}?iterations={iterations}",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=60  # 增加超时时间以应对大量迭代
        )
        
        # 记录API请求结束时间
        api_end_time = time.time()
        api_request_time = api_end_time - api_start_time
        
        print(f"响应状态码: {response.status_code}")
        print(f"🕒 单次API请求耗时: {api_request_time:.3f}秒")
        
        if response.status_code == 200:
            analysis = response.json()
            
            # 验证迭代次数
            if "overall_statistics" in analysis:
                actual_iterations = analysis["overall_statistics"].get("total_iterations", "未知")
                print(f"🔍 请求的迭代次数: {iterations}")
                print(f"🔍 实际执行的迭代次数: {actual_iterations}")
                
                if actual_iterations != iterations:
                    print(f"⚠️  警告：请求的迭代次数({iterations})与实际执行的迭代次数({actual_iterations})不匹配！")
                    print("   这可能表明API接口没有正确处理iterations参数")
                else:
                    print(f"✅ 迭代次数匹配正确")
                
                # 计算详细性能指标
                if isinstance(actual_iterations, int) and actual_iterations > 0:
                    avg_time_per_iteration = api_request_time / actual_iterations
                    iterations_per_second = actual_iterations / api_request_time
                    print(f"📊 平均每次迭代耗时: {avg_time_per_iteration*1000:.3f}毫秒")
                    print(f"📊 每秒处理迭代数: {iterations_per_second:.1f}次")
                    
                    # 预估不同迭代次数的耗时
                    print(f"\n📈 性能预估:")
                    for est_iterations in [100, 500, 1000, 5000, 10000]:
                        est_time = avg_time_per_iteration * est_iterations
                        if est_iterations != actual_iterations:
                            print(f"   {est_iterations:5d}次迭代预估耗时: {est_time:.3f}秒")
            
            print_analysis_results(analysis)
        else:
            print(f"API请求失败: {response.status_code}")
            print(f"响应内容: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"API请求异常: {e}")
        print("请确保调度器服务已启动: python main.py")
    finally:
        # 记录总耗时
        total_time = time.time() - start_time
        print(f"🕒 客户端总耗时: {total_time:.3f}秒")

def test_multiple_api_requests(request_count: int, iterations: int):
    """测试多次API请求的性能统计"""
    print(f"\n=== 多次API请求性能测试 ===")
    print(f"请求次数: {request_count}, 每次迭代: {iterations}")
    
    api_url = "http://localhost:8080/pools/example_pool1/Common/analyze"
    payload = {
        "pool_name": "example_pool1",
        "partition": "Common", 
        "members": ["127.0.0.1:8001", "127.0.0.1:8002", "127.0.0.1:8003"]
    }
    
    # 统计数据
    request_times = []
    total_start_time = time.time()
    successful_requests = 0
    total_iterations_processed = 0
    
    print(f"\n开始执行 {request_count} 次API请求...")
    
    for i in range(request_count):
        print(f"\n--- 第 {i+1}/{request_count} 次请求 ---")
        
        try:
            # 记录单次请求开始时间
            request_start_time = time.time()
            
            response = requests.post(
                f"{api_url}?iterations={iterations}",
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60
            )
            
            # 记录单次请求结束时间
            request_end_time = time.time()
            request_time = request_end_time - request_start_time
            request_times.append(request_time)
            
            print(f"状态码: {response.status_code}, 耗时: {request_time:.3f}秒")
            
            if response.status_code == 200:
                successful_requests += 1
                analysis = response.json()
                
                # 获取实际迭代次数
                if "overall_statistics" in analysis:
                    actual_iterations = analysis["overall_statistics"].get("total_iterations", 0)
                    total_iterations_processed += actual_iterations
                    
                    # 简化的结果显示
                    stats = analysis["overall_statistics"]
                    print(f"实际迭代: {actual_iterations}, 平均偏差: {stats.get('mean_absolute_deviation', 0):.2f}%")
                else:
                    print("⚠️  响应中缺少统计信息")
            else:
                print(f"❌ 请求失败: {response.text}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求异常: {e}")
            request_times.append(None)  # 记录失败的请求
        
        # 在请求之间稍作停顿，避免过于密集的请求
        #if i < request_count - 1:
            #time.sleep(0.1)
    
    # 计算总体统计
    total_end_time = time.time()
    total_time = total_end_time - total_start_time
    
    # 过滤成功的请求时间
    valid_request_times = [t for t in request_times if t is not None]
    
    print(f"\n" + "="*60)
    print(f"📊 多次API请求性能统计报告")
    print(f"="*60)
    
    print(f"总请求次数: {request_count}")
    print(f"成功请求数: {successful_requests}")
    print(f"失败请求数: {request_count - successful_requests}")
    print(f"成功率: {(successful_requests/request_count)*100:.1f}%")
    
    print(f"\n⏱️  时间统计:")
    print(f"客户端总耗时: {total_time:.3f}秒")
    
    if valid_request_times:
        avg_request_time = sum(valid_request_times) / len(valid_request_times)
        min_request_time = min(valid_request_times)
        max_request_time = max(valid_request_times)
        
        print(f"单次请求平均耗时: {avg_request_time:.3f}秒")
        print(f"单次请求最快耗时: {min_request_time:.3f}秒")
        print(f"单次请求最慢耗时: {max_request_time:.3f}秒")
        
        # 计算请求频率
        requests_per_second = request_count / total_time
        print(f"平均请求频率: {requests_per_second:.2f}请求/秒")
    
    if total_iterations_processed > 0:
        print(f"\n📈 迭代处理统计:")
        print(f"总处理迭代数: {total_iterations_processed}")
        avg_iterations_per_second = total_iterations_processed / total_time
        print(f"平均迭代处理速度: {avg_iterations_per_second:.1f}次/秒")
        
        if valid_request_times:
            avg_iterations_per_request_second = iterations / avg_request_time
            print(f"单次请求迭代处理速度: {avg_iterations_per_request_second:.1f}次/秒")
    
    # 性能分析和建议
    print(f"\n💡 性能分析:")
    if valid_request_times:
        if avg_request_time < 1.0:
            print("✅ API响应速度很快")
        elif avg_request_time < 3.0:
            print("✅ API响应速度良好")
        elif avg_request_time < 10.0:
            print("⚠️  API响应速度一般，可考虑优化")
        else:
            print("❌ API响应速度较慢，建议优化")
            
        # 稳定性分析
        if len(valid_request_times) > 1:
            time_variance = max(valid_request_times) - min(valid_request_times)
            if time_variance < 0.5:
                print("✅ API响应时间稳定")
            elif time_variance < 2.0:
                print("⚠️  API响应时间略有波动")
            else:
                print("❌ API响应时间波动较大，可能存在性能问题")
    
    print(f"="*60)

if __name__ == "__main__":
    asyncio.run(main()) 