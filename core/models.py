"""
Data model definition module
Defines core data structures used by the scheduler
"""

from typing import Dict, List, Optional
from enum import Enum


class EngineType(Enum):
    """Inference engine type enumeration"""
    VLLM = "vllm"
    SGLANG = "sglang"


class PoolMember:
    """Pool member data model"""
    __slots__ = ("ip", "port", "partition", "metrics", "score")
    
    def __init__(self, ip: str, port: int, partition: str):
        self.ip: str = ip
        self.port: int = port
        self.partition: str = partition
        self.metrics: Dict[str, float] = {}
        # Initialize to a small positive number to avoid all members being filtered out in initial state
        # This value is small enough not to affect normal weighted selection, but large enough to be > 0
        self.score: float = 0.001
    
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


class Pool:
    """Pool data model"""
    __slots__ = ("name", "partition", "engine_type", "members", "_consecutive_failures", 
                 "pool_fallback", "member_running_req_threshold", "member_waiting_queue_threshold")
    
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
    
    def update_members_smartly(self, new_members: List[PoolMember]) -> None:
        """Smartly update member list, preserving existing members' score values"""
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
                # Member already exists, preserve its score value and metrics
                existing_member = existing_members_map[key]
                # Keep score value and metrics, but update other potentially changed attributes
                new_member.score = existing_member.score
                new_member.metrics = existing_member.metrics
                updated_members.append(new_member)
            else:
                # New member, use default initial values
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
    
    def get_pool_key(self) -> str:
        """Get Pool's unique identifier"""
        return f"{self.name}:{self.partition}"
    
    def find_member(self, ip: str, port: int) -> Optional[PoolMember]:
        """Find specified member"""
        for member in self.members:
            if member.ip == ip and member.port == port:
                return member
        return None


# Global memory: pool name → Pool object
POOLS: Dict[str, Pool] = {}


# Inference engine key metrics definition
# Metrics return format should be like "sglang:token_usage{model_name="meta-llama/Llama-3.1-8B-Instruct"} 0.28"
ENGINE_METRICS = {
    EngineType.VLLM: {
        "waiting_queue": "vllm:num_requests_waiting",
        "cache_usage": "vllm:gpu_cache_usage_perc",
        "running_req": "vllm:num_requests_running"
    },
    EngineType.SGLANG: {
        "waiting_queue": "sglang:num_queue_reqs", 
        "cache_usage": "sglang:token_usage",
        "running_req": "sglang:num_running_reqs"
    }
}


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