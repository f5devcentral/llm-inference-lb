"""
Metrics collection module
Responsible for collecting performance metrics from inference engines
"""

import asyncio
import re
import ssl
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
import aiohttp

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from utils.exceptions import MetricsCollectionError
from core.models import PoolMember, Pool, EngineType, ENGINE_METRICS


class MetricsCollector:
    """Metrics collector"""
    
    def __init__(self, timeout: int = 3):
        self.logger = get_logger()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = timeout
    
    async def __aenter__(self):
        """Async context manager entry"""
        # Create SSL context, ignore certificate verification
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        # Create session without default timeout, specify timeout individually for requests
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=None)
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
            # Create session without default timeout, specify timeout individually for requests
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=None)
            )
    
    async def collect_member_metrics(
        self, 
        member: PoolMember, 
        pool: Pool,
        schema: str,
        path: str,
        metrics_port: Optional[int] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> Dict[str, float]:
        """Collect metrics for a single member
        
        Args:
            member: Pool member
            pool: Pool object
            schema: http/https protocol
            path: metrics path
            metrics_port: Optional metrics port, if provided use this port, otherwise use member's own port
            api_key: API key
            username: Username
            password: Password
            timeout: HTTP request timeout (seconds), if not provided use instance default value
        """
        await self._ensure_session()
        
        # Build metrics URL - new logic: if metrics_port is not None use configured port, otherwise use member port
        metrics_url = member.metric_uri(schema, path, metrics_port)
        
        # Prepare authentication
        headers = {}
        auth = None
        
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        elif username and password:
            auth = aiohttp.BasicAuth(username, password)
        
        try:
            # Determine actual timeout to use
            actual_timeout = timeout if timeout is not None else self.timeout
            
            self.logger.debug(f"Collecting metrics: {metrics_url} (timeout: {actual_timeout}s)")
            async with self.session.get(
                metrics_url,
                headers=headers,
                auth=auth,
                timeout=aiohttp.ClientTimeout(total=actual_timeout)
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    self.logger.warning(
                        f"Unable to get metrics for member {member}: HTTP {response.status}, {error_text}"
                    )
                    return {}
                
                metrics_text = await response.text()
                return self._parse_metrics(metrics_text, pool.engine_type)
                
        except aiohttp.ClientError as e:
            self.logger.warning(f"Network error getting metrics for member {member}: {e}")
            return {}
        except Exception as e:
            self.logger.warning(f"Exception getting metrics for member {member}: {e}")
            return {}
    
    def _parse_metrics(self, metrics_text: str, engine_type: EngineType) -> Dict[str, float]:
        """Parse Prometheus format metrics"""
        metrics = {}
        
        try:
            # Get key metrics for the engine
            key_metrics = ENGINE_METRICS.get(engine_type, {})
            
            waiting_queue_metric = key_metrics.get("waiting_queue", "")
            cache_usage_metric = key_metrics.get("cache_usage", "")
            running_req_metric = key_metrics.get("running_req", "")
            
            if not waiting_queue_metric or not cache_usage_metric:
                self.logger.warning(f"Key metrics not defined for engine type {engine_type}")
                return metrics
            
            # Parse waiting queue metric
            waiting_values = self._extract_metric_values(metrics_text, waiting_queue_metric)
            if waiting_values:
                metrics["waiting_queue"] = self._calculate_average(waiting_values)
            
            # Parse cache usage metric
            cache_values = self._extract_metric_values(metrics_text, cache_usage_metric)
            if cache_values:
                metrics["cache_usage"] = self._calculate_average(cache_values)
            
            # Parse running requests metric (for S2 algorithm)
            if running_req_metric:
                running_values = self._extract_metric_values(metrics_text, running_req_metric)
                if running_values:
                    metrics["running_req"] = self._calculate_average(running_values)
            
            self.logger.debug(f"Parsed metrics: {metrics}")
            return metrics
            
        except Exception as e:
            self.logger.warning(f"Exception parsing metrics: {e}")
            return {}
    
    def _extract_metric_values(self, metrics_text: str, metric_name: str) -> List[float]:
        """Extract values for specified metric from Prometheus format text"""
        values = []
        
        # Build regex pattern to match metric lines
        # Format: metric_name{labels...} value
        pattern = rf'^{re.escape(metric_name)}\{{.*?\}}\s+([0-9.-]+)$'
        
        for line in metrics_text.split('\n'):
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            
            match = re.match(pattern, line)
            if match:
                try:
                    value = float(match.group(1))
                    values.append(value)
                except ValueError:
                    self.logger.warning(f"Unable to parse metric value: {line}")
                    continue
        
        return values
    
    def _calculate_average(self, values: List[float]) -> float:
        """Calculate average"""
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    async def collect_pool_metrics(
        self,
        pool: Pool,
        schema: str,
        path: str,
        metrics_port: Optional[int] = None,
        api_key: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        timeout: Optional[int] = None
    ) -> None:
        """Collect metrics for all members in the pool
        
        Args:
            pool: Pool object
            schema: http/https protocol  
            path: metrics path
            metrics_port: Optional metrics port, if provided all members use this port, otherwise each member uses its own port
            api_key: API key
            username: Username
            password: Password
            timeout: HTTP request timeout (seconds), if not provided use default value from initialization
        """
        if not pool.members:
            self.logger.debug(f"Pool {pool.name} has no members, skipping metrics collection")
            return
        
        # Determine port usage strategy
        port_strategy = "configured port" if metrics_port is not None else "member port"
        port_info = f"({metrics_port})" if metrics_port is not None else "(each member's own port)"
        
        self.logger.info(f"Starting metrics collection for Pool {pool.name} with {len(pool.members)} members, port strategy: {port_strategy}{port_info}")
        
        # Concurrently collect metrics for all members
        tasks = []
        for member in pool.members:
            # Record the specific port used for each member
            actual_port = metrics_port if metrics_port is not None else member.port
            self.logger.debug(f"Member {member.ip}:{member.port} using metrics port: {actual_port}")
            
            task = self.collect_member_metrics(
                member, pool, schema, path, metrics_port, api_key, username, password, timeout
            )
            tasks.append(task)
        
        # Actually await all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and update member metrics
        for i, (member, result) in enumerate(zip(pool.members, results)):
            if isinstance(result, Exception):
                self.logger.warning(f"Failed to collect metrics for member {member}: {result}")
                member.metrics = {}
            else:
                member.metrics = result
                self.logger.debug(f"Metrics for member {member}: {result}")
        
        self.logger.info(f"Completed metrics collection for Pool {pool.name}")
    
    async def close(self):
        """Close collector"""
        if self.session:
            await self.session.close()
            self.session = None 