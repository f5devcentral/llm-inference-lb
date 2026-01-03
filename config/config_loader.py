"""
Configuration file loading module
Responsible for reading and parsing YAML configuration files, handling default values and environment variables
"""

import os
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from pathlib import Path
import yaml

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from utils.exceptions import ConfigurationError


@dataclass 
class GlobalConfig:
    """Global configuration"""
    interval: int = 60
    log_debug: bool = False
    log_level: str = "INFO"
    api_port: int = 8080
    api_host: str = "0.0.0.0"


@dataclass
class F5Config:
    """F5 configuration"""
    host: str = ""
    port: int = 443
    username: str = "admin"
    password: str = "admin"


@dataclass
class SchedulerConfig:
    """Scheduler configuration"""
    pool_fetch_interval: int = 10
    metrics_fetch_interval: int = 1000


@dataclass
class ModeConfig:
    """Algorithm mode configuration"""
    name: str = "s1"
    w_a: float = 0.5
    w_b: float = 0.5
    w_g: float = 0.0
    # 动态waiting权重算法专用参数
    transition_point: float = 30.0  # 过渡点：多少个等待请求作为权重调整的中心点
    steepness: float = 1.0         # 陡峭度：控制权重过渡的平滑程度


@dataclass
class MetricsConfig:
    """Metrics configuration"""
    schema: str = "http"
    port: Optional[int] = None  # None means use member's own port, specific value means use specified port
    path: str = "/metrics"
    api_key: Optional[str] = None
    metric_user: Optional[str] = None
    metric_password: Optional[str] = None
    timeout: int = 3  # HTTP request timeout (seconds)


@dataclass
class FallbackConfig:
    """Fallback configuration"""
    pool_fallback: bool = False  # Pool level fallback switch, default is off
    member_running_req_threshold: Optional[float] = None  # Running request threshold for member filtering
    member_waiting_queue_threshold: Optional[float] = None  # Waiting queue threshold for member filtering


@dataclass
class ModelApiKeyConfig:
    """Model API Key configuration for XInference engine type"""
    path: str = "/v1/cluster/authorizations"
    f5datagroup: str = ""
    timeout: int = 4
    api_key_sync_interval: int = 300
    APIkey: Optional[str] = None
    apikey_user: Optional[str] = None
    apikey_pwd_env: Optional[str] = None
    # 故障处理配置
    failure_mode: str = "preserve"           # preserve/clear/smart
    max_failures_threshold: int = 10         # 智能模式下的失败阈值
    failure_timeout_hours: float = 2.0       # 智能模式下的超时时间


@dataclass
class EngineVariantConfig:
    """Engine variant metrics key configuration
    
    Used to define custom metrics keys for engine variants like vllm_ascend, vllm_musa, sglang_xxx
    """
    variant_name: str = ""  # Variant name, e.g., vllm_ascend, vllm-mlu, sglang_xxx
    waiting_queue: Optional[str] = None  # Custom waiting_queue metric key
    cache_usage: Optional[str] = None    # Custom cache_usage metric key
    running_req: Optional[str] = None    # Custom running_req metric key


@dataclass
class PoolConfig:
    """Pool configuration"""
    name: str = ""
    partition: str = "Common"
    engine_type: str = ""
    fallback: FallbackConfig = field(default_factory=FallbackConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    model_APIkey: Optional[ModelApiKeyConfig] = None  # Only for XInference engine type


@dataclass
class AppConfig:
    """Application total configuration"""
    global_config: GlobalConfig = field(default_factory=GlobalConfig)
    f5: F5Config = field(default_factory=F5Config)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    modes: List[ModeConfig] = field(default_factory=lambda: [ModeConfig()])
    pools: List[PoolConfig] = field(default_factory=list)
    # Engine variant metrics keys configuration
    # Structure: {variant_name: {waiting_queue: str, cache_usage: str, running_req: str}}
    engine_metrics_keys: Dict[str, Dict[str, str]] = field(default_factory=dict)


class ConfigLoader:
    """Configuration loader"""
    
    # Supported engine types
    SUPPORTED_ENGINE_TYPES = ['vllm', 'sglang', 'xinference']
    
    def __init__(self, config_file: str = "config/scheduler-config.yaml"):
        self.config_file = config_file
        self.logger = get_logger()
        self._config: Optional[AppConfig] = None
    
    def load_config(self) -> AppConfig:
        """Load configuration file"""
        try:
            # Check if configuration file exists
            if not Path(self.config_file).exists():
                self.logger.warning(f"Configuration file {self.config_file} does not exist, using default configuration")
                return self._create_default_config()
            
            # Read YAML file
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f) or {}
            
            self.logger.info(f"Successfully loaded configuration file: {self.config_file}")
            return self._parse_config(config_data)
            
        except yaml.YAMLError as e:
            self.logger.error(f"Configuration file format error: {e}")
            raise ConfigurationError(f"Configuration file format error: {e}")
        except Exception as e:
            self.logger.error(f"Failed to load configuration file: {e}")
            raise ConfigurationError(f"Configuration file loading failed: {e}")
    
    def _create_default_config(self) -> AppConfig:
        """Create default configuration"""
        config = AppConfig()
        self.logger.info("Using default configuration")
        return config
    
    def _parse_config(self, config_data: Dict[str, Any]) -> AppConfig:
        """Parse configuration data"""
        config = AppConfig()
        
        # Parse global configuration
        if 'global' in config_data:
            global_data = config_data['global']
            config.global_config.interval = global_data.get('interval', 60)
            config.global_config.api_port = global_data.get('api_port', 8080)
            config.global_config.api_host = global_data.get('api_host', '0.0.0.0')
            
            # Handle log level configuration (prioritize log_level, maintain backward compatibility with log_debug)
            if 'log_level' in global_data:
                # If log_level is configured, use it
                config.global_config.log_level = str(global_data['log_level']).upper()
                # For backward compatibility, set log_debug based on log_level
                config.global_config.log_debug = (config.global_config.log_level == 'DEBUG')
            else:
                # If log_level is not configured, use original log_debug logic
                log_debug_value = global_data.get('log_debug', False)
                if isinstance(log_debug_value, bool):
                    config.global_config.log_debug = log_debug_value
                elif isinstance(log_debug_value, str):
                    config.global_config.log_debug = log_debug_value.lower() in ['true', 'yes', '1', 'on']
                else:
                    config.global_config.log_debug = bool(log_debug_value)
                
                # Set log_level based on log_debug
                config.global_config.log_level = 'DEBUG' if config.global_config.log_debug else 'INFO'
        
        # Parse F5 configuration
        if 'f5' in config_data:
            f5_data = config_data['f5']
            config.f5.host = f5_data.get('host', '')
            config.f5.port = f5_data.get('port', 443)
            config.f5.username = f5_data.get('username', 'admin')
            
            # Handle password environment variable
            password_env = f5_data.get('password_env', '')
            if password_env:
                config.f5.password = os.getenv(password_env, 'admin')
                if config.f5.password == 'admin':
                    self.logger.warning(f"Environment variable {password_env} not set, using default password")
        
        # Validate required F5 configuration
        if not config.f5.host:
            self.logger.error("Missing required configuration item: f5.host")
            raise ConfigurationError("Missing required configuration item: f5.host")
        
        # Parse scheduler configuration
        if 'scheduler' in config_data:
            scheduler_data = config_data['scheduler']
            config.scheduler.pool_fetch_interval = scheduler_data.get('pool_fetch_interval', 10)
            config.scheduler.metrics_fetch_interval = scheduler_data.get('metrics_fetch_interval', 5000)
        
        # Parse modes configuration
        if 'modes' in config_data:
            config.modes = []
            for mode_data in config_data['modes']:
                mode = ModeConfig()
                mode.name = mode_data.get('name', 's1')
                mode.w_a = float(mode_data.get('w_a', 0.5))
                mode.w_b = float(mode_data.get('w_b', 0.5))
                mode.w_g = float(mode_data.get('w_g', 0.0))
                
                # 解析动态waiting权重算法专用参数
                mode.transition_point = float(mode_data.get('transition_point', 30.0))
                mode.steepness = float(mode_data.get('steepness', 1.0))
                
                # Validate algorithm mode
                supported_modes = ['s1', 's1_enhanced', 's1_adaptive', 's1_ratio', 's1_precise', 's1_nonlinear', 
                                 's1_balanced', 's1_adaptive_distribution', 's1_advanced', 's1_dynamic_waiting',
                                 's2', 's2_enhanced', 's2_nonlinear', 's2_adaptive', 's2_advanced', 's2_dynamic_waiting']
                if mode.name not in supported_modes:
                    self.logger.warning(f"Unsupported algorithm mode: {mode.name}, supported modes: {supported_modes}, using default mode s1")
                    mode.name = 's1'
                
                config.modes.append(mode)
        
        # Parse engines_metrics_keys configuration
        if 'engines_metrics_keys' in config_data:
            config.engine_metrics_keys = self._parse_engine_metrics_keys(config_data['engines_metrics_keys'])
        
        # Parse pools configuration
        if 'pools' in config_data:
            config.pools = []
            for pool_data in config_data['pools']:
                pool = self._parse_pool_config(pool_data)
                config.pools.append(pool)
        
        # Validate required pool configuration
        if not config.pools:
            self.logger.error("At least one Pool must be configured")
            raise ConfigurationError("At least one Pool must be configured")
        
        self._config = config
        return config
    
    def _parse_engine_metrics_keys(self, engine_metrics_data: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """Parse engines_metrics_keys configuration
        
        Args:
            engine_metrics_data: Raw engines_metrics_keys configuration from YAML
            
        Returns:
            Parsed configuration: {variant_name: {waiting_queue: str, cache_usage: str, running_req: str}}
        """
        result = {}
        
        if not engine_metrics_data or not isinstance(engine_metrics_data, dict):
            return result
        
        for variant_name, variant_config in engine_metrics_data.items():
            if not isinstance(variant_config, dict):
                self.logger.warning(f"Invalid engines_metrics_keys configuration for '{variant_name}', expected dict")
                continue
            
            # Validate variant name starts with known engine type prefix
            lower_name = variant_name.lower()
            if not (lower_name.startswith('vllm') or lower_name.startswith('sglang')):
                self.logger.warning(
                    f"Variant name '{variant_name}' does not start with 'vllm' or 'sglang', skipping. "
                    f"Note: xinference variants are not supported."
                )
                continue
            
            # Parse metrics keys (all optional)
            parsed_config = {}
            for key_type in ['waiting_queue', 'cache_usage', 'running_req']:
                if key_type in variant_config and variant_config[key_type]:
                    parsed_config[key_type] = str(variant_config[key_type])
            
            if parsed_config:
                result[variant_name] = parsed_config
                self.logger.debug(f"Parsed engine variant '{variant_name}': {parsed_config}")
            else:
                self.logger.warning(f"Variant '{variant_name}' has no valid metrics keys configured, skipping")
        
        if result:
            self.logger.info(f"Loaded engines_metrics_keys configuration: {', '.join(result.keys())}")
        
        return result
    
    def _parse_pool_config(self, pool_data: Dict[str, Any]) -> PoolConfig:
        """Parse Pool configuration"""
        pool = PoolConfig()
        
        # Required configuration
        pool.name = pool_data.get('name', '')
        pool.engine_type = pool_data.get('engine_type', '')
        
        if not pool.name:
            raise ConfigurationError("Pool configuration missing name field")
        if not pool.engine_type:
            raise ConfigurationError(f"Pool {pool.name} missing engine_type field")
        
        # Validate engine_type
        if pool.engine_type.lower() not in self.SUPPORTED_ENGINE_TYPES:
            raise ConfigurationError(
                f"Pool {pool.name} has unsupported engine_type '{pool.engine_type}'. "
                f"Supported types: {', '.join(self.SUPPORTED_ENGINE_TYPES)}. "
                f"For vllm variants (vllm_ascend, vllm_musa, etc.), use 'vllm' as engine_type "
                f"and configure the variant in 'engines_metrics_keys' section."
            )
        
        # Optional configuration
        pool.partition = pool_data.get('partition', 'Common')
        
        # Parse fallback configuration
        if 'fallback' in pool_data:
            fallback_data = pool_data['fallback']
            pool.fallback.pool_fallback = fallback_data.get('pool_fallback', False)
            
            # Parse member thresholds
            running_threshold = fallback_data.get('member_running_req_threshold')
            if running_threshold is not None:
                pool.fallback.member_running_req_threshold = float(running_threshold)
            
            waiting_threshold = fallback_data.get('member_waiting_queue_threshold')
            if waiting_threshold is not None:
                pool.fallback.member_waiting_queue_threshold = float(waiting_threshold)
        
        # Parse metrics configuration
        if 'metrics' in pool_data:
            metrics_data = pool_data['metrics']
            pool.metrics.schema = metrics_data.get('schema', 'http')
            
            # Handle port field: if user configured port, use configured value, otherwise None (use member port)
            configured_port = metrics_data.get('port')
            if configured_port is not None:
                pool.metrics.port = int(configured_port)
                self.logger.debug(f"Pool {pool.name} configured metrics port: {pool.metrics.port}")
            else:
                pool.metrics.port = None
                self.logger.debug(f"Pool {pool.name} no configured metrics port, will use each member's own port")
            
            pool.metrics.path = metrics_data.get('path', '/metrics')
            pool.metrics.api_key = metrics_data.get('APIkey')
            pool.metrics.metric_user = metrics_data.get('metric_user')
            pool.metrics.timeout = int(metrics_data.get('timeout', 3))
            
            # Handle password environment variable
            metric_pwd_env = metrics_data.get('metric_pwd_env', '')
            if metric_pwd_env:
                pool.metrics.metric_password = os.getenv(metric_pwd_env, '')
                if not pool.metrics.metric_password:
                    self.logger.warning(f"Environment variable {metric_pwd_env} not set")
        else:
            self.logger.debug(f"Pool {pool.name} no metrics configuration")
        
        # Parse model_APIkey configuration (only for XInference engine type)
        if 'model_APIkey' in pool_data:
            if pool.engine_type.lower() == 'xinference':
                model_apikey_data = pool_data['model_APIkey']
                pool.model_APIkey = ModelApiKeyConfig()
                
                # Required fields
                pool.model_APIkey.path = model_apikey_data.get('path', '/v1/cluster/authorizations')
                pool.model_APIkey.f5datagroup = model_apikey_data.get('f5datagroup', '')
                
                if not pool.model_APIkey.f5datagroup:
                    raise ConfigurationError(f"Pool {pool.name} with XInference engine type missing f5datagroup field in model_APIkey")
                
                # Optional fields
                pool.model_APIkey.timeout = int(model_apikey_data.get('timeout', 4))
                pool.model_APIkey.api_key_sync_interval = int(model_apikey_data.get('api_key_sync_interval', 300))
                pool.model_APIkey.APIkey = model_apikey_data.get('APIkey')
                pool.model_APIkey.apikey_user = model_apikey_data.get('apikey_user')
                pool.model_APIkey.apikey_pwd_env = model_apikey_data.get('apikey_pwd_env')
                
                # Failure handling configuration
                pool.model_APIkey.failure_mode = model_apikey_data.get('failure_mode', 'preserve')
                pool.model_APIkey.max_failures_threshold = int(model_apikey_data.get('max_failures_threshold', 10))
                pool.model_APIkey.failure_timeout_hours = float(model_apikey_data.get('failure_timeout_hours', 2.0))
                
                # Validate failure_mode
                valid_failure_modes = ['preserve', 'clear', 'smart']
                if pool.model_APIkey.failure_mode not in valid_failure_modes:
                    self.logger.warning(f"Invalid failure_mode '{pool.model_APIkey.failure_mode}' for pool {pool.name}, using 'preserve'")
                    pool.model_APIkey.failure_mode = 'preserve'
                
                self.logger.debug(f"Pool {pool.name} configured model_APIkey: datagroup={pool.model_APIkey.f5datagroup}, interval={pool.model_APIkey.api_key_sync_interval}s")
            else:
                self.logger.warning(f"Pool {pool.name} has model_APIkey configuration but engine_type is '{pool.engine_type}', not 'xinference'. Ignoring model_APIkey configuration.")
        elif pool.engine_type.lower() == 'xinference':
            self.logger.info(f"Pool {pool.name} is XInference type but no model_APIkey configuration found. API key synchronization will be disabled.")
        
        return pool
    
    def get_current_config(self) -> Optional[AppConfig]:
        """Get current configuration"""
        return self._config
    
    def reload_config(self) -> AppConfig:
        """Reload configuration"""
        self.logger.info("Reloading configuration file")
        return self.load_config()


# Global configuration loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader(config_file: str = "config/scheduler-config.yaml") -> ConfigLoader:
    """Get configuration loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader(config_file)
    return _config_loader


def load_config(config_file: str = "config/scheduler-config.yaml") -> AppConfig:
    """Convenient function to load configuration"""
    loader = get_config_loader(config_file)
    return loader.load_config()
