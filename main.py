"""
F5 LLM Inference Gateway Scheduler Main Program
Integrates all modules to implement complete scheduler functionality
"""

import asyncio
import signal
import sys
import os
import hashlib
from typing import Dict, List, Optional
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from utils.logger import init_logger, get_logger, LogLevel
from utils.exceptions import ConfigurationError, F5ApiError, MetricsCollectionError
from config.config_loader import load_config, get_config_loader, AppConfig, PoolConfig
from core.models import Pool, PoolMember, EngineType, add_or_update_pool, get_all_pools, get_pool_by_key, POOLS
from core.f5_client import F5Client
from core.metrics_collector import MetricsCollector
from core.score_calculator import ScoreCalculator
from api.server import create_api_server


class ConfigHotReloader:
    """Configuration file hot reload detector"""
    
    def __init__(self, config_file: str):
        self.config_file = config_file
        self.last_mtime = None
        self.last_hash = None
        self.logger = get_logger()
        self.initialized = False
        
    async def _initialize_baseline(self):
        """Initialize baseline values (establish baseline on first call, not considered as change)"""
        try:
            if os.path.exists(self.config_file):
                self.last_mtime = os.path.getmtime(self.config_file)
                with open(self.config_file, 'rb') as f:
                    self.last_hash = hashlib.sha256(f.read()).hexdigest()
                self.initialized = True
                self.logger.debug("Configuration file baseline established")
        except Exception as e:
            self.logger.warning(f"Failed to establish configuration file baseline: {e}")
        
    async def detect_changes(self) -> bool:
        """Detect if configuration file has changed"""
        try:
            # Establish baseline on first call, not considered as change
            if not self.initialized:
                await self._initialize_baseline()
                return False
                
            # 1. Check if file exists
            if not os.path.exists(self.config_file):
                return False
                
            # 2. Check file modification time
            current_mtime = os.path.getmtime(self.config_file)
            if self.last_mtime is not None and current_mtime <= self.last_mtime:
                return False
                
            # 3. Check file content hash
            with open(self.config_file, 'rb') as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()
                
            if self.last_hash == current_hash:
                return False
                
            # 4. Record new timestamp and hash
            self.last_mtime = current_mtime
            self.last_hash = current_hash
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to detect configuration changes: {e}")
            return False


class SchedulerApp:
    """Scheduler application"""
    
    def __init__(self, config_file: str = "config/scheduler-config.yaml"):
        self.config_file = config_file
        self.config: Optional[AppConfig] = None
        self.logger = None
        self.f5_client: Optional[F5Client] = None
        self.metrics_collector: Optional[MetricsCollector] = None
        self.score_calculator: Optional[ScoreCalculator] = None
        self.api_server = None
        self.running = False
        self.tasks: List[asyncio.Task] = []
        # Configuration hot reloader
        self.config_hot_reloader = None
    
    async def initialize(self):
        """Initialize application"""
        try:
            # Load configuration
            self.config = load_config(self.config_file)
            
            # Initialize configuration hot reloader
            self.config_hot_reloader = ConfigHotReloader(self.config_file)
            
            # Initialize logging
            # Support environment variable for log file path
            log_file_path = os.getenv('LOG_FILE_PATH', 'scheduler.log')
            self.logger = init_logger(
                debug=self.config.global_config.log_debug,
                log_file=log_file_path,
                log_level=self.config.global_config.log_level
            )
            
            # Output log level status
            self.logger.info(f"Log level set to: {self.config.global_config.log_level}")
            self.logger.debug("This is a Debug test log. If you see this message, Debug logging is working properly")
            if self.config.global_config.log_level == 'WARNING':
                self.logger.warning("Current log level is WARNING, only WARNING and above level logs will be displayed")
            elif self.config.global_config.log_level == 'ERROR':
                self.logger.error("Current log level is ERROR, only ERROR and above level logs will be displayed")
            
            self.logger.info("Starting F5 LLM Inference Gateway Scheduler...")
            
            # Initialize components
            self.f5_client = F5Client(
                host=self.config.f5.host,
                port=self.config.f5.port,
                username=self.config.f5.username,
                password=self.config.f5.password
            )
            
            self.metrics_collector = MetricsCollector()
            self.score_calculator = ScoreCalculator()
            
            # Create API server
            self.api_server = create_api_server(
                host=self.config.global_config.api_host,
                port=self.config.global_config.api_port
            )
            
            self.logger.info("Scheduler initialization completed")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Initialization failed: {e}")
            else:
                print(f"Initialization failed: {e}")
            raise

    def _validate_new_config(self, new_config: AppConfig) -> bool:
        """Validate new configuration validity"""
        try:
            # Basic validation
            if not new_config.f5.host:
                raise ValueError("F5 host cannot be empty")
            if not new_config.pools:
                raise ValueError("At least one Pool configuration is required")
            
            # Interval validation
            if new_config.global_config.interval <= 0:
                raise ValueError("global.interval must be greater than 0")
            if new_config.scheduler.pool_fetch_interval <= 0:
                raise ValueError("scheduler.pool_fetch_interval must be greater than 0")
            if new_config.scheduler.metrics_fetch_interval <= 0:
                raise ValueError("scheduler.metrics_fetch_interval must be greater than 0")
            
            return True
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            return False

    def _analyze_config_changes(self, old_config: AppConfig, new_config: AppConfig) -> Dict[str, bool]:
        """Analyze configuration changes"""
        changes = {
            'global': old_config.global_config != new_config.global_config,
            'f5': old_config.f5 != new_config.f5,
            'scheduler': old_config.scheduler != new_config.scheduler,
            'modes': old_config.modes != new_config.modes,
            'pools': old_config.pools != new_config.pools,
        }
        
        # Detailed analysis of global configuration changes
        if changes['global']:
            changes['global_interval'] = (old_config.global_config.interval != 
                                        new_config.global_config.interval)
            changes['global_log'] = (old_config.global_config.log_level != 
                                   new_config.global_config.log_level)
            changes['global_api_port'] = (old_config.global_config.api_port != 
                                         new_config.global_config.api_port)
            changes['global_api_host'] = (old_config.global_config.api_host != 
                                         new_config.global_config.api_host)
        
        # Detailed analysis of scheduler configuration changes
        if changes['scheduler']:
            changes['scheduler_pool_interval'] = (old_config.scheduler.pool_fetch_interval != 
                                                new_config.scheduler.pool_fetch_interval)
            changes['scheduler_metrics_interval'] = (old_config.scheduler.metrics_fetch_interval != 
                                                   new_config.scheduler.metrics_fetch_interval)
        
        return changes

    async def _update_logger_config(self, new_global_config):
        """Update logger configuration"""
        old_level = self.config.global_config.log_level
        new_level = new_global_config.log_level
        
        if old_level != new_level:
            self.logger.set_log_level(LogLevel[new_level])
            self.logger.info(f"Log level changed from {old_level} to {new_level}")

    async def _update_f5_config(self, new_f5_config):
        """Update F5 client configuration"""
        # Close old connection
        if self.f5_client:
            await self.f5_client.close()
            
        # Create new connection
        self.f5_client = F5Client(
            host=new_f5_config.host,
            port=new_f5_config.port,
            username=new_f5_config.username,
            password=new_f5_config.password
        )
        
        self.logger.info("F5 client configuration updated")

    async def _restart_pool_fetch_task(self, new_interval: int):
        """Restart Pool fetch task"""
        # Only restart if task list exists and has enough elements
        if self.tasks and len(self.tasks) > 1:
            # Cancel old Pool fetch task (index 1)
            old_task = self.tasks[1]  # pool_fetch_task is at index 1
            self.logger.debug("Canceling old Pool fetch task")
            old_task.cancel()
            
            try:
                await old_task  # Wait for task to complete fully
            except asyncio.CancelledError:
                pass
            
            # Create new task
            new_task = asyncio.create_task(self._pool_fetch_task())
            self.tasks[1] = new_task
            self.logger.info(f"Pool fetch task restarted, new interval: {new_interval} seconds")
        else:
            self.logger.info(f"Pool fetch task configuration updated, new interval: {new_interval} seconds (will take effect on next start)")

    async def _restart_metrics_collection_task(self, new_interval: int):
        """Restart Metrics collection task"""
        # Only restart if task list exists and has enough elements
        if self.tasks and len(self.tasks) > 2:
            # Cancel old Metrics collection task (index 2)
            old_task = self.tasks[2]  # metrics_collection_task is at index 2
            self.logger.debug("Canceling old Metrics collection task")
            old_task.cancel()
            
            try:
                await old_task  # Wait for task to complete fully
            except asyncio.CancelledError:
                pass
            
            # Create new task
            new_task = asyncio.create_task(self._metrics_collection_task())
            self.tasks[2] = new_task
            self.logger.info(f"Metrics collection task restarted, new interval: {new_interval/1000} seconds")
        else:
            self.logger.info(f"Metrics collection task configuration updated, new interval: {new_interval/1000} seconds (will take effect on next start)")

    async def _update_pools_config(self, old_pools: List[PoolConfig], new_pools: List[PoolConfig]):
        """Smart update Pool configuration"""
        # Build mapping between old and new configurations
        old_pool_map = {f"{p.name}:{p.partition}": p for p in old_pools}
        new_pool_map = {f"{p.name}:{p.partition}": p for p in new_pools}
        
        # 1. Handle removed Pools (explicitly deleted in configuration)
        removed_pools = set(old_pool_map.keys()) - set(new_pool_map.keys())
        for pool_key in removed_pools:
            if pool_key in POOLS:
                del POOLS[pool_key]
                self.logger.info(f"Configuration deleted Pool: {pool_key}")
        
        # 2. Handle added Pools (automatically created on next fetch)
        added_pools = set(new_pool_map.keys()) - set(old_pool_map.keys())
        for pool_key in added_pools:
            self.logger.info(f"Configuration added Pool: {pool_key}")
        
        # 3. Handle updated Pools (preserve member data and score)
        updated_pools = set(old_pool_map.keys()) & set(new_pool_map.keys())
        for pool_key in updated_pools:
            old_pool_config = old_pool_map[pool_key]
            new_pool_config = new_pool_map[pool_key]
            
            # Check for substantive changes
            if old_pool_config.engine_type != new_pool_config.engine_type:
                existing_pool = get_pool_by_key(new_pool_config.name, new_pool_config.partition)
                if existing_pool:
                    existing_pool.engine_type = EngineType(new_pool_config.engine_type)
                    self.logger.info(f"Updated Pool {pool_key} engine_type: {new_pool_config.engine_type}")
            
            # metrics configuration changes will be automatically applied on next collection
            if old_pool_config.metrics != new_pool_config.metrics:
                self.logger.info(f"Updated Pool {pool_key} metrics configuration")
        
        # 4. Clean up memory of Pools that exist in memory but not in configuration (avoid conflicts with fetch failure cleanup)
        # This handles configuration-level deletion, unlike fetch failure-driven cleanup
        configured_pool_keys = set(new_pool_map.keys())
        memory_pool_keys = set(POOLS.keys())
        orphaned_pools = memory_pool_keys - configured_pool_keys
        
        for orphaned_key in orphaned_pools:
            # Check if this is the most recent fetch failed Pool (avoid repeated processing)
            existing_pool = POOLS.get(orphaned_key)
            if existing_pool and hasattr(existing_pool, '_consecutive_failures'):
                if existing_pool._consecutive_failures > 0:
                    # This Pool has already been processed in fetch failure flow, skip
                    continue
            
            self.logger.info(f"Configuration cleanup: Deleting orphaned Pool from memory: {orphaned_key}")
            del POOLS[orphaned_key]

    def _update_modes_config(self, new_modes):
        """Update algorithm mode configuration"""
        self.logger.info("Algorithm mode configuration updated")

    async def apply_config_changes(self, new_config: AppConfig) -> bool:
        """Main process for applying configuration changes"""
        # Validate new configuration
        if not self._validate_new_config(new_config):
            raise ConfigurationError("New configuration validation failed")
        
        old_config = self.config
        changes = self._analyze_config_changes(old_config, new_config)
        
        changed_items = [k for k, v in changes.items() if v]
        self.logger.info(f"Starting to apply configuration changes: {changed_items}")
        
        try:
            # 1. Logger system hot update
            if changes.get('global_log', False):
                await self._update_logger_config(new_config.global_config)
                
            # 2. F5 client hot update
            if changes.get('f5', False):
                await self._update_f5_config(new_config.f5)
                
            # 3. Background task hot update
            if changes.get('scheduler_pool_interval', False):
                await self._restart_pool_fetch_task(new_config.scheduler.pool_fetch_interval)
                
            if changes.get('scheduler_metrics_interval', False):
                await self._restart_metrics_collection_task(new_config.scheduler.metrics_fetch_interval)
                
            # 4. Smart Pool configuration update
            if changes.get('pools', False):
                await self._update_pools_config(old_config.pools, new_config.pools)
                
            # 5. Algorithm mode update
            if changes.get('modes', False):
                self._update_modes_config(new_config.modes)
                
            # 6. API port change reminder
            if changes.get('global_api_port', False):
                self.logger.warning(f"API port changed from {old_config.global_config.api_port} "
                                  f"to {new_config.global_config.api_port}, need to restart program to take effect")
            
            # API address change reminder
            if changes.get('global_api_host', False):
                self.logger.warning(f"API listening address changed from {old_config.global_config.api_host} "
                                  f"to {new_config.global_config.api_host}, need to restart program to take effect")
                
            # 7. Apply new configuration
            self.config = new_config
            self.logger.info("Hot configuration update completed")
            
            # 8. Return whether to adjust monitoring interval
            return changes.get('global_interval', False)
            
        except Exception as e:
            self.logger.error(f"Hot configuration update failed, keeping original configuration: {e}")
            raise
    
    async def start(self):
        """Start scheduler"""
        await self.initialize()
        
        self.running = True
        
        # Start background tasks (excluding independent scheduled tasks for Score calculation)
        self.tasks = [
            asyncio.create_task(self._config_monitor_task()),
            asyncio.create_task(self._pool_fetch_task()),
            asyncio.create_task(self._metrics_collection_task()),
            asyncio.create_task(self._api_server_task())
        ]
        
        self.logger.info("Scheduler started, all background tasks are running...")
        
        # Wait for all tasks to complete
        try:
            await asyncio.gather(*self.tasks)
        except asyncio.CancelledError:
            self.logger.info("Scheduler tasks cancelled")
    
    async def stop(self):
        """Stop scheduler"""
        self.logger.info("Stopping scheduler...")
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for task cleanup
        await asyncio.gather(*self.tasks, return_exceptions=True)
        
        # Close connections
        if self.f5_client:
            await self.f5_client.close()
        if self.metrics_collector:
            await self.metrics_collector.close()
        
        self.logger.info("Scheduler stopped")
    
    async def _config_monitor_task(self):
        """Configuration file monitoring task (supports hot reload)"""
        # Use dynamic interval
        def get_current_interval():
            return self.config.global_config.interval
        
        self.logger.debug(f"Configuration monitoring task started, initial interval: {get_current_interval()}s")
        
        while self.running:
            try:
                current_interval = get_current_interval()
                await asyncio.sleep(current_interval)
                
                if not self.running:
                    break
                
                self.logger.debug("Checking configuration file updates...")
                
                # Detect configuration changes
                if await self.config_hot_reloader.detect_changes():
                    self.logger.info("Configuration file changes detected, starting hot reload...")
                    
                    try:
                        # Reload configuration
                        config_loader = get_config_loader(self.config_file)
                        new_config = config_loader.reload_config()
                        
                        # Apply configuration changes
                        interval_changed = await self.apply_config_changes(new_config)
                        
                        if interval_changed:
                            new_interval = get_current_interval()
                            self.logger.info(f"Configuration monitoring interval updated to: {new_interval}s")
                        
                    except Exception as e:
                        self.logger.error(f"Configuration hot reload failed: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Configuration monitoring task exception: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error
    
    async def _pool_fetch_task(self):
        """Pool member fetch task"""
        self.logger.debug(f"Pool fetch task started, interval: {self.config.scheduler.pool_fetch_interval}s")
        
        while self.running:
            try:
                await asyncio.sleep(self.config.scheduler.pool_fetch_interval)
                
                if not self.running:
                    break
                
                self.logger.debug("Starting to fetch Pool member information...")
                await self._fetch_all_pools()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Pool fetch task exception: {e}")
                await asyncio.sleep(30)  # Wait 30 seconds on error
    
    async def _score_calculation_task(self):
        """Score calculation task (single execution)"""
        try:
            await self._calculate_all_scores()
        except Exception as e:
            self.logger.error(f"Score calculation task exception: {e}")

    async def _metrics_collection_task(self):
        """Metrics collection task"""
        interval_seconds = self.config.scheduler.metrics_fetch_interval / 1000.0
        self.logger.debug(f"Metrics collection task started, interval: {interval_seconds}s")
        
        while self.running:
            try:
                await asyncio.sleep(interval_seconds)

                if not self.running:
                    break

                self.logger.debug("Starting to collect metrics...")
                await self._collect_all_metrics()
                
                # Note: Each Pool now triggers score calculation immediately after its metrics collection
                # No need for unified score calculation call here
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Metrics collection task exception: {e}")
                await asyncio.sleep(10)  # Wait 10 seconds on error
    
    async def _api_server_task(self):
        """API server task"""
        try:
            await self.api_server.start()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"API server exception: {e}")
    
    async def _fetch_all_pools(self):
        """Fetch member information for all Pools"""
        # Track successfully fetched Pools in this fetch
        successfully_fetched_pools = set()
        
        async with self.f5_client:
            for pool_config in self.config.pools:
                pool_key = f"{pool_config.name}:{pool_config.partition}"
                try:
                    # Get latest member list from F5
                    new_members = await self.f5_client.get_pool_members(
                        pool_config.name,
                        pool_config.partition
                    )
                    
                    engine_type = EngineType(pool_config.engine_type)
                    
                    # Check if Pool already exists
                    existing_pool = get_pool_by_key(pool_config.name, pool_config.partition)
                    
                    if existing_pool:
                        # Pool exists, smartly update member list (preserve score values)
                        # Record member information before update for comparison
                        old_member_keys = set(f"{m.ip}:{m.port}" for m in existing_pool.members)
                        new_member_keys = set(f"{m.ip}:{m.port}" for m in new_members)
                        
                        update_stats = existing_pool.update_members_smartly(new_members)
                        
                        self.logger.info(
                            f"Updated Pool {pool_config.name} members: "
                            f"preserved={update_stats['preserved']}, "
                            f"added={update_stats['added']}, "
                            f"removed={update_stats['removed']}, "
                            f"total={update_stats['total']}"
                        )
                        
                        # Record newly added members
                        added_members = new_member_keys - old_member_keys
                        if added_members:
                            self.logger.info(f"Added members: {list(added_members)}")
                        
                        # Record removed members
                        removed_members = old_member_keys - new_member_keys
                        if removed_members:
                            self.logger.info(f"Removed members: {list(removed_members)}")
                        
                        # Reset consecutive failure count
                        existing_pool._consecutive_failures = 0
                    else:
                        # Pool doesn't exist, create new Pool
                        pool = Pool(
                            name=pool_config.name,
                            partition=pool_config.partition,
                            engine_type=engine_type,
                            members=new_members
                        )
                        
                        # Add to memory
                        add_or_update_pool(pool)
                        
                        self.logger.info(f"Created new Pool {pool_config.name} with {len(new_members)} members")
                    
                    # Mark this Pool as successfully fetched
                    successfully_fetched_pools.add(pool_key)
                    
                except Exception as e:
                    # Analyze failure type and severity
                    failure_type, should_count_failure = self._analyze_fetch_failure(e, pool_config.name)
                    
                    self.logger.error(f"Failed to fetch Pool {pool_config.name} members ({failure_type}): {e}")
                    
                    # Only count serious failures (avoid false deletions due to temporary network issues)
                    if should_count_failure:
                        existing_pool = get_pool_by_key(pool_config.name, pool_config.partition)
                        if existing_pool:
                            # Increase consecutive failure count
                            if not hasattr(existing_pool, '_consecutive_failures'):
                                existing_pool._consecutive_failures = 0
                            existing_pool._consecutive_failures += 1
                            
                            self.logger.warning(
                                f"Pool {pool_key} consecutive serious failures {existing_pool._consecutive_failures} times (type: {failure_type})"
                            )
                            
                            # If consecutive failures exceed threshold, remove from memory
                            failure_threshold = 5
                            if existing_pool._consecutive_failures >= failure_threshold:
                                self.logger.warning(
                                    f"Pool {pool_key} consecutive serious failures {failure_threshold} times, may have been deleted, cleaning from memory"
                                )
                                del POOLS[pool_key]
                    else:
                        self.logger.info(f"Pool {pool_key} encountered temporary issues, not counting as failure")
        
        # Note: Removed configuration consistency cleanup to avoid conflicts with hot reload
        # Configuration consistency cleanup is handled in hot reload's _update_pools_config
    
    def _analyze_fetch_failure(self, exception: Exception, pool_name: str) -> tuple[str, bool]:
        """Analyze the type and severity of fetch failures
        
        Returns:
            tuple: (failure_type, should_count_failure)
            - failure_type: Description of failure type
            - should_count_failure: Whether it should be counted in consecutive failure count
        """
        from utils.exceptions import F5ApiError, TokenAuthenticationError
        import aiohttp
        
        # 1. Network connection issues - might be temporary, count as failure but with reduced weight
        if isinstance(exception, aiohttp.ClientError):
            if "timeout" in str(exception).lower():
                return "Network timeout", True  # Timeout might indicate serious issues
            else:
                return "Network connection error", False  # Other network issues might be temporary
        
        # 2. F5 API errors - analyze specific status codes
        if isinstance(exception, F5ApiError):
            error_msg = str(exception).lower()
            if "404" in error_msg:
                return "Pool does not exist (404)", True  # Pool deleted, serious failure
            elif "401" in error_msg or "403" in error_msg:
                return "Authentication failed", False  # Authentication issue, not Pool issue
            elif "500" in error_msg or "502" in error_msg or "503" in error_msg:
                return "F5 server error", False  # Server issue, might be temporary
            else:
                return "F5 API error", True  # Other API errors, might be serious
        
        # 3. Token authentication failure - usually temporary issue
        if isinstance(exception, TokenAuthenticationError):
            return "Token authentication failed", False
        
        # 4. Other exceptions - might be configuration or code issues
        return "Unknown error", True

    async def _collect_all_metrics(self):
        """Collect metrics from all Pools (parallel execution)"""
        pools = get_all_pools()
        if not pools:
            return
        
        async with self.metrics_collector:
            # Create async tasks for each Pool
            tasks = []
            pool_names = []  # For logging
            
            for pool in pools:
                # Find corresponding configuration
                pool_config = None
                for config in self.config.pools:
                    if config.name == pool.name and config.partition == pool.partition:
                        pool_config = config
                        break
                
                if not pool_config:
                    self.logger.warning(f"Configuration not found for Pool {pool.name}")
                    continue
                
                # Port usage strategy: use configured port if available, otherwise use None to let members use their own ports
                metrics_port = pool_config.metrics.port if pool_config.metrics.port else None
                
                self.logger.debug(f"Pool {pool.name} metrics port strategy: "
                                f"{'Use configured port ' + str(metrics_port) if metrics_port else 'Use member own ports'}")
                
                # Create metrics collection task for single Pool
                task = self._collect_single_pool_metrics(
                    pool,
                    pool_config.metrics.schema,
                    pool_config.metrics.path,
                    metrics_port,
                    pool_config.metrics.api_key,
                    pool_config.metrics.metric_user,
                    pool_config.metrics.metric_password,
                    pool_config.metrics.timeout
                )
                tasks.append(task)
                pool_names.append(pool.name)
            
            if not tasks:
                self.logger.debug("No valid Pool configurations, skipping metrics collection")
                return
            
            # Execute all Pool metrics collection and score calculation in parallel
            self.logger.info(f"Starting parallel processing of {len(tasks)} Pools (Metrics collection + Score calculation): {pool_names}")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results and log
            success_count = 0
            for i, (pool_name, result) in enumerate(zip(pool_names, results)):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to process Pool {pool_name}: {result}")
                else:
                    success_count += 1
                    
            self.logger.info(f"Parallel processing completed: {success_count}/{len(tasks)} Pools successful")
    
    async def _collect_single_pool_metrics(
        self,
        pool: Pool,
        schema: str,
        path: str,
        metrics_port: Optional[int],
        api_key: Optional[str],
        username: Optional[str],
        password: Optional[str],
        timeout: Optional[int]
    ) -> None:
        """Collect metrics for a single Pool (for parallel execution)"""
        try:
            # Collect metrics for this Pool
            await self.metrics_collector.collect_pool_metrics(
                pool, schema, path, metrics_port, api_key, username, password, timeout
            )
            
            # Immediately trigger score calculation for this Pool after metrics collection
            await self._calculate_single_pool_score(pool)
            
        except Exception as e:
            # Let exception propagate up, handled by caller
            raise e
    
    async def _calculate_single_pool_score(self, pool: Pool) -> None:
        """Calculate score for a single Pool (for independent triggering)"""
        # Get algorithm mode configuration
        mode_config = self.config.modes[0] if self.config.modes else None
        if not mode_config:
            self.logger.warning("Algorithm mode configuration not found")
            return
        
        try:
            self.score_calculator.calculate_pool_scores(pool, mode_config)
        except Exception as e:
            self.logger.error(f"Failed to calculate score for Pool {pool.name}: {e}")

    async def _calculate_all_scores(self):
        """Calculate scores for all Pools (kept for compatibility, but rarely used now)"""
        pools = get_all_pools()
        if not pools:
            return
        
        # Get algorithm mode configuration
        mode_config = self.config.modes[0] if self.config.modes else None
        if not mode_config:
            self.logger.warning("Algorithm mode configuration not found")
            return
        
        for pool in pools:
            try:
                self.score_calculator.calculate_pool_scores(pool, mode_config)
            except Exception as e:
                self.logger.error(f"Failed to calculate score for Pool {pool.name}: {e}")


def setup_signal_handlers(app: SchedulerApp):
    """Setup signal handlers"""
    def signal_handler(signum, frame):
        print(f"\nReceived signal {signum}, shutting down scheduler...")
        asyncio.create_task(app.stop())
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


async def main():
    """Main function"""
    app = SchedulerApp()
    
    try:
        setup_signal_handlers(app)
        await app.start()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt, shutting down...")
    except Exception as e:
        print(f"Program exception: {e}")
    finally:
        await app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram interrupted")
    except Exception as e:
        print(f"Program startup failed: {e}")
        sys.exit(1) 