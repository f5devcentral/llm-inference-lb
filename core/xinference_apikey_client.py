"""
XInference API Key客户端
按照API key更新与处理.md文档规范实现
"""

import json
import os
import ssl
from typing import Dict, List, Optional, Set
import aiohttp

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from core.models import PoolMember, Pool


class XInferenceApiKeyClient:
    """XInference API Key客户端"""
    
    def __init__(self, timeout: int = 3):
        self.logger = get_logger()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = timeout
    
    async def __aenter__(self):
        """Async context manager entry"""
        # 复用现有的SSL设置
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=None)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def fetch_pool_api_keys(self, pool: Pool, config) -> Dict[str, List[str]]:
        """
        获取整个pool的API keys
        
        Args:
            pool: Pool对象
            config: ModelApiKeyConfig配置对象
            
        Returns:
            Dict[datagroup_key, List[api_keys]]
            例如：
            {
                "model-001_192.168.1.132_5001": ["sha256_sk11111", "sha256_sk2222"],
                "model-001_192.168.1.132_5002": ["sha256_sk3333"],
                "model-002_192.168.1.132_5001": ["sha256_sk11111", "sha256_sk2222"]
            }
        """
        results = {}
        
        # 处理pool没有members的情况
        if not pool.members:
            self.logger.warning(f"Pool {pool.name} has no members, cannot fetch API keys")
            return results
        
        successful_members = 0
        total_members = len(pool.members)
        
        for member in pool.members:
            try:
                member_api_keys = await self._fetch_member_api_keys(member, config)
                
                if member_api_keys:
                    # 转换为datagroup格式
                    for model_id, api_keys in member_api_keys.items():
                        datagroup_key = f"{model_id}_{member.ip}_{member.port}"
                        results[datagroup_key] = api_keys
                    successful_members += 1
                else:
                    self.logger.warning(f"No API keys returned from member {member}")
                    
            except Exception as e:
                self.logger.error(f"Failed to fetch API keys from member {member}: {e}")
                continue
        
        self.logger.info(f"Pool {pool.name}: Successfully fetched API keys from {successful_members}/{total_members} members")
        
        # 如果没有任何member成功返回数据，记录警告
        if successful_members == 0:
            self.logger.warning(f"Pool {pool.name}: No members returned API keys - possible service issues")
        
        return results
    
    async def _fetch_member_api_keys(self, member: PoolMember, config) -> Dict[str, List[str]]:
        """
        从单个member获取API keys
        
        Returns:
            Dict[model_id, List[api_keys]]
        """
        await self._ensure_session()
        
        # 构建请求URL
        url = member.metric_uri("http", config.path)
        headers = {}
        auth = None
        
        # 设置认证 - APIkey优先，否则使用用户密码认证
        if hasattr(config, 'APIkey') and config.APIkey:
            headers["Authorization"] = f"Bearer {config.APIkey}"
            self.logger.debug(f"Using APIkey authentication for {member}")
        elif (hasattr(config, 'apikey_user') and config.apikey_user and 
              hasattr(config, 'apikey_pwd_env') and config.apikey_pwd_env):
            password = os.getenv(config.apikey_pwd_env)
            if password:
                auth = aiohttp.BasicAuth(config.apikey_user, password)
                self.logger.debug(f"Using basic authentication for {member} with user: {config.apikey_user}")
            else:
                self.logger.warning(f"Environment variable {config.apikey_pwd_env} not set for {member}")
        else:
            self.logger.debug(f"No authentication configured for {member}")
        
        try:
            async with self.session.get(
                url,
                headers=headers,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=config.timeout)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.warning(f"API key request failed for {member}: HTTP {response.status}, {error_text}")
                    return {}
                
                response_text = await response.text()
                return self._parse_authorization_response(response_text, member)
                
        except Exception as e:
            self.logger.error(f"Exception fetching API keys from {member}: {e}")
            return {}
    
    def _parse_authorization_response(self, response_text: str, member: PoolMember) -> Dict[str, List[str]]:
        """解析XInference授权响应 - 按照文档格式，增强异常处理"""
        try:
            # 处理空响应
            if not response_text or not response_text.strip():
                self.logger.warning(f"Empty response from {member}")
                return {}
            
            response_data = json.loads(response_text)
            
            # 验证响应是否为字典
            if not isinstance(response_data, dict):
                self.logger.warning(f"Invalid response format from {member}: expected dict, got {type(response_data)}")
                return {}
            
            # 验证响应结构
            code = response_data.get("code")
            if code != 200:
                message = response_data.get("message", "Unknown error")
                self.logger.warning(f"Authorization response error for {member}: code={code}, message={message}")
                return {}
            
            data = response_data.get("data", {})
            if not isinstance(data, dict):
                self.logger.warning(f"Invalid data format from {member}: expected dict, got {type(data)}")
                return {}
                
            authorization_records = data.get("authorization_records", [])
            if not isinstance(authorization_records, list):
                self.logger.warning(f"Invalid authorization_records format from {member}: expected list, got {type(authorization_records)}")
                return {}
            
            # 构建 model_id -> [api_keys] 的映射
            model_to_keys: Dict[str, Set[str]] = {}
            
            for record in authorization_records:
                api_key = record.get("api_key")
                # 尝试多种可能的字段名（处理文档中的格式错误）
                model_ids = record.get("model_ids", record.get("model_ids:", []))
                
                if not api_key:
                    self.logger.warning(f"Missing api_key in authorization record for {member}: {record}")
                    continue
                
                if not model_ids:
                    self.logger.warning(f"Missing model_ids in authorization record for {member}: {record}")
                    continue
                
                if not isinstance(model_ids, list):
                    self.logger.warning(f"model_ids is not a list for {member}: {model_ids}, trying to convert")
                    try:
                        # 尝试转换为列表
                        if isinstance(model_ids, str):
                            model_ids = [model_ids]
                        else:
                            model_ids = list(model_ids)
                    except Exception as e:
                        self.logger.error(f"Cannot convert model_ids to list for {member}: {e}")
                        continue
                
                # 一个API key可以对应多个模型
                for model_id in model_ids:
                    if not model_id or not isinstance(model_id, str):
                        self.logger.warning(f"Invalid model_id '{model_id}' for {member}")
                        continue
                        
                    if model_id not in model_to_keys:
                        model_to_keys[model_id] = set()
                    model_to_keys[model_id].add(api_key)
            
            # 转换为列表格式并验证
            result = {}
            for model_id, api_keys in model_to_keys.items():
                if model_id and api_keys:  # 确保model_id和api_keys都非空
                    api_keys_list = list(api_keys)
                    # 验证API key格式（简单检查）
                    valid_keys = [key for key in api_keys_list if key and isinstance(key, str) and len(key.strip()) > 0]
                    if valid_keys:
                        result[model_id] = valid_keys
                    else:
                        self.logger.warning(f"No valid API keys for model {model_id} from {member}")
            
            total_keys = sum(len(keys) for keys in result.values())
            self.logger.debug(f"Parsed API keys for {member}: {len(result)} models, {total_keys} total keys")
            
            # 如果没有解析到任何有效数据，记录详细信息
            if not result:
                self.logger.warning(f"No valid model-key mappings parsed from {member}, raw response: {response_text[:200]}...")
            
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse authorization JSON from {member}: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Exception parsing authorization response from {member}: {e}")
            return {}
    
    async def _ensure_session(self):
        """确保session已创建"""
        if not self.session:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=None)
            )
    
    async def close(self):
        """关闭客户端"""
        if self.session:
            await self.session.close()
            self.session = None
