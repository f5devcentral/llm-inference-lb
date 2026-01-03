"""
API Key管理器 - 协调XInference客户端和F5 DataGroup客户端
包含故障处理和恢复逻辑
"""

import asyncio
import time
from enum import Enum
from typing import Dict, Optional, List
from dataclasses import dataclass

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from core.models import Pool, EngineType
from core.xinference_apikey_client import XInferenceApiKeyClient
from core.f5_datagroup_client import F5DataGroupClient


class FailureMode(Enum):
    """故障处理模式"""
    PRESERVE = "preserve"    # 保持现有datagroup
    CLEAR = "clear"         # 清空datagroup  
    SMART = "smart"         # 智能处理


@dataclass
class PoolSyncStatus:
    """Pool同步状态"""
    pool_name: str
    last_success_time: float = 0
    consecutive_failures: int = 0
    total_failures: int = 0
    last_error: str = ""
    is_healthy: bool = True
    last_model_count: int = 0  # 上次同步的模型数量
    last_key_count: int = 0    # 上次同步的key总数
    total_syncs: int = 0       # 总同步次数


class ApiKeyManager:
    """API Key管理器"""
    
    def __init__(self, f5_datagroup_client: F5DataGroupClient):
        self.f5_datagroup_client = f5_datagroup_client
        self.xinference_client = XInferenceApiKeyClient()
        self.logger = get_logger()
        
        # 故障处理配置 - 默认值，可通过配置覆盖
        self.failure_mode = FailureMode.PRESERVE  # 默认保守策略
        self.max_failures_before_action = 10      # 连续失败次数阈值
        self.failure_timeout_hours = 2            # 失败超时时间（小时）
        
        # 状态跟踪
        self.pool_status: Dict[str, PoolSyncStatus] = {}
        self.running = False
    
    async def sync_pool_api_keys(self, pool: Pool) -> bool:
        """同步单个pool的API keys - 增强错误处理和变化检测"""
        config = pool.model_APIkey
        pool_key = f"{pool.name}_{pool.partition}"
        
        if not config:
            self.logger.debug(f"Pool {pool.name} has no model_APIkey configuration")
            return True
        
        # 应用pool级别的故障处理配置
        self._apply_pool_config(config)
        
        # 初始化状态跟踪
        if pool_key not in self.pool_status:
            self.pool_status[pool_key] = PoolSyncStatus(pool_name=pool.name)
        
        status = self.pool_status[pool_key]
        
        try:
            self.logger.info(f"Starting API key sync for pool {pool.name}")
            
            # 1. 获取当前F5 datagroup中的记录（用于变化检测）
            current_f5_records = await self.f5_datagroup_client.get_datagroup_records(
                name=config.f5datagroup,
                partition=pool.partition
            )
            
            # 2. 尝试从XInference获取API keys
            async with self.xinference_client:
                api_keys_data = await self.xinference_client.fetch_pool_api_keys(pool, config)
            
            if not api_keys_data:
                # 空数据处理策略
                await self._handle_empty_api_keys_data(pool, config, current_f5_records)
                return True
            
            # 3. 转换为datagroup格式并检测变化
            new_datagroup_records = {}
            for datagroup_key, api_keys_list in api_keys_data.items():
                if api_keys_list:  # 只添加非空的key列表
                    # 按文档格式：多个API key用逗号分隔，去重并排序保证一致性
                    unique_keys = sorted(list(set(api_keys_list)))
                    new_datagroup_records[datagroup_key] = ",".join(unique_keys)
            
            # 4. 检测并记录变化
            changes = self._detect_datagroup_changes(current_f5_records, new_datagroup_records, pool.name)
            
            # 5. 同步到F5 datagroup
            sync_success = await self.f5_datagroup_client.sync_datagroup_records(
                name=config.f5datagroup,
                records=new_datagroup_records,
                partition=pool.partition
            )
            
            if sync_success:
                # 成功：重置失败计数并记录变化
                status.last_success_time = time.time()
                status.consecutive_failures = 0
                status.is_healthy = True
                status.last_error = ""
                status.total_syncs += 1
                
                # 统计信息
                model_count = len(new_datagroup_records)
                total_keys = sum(len(keys.split(',')) for keys in new_datagroup_records.values())
                status.last_model_count = model_count
                status.last_key_count = total_keys
                
                if changes:
                    self.logger.info(f"Pool {pool.name} API key changes applied: {changes}")
                
                self.logger.info(
                    f"Successfully synced {model_count} models with {total_keys} total API keys for pool {pool.name} "
                    f"(datagroup: {config.f5datagroup}, sync #{status.total_syncs})"
                )
                return True
            else:
                # F5同步失败
                raise Exception("Failed to sync records to F5 datagroup")
                
        except Exception as e:
            # 记录失败信息
            status.consecutive_failures += 1
            status.total_failures += 1
            status.last_error = str(e)
            status.is_healthy = False
            
            self.logger.error(
                f"API key sync failed for pool {pool.name} "
                f"(failure #{status.consecutive_failures}): {e}"
            )
            
            # 根据故障处理策略决定后续动作
            return await self._handle_sync_failure(pool, status)
    
    def _apply_pool_config(self, config):
        """应用pool级别的故障处理配置"""
        if hasattr(config, 'failure_mode'):
            try:
                self.failure_mode = FailureMode(config.failure_mode.lower())
            except ValueError:
                self.logger.warning(f"Invalid failure_mode: {config.failure_mode}, using default: preserve")
                self.failure_mode = FailureMode.PRESERVE
        
        if hasattr(config, 'max_failures_threshold'):
            self.max_failures_before_action = config.max_failures_threshold
        
        if hasattr(config, 'failure_timeout_hours'):
            self.failure_timeout_hours = config.failure_timeout_hours
    
    async def _handle_sync_failure(self, pool: Pool, status: PoolSyncStatus) -> bool:
        """处理同步失败"""
        config = pool.model_APIkey
        
        # 重要失败节点的告警
        if status.consecutive_failures in [1, 5, 10, 20]:
            self.logger.error(
                f"ALERT: Pool {pool.name} API key sync has failed "
                f"{status.consecutive_failures} consecutive times. "
                f"Last error: {status.last_error}"
            )
        
        # 长时间失败告警
        failure_hours = (time.time() - status.last_success_time) / 3600
        if failure_hours >= 1 and status.consecutive_failures % 5 == 0:
            self.logger.critical(
                f"CRITICAL: Pool {pool.name} API key sync has been failing for "
                f"{failure_hours:.1f} hours with {status.consecutive_failures} consecutive failures"
            )
        
        if self.failure_mode == FailureMode.PRESERVE:
            # 保守策略：始终保持现有datagroup
            self.logger.warning(
                f"Pool {pool.name}: Preserving existing datagroup due to sync failure "
                f"(failure mode: PRESERVE)"
            )
            return False  # 返回False表示同步失败，但不影响现有数据
            
        elif self.failure_mode == FailureMode.CLEAR:
            # 激进策略：立即清空datagroup
            self.logger.warning(
                f"Pool {pool.name}: Clearing datagroup due to sync failure "
                f"(failure mode: CLEAR)"
            )
            return await self._clear_datagroup(config.f5datagroup, pool.partition)
            
        elif self.failure_mode == FailureMode.SMART:
            # 智能策略：基于失败次数决定
            return await self._smart_failure_handling(pool, status)
        
        return False
    
    async def _smart_failure_handling(self, pool: Pool, status: PoolSyncStatus) -> bool:
        """智能故障处理"""
        config = pool.model_APIkey
        
        # 检查是否达到清空阈值
        if status.consecutive_failures >= self.max_failures_before_action:
            # 检查失败是否持续太久
            failure_duration_hours = (time.time() - status.last_success_time) / 3600
            
            if failure_duration_hours >= self.failure_timeout_hours:
                self.logger.warning(
                    f"Pool {pool.name}: Clearing datagroup after {status.consecutive_failures} "
                    f"consecutive failures over {failure_duration_hours:.1f} hours"
                )
                return await self._clear_datagroup(config.f5datagroup, pool.partition)
        
        # 否则保持现有数据
        self.logger.warning(
            f"Pool {pool.name}: Preserving datagroup "
            f"({status.consecutive_failures}/{self.max_failures_before_action} failures, "
            f"{(time.time() - status.last_success_time) / 3600:.1f}h since last success)"
        )
        return False
    
    async def _clear_datagroup(self, datagroup_name: str, partition: str) -> bool:
        """清空datagroup（保留结构，清空records）"""
        try:
            success = await self.f5_datagroup_client.clear_datagroup_records(
                name=datagroup_name,
                partition=partition
            )
            
            if success:
                self.logger.info(f"Successfully cleared datagroup: {datagroup_name}")
            else:
                self.logger.error(f"Failed to clear datagroup: {datagroup_name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Exception clearing datagroup {datagroup_name}: {e}")
            return False
    
    def get_pool_health_status(self) -> Dict[str, Dict]:
        """获取所有pool的健康状态"""
        result = {}
        current_time = time.time()
        
        for pool_key, status in self.pool_status.items():
            last_success_hours = (current_time - status.last_success_time) / 3600
            
            result[pool_key] = {
                "pool_name": status.pool_name,
                "is_healthy": status.is_healthy,
                "consecutive_failures": status.consecutive_failures,
                "total_failures": status.total_failures,
                "total_syncs": status.total_syncs,
                "last_success_hours_ago": round(last_success_hours, 2),
                "last_model_count": status.last_model_count,
                "last_key_count": status.last_key_count,
                "last_error": status.last_error,
                "failure_mode": self.failure_mode.value
            }
        
        return result
    
    def get_sync_summary(self) -> Dict:
        """获取同步状态摘要"""
        if not self.pool_status:
            return {
                "total_pools": 0,
                "healthy_pools": 0,
                "unhealthy_pools": 0,
                "overall_status": "no_pools"
            }
        
        healthy_count = sum(1 for status in self.pool_status.values() if status.is_healthy)
        total_count = len(self.pool_status)
        
        overall_status = "healthy" if healthy_count == total_count else "degraded"
        if healthy_count == 0:
            overall_status = "critical"
        
        return {
            "total_pools": total_count,
            "healthy_pools": healthy_count,
            "unhealthy_pools": total_count - healthy_count,
            "overall_status": overall_status,
            "failure_mode": self.failure_mode.value
        }
    
    async def _handle_empty_api_keys_data(self, pool: Pool, config, current_f5_records: Dict[str, str]):
        """处理从XInference获取到空API keys数据的情况"""
        if current_f5_records:
            self.logger.warning(
                f"Pool {pool.name}: XInference returned empty API keys, but F5 datagroup has {len(current_f5_records)} records. "
                f"This might indicate XInference service issues or all models were removed."
            )
            
            # 根据故障处理模式决定是否清空F5 datagroup
            if self.failure_mode == FailureMode.CLEAR:
                self.logger.warning(f"Pool {pool.name}: Clearing F5 datagroup due to empty XInference response (CLEAR mode)")
                await self.f5_datagroup_client.clear_datagroup_records(config.f5datagroup, pool.partition)
            elif self.failure_mode == FailureMode.PRESERVE:
                self.logger.info(f"Pool {pool.name}: Preserving existing F5 datagroup records (PRESERVE mode)")
            elif self.failure_mode == FailureMode.SMART:
                self.logger.info(f"Pool {pool.name}: Smart mode - treating empty response as potential service issue, preserving records")
        else:
            self.logger.info(f"Pool {pool.name}: Both XInference and F5 datagroup are empty - normal state")

    def _detect_datagroup_changes(self, old_records: Dict[str, str], new_records: Dict[str, str], pool_name: str) -> Dict[str, List[str]]:
        """检测datagroup记录的变化"""
        changes = {
            "added": [],
            "removed": [], 
            "modified": []
        }
        
        # 检测新增的记录
        for key in new_records:
            if key not in old_records:
                changes["added"].append(key)
                
        # 检测删除的记录
        for key in old_records:
            if key not in new_records:
                changes["removed"].append(key)
                
        # 检测修改的记录
        for key in new_records:
            if key in old_records and old_records[key] != new_records[key]:
                changes["modified"].append(key)
                
        # 记录详细变化信息
        if changes["added"]:
            self.logger.info(f"Pool {pool_name}: Added model keys: {changes['added']}")
        if changes["removed"]:
            self.logger.info(f"Pool {pool_name}: Removed model keys: {changes['removed']}")
        if changes["modified"]:
            self.logger.info(f"Pool {pool_name}: Modified model keys: {changes['modified']}")
            for key in changes["modified"]:
                old_keys = old_records[key].split(",") if old_records[key] else []
                new_keys = new_records[key].split(",") if new_records[key] else []
                added_keys = set(new_keys) - set(old_keys)
                removed_keys = set(old_keys) - set(new_keys)
                if added_keys:
                    self.logger.debug(f"  {key}: Added API keys: {list(added_keys)}")
                if removed_keys:
                    self.logger.debug(f"  {key}: Removed API keys: {list(removed_keys)}")
        
        # 返回非空的变化信息
        return {k: v for k, v in changes.items() if v}

    async def close(self):
        """关闭管理器"""
        self.running = False
        if hasattr(self.xinference_client, 'close'):
            await self.xinference_client.close()
        self.logger.info("API Key Manager closed")
