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
from core.models import PoolMember, Pool, EngineType
# Import the models module to access ENGINE_METRICS_CANDIDATES dynamically
# This avoids the issue where reassigning the dict in initialize_engine_metrics_candidates
# would not be visible to this module's imported reference
from core import models as models_module
import json


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
                
                response_text = await response.text()
                
                # Handle different engine types
                if pool.engine_type == EngineType.XINFERENCE:
                    return self._parse_xinference_metrics(response_text, member)
                else:
                    return self._parse_prometheus_metrics(response_text, pool.engine_type, member)
                
        except aiohttp.ClientError as e:
            self.logger.warning(f"Network error getting metrics for member {member}: {e}")
            return {}
        except Exception as e:
            self.logger.warning(f"Exception getting metrics for member {member}: {e}")
            return {}
    
    def _parse_prometheus_metrics(
        self, 
        metrics_text: str, 
        engine_type: EngineType,
        member: PoolMember
    ) -> Dict[str, float]:
        """Parse Prometheus format metrics with automatic key detection
        
        This method tries multiple candidate keys for each metric type,
        caches the detected keys for future use, and tracks which variant
        the member is using.
        
        Args:
            metrics_text: Raw prometheus format metrics text
            engine_type: Engine type (VLLM or SGLANG)
            member: Pool member (used for caching and variant tracking)
            
        Returns:
            Dict with normalized metric names (waiting_queue, cache_usage, running_req)
        """
        metrics = {}
        
        try:
            # Get candidate keys for this engine type
            # Use models_module to get the current value (after initialization)
            candidates = models_module.ENGINE_METRICS_CANDIDATES.get(engine_type, {})
            if not candidates:
                self.logger.warning(f"No metrics candidates defined for engine type {engine_type}")
                return metrics
            
            # Track if we detected new keys in this parse
            detected_new_keys = False
            detected_variants = set()
            
            # Process each metric type
            for metric_type in ["waiting_queue", "cache_usage", "running_req"]:
                # 1. Check if we have a cached key for this metric type
                cached_key = member.metrics_key_cache.get(metric_type)
                
                if cached_key:
                    # Try using the cached key
                    values = self._extract_metric_values(metrics_text, cached_key)
                    if values:
                        metrics[metric_type] = self._calculate_average(values)
                        # Track the variant for logging
                        variant = models_module.METRICS_KEY_VARIANT_MAP.get(cached_key, "unknown")
                        detected_variants.add(variant)
                        continue
                    else:
                        # Cached key no longer works, clear it and re-detect
                        self.logger.debug(
                            f"Member {member}: cached key '{cached_key}' for {metric_type} no longer found, re-detecting"
                        )
                        del member.metrics_key_cache[metric_type]
                
                # 2. Try candidate keys in order (user-configured first, then built-in)
                candidate_keys = candidates.get(metric_type, [])
                found = False
                
                for key in candidate_keys:
                    values = self._extract_metric_values(metrics_text, key)
                    if values:
                        # Found a working key, cache it
                        member.metrics_key_cache[metric_type] = key
                        metrics[metric_type] = self._calculate_average(values)
                        
                        # Get variant name for logging
                        variant = models_module.METRICS_KEY_VARIANT_MAP.get(key, "unknown")
                        detected_variants.add(variant)
                        detected_new_keys = True
                        
                        self.logger.info(
                            f"Member {member}: detected {metric_type} using variant '{variant}' (key: {key})"
                        )
                        found = True
                        break
                
                if not found and metric_type in ["waiting_queue", "cache_usage"]:
                    # These are required metrics, log warning if not found
                    self.logger.warning(
                        f"Member {member}: unable to find {metric_type} metric, tried keys: {candidate_keys}"
                    )
            
            # Update member's detected variant based on the keys found
            if detected_variants:
                # Use the most specific variant (prefer user-configured over built-in)
                # Priority: user variants > built-in (engine type name)
                for variant in detected_variants:
                    if variant not in [EngineType.VLLM.value, EngineType.SGLANG.value]:
                        member.detected_variant = variant
                        break
                else:
                    # Only built-in variants found
                    member.detected_variant = list(detected_variants)[0]
            
            # Log summary if we have cached variant info
            if member.detected_variant and member.metrics_key_cache:
                self.logger.debug(
                    f"Member {member}: using variant '{member.detected_variant}', metrics: {metrics}"
                )
            
            return metrics
            
        except Exception as e:
            self.logger.warning(f"Exception parsing prometheus metrics for {member}: {e}")
            return {}
    
    def _parse_xinference_metrics(self, response_text: str, member: PoolMember) -> Dict[str, float]:
        """Parse XInference JSON format metrics
        
        Args:
            response_text: Raw response text from XInference API
            member: PoolMember to store model metrics
            
        Returns:
            Empty dict (XInference uses model_metrics storage instead)
        """
        try:
            # Parse JSON response
            response_data = json.loads(response_text)
            
            # Validate response structure
            if not isinstance(response_data, dict):
                self.logger.warning(f"Invalid XInference response format for {member}: not a JSON object")
                return {}
            
            # Check response code
            code = response_data.get("code")
            if code != 200:
                message = response_data.get("message", "Unknown error")
                self.logger.warning(f"XInference API error for {member}: code={code}, message={message}")
                return {}
            
            # Extract data section
            data = response_data.get("data", {})
            if not isinstance(data, dict):
                self.logger.warning(f"Invalid XInference data format for {member}: data is not a dict")
                return {}
            
            # Extract model_metrics array
            model_metrics = data.get("model_metrics", [])
            if not isinstance(model_metrics, list):
                self.logger.warning(f"Invalid XInference model_metrics format for {member}: not a list")
                return {}
            
            # Process each model's metrics
            model_count = 0
            for model_data in model_metrics:
                if not isinstance(model_data, dict):
                    self.logger.warning(f"Invalid model data format for {member}: {model_data}")
                    continue
                
                model_name = model_data.get("model_id")  # 使用model_id作为内存中的model标识
                throughput_utilization = model_data.get("throughput_utilization")
                
                if not model_name:
                    self.logger.warning(f"Missing model_id for {member}: {model_data}")
                    continue
                
                if throughput_utilization is None:
                    self.logger.warning(f"Missing throughput_utilization for {member} model_id {model_name}")
                    continue
                
                # Validate and store model metric
                try:
                    utilization_float = float(throughput_utilization)
                    member.set_model_metric(model_name, utilization_float)
                    model_count += 1
                    self.logger.debug(f"Stored metric for {member} model_id {model_name}: {utilization_float}")
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Invalid throughput_utilization value for {member} model_id {model_name}: {throughput_utilization}, error: {e}")
                    continue
            
            self.logger.debug(f"Processed {model_count} models for XInference member {member}")
            
            # XInference uses its own variant tracking
            member.detected_variant = "xinference"
            
            # XInference stores metrics in model_metrics, return empty dict for regular metrics
            return {}
            
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse XInference JSON response for {member}: {e}")
            return {}
        except Exception as e:
            self.logger.warning(f"Exception parsing XInference metrics for {member}: {e}")
            return {}
    
    def _extract_metric_values(self, metrics_text: str, metric_name: str) -> List[float]:
        """Extract values for specified metric from Prometheus format text"""
        values = []
        
        # Build regex pattern to match metric lines
        # Format: metric_name{labels...} value
        # Support both regular decimal format and scientific notation (e.g., 1.23e-05)
        pattern = rf'^{re.escape(metric_name)}\{{.*?\}}\s+([0-9.-]+(?:[eE][+-]?[0-9]+)?)$'
        
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
        
        # Determine port usage strategy and engine-specific logging
        port_strategy = "configured port" if metrics_port is not None else "member port"
        port_info = f"({metrics_port})" if metrics_port is not None else "(each member's own port)"
        engine_info = f"engine_type={pool.engine_type.value}"
        
        self.logger.info(f"Starting metrics collection for Pool {pool.name} with {len(pool.members)} members, {engine_info}, port strategy: {port_strategy}{port_info}")
        
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
        successful_count = 0
        for i, (member, result) in enumerate(zip(pool.members, results)):
            if isinstance(result, Exception):
                self.logger.warning(f"Failed to collect metrics for member {member}: {result}")
                member.metrics = {}
            else:
                member.metrics = result
                successful_count += 1
                
                # Special logging for XInference
                if pool.engine_type == EngineType.XINFERENCE:
                    model_count = len(member.model_metrics)
                    self.logger.debug(f"XInference member {member}: {model_count} models with metrics")
                else:
                    # Log with detected variant info
                    variant_info = f" (variant: {member.detected_variant})" if member.detected_variant else ""
                    self.logger.debug(f"Prometheus member {member}{variant_info}: {result}")
        
        # Summary with variant information for non-xinference pools
        if pool.engine_type != EngineType.XINFERENCE:
            variant_summary = {}
            for member in pool.members:
                if member.detected_variant:
                    variant_summary[member.detected_variant] = variant_summary.get(member.detected_variant, 0) + 1
            
            if variant_summary:
                variant_str = ", ".join([f"{v}: {c}" for v, c in variant_summary.items()])
                self.logger.info(
                    f"Completed metrics collection for Pool {pool.name}: "
                    f"{successful_count}/{len(pool.members)} members successful, "
                    f"variants: [{variant_str}]"
                )
            else:
                self.logger.info(f"Completed metrics collection for Pool {pool.name}: {successful_count}/{len(pool.members)} members successful")
        else:
            self.logger.info(f"Completed metrics collection for Pool {pool.name}: {successful_count}/{len(pool.members)} members successful")
    
    async def close(self):
        """Close collector"""
        if self.session:
            await self.session.close()
            self.session = None
