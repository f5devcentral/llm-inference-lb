"""
F5 API client module
Responsible for interacting with F5 LTM's iControl REST API
"""

import asyncio
import json
import ssl
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import aiohttp

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from utils.exceptions import F5ApiError, TokenAuthenticationError
from core.models import PoolMember


@dataclass
class F5Token:
    """F5 Token information"""
    token: str
    name: str
    expiration_time: float
    timeout: int = 36000


class F5Client:
    """F5 API client"""
    
    def __init__(self, host: str, port: int, username: str, password: str):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_url = f"https://{host}:{port}/mgmt"
        self.logger = get_logger()
        self.current_token: Optional[F5Token] = None
        self.session: Optional[aiohttp.ClientSession] = None
        self._token_lock = asyncio.Lock()  # Add token operation lock
        
    async def __aenter__(self):
        """Async context manager entry"""
        # Create SSL context, ignore certificate verification
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def _ensure_session(self):
        """Ensure session is created"""
        if not self.session:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=30)
            )
    
    async def delete_token(self, token: F5Token) -> bool:
        """Delete token on F5"""
        await self._ensure_session()
        delete_url = f"{self.base_url}/shared/authz/tokens/{token.name}"
        try:
            self.logger.debug(f"Deleting Token: {token.name}")
            async with self.session.delete(
                delete_url,
                headers={"X-F5-Auth-Token": token.token}
            ) as response:
                if response.status == 200:
                    self.logger.info(f"Successfully deleted Token: {token.name}")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.warning(f"Failed to delete Token: HTTP {response.status}, {error_text}")
                    return False
        except Exception as e:
            self.logger.warning(f"Exception deleting Token: {e}")
            return False
    
    async def login(self) -> F5Token:
        """Login to F5 to get Token"""
        await self._ensure_session()
        
        login_url = f"{self.base_url}/shared/authn/login"
        login_data = {
            "username": self.username,
            "password": self.password,
            "loginProviderName": "tmos"
        }
        
        try:
            self.logger.debug(f"Logging into F5: {login_url}")
            async with self.session.post(
                login_url,
                json=login_data,
                headers={"Content-Type": "application/json"}
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"F5 login failed: HTTP {response.status}, {error_text}")
                    raise TokenAuthenticationError(f"Login failed: HTTP {response.status}")
                
                response_data = await response.json()
                token_info = response_data.get("token", {})
                
                if not token_info.get("token"):
                    self.logger.error("Token not found in login response")
                    raise TokenAuthenticationError("Token not found in login response")
                
                # Create Token object
                token = F5Token(
                    token=token_info["token"],
                    name=token_info["name"],
                    expiration_time=time.time() + token_info.get("timeout", 1200)
                )
                
                self.logger.info(f"Successfully obtained F5 Token: {token.name}")
                self.current_token = token
                
                # Extend token timeout
                await self._extend_token_timeout(token)
                
                return token
                
        except aiohttp.ClientError as e:
            self.logger.error(f"F5 login network error: {e}")
            raise F5ApiError(f"Login network error: {e}")
        except Exception as e:
            self.logger.error(f"F5 login exception: {e}")
            raise TokenAuthenticationError(f"Login failed: {e}")
    
    async def _extend_token_timeout(self, token: F5Token) -> bool:
        """Extend Token timeout to 36000 seconds"""
        await self._ensure_session()
        
        extend_url = f"{self.base_url}/shared/authz/tokens/{token.name}"
        extend_data = {"timeout": "36000"}
        
        try:
            async with self.session.patch(
                extend_url,
                json=extend_data,
                headers={
                    "Content-Type": "application/json",
                    "X-F5-Auth-Token": token.token
                }
            ) as response:
                
                if response.status == 200:
                    response_data = await response.json()
                    new_timeout = response_data.get("timeout", 36000)
                    token.timeout = new_timeout
                    token.expiration_time = time.time() + new_timeout
                    self.logger.info(f"Successfully extended Token timeout to: {new_timeout} seconds")
                    return True
                else:
                    error_text = await response.text()
                    self.logger.warning(f"Failed to extend Token timeout: HTTP {response.status}, {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.warning(f"Exception extending Token timeout: {e}")
            return False
    
    async def validate_token(self, token: F5Token) -> bool:
        """Validate if Token is valid"""
        await self._ensure_session()
        
        # Check if Token has expired
        if time.time() >= token.expiration_time:
            self.logger.debug("Token has expired")
            return False
        
        # Use a simple API call to validate token
        validate_url = f"{self.base_url}/tm/sys/version"  # Use system version API, this is a lightweight API call
        
        try:
            async with self.session.get(
                validate_url,
                headers={"X-F5-Auth-Token": token.token}
            ) as response:
                
                if response.status == 200:
                    return True
                elif response.status == 401:
                    self.logger.warning("Token validation failed: HTTP 401")
                    return False
                else:
                    error_text = await response.text()
                    self.logger.warning(f"Token validation failed: HTTP {response.status}, {error_text}")
                    return False
                    
        except Exception as e:
            self.logger.warning(f"Token validation exception: {e}")
            return False
    
    async def ensure_valid_token(self) -> F5Token:
        """Ensure valid Token"""
        try:
            async with self._token_lock:  # Use lock to protect token operations
                self.logger.debug("Checking if local token is available")
                if self.current_token:
                    # Only check if locally cached token has expired
                    if time.time() < self.current_token.expiration_time:
                        self.logger.debug(f"Using cached token: {self.current_token.name}")
                        return self.current_token
                    else:
                        # Token has expired, delete it
                        self.logger.info("Local Token has expired, preparing to delete F5-side Token as well. If F5 returns failure due to Token expiration for this deletion, please ignore this warning.")
                        await self.delete_token(self.current_token)
                        self.current_token = None
                
                # Re-login to get new token
                self.logger.info("Token does not exist or has expired, re-logging in")
                return await self.login()
        except Exception as e:
            self.logger.error(f"Exception occurred during Token check process: {e}")
            # Ensure lock is released even when exception occurs
            self.current_token = None
            return await self.login()
    
    async def get_pool_members(self, pool_name: str, partition: str) -> List[PoolMember]:
        """Get Pool member list"""
        await self._ensure_session()
        
        token = await self.ensure_valid_token()
        
        # Build URL, handle partition
        pool_url = f"{self.base_url}/tm/ltm/pool/~{partition}~{pool_name}/members"
        
        try:
            self.logger.debug(f"Getting Pool members: {pool_url}")
            async with self.session.get(
                pool_url,
                headers={"X-F5-Auth-Token": token.token}
            ) as response:
                
                if response.status == 401:
                    # Token invalid, delete old token and re-login
                    self.logger.info("Token invalid, deleting old token and re-logging in")
                    await self.delete_token(token)
                    self.current_token = None
                    token = await self.login()
                    
                    # Retry with new token
                    async with self.session.get(
                        pool_url,
                        headers={"X-F5-Auth-Token": token.token}
                    ) as retry_response:
                        if retry_response.status != 200:
                            error_text = await retry_response.text()
                            raise F5ApiError(f"Failed to get Pool members: HTTP {retry_response.status}, {error_text}")
                        response_data = await retry_response.json()
                elif response.status == 404:
                    # Pool does not exist business error, directly raise exception
                    error_text = await response.text()
                    self.logger.error(f"Pool does not exist: HTTP 404, {error_text}")
                    raise F5ApiError(f"Pool does not exist (404): {error_text}")
                elif response.status != 200:
                    error_text = await response.text()
                    self.logger.error(f"Failed to get Pool members: HTTP {response.status}, {error_text}")
                    raise F5ApiError(f"Failed to get Pool members: HTTP {response.status}")
                else:
                    response_data = await response.json()
                
                # Parse member information
                members = []
                items = response_data.get("items", [])
                
                for item in items:
                    address = item.get("address", "")
                    name = item.get("name", "")
                    
                    if not address:
                        self.logger.warning(f"Pool {pool_name} member missing address field")
                        continue
                    
                    # Extract port from name field (format: IP:Port)
                    port = 0
                    if ":" in name:
                        try:
                            port = int(name.split(":")[-1])
                        except ValueError:
                            self.logger.warning(f"Unable to parse port: {name}")
                            continue
                    
                    if port == 0:
                        self.logger.warning(f"Pool {pool_name} member port is 0: {name}")
                        continue
                    
                    member = PoolMember(
                        ip=address,
                        port=port,
                        partition=partition
                    )
                    members.append(member)
                
                self.logger.info(f"Successfully obtained {len(members)} members for Pool {pool_name}")
                return members
                
        except aiohttp.ClientError as e:
            self.logger.error(f"Network error getting Pool members: {e}")
            raise F5ApiError(f"Network error getting Pool members: {e}")
        except Exception as e:
            self.logger.error(f"Exception getting Pool members: {e}")
            raise F5ApiError(f"Failed to get Pool members: {e}")
    
    async def close(self):
        """Close client"""
        if self.session:
            await self.session.close()
            self.session = None 