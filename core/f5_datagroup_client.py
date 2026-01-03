"""
F5 DataGroup客户端
按照API key更新与处理.md文档的F5 API操作规范实现
"""

import asyncio
import json
from typing import Dict, Optional
from urllib.parse import quote

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from core.f5_client import F5Client


class F5DataGroupClient:
    """F5 DataGroup操作客户端"""
    
    def __init__(self, f5_client: F5Client):
        self.f5_client = f5_client
        self.logger = get_logger()
    
    async def datagroup_exists(self, name: str, partition: str = "Common") -> bool:
        """检查datagroup是否存在"""
        await self.f5_client._ensure_session()
        token = await self.f5_client.ensure_valid_token()
        
        # 按文档格式构建URL
        datagroup_url = f"{self.f5_client.base_url}/tm/ltm/data-group/internal/~{partition}~{name}"
        
        try:
            async with self.f5_client.session.get(
                datagroup_url,
                headers={"X-F5-Auth-Token": token.token}
            ) as response:
                return response.status == 200
        except Exception as e:
            self.logger.warning(f"Error checking datagroup existence: {e}")
            return False
    
    async def create_datagroup_with_records(
        self, 
        name: str, 
        records: Dict[str, str], 
        partition: str = "Common"
    ) -> bool:
        """
        POST创建新datagroup并同时创建records
        按照文档操作方法2的格式
        """
        await self.f5_client._ensure_session()
        token = await self.f5_client.ensure_valid_token()
        
        # 构建F5 records格式
        f5_records = [
            {"name": key, "data": value} 
            for key, value in records.items()
        ]
        
        payload = {
            "name": name,
            "partition": partition,
            "type": "string",
            "records": f5_records
        }
        
        create_url = f"{self.f5_client.base_url}/tm/ltm/data-group/internal"
        
        try:
            self.logger.info(f"Creating datagroup {name} with {len(records)} records")
            async with self.f5_client.session.post(
                create_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-F5-Auth-Token": token.token
                }
            ) as response:
                
                if response.status == 200:
                    self.logger.info(f"Successfully created datagroup: {name}")
                    return True
                elif response.status == 409:
                    # Datagroup已存在，尝试更新
                    self.logger.info(f"Datagroup {name} already exists, will update instead")
                    return await self.update_datagroup_records(name, records, partition)
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to create datagroup {name}: HTTP {response.status}, {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Exception creating datagroup {name}: {e}")
            return False
    
    async def update_datagroup_records(
        self, 
        name: str, 
        records: Dict[str, str], 
        partition: str = "Common"
    ) -> bool:
        """
        PUT全量更新datagroup的所有records
        按照文档操作方法3的格式
        """
        await self.f5_client._ensure_session()
        token = await self.f5_client.ensure_valid_token()
        
        # 构建F5 records格式
        f5_records = [
            {"name": key, "data": value} 
            for key, value in records.items()
        ]
        
        payload = {
            "type": "string",
            "records": f5_records
        }
        
        # 按文档格式构建PUT URL
        update_url = f"{self.f5_client.base_url}/tm/ltm/data-group/internal/~{partition}~{name}"
        
        try:
            self.logger.info(f"Updating datagroup {name} with {len(records)} records")
            async with self.f5_client.session.put(
                update_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-F5-Auth-Token": token.token
                }
            ) as response:
                
                if response.status == 200:
                    self.logger.info(f"Successfully updated datagroup: {name}")
                    return True
                elif response.status == 404:
                    # Datagroup不存在，尝试创建
                    self.logger.info(f"Datagroup {name} not found, will create instead")
                    return await self.create_datagroup_with_records(name, records, partition)
                else:
                    error_text = await response.text()
                    self.logger.error(f"Failed to update datagroup {name}: HTTP {response.status}, {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.error(f"Exception updating datagroup {name}: {e}")
            return False
    
    async def sync_datagroup_records(
        self, 
        name: str, 
        records: Dict[str, str], 
        partition: str = "Common"
    ) -> bool:
        """
        同步datagroup records：首次创建或后续全量更新
        按照文档建议的POST创建+PUT更新策略，增强错误处理
        """
        # 验证输入参数
        if not name or not isinstance(name, str):
            self.logger.error(f"Invalid datagroup name: {name}")
            return False
            
        if not isinstance(records, dict):
            self.logger.error(f"Invalid records format: expected dict, got {type(records)}")
            return False
        
        # 验证记录格式和内容
        validated_records = {}
        for key, value in records.items():
            if not key or not isinstance(key, str):
                self.logger.warning(f"Skipping invalid record key: {key}")
                continue
            if not isinstance(value, str):
                self.logger.warning(f"Converting non-string value to string for key {key}: {value}")
                value = str(value)
            
            # 验证key格式（应该符合 model_id_ip_port 格式）
            if not self._validate_datagroup_key_format(key):
                self.logger.warning(f"Key format may be incorrect: {key}")
            
            validated_records[key] = value
        
        if not validated_records:
            self.logger.warning(f"No valid records to sync for datagroup {name}")
            # 如果没有有效记录，清空datagroup
            return await self.clear_datagroup_records(name, partition)
        
        try:
            # 检查datagroup是否存在
            exists = await self.datagroup_exists(name, partition)
            
            self.logger.debug(f"Syncing {len(validated_records)} records to datagroup {name} (exists: {exists})")
            
            if exists:
                # 存在则使用PUT全量更新
                return await self.update_datagroup_records(name, validated_records, partition)
            else:
                # 不存在则使用POST创建
                return await self.create_datagroup_with_records(name, validated_records, partition)
                
        except Exception as e:
            self.logger.error(f"Exception syncing datagroup {name}: {e}")
            return False
    
    def _validate_datagroup_key_format(self, key: str) -> bool:
        """验证datagroup key格式: model_id_ip_port"""
        try:
            # 简单验证：至少包含两个下划线，且最后一部分是数字（端口）
            parts = key.split('_')
            if len(parts) < 3:
                return False
            
            # 最后一部分应该是端口号
            try:
                port = int(parts[-1])
                return 1 <= port <= 65535
            except ValueError:
                return False
                
        except Exception:
            return False
    
    async def get_datagroup_records(self, name: str, partition: str = "Common") -> Dict[str, str]:
        """
        获取datagroup中的所有记录
        """
        await self.f5_client._ensure_session()
        token = await self.f5_client.ensure_valid_token()
        
        datagroup_url = f"{self.f5_client.base_url}/tm/ltm/data-group/internal/~{partition}~{name}"
        
        try:
            async with self.f5_client.session.get(
                datagroup_url,
                headers={"X-F5-Auth-Token": token.token}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    records = data.get("records", [])
                    
                    # 转换为字典格式
                    result = {}
                    for record in records:
                        key = record.get("name")
                        value = record.get("data", "")
                        if key:
                            result[key] = value
                    
                    self.logger.debug(f"Retrieved {len(result)} records from datagroup {name}")
                    return result
                elif response.status == 404:
                    self.logger.debug(f"Datagroup {name} not found")
                    return {}
                else:
                    error_text = await response.text()
                    self.logger.warning(f"Failed to get datagroup {name}: HTTP {response.status}, {error_text}")
                    return {}
                    
        except Exception as e:
            self.logger.error(f"Exception getting datagroup records {name}: {e}")
            return {}

    async def clear_datagroup_records(self, name: str, partition: str = "Common") -> bool:
        """
        清空datagroup（保留结构，清空records）
        使用空records进行全量更新
        """
        try:
            success = await self.update_datagroup_records(
                name=name,
                records={},  # 空records
                partition=partition
            )
            
            if success:
                self.logger.info(f"Successfully cleared datagroup: {name}")
            else:
                self.logger.error(f"Failed to clear datagroup: {name}")
            
            return success
            
        except Exception as e:
            self.logger.error(f"Exception clearing datagroup {name}: {e}")
            return False
