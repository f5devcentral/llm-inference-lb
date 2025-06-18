"""
Score calculation module
Responsible for calculating member scores based on metrics
"""

import math
from typing import Dict, List, Optional, Tuple

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from utils.exceptions import ScoreCalculationError
from core.models import Pool, PoolMember
from config.config_loader import ModeConfig


class ScoreCalculator:
    """Score calculator"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def calculate_pool_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores for all members in the pool"""
        if not pool.members:
            self.logger.debug(f"Pool {pool.name} has no members, skipping score calculation")
            return
        
        self.logger.info(f"Starting score calculation for Pool {pool.name} with {len(pool.members)} members")
        
        try:
            if mode_config.name == "s1":
                self._calculate_s1_scores(pool, mode_config)
            elif mode_config.name == "s2":
                self._calculate_s2_scores(pool, mode_config)
            else:
                self.logger.error(f"Unsupported algorithm mode: {mode_config.name}")
                raise ScoreCalculationError(f"Unsupported algorithm mode: {mode_config.name}")
            
            self.logger.info(f"Completed score calculation for Pool {pool.name}")
            
        except Exception as e:
            self.logger.error(f"Failed to calculate scores for Pool {pool.name}: {e}")
            raise ScoreCalculationError(f"Failed to calculate scores for Pool {pool.name}: {e}")
    
    def _calculate_s1_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S1 algorithm"""
        # Collect metrics from all members
        waiting_queue_values = []
        cache_usage_values = []
        valid_members = []
        
        for member in pool.members:
            metrics = member.metrics
            if not metrics:
                self.logger.warning(f"Member {member} has no metrics data, keeping original score: {member.score:.3f}")
                continue
            
            waiting_queue = metrics.get("waiting_queue")
            cache_usage = metrics.get("cache_usage")
            
            if waiting_queue is None or cache_usage is None:
                self.logger.warning(f"Member {member} missing key metrics, keeping original score: {member.score:.3f}")
                continue
            
            waiting_queue_values.append(waiting_queue)
            cache_usage_values.append(cache_usage)
            valid_members.append(member)
        
        if not valid_members:
            self.logger.warning(f"Pool {pool.name} has no valid members for score calculation, all members keep original scores")
            return
        
        # Min-max normalize waiting queue values
        normalized_waiting = self._min_max_normalize(waiting_queue_values)
        
        # cache_usage is already normalized (0-1), use directly
        normalized_cache = cache_usage_values
        
        # Calculate score for each member
        new_scores = []  # Store all new score values for sum calculation
        old_scores = []  # Store all old score values for logging
        
        for i, member in enumerate(valid_members):
            try:
                # S1 algorithm: score = w_a * (1 - normalized_waiting) + w_b * (1 - cache_usage)
                # This way, smaller waiting_queue and cache_usage result in higher scores
                # Cache usage in the engine typically represents kv cache utilization. Theoretically, a moderate range is better, as both too high and too low are suboptimal. However, from an external Gateway product perspective, lower utilization indicates more available capacity on that machine.
                new_score = (
                    mode_config.w_a * (1.0 - normalized_waiting[i]) +
                    mode_config.w_b * (1.0 - normalized_cache[i])
                )
                
                # Ensure score is within reasonable range
                new_score = max(0.0, min(1.0, new_score))
                
                # Atomic score update (assignment operations are atomic in Python)
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)  # Use original score
                old_scores.append(member.score)  # Old score is also current score
        
        # Calculate total sum of all scores
        total_score = sum(new_scores)
        
        # Re-iterate through valid members to output logs with percentages
        for i, member in enumerate(valid_members):
            try:
                # Calculate this member's score percentage of total
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(normalized：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}, score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s2_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S2 algorithm (S1 + running_req metric)"""
        # Collect metrics from all members
        waiting_queue_values = []
        cache_usage_values = []
        running_req_values = []
        valid_members = []
        
        for member in pool.members:
            metrics = member.metrics
            if not metrics:
                self.logger.warning(f"Member {member} has no metrics data, keeping original score: {member.score:.3f}")
                continue
            
            waiting_queue = metrics.get("waiting_queue")
            cache_usage = metrics.get("cache_usage")
            running_req = metrics.get("running_req")
            
            if waiting_queue is None or cache_usage is None or running_req is None:
                self.logger.warning(f"Member {member} missing key metrics, keeping original score: {member.score:.3f}")
                continue
            
            waiting_queue_values.append(waiting_queue)
            cache_usage_values.append(cache_usage)
            running_req_values.append(running_req)
            valid_members.append(member)
        
        if not valid_members:
            self.logger.warning(f"Pool {pool.name} has no valid members for score calculation, all members keep original scores")
            return
        
        # Min-max normalize waiting queue values
        normalized_waiting = self._min_max_normalize(waiting_queue_values)
        
        # cache_usage is already normalized (0-1), use directly
        normalized_cache = cache_usage_values
        
        # Min-max normalize running requests values
        normalized_running = self._min_max_normalize(running_req_values)
        
        # Calculate score for each member
        new_scores = []  # Store all new score values for sum calculation
        old_scores = []  # Store all old score values for logging
        
        for i, member in enumerate(valid_members):
            try:
                # S2 algorithm: score = w_a * (1 - normalized_waiting) + w_b * (1 - cache_usage) + w_g * (1 - normalized_running)
                # This way, smaller waiting_queue, cache_usage, and running_req result in higher scores
                new_score = (
                    mode_config.w_a * (1.0 - normalized_waiting[i]) +
                    mode_config.w_b * (1.0 - normalized_cache[i]) +
                    mode_config.w_g * (1.0 - normalized_running[i])
                )
                
                # Ensure score is within reasonable range
                new_score = max(0.0, min(1.0, new_score))
                
                # Atomic score update (assignment operations are atomic in Python)
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)  # Use original score
                old_scores.append(member.score)  # Old score is also current score
        
        # Calculate total sum of all scores
        total_score = sum(new_scores)
        
        # Re-iterate through valid members to output logs with percentages
        for i, member in enumerate(valid_members):
            try:
                # Calculate this member's score percentage of total
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(normalized：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}, running={running_req_values[i]:.3f}(normalized：{normalized_running[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _min_max_normalize(self, values: List[float]) -> List[float]:
        """Min-Max normalization"""
        if not values:
            return []
        
        if len(values) == 1:
            return [0.0]  # When there's only one value, normalize to 0
        
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            # All values are the same, normalize to 0
            return [0.0] * len(values)
        
        normalized = []
        for value in values:
            norm_value = (value - min_val) / (max_val - min_val)
            normalized.append(norm_value)
        
        return normalized
    
    def get_members_by_score(self, pool: Pool, descending: bool = True) -> List[PoolMember]:
        """Get member list sorted by score"""
        if not pool.members:
            return []
        
        sorted_members = sorted(
            pool.members,
            key=lambda m: m.score,
            reverse=descending
        )
        
        return sorted_members
    
    def get_top_members(self, pool: Pool, top_n: int = 5) -> List[PoolMember]:
        """Get top N members with highest scores"""
        sorted_members = self.get_members_by_score(pool, descending=True)
        return sorted_members[:top_n]
    
    def get_pool_score_stats(self, pool: Pool) -> Dict[str, float]:
        """Get pool score statistics"""
        if not pool.members:
            return {
                "count": 0,
                "max": 0.0,
                "min": 0.0,
                "avg": 0.0,
                "std": 0.0
            }
        
        scores = [member.score for member in pool.members]
        count = len(scores)
        max_score = max(scores)
        min_score = min(scores)
        avg_score = sum(scores) / count
        
        # Calculate standard deviation
        variance = sum((score - avg_score) ** 2 for score in scores) / count
        std_score = math.sqrt(variance)
        
        return {
            "count": count,
            "max": max_score,
            "min": min_score,
            "avg": avg_score,
            "std": std_score
        } 