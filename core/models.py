"""
Data model definition module
Defines core data structures used by the scheduler
"""

from typing import Dict, List, Optional, Any
from enum import Enum


class EngineType(Enum):
    """Inference engine type enumeration"""
    VLLM = "vllm"
    SGLANG = "sglang"
    XINFERENCE = "xinference"


class PoolMember:
    """Pool member data model"""
    __slots__ = ("ip", "port", "partition", "metrics", "score", "model_metrics", 
                 "model_scores", "metrics_key_cache", "detected_variant")
    
    def __init__(self, ip: str, port: int, partition: str):
        self.ip: str = ip
        self.port: int = port
        self.partition: str = partition
        self.metrics: Dict[str, float] = {}  # For vLLM/SGLang prometheus metrics
        self.model_metrics: Dict[str, float] = {}  # For XInference model-level metrics: {model_name: throughput_utilization}
        self.model_scores: Dict[str, float] = {}  # For XInference precomputed model scores: {model_name: score}
        # Initialize to a small positive number to avoid all members being filtered out in initial state
        # This value is small enough not to affect normal weighted selection, but large enough to be > 0
        self.score: float = 0.001
        # Cache for detected metrics keys: {metric_type: actual_key}
        # e.g., {"waiting_queue": "vllm:num_requests_waiting", "cache_usage": "vllm:kv_cache_usage_perc"}
        self.metrics_key_cache: Dict[str, str] = {}
        # Detected variant name for this member (e.g., "vllm_ascend", "vllm", "sglang_xxx")
        self.detected_variant: Optional[str] = None
    
    def metric_uri(self, schema: str, path: str, metrics_port: Optional[int] = None) -> str:
        """Construct metrics interface URI
        
        Args:
            schema: http/https protocol
            path: metrics path
            metrics_port: Optional metrics port, if not provided, use member's own port
        """
        port = metrics_port if metrics_port is not None else self.port
        return f"{schema}://{self.ip}:{port}{path}"
    
    def __str__(self) -> str:
        return f"{self.ip}:{self.port}"
    
    def __eq__(self, other) -> bool:
        if not isinstance(other, PoolMember):
            return False
        return self.ip == other.ip and self.port == other.port
    
    def __hash__(self) -> int:
        return hash((self.ip, self.port))
    
    def get_model_score(self, model_name: str) -> float:
        """Get precomputed score for specific model (XInference)
        
        Args:
            model_name: Model name to get score for
            
        Returns:
            Precomputed score for the model, or default score if not found
        """
        if model_name and model_name in self.model_scores:
            return self.model_scores[model_name]
        return self.score
    
    def set_model_metric(self, model_name: str, throughput_utilization: float) -> None:
        """Set throughput utilization for specific model (XInference)
        
        Args:
            model_name: Model name
            throughput_utilization: Throughput utilization value (0.0-1.0)
        """
        if not model_name:
            return
            
        # Validate throughput_utilization range and handle edge cases
        if throughput_utilization is None:
            throughput_utilization = 0.0
        elif throughput_utilization < 0.0:
            throughput_utilization = 0.0
        elif throughput_utilization > 1.0:
            throughput_utilization = 1.0
            
        self.model_metrics[model_name] = throughput_utilization
    
    def has_model(self, model_name: str) -> bool:
        """Check if member has metrics for specific model
        
        Args:
            model_name: Model name to check
            
        Returns:
            True if member has metrics for the model
        """
        return model_name and model_name in self.model_metrics
    
    def clear_metrics_key_cache(self) -> None:
        """Clear cached metrics keys and detected variant
        
        Called when configuration changes or when cached key becomes invalid
        """
        self.metrics_key_cache = {}
        self.detected_variant = None


class Pool:
    """Pool data model"""
    __slots__ = ("name", "partition", "engine_type", "members", "_consecutive_failures", 
                 "pool_fallback", "member_running_req_threshold", "member_waiting_queue_threshold", "model_APIkey")
    
    def __init__(self, name: str, partition: str, engine_type: EngineType, members: List[PoolMember] = None, 
                 pool_fallback: bool = False, member_running_req_threshold: Optional[float] = None, 
                 member_waiting_queue_threshold: Optional[float] = None):
        self.name: str = name
        self.partition: str = partition
        self.engine_type: EngineType = engine_type
        self.members: List[PoolMember] = members or []
        self._consecutive_failures: int = 0  # Consecutive fetch failure count
        self.pool_fallback: bool = pool_fallback  # Pool level fallback switch
        self.member_running_req_threshold: Optional[float] = member_running_req_threshold  # Running request threshold
        self.member_waiting_queue_threshold: Optional[float] = member_waiting_queue_threshold  # Waiting queue threshold
        self.model_APIkey = None  # XInference API key configuration
    
    def update_members_smartly(self, new_members: List[PoolMember]) -> None:
        """Smartly update member list, preserving existing members' score values and metrics key cache"""
        # Create mapping table for existing members (based on ip:port)
        existing_members_map = {}
        for member in self.members:
            key = f"{member.ip}:{member.port}"
            existing_members_map[key] = member
        
        # Process new member list
        updated_members = []
        for new_member in new_members:
            key = f"{new_member.ip}:{new_member.port}"
            
            if key in existing_members_map:
                # Member already exists, preserve its score value, metrics, and key cache
                existing_member = existing_members_map[key]
                # Keep score value, metrics, and key cache
                new_member.score = existing_member.score
                new_member.metrics = existing_member.metrics
                new_member.model_metrics = existing_member.model_metrics
                new_member.metrics_key_cache = existing_member.metrics_key_cache
                new_member.detected_variant = existing_member.detected_variant
                updated_members.append(new_member)
            else:
                # New member, use default initial values (no cache, will auto-detect)
                updated_members.append(new_member)
        
        # Record changes
        old_count = len(self.members)
        new_count = len(updated_members)
        preserved_count = sum(1 for new_member in updated_members 
                            if f"{new_member.ip}:{new_member.port}" in existing_members_map)
        added_count = new_count - preserved_count
        removed_count = old_count - preserved_count
        
        # Update member list
        self.members = updated_members
        
        return {
            "preserved": preserved_count,
            "added": added_count, 
            "removed": removed_count,
            "total": new_count
        }
    
    def clear_all_members_key_cache(self) -> None:
        """Clear metrics key cache for all members in this pool
        
        Called when engines_metrics_keys configuration changes
        """
        for member in self.members:
            member.clear_metrics_key_cache()
    
    def get_pool_key(self) -> str:
        """Get Pool's unique identifier"""
        return f"{self.name}:{self.partition}"
    
    def find_member(self, ip: str, port: int) -> Optional[PoolMember]:
        """Find specified member"""
        for member in self.members:
            if member.ip == ip and member.port == port:
                return member
        return None
    
    def is_xinference(self) -> bool:
        """Check if this pool is XInference type"""
        return self.engine_type == EngineType.XINFERENCE
    
    def get_members_with_model(self, model_name: str) -> List[PoolMember]:
        """Get members that have metrics for specific model (XInference)
        
        Args:
            model_name: Model name to filter by
            
        Returns:
            List of members that have the specified model
        """
        if not model_name or not self.is_xinference():
            return self.members
            
        return [member for member in self.members if member.has_model(model_name)]


# Global memory: pool name → Pool object
POOLS: Dict[str, Pool] = {}


# ============================================================================
# ENGINE METRICS CONFIGURATION
# ============================================================================

# Built-in base metrics keys (standard keys for each engine type)
BASE_ENGINE_METRICS = {
    EngineType.VLLM: {
        "waiting_queue": "vllm:num_requests_waiting",
        "cache_usage": "vllm:gpu_cache_usage_perc",
        "running_req": "vllm:num_requests_running"
    },
    EngineType.SGLANG: {
        "waiting_queue": "sglang:num_queue_reqs", 
        "cache_usage": "sglang:token_usage",
        "running_req": "sglang:num_running_reqs"
    },
    EngineType.XINFERENCE: {
        "throughput_utilization": "throughput_utilization"  # XInference uses JSON format, not prometheus
    }
}

# Runtime candidate lists for metrics keys (populated on startup and config reload)
# Structure: {EngineType: {metric_type: [key1, key2, ...]}}
# Keys are ordered by priority: user-configured variants first, then built-in
ENGINE_METRICS_CANDIDATES: Dict[EngineType, Dict[str, List[str]]] = {}

# Mapping from metrics key to variant name (for logging and API response)
# Structure: {metrics_key: variant_name}
# e.g., {"vllm:kv_cache_usage_perc": "vllm_ascend", "vllm:gpu_cache_usage_perc": "vllm"}
METRICS_KEY_VARIANT_MAP: Dict[str, str] = {}

# Legacy compatibility: ENGINE_METRICS will be dynamically updated
# For code that still references ENGINE_METRICS, return first candidate
ENGINE_METRICS: Dict[EngineType, Dict[str, str]] = {}


def _infer_base_engine(variant_name: str) -> Optional[EngineType]:
    """Infer base engine type from variant name
    
    Args:
        variant_name: Variant name like 'vllm_ascend', 'vllm-mlu', 'sglang_xxx'
        
    Returns:
        EngineType if can infer, None otherwise
    """
    lower_name = variant_name.lower()
    if lower_name.startswith("vllm"):
        return EngineType.VLLM
    elif lower_name.startswith("sglang"):
        return EngineType.SGLANG
    return None


def initialize_engine_metrics_candidates(engine_metrics_keys_config: Optional[Dict[str, Any]] = None) -> None:
    """Initialize ENGINE_METRICS_CANDIDATES from configuration
    
    This function should be called on startup after loading configuration.
    
    Args:
        engine_metrics_keys_config: Parsed engines_metrics_keys configuration
            Structure: {variant_name: {waiting_queue: str, cache_usage: str, running_req: str}}
    """
    global ENGINE_METRICS_CANDIDATES, METRICS_KEY_VARIANT_MAP, ENGINE_METRICS
    
    # Reset candidates and mapping
    ENGINE_METRICS_CANDIDATES = {}
    METRICS_KEY_VARIANT_MAP = {}
    ENGINE_METRICS = {}
    
    # Initialize with empty lists for each engine type
    for engine_type in [EngineType.VLLM, EngineType.SGLANG]:
        ENGINE_METRICS_CANDIDATES[engine_type] = {
            "waiting_queue": [],
            "cache_usage": [],
            "running_req": []
        }
    
    # XInference uses different structure (JSON, not prometheus)
    ENGINE_METRICS_CANDIDATES[EngineType.XINFERENCE] = {
        "throughput_utilization": ["throughput_utilization"]
    }
    
    # Step 1: Add user-configured variant keys first (higher priority)
    if engine_metrics_keys_config:
        for variant_name, variant_config in engine_metrics_keys_config.items():
            base_engine = _infer_base_engine(variant_name)
            if not base_engine:
                continue  # Skip unknown engine types
            
            if base_engine == EngineType.XINFERENCE:
                continue  # Skip xinference variants
            
            # Add configured keys to candidate lists
            for metric_type in ["waiting_queue", "cache_usage", "running_req"]:
                key = variant_config.get(metric_type)
                if key and key not in ENGINE_METRICS_CANDIDATES[base_engine][metric_type]:
                    ENGINE_METRICS_CANDIDATES[base_engine][metric_type].append(key)
                    METRICS_KEY_VARIANT_MAP[key] = variant_name
    
    # Step 2: Add built-in base keys (lower priority, as fallback)
    for engine_type in [EngineType.VLLM, EngineType.SGLANG]:
        base_metrics = BASE_ENGINE_METRICS.get(engine_type, {})
        for metric_type in ["waiting_queue", "cache_usage", "running_req"]:
            base_key = base_metrics.get(metric_type)
            if base_key and base_key not in ENGINE_METRICS_CANDIDATES[engine_type][metric_type]:
                ENGINE_METRICS_CANDIDATES[engine_type][metric_type].append(base_key)
                # Mark built-in keys with engine type name as variant
                if base_key not in METRICS_KEY_VARIANT_MAP:
                    METRICS_KEY_VARIANT_MAP[base_key] = engine_type.value
    
    # Step 3: Build legacy ENGINE_METRICS for backward compatibility
    # Use the first candidate (highest priority) for each metric type
    for engine_type in [EngineType.VLLM, EngineType.SGLANG]:
        ENGINE_METRICS[engine_type] = {}
        for metric_type in ["waiting_queue", "cache_usage", "running_req"]:
            candidates = ENGINE_METRICS_CANDIDATES[engine_type].get(metric_type, [])
            if candidates:
                ENGINE_METRICS[engine_type][metric_type] = candidates[0]
    
    # XInference keeps its original structure
    ENGINE_METRICS[EngineType.XINFERENCE] = BASE_ENGINE_METRICS[EngineType.XINFERENCE].copy()


def refresh_engine_metrics_candidates(engine_metrics_keys_config: Optional[Dict[str, Any]] = None) -> None:
    """Refresh ENGINE_METRICS_CANDIDATES when configuration changes
    
    This function is an alias for initialize_engine_metrics_candidates,
    used for semantic clarity during hot reload.
    
    Args:
        engine_metrics_keys_config: Parsed engines_metrics_keys configuration
    """
    initialize_engine_metrics_candidates(engine_metrics_keys_config)


def clear_all_pools_metrics_key_cache() -> None:
    """Clear metrics key cache for all members in all pools
    
    Called when engines_metrics_keys configuration changes during hot reload
    """
    for pool in POOLS.values():
        pool.clear_all_members_key_cache()


def get_candidates_summary() -> Dict[str, Dict[str, int]]:
    """Get summary of ENGINE_METRICS_CANDIDATES for logging
    
    Returns:
        Summary dict: {engine_name: {metric_type: count}}
    """
    summary = {}
    for engine_type, metrics in ENGINE_METRICS_CANDIDATES.items():
        if engine_type == EngineType.XINFERENCE:
            continue
        summary[engine_type.value] = {
            metric_type: len(keys) for metric_type, keys in metrics.items()
        }
    return summary


# ============================================================================
# POOL ACCESS FUNCTIONS
# ============================================================================

def get_pool_by_key(pool_name: str, partition: str) -> Optional[Pool]:
    """Get Pool object by pool name and partition"""
    key = f"{pool_name}:{partition}"
    return POOLS.get(key)


def add_or_update_pool(pool: Pool) -> None:
    """Add or update Pool object"""
    key = pool.get_pool_key()
    POOLS[key] = pool


def get_all_pools() -> List[Pool]:
    """Get all Pool objects"""
    return list(POOLS.values())
