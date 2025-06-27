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
            self.logger.info(f"ALGORITHM_CHECK: Using algorithm mode: {mode_config.name}")
            if mode_config.name == "s1":
                self.logger.info("ALGORITHM_CHECK: Executing S1 algorithm")
                self._calculate_s1_scores(pool, mode_config)
            elif mode_config.name == "s1_enhanced":
                self.logger.info("ALGORITHM_CHECK: Executing S1_ENHANCED algorithm")
                self._calculate_s1_enhanced_scores(pool, mode_config)
            elif mode_config.name == "s1_adaptive":
                self.logger.info("ALGORITHM_CHECK: Executing S1_ADAPTIVE algorithm")
                self._calculate_s1_adaptive_scores(pool, mode_config)
            elif mode_config.name == "s1_ratio":
                self.logger.info("ALGORITHM_CHECK: Executing S1_RATIO algorithm")
                self._calculate_s1_ratio_scores(pool, mode_config)
            elif mode_config.name == "s1_precise":
                self.logger.info("ALGORITHM_CHECK: Executing S1_PRECISE algorithm")
                self._calculate_s1_precise_scores(pool, mode_config)
            elif mode_config.name == "s1_nonlinear":
                self.logger.info("ALGORITHM_CHECK: Executing S1_NONLINEAR algorithm")
                self._calculate_s1_nonlinear_scores(pool, mode_config)
            elif mode_config.name == "s1_balanced":
                self.logger.info("ALGORITHM_CHECK: Executing S1_BALANCED algorithm")
                self._calculate_s1_balanced_scores(pool, mode_config)
            elif mode_config.name == "s2":
                self._calculate_s2_scores(pool, mode_config)
            elif mode_config.name == "s2_enhanced":
                self._calculate_s2_enhanced_scores(pool, mode_config)
            elif mode_config.name == "s2_nonlinear":
                self._calculate_s2_nonlinear_scores(pool, mode_config)
            elif mode_config.name == "s2_adaptive":
                self._calculate_s2_adaptive_scores(pool, mode_config)
            elif mode_config.name == "s1_adaptive_distribution":
                self.logger.info("ALGORITHM_CHECK: Executing S1_ADAPTIVE_DISTRIBUTION algorithm")
                self._calculate_s1_adaptive_distribution_scores(pool, mode_config)
            elif mode_config.name == "s1_advanced":
                self.logger.info("ALGORITHM_CHECK: Executing S1_ADVANCED algorithm (自适应分布归一化+动态权重)")
                self._calculate_s1_advanced_scores(pool, mode_config)
            elif mode_config.name == "s2_advanced":
                self.logger.info("ALGORITHM_CHECK: Executing S2_ADVANCED algorithm (自适应分布归一化+动态权重)")
                self._calculate_s2_advanced_scores(pool, mode_config)
            elif mode_config.name == "s1_dynamic_waiting":
                self.logger.info("ALGORITHM_CHECK: Executing S1_DYNAMIC_WAITING algorithm (动态waiting权重调整)")
                self._calculate_s1_dynamic_waiting_scores(pool, mode_config)
            elif mode_config.name == "s2_dynamic_waiting":
                self.logger.info("ALGORITHM_CHECK: Executing S2_DYNAMIC_WAITING algorithm (动态waiting权重调整-三指标版本)")
                self._calculate_s2_dynamic_waiting_scores(pool, mode_config)
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
        
        # cache_usage is in [0-1], use directly
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
    
    def _calculate_s1_enhanced_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S1 Enhanced algorithm (with normalized cache_usage)"""
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
        
        # Use precise normalization for better differentiation
        normalized_waiting = self._min_max_normalize(waiting_queue_values)
        normalized_cache = self._precise_cache_normalize(cache_usage_values)  # Use precise cache normalization
        
        # Calculate score for each member
        new_scores = []  # Store all new score values for sum calculation
        old_scores = []  # Store all old score values for logging
        
        for i, member in enumerate(valid_members):
            try:
                # S1 Enhanced algorithm: score = w_a * (1 - normalized_waiting) + w_b * (1 - normalized_cache)
                # Both metrics are normalized to amplify differences
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
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s1_adaptive_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S1 Adaptive algorithm (dynamic weight adjustment)"""
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
        
        # Calculate coefficient of variation (CV) for each metric to determine importance
        def coefficient_of_variation(values):
            if len(values) <= 1:
                return 0.0
            mean = sum(values) / len(values)
            if mean == 0:
                return 0.0
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_dev = math.sqrt(variance)
            return std_dev / mean
        
        cv_waiting = coefficient_of_variation(waiting_queue_values)
        cv_cache = coefficient_of_variation(cache_usage_values)
        
        # Dynamically adjust weights based on variation
        total_cv = cv_waiting + cv_cache
        if total_cv > 0:
            # Give more weight to metrics with higher variation (more discriminative)
            adaptive_w_a = mode_config.w_a * (1 + cv_waiting / total_cv)
            adaptive_w_b = mode_config.w_b * (1 + cv_cache / total_cv)
            
            # Normalize to ensure sum equals original sum
            total_adaptive = adaptive_w_a + adaptive_w_b
            original_sum = mode_config.w_a + mode_config.w_b
            if total_adaptive > 0:
                adaptive_w_a = adaptive_w_a * original_sum / total_adaptive
                adaptive_w_b = adaptive_w_b * original_sum / total_adaptive
        else:
            adaptive_w_a = mode_config.w_a
            adaptive_w_b = mode_config.w_b
        
        self.logger.debug(f"Adaptive weights: w_a={adaptive_w_a:.3f}, w_b={adaptive_w_b:.3f} "
                         f"(CV: waiting={cv_waiting:.3f}, cache={cv_cache:.3f})")
        
        # Normalize all metrics
        normalized_waiting = self._min_max_normalize(waiting_queue_values)
        normalized_cache = self._min_max_normalize(cache_usage_values)
        
        # Calculate score for each member with adaptive weights
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                new_score = (
                    adaptive_w_a * (1.0 - normalized_waiting[i]) +
                    adaptive_w_b * (1.0 - normalized_cache[i])
                )
                
                new_score = max(0.0, min(1.0, new_score))
                
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum and log results
        total_score = sum(new_scores)
        
        for i, member in enumerate(valid_members):
            try:
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s1_ratio_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S1 Ratio algorithm"""
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
        
        # Use ratio-based normalization for cache usage values
        normalized_cache = self._ratio_based_normalize(cache_usage_values)
        
        # Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # S1 Ratio algorithm: score = w_a * (1 - waiting_queue) + w_b * (1 - normalized_cache)
                # Lower cache usage (better performance) gets higher score
                new_score = (
                    mode_config.w_a * (1.0 - waiting_queue_values[i]) +
                    mode_config.w_b * (1.0 - normalized_cache[i])
                )
                
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum and log results
        total_score = sum(new_scores)
        
        for i, member in enumerate(valid_members):
            try:
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}, cache={cache_usage_values[i]:.3f}(norm:{normalized_cache[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s1_precise_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S1 Precise algorithm"""
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
        
        # Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # S1 Precise algorithm: score = w_a * (1 - waiting_queue) + w_b * (1 - cache_usage)
                # This way, smaller waiting_queue and cache_usage result in higher scores
                new_score = (
                    mode_config.w_a * (1.0 - waiting_queue_values[i]) +
                    mode_config.w_b * (1.0 - cache_usage_values[i])
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
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum of all scores
        total_score = sum(new_scores)
        
        # Re-iterate through valid members to output logs with percentages
        for i, member in enumerate(valid_members):
            try:
                # Calculate this member's score percentage of total
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}, cache={cache_usage_values[i]:.3f}, "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s1_nonlinear_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S1 Nonlinear algorithm (ChatGPT suggestion with power amplification)"""
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
        
        # ChatGPT suggested method: Min-Max normalization with epsilon + non-linear amplification
        epsilon = 1e-6  # Prevent division by zero
        power = getattr(mode_config, 'power', 2.0)  # Configurable power, default 2.0
        
        # Min-Max normalize with epsilon protection
        min_w, max_w = min(waiting_queue_values), max(waiting_queue_values)
        min_c, max_c = min(cache_usage_values), max(cache_usage_values)
        
        if max_w == min_w:
            normalized_waiting = [0.0] * len(waiting_queue_values)
        else:
            normalized_waiting = [(w - min_w) / (max_w - min_w + epsilon) for w in waiting_queue_values]
        
        if max_c == min_c:
            normalized_cache = [0.5] * len(cache_usage_values)
        else:
            normalized_cache = [(c - min_c) / (max_c - min_c + epsilon) for c in cache_usage_values]
        
        # Non-linear amplification for cache usage (ChatGPT suggestion)
        amplified_cache = [nc ** power for nc in normalized_cache]
        
        # Re-normalize amplified values to [0,1] range
        if max(amplified_cache) > min(amplified_cache):
            min_amp, max_amp = min(amplified_cache), max(amplified_cache)
            amplified_cache = [(ac - min_amp) / (max_amp - min_amp) for ac in amplified_cache]
        
        # Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # Score calculation: w_a * (1 - waiting_norm) + w_b * (1 - cache_amplified)
                new_score = (
                    mode_config.w_a * (1.0 - normalized_waiting[i]) +
                    mode_config.w_b * (1.0 - amplified_cache[i])
                )
                
                new_score = max(0.0, min(1.0, new_score))
                
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum and log results
        total_score = sum(new_scores)
        
        for i, member in enumerate(valid_members):
            try:
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm:{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm:{normalized_cache[i]:.3f}→amp:{amplified_cache[i]:.3f}), "
                    f"power={power}, score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s1_balanced_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """
        Calculate scores using S1 Balanced algorithm - 专门解决两节点归一化极值问题
        
        核心改进：
        1. 使用平滑归一化避免[0,1]极值
        2. 保持原始差异的敏感性
        3. 避免过度极化的流量分配
        """
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
        
        # 使用平滑归一化方法，避免极值
        normalized_waiting = self._smooth_normalize(waiting_queue_values)
        normalized_cache = self._smooth_normalize(cache_usage_values)
        
        # Log normalization details for debugging
        self.logger.debug(f"Smooth normalization results:")
        self.logger.debug(f"  Waiting: {waiting_queue_values} → {[f'{v:.3f}' for v in normalized_waiting]}")
        self.logger.debug(f"  Cache: {cache_usage_values} → {[f'{v:.3f}' for v in normalized_cache]}")
        
        # Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # S1 Balanced algorithm: score = w_a * (1 - normalized_waiting) + w_b * (1 - normalized_cache)
                # 使用平滑归一化后的值，避免极值影响
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
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum of all scores
        total_score = sum(new_scores)
        
        # Re-iterate through valid members to output logs with percentages
        for i, member in enumerate(valid_members):
            try:
                # Calculate this member's score percentage of total
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
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
    
    def _calculate_s2_enhanced_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """
        Calculate scores using S2 Enhanced algorithm (with specialized precise normalization)
        
        归一化策略：
        - waiting_queue: _min_max_normalize (适合等待队列的线性特征)
        - cache_usage: _precise_cache_normalize (精确感知微小差异，避免极值 [0.2, 1.0])
        - running_req: _precise_running_normalize (专门处理运行请求，避免极值 [0.15, 0.95])
        
        优势：
        1. 能够精确感知和区分数值很相近的指标
        2. 避免出现极值（0或1），保持较差选项的竞争力
        3. 使用对数缩放，对微小差异更敏感
        """
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
        
        # Use specialized precise normalization for each metric type
        normalized_waiting = self._min_max_normalize(waiting_queue_values)
        normalized_cache = self._precise_cache_normalize(cache_usage_values)  # Use precise cache normalization
        normalized_running = self._precise_running_normalize(running_req_values)  # Use precise running normalization
        
        # Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # S2 Enhanced: normalize all metrics to amplify differences
                new_score = (
                    mode_config.w_a * (1.0 - normalized_waiting[i]) +
                    mode_config.w_b * (1.0 - normalized_cache[i]) +
                    mode_config.w_g * (1.0 - normalized_running[i])
                )
                
                new_score = max(0.0, min(1.0, new_score))
                
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum and log results
        total_score = sum(new_scores)
        
        for i, member in enumerate(valid_members):
            try:
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"running={running_req_values[i]:.3f}(norm：{normalized_running[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s2_nonlinear_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S2 Non-linear algorithm (with exponential amplification)"""
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
        
        # Normalize all metrics
        normalized_waiting = self._min_max_normalize(waiting_queue_values)
        normalized_cache = self._min_max_normalize(cache_usage_values)
        normalized_running = self._min_max_normalize(running_req_values)
        
        # Calculate score for each member with non-linear transformation
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # Apply exponential transformation to amplify differences
                # Use power function to make small differences more pronounced
                exp_factor = 2.0  # Can be configured
                
                waiting_contrib = mode_config.w_a * (1.0 - normalized_waiting[i]) ** exp_factor
                cache_contrib = mode_config.w_b * (1.0 - normalized_cache[i]) ** exp_factor
                running_contrib = mode_config.w_g * (1.0 - normalized_running[i]) ** exp_factor
                
                new_score = waiting_contrib + cache_contrib + running_contrib
                new_score = max(0.0, min(1.0, new_score))
                
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum and log results
        total_score = sum(new_scores)
        
        for i, member in enumerate(valid_members):
            try:
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"running={running_req_values[i]:.3f}(norm：{normalized_running[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s2_adaptive_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """Calculate scores using S2 Adaptive algorithm (dynamic weight adjustment)"""
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
        
        # Calculate coefficient of variation (CV) for each metric to determine importance
        def coefficient_of_variation(values):
            if len(values) <= 1:
                return 0.0
            mean = sum(values) / len(values)
            if mean == 0:
                return 0.0
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_dev = math.sqrt(variance)
            return std_dev / mean
        
        cv_waiting = coefficient_of_variation(waiting_queue_values)
        cv_cache = coefficient_of_variation(cache_usage_values)
        cv_running = coefficient_of_variation(running_req_values)
        
        # Dynamically adjust weights based on variation
        total_cv = cv_waiting + cv_cache + cv_running
        if total_cv > 0:
            # Give more weight to metrics with higher variation (more discriminative)
            adaptive_w_a = mode_config.w_a * (1 + cv_waiting / total_cv)
            adaptive_w_b = mode_config.w_b * (1 + cv_cache / total_cv)
            adaptive_w_g = mode_config.w_g * (1 + cv_running / total_cv)
            
            # Normalize to ensure sum equals original sum
            total_adaptive = adaptive_w_a + adaptive_w_b + adaptive_w_g
            original_sum = mode_config.w_a + mode_config.w_b + mode_config.w_g
            if total_adaptive > 0:
                adaptive_w_a = adaptive_w_a * original_sum / total_adaptive
                adaptive_w_b = adaptive_w_b * original_sum / total_adaptive
                adaptive_w_g = adaptive_w_g * original_sum / total_adaptive
        else:
            adaptive_w_a = mode_config.w_a
            adaptive_w_b = mode_config.w_b
            adaptive_w_g = mode_config.w_g
        
        self.logger.debug(f"Adaptive weights: w_a={adaptive_w_a:.3f}, w_b={adaptive_w_b:.3f}, w_g={adaptive_w_g:.3f} "
                         f"(CV: waiting={cv_waiting:.3f}, cache={cv_cache:.3f}, running={cv_running:.3f})")
        
        # Normalize all metrics
        normalized_waiting = self._min_max_normalize(waiting_queue_values)
        normalized_cache = self._min_max_normalize(cache_usage_values)
        normalized_running = self._min_max_normalize(running_req_values)
        
        # Calculate score for each member with adaptive weights
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                new_score = (
                    adaptive_w_a * (1.0 - normalized_waiting[i]) +
                    adaptive_w_b * (1.0 - normalized_cache[i]) +
                    adaptive_w_g * (1.0 - normalized_running[i])
                )
                
                new_score = max(0.0, min(1.0, new_score))
                
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum and log results
        total_score = sum(new_scores)
        
        for i, member in enumerate(valid_members):
            try:
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"running={running_req_values[i]:.3f}(norm：{normalized_running[i]:.3f}), "
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
    
    def _relative_ratio_normalize(self, values: List[float]) -> List[float]:
        """Relative ratio normalization - preserves actual difference ratios"""
        if not values:
            return []
        
        if len(values) == 1:
            return [0.5]  # Single value gets middle score
        
        # Find min value (but avoid division by zero)
        min_val = min(values)
        if min_val == 0:
            min_val = min([v for v in values if v > 0] + [0.001])  # Use smallest non-zero or 0.001
        
        # Calculate ratios relative to minimum
        ratios = [val / min_val for val in values]
        max_ratio = max(ratios)
        
        # Normalize ratios to [0, 1] using logarithmic scaling
        if max_ratio > 1:
            normalized = []
            for ratio in ratios:
                # Use log to compress large differences
                norm_value = math.log(ratio) / math.log(max_ratio)
                normalized.append(norm_value)
            return normalized
        else:
            return [0.0] * len(values)
    
    def _exponential_difference_normalize(self, values: List[float], base: float = 2.0) -> List[float]:
        """Exponential difference normalization - amplifies relative differences"""
        if not values:
            return []
        
        if len(values) == 1:
            return [0.5]
        
        # Calculate relative differences from mean
        mean_val = sum(values) / len(values)
        if mean_val == 0:
            return [0.0] * len(values)
        
        # Calculate relative deviations
        relative_deviations = [(val - mean_val) / mean_val for val in values]
        
        # Apply exponential transformation
        exp_values = [base ** deviation for deviation in relative_deviations]
        
        # Normalize to [0, 1]
        min_exp = min(exp_values)
        max_exp = max(exp_values)
        
        if max_exp == min_exp:
            return [0.5] * len(values)
        
        normalized = [(exp_val - min_exp) / (max_exp - min_exp) for exp_val in exp_values]
        return normalized
    
    def _sigmoid_difference_normalize(self, values: List[float], sensitivity: float = 5.0) -> List[float]:
        """Sigmoid-based normalization - smooth transition with adjustable sensitivity"""
        if not values:
            return []
        
        if len(values) == 1:
            return [0.5]
        
        # Calculate mean and standard deviation
        mean_val = sum(values) / len(values)
        if len(values) < 2:
            return [0.5] * len(values)
        
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0
        
        # Apply sigmoid transformation
        def sigmoid(x):
            return 1 / (1 + math.exp(-x))
        
        normalized = []
        for val in values:
            # Standardize value
            z_score = (val - mean_val) / std_dev if std_dev > 0 else 0
            # Apply sigmoid with sensitivity adjustment
            sigmoid_val = sigmoid(z_score * sensitivity)
            normalized.append(sigmoid_val)
        
        return normalized
    
    def _adaptive_cache_normalize(self, values: List[float]) -> List[float]:
        """Adaptive cache normalization - considers both absolute and relative differences"""
        if not values:
            return []
        
        if len(values) == 1:
            return [0.5]
        
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return [0.5] * len(values)
        
        # Method 1: Preserve relative ratios
        if min_val > 0:
            # Calculate ratio-based scores
            ratios = [val / min_val for val in values]
            max_ratio = max(ratios)
            
            # Use square root to moderate extreme differences
            sqrt_ratios = [math.sqrt(ratio) for ratio in ratios]
            max_sqrt_ratio = max(sqrt_ratios)
            
            # Normalize sqrt ratios to [0.1, 1.0] to avoid complete elimination
            normalized = []
            for sqrt_ratio in sqrt_ratios:
                norm_val = 0.1 + 0.9 * ((sqrt_ratio - 1) / (max_sqrt_ratio - 1)) if max_sqrt_ratio > 1 else 0.55
                normalized.append(min(1.0, max(0.0, norm_val)))
            
            return normalized
        else:
            # Fallback to min-max if any value is 0
            return self._min_max_normalize(values)
    
    def _precise_cache_normalize(self, values: List[float]) -> List[float]:
        """
        精确cache归一化 - 专门解决两值情况下保留差异程度的问题
        使用多种策略组合来精确反映实际差异
        """
        if not values:
            return []
        
        if len(values) == 1:
            return [0.5]  # Single value gets middle score
        
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return [0.5] * len(values)
        
        # 策略1: 基于相对比例的对数缩放
        if min_val > 0:
            ratios = [val / min_val for val in values]
            max_ratio = max(ratios)
            
            # 使用对数来压缩比例差异到合理范围
            # log_2(ratio) 可以将 2倍差异映射到1, 4倍差异映射到2, 8倍差异映射到3
            log_ratios = [math.log2(ratio) for ratio in ratios]
            max_log_ratio = max(log_ratios)
            
            if max_log_ratio > 0:
                # 将对数比例映射到 [0.2, 1.0] 范围，避免完全消除较差的选项
                base_range = 0.8  # [0.2, 1.0] 的范围是0.8
                normalized = []
                for log_ratio in log_ratios:
                    # 归一化到 [0, 1]，然后映射到 [0.2, 1.0]
                    norm_val = 0.2 + base_range * (log_ratio / max_log_ratio)
                    normalized.append(norm_val)
                return normalized
        
        # 策略2: 基于标准差的缩放（备用方案）
        mean_val = sum(values) / len(values)
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0
        
        # 使用3-sigma规则进行归一化
        normalized = []
        for val in values:
            z_score = (val - mean_val) / (std_dev * 3) if std_dev > 0 else 0
            # 将z-score转换为 [0.1, 0.9] 范围的概率
            sigmoid_val = 1 / (1 + math.exp(-z_score * 2))  # 乘以2增加敏感度
            # 映射到 [0.2, 1.0] 范围
            norm_val = 0.2 + 0.8 * sigmoid_val
            normalized.append(norm_val)
        
        return normalized
    
    def _ratio_based_normalize(self, values: List[float]) -> List[float]:
        """
        基于比例的归一化 - 直接使用相对比例作为权重
        为两个值的情况专门优化
        """
        if not values or len(values) == 1:
            return [0.5] * len(values)
        
        if len(values) == 2:
            val1, val2 = values[0], values[1]
            if val1 == val2:
                return [0.5, 0.5]
            
            # 计算相对比例
            if min(val1, val2) > 0:
                if val1 > val2:
                    ratio = val1 / val2
                    # 将比例转换为权重分配
                    # 例如: 4.6倍差异 → 较好的得到82%, 较差的得到18%
                    better_weight = ratio / (ratio + 1)
                    worse_weight = 1 / (ratio + 1)
                    return [better_weight, worse_weight]
                else:
                    ratio = val2 / val1  
                    better_weight = ratio / (ratio + 1)
                    worse_weight = 1 / (ratio + 1)
                    return [worse_weight, better_weight]
            else:
                # 有零值的情况，使用min-max
                return self._min_max_normalize(values)
        
        # 多值情况使用通用方法
        return self._min_max_normalize(values)
    
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
    
    def _smooth_normalize(self, values: List[float]) -> List[float]:
        """
        平滑归一化 - 专门解决两节点[0,1]极值问题
        
        核心思想：
        1. 避免完全的[0,1]极值分配
        2. 根据实际差异程度动态调整输出范围
        3. 保持相对关系的同时提供更平衡的分配
        
        适用场景：
        - 两节点场景下的极值问题
        - 需要敏感反映微小差异但避免过度极化
        """
        if not values or len(values) <= 1:
            return [0.5] * len(values)
        
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return [0.5] * len(values)
        
        # 计算相对差异程度
        if min_val > 0:
            relative_diff = (max_val - min_val) / min_val
        else:
            relative_diff = max_val - min_val  # 绝对差异
        
        # 根据差异程度动态调整输出范围
        if relative_diff < 0.1:
            # 差异很小：[0.45, 0.55] - 几乎均衡分配
            output_min, output_max = 0.45, 0.55
        elif relative_diff < 0.3:
            # 差异较小：[0.35, 0.65] - 轻微倾斜
            output_min, output_max = 0.35, 0.65
        elif relative_diff < 0.8:
            # 差异中等：[0.25, 0.75] - 中等倾斜
            output_min, output_max = 0.25, 0.75
        elif relative_diff < 2.0:
            # 差异较大：[0.15, 0.85] - 明显倾斜
            output_min, output_max = 0.15, 0.85
        else:
            # 差异很大：[0.05, 0.95] - 强烈倾斜但仍避免完全极值
            output_min, output_max = 0.05, 0.95
        
        # 执行归一化并映射到动态范围
        normalized = []
        for val in values:
            # 标准min-max归一化到[0,1]
            norm_val = (val - min_val) / (max_val - min_val)
            # 映射到动态输出范围
            smooth_val = output_min + norm_val * (output_max - output_min)
            normalized.append(smooth_val)
        
        return normalized
    
    def _calculate_s1_adaptive_distribution_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """
        Calculate scores using S1 Adaptive Distribution algorithm
        
        数学原理：
        1. 基于数据分布特征的自适应归一化
        2. 使用变异系数和偏度来调整映射函数
        3. 保持相对关系的同时避免极值
        4. 对2节点和N节点都具有普适性
        """
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
        
        # 使用自适应分布归一化
        normalized_waiting = self._adaptive_distribution_normalize(waiting_queue_values, "waiting_queue")
        normalized_cache = self._adaptive_distribution_normalize(cache_usage_values, "cache_usage")
        
        # Log normalization details for debugging
        self.logger.debug(f"Adaptive distribution normalization results:")
        self.logger.debug(f"  Waiting: {waiting_queue_values} → {[f'{v:.3f}' for v in normalized_waiting]}")
        self.logger.debug(f"  Cache: {cache_usage_values} → {[f'{v:.3f}' for v in normalized_cache]}")
        
        # Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # S1 Adaptive Distribution algorithm: score = w_a * (1 - normalized_waiting) + w_b * (1 - normalized_cache)
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
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum of all scores
        total_score = sum(new_scores)
        
        # Re-iterate through valid members to output logs with percentages
        for i, member in enumerate(valid_members):
            try:
                # Calculate this member's score percentage of total
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _adaptive_distribution_normalize(self, values: List[float], metric_type: str = "general") -> List[float]:
        """
        自适应分布归一化 - 基于数学统计原理的普适算法
        
        数学原理：
        1. 计算数据的统计特征：均值、标准差、变异系数、偏度
        2. 基于变异系数自适应选择映射函数
        3. 使用改进的Sigmoid函数避免极值
        4. 针对不同指标类型进行优化
        
        Args:
            values: 待归一化的数值列表
            metric_type: 指标类型 ("waiting_queue", "cache_usage", "general")
        
        Returns:
            归一化后的数值列表，范围动态调整但避免[0,1]极值
        """
        if not values or len(values) <= 1:
            return [0.5] * len(values)
        
        # 1. 计算基础统计量
        n = len(values)
        mean_val = sum(values) / n
        
        if n < 2:
            return [0.5] * len(values)
        
        # 计算方差和标准差
        variance = sum((x - mean_val) ** 2 for x in values) / n
        std_dev = math.sqrt(variance) if variance > 0 else 1e-6
        
        # 计算变异系数 (Coefficient of Variation)
        cv = std_dev / abs(mean_val) if abs(mean_val) > 1e-6 else std_dev
        
        # 计算偏度 (Skewness) - 衡量数据分布的对称性
        if std_dev > 1e-6:
            skewness = sum(((x - mean_val) / std_dev) ** 3 for x in values) / n
        else:
            skewness = 0.0
        
        # 2. 基于统计特征选择归一化策略
        self.logger.debug(f"Distribution stats for {metric_type}: mean={mean_val:.3f}, std={std_dev:.3f}, cv={cv:.3f}, skew={skewness:.3f}")
        
        # 3. 自适应参数选择
        if cv < 0.1:
            # 低变异：数据相近，使用高敏感度
            sensitivity = 3.0
            output_range = (0.4, 0.6)  # 窄范围
        elif cv < 0.3:
            # 中等变异：平衡敏感度和稳定性
            sensitivity = 2.0
            output_range = (0.25, 0.75)
        elif cv < 0.8:
            # 高变异：使用中等敏感度
            sensitivity = 1.5
            output_range = (0.15, 0.85)
        else:
            # 极高变异：降低敏感度避免过度反应
            sensitivity = 1.0
            output_range = (0.1, 0.9)
        
        # 4. 针对特定指标类型的优化
        if metric_type == "waiting_queue":
            # waiting_queue通常有很大的动态范围，需要对数变换
            if max(values) > 10 * min(values) and min(values) >= 0:
                # 使用对数变换处理大动态范围
                log_values = [math.log(max(1, x + 1)) for x in values]
                return self._adaptive_distribution_normalize(log_values, "general")
        elif metric_type == "cache_usage":
            # cache_usage在[0,1]范围，需要更高敏感度
            sensitivity *= 1.5
            if cv < 0.2:
                output_range = (0.35, 0.65)  # 对微小差异更敏感
        
        # 5. 改进的Sigmoid归一化
        normalized = []
        output_min, output_max = output_range
        range_span = output_max - output_min
        
        for val in values:
            # 标准化z-score
            z_score = (val - mean_val) / std_dev if std_dev > 1e-6 else 0
            
            # 应用敏感度调整
            adjusted_z = z_score * sensitivity
            
            # 改进的Sigmoid函数：避免极值但保持单调性
            # 使用tanh函数，它比标准sigmoid在极值处更平缓
            sigmoid_val = math.tanh(adjusted_z / 2) * 0.5 + 0.5
            
            # 映射到自适应输出范围
            norm_val = output_min + sigmoid_val * range_span
            
            # 确保在合理范围内
            norm_val = max(0.0, min(1.0, norm_val))
            normalized.append(norm_val)
        
        # 6. 质量检查：确保保持相对顺序
        original_order = sorted(range(len(values)), key=lambda i: values[i])
        normalized_order = sorted(range(len(normalized)), key=lambda i: normalized[i])
        
        if original_order != normalized_order:
            self.logger.warning(f"Order preservation failed for {metric_type}, falling back to rank-based normalization")
            return self._rank_based_normalize(values, output_range)
        
        return normalized
    
    def _rank_based_normalize(self, values: List[float], output_range: tuple = (0.1, 0.9)) -> List[float]:
        """
        基于排名的归一化 - 保证顺序保持的备用方案
        """
        if not values:
            return []
        
        if len(values) == 1:
            return [0.5]
        
        # 获取排名（处理相同值）
        sorted_indices = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0] * len(values)
        
        for rank, idx in enumerate(sorted_indices):
            ranks[idx] = rank
        
        # 归一化排名到指定范围
        max_rank = len(values) - 1
        output_min, output_max = output_range
        
        normalized = []
        for rank in ranks:
            if max_rank > 0:
                norm_val = output_min + (rank / max_rank) * (output_max - output_min)
            else:
                norm_val = (output_min + output_max) / 2
            normalized.append(norm_val)
        
        return normalized
    
    def _calculate_s1_advanced_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """
        Calculate scores using S1 Advanced algorithm
        自适应分布归一化 + 动态权重调整
        
        核心特点：
        1. 对每个指标使用自适应分布归一化（避免极值，保留小差异）
        2. 根据变异系数动态调整权重（区分度高的指标权重更大）
        3. 数学上最优，适用于所有场景
        """
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
        
        # 1. 计算变异系数用于动态权重调整
        def coefficient_of_variation(values):
            if len(values) <= 1:
                return 0.0
            mean = sum(values) / len(values)
            if abs(mean) < 1e-6:
                return 0.0
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_dev = math.sqrt(variance)
            return std_dev / abs(mean)
        
        cv_waiting = coefficient_of_variation(waiting_queue_values)
        cv_cache = coefficient_of_variation(cache_usage_values)
        
        # 2. 动态权重调整
        total_cv = cv_waiting + cv_cache
        if total_cv > 0:
            # 给变异系数高的指标更大权重
            adaptive_w_a = mode_config.w_a * (1 + cv_waiting / total_cv)
            adaptive_w_b = mode_config.w_b * (1 + cv_cache / total_cv)
            
            # 归一化权重和
            total_adaptive = adaptive_w_a + adaptive_w_b
            original_sum = mode_config.w_a + mode_config.w_b
            if total_adaptive > 0:
                adaptive_w_a = adaptive_w_a * original_sum / total_adaptive
                adaptive_w_b = adaptive_w_b * original_sum / total_adaptive
        else:
            adaptive_w_a = mode_config.w_a
            adaptive_w_b = mode_config.w_b
        
        self.logger.debug(f"S1_ADVANCED 动态权重调整: w_a={mode_config.w_a:.3f}→{adaptive_w_a:.3f}, "
                         f"w_b={mode_config.w_b:.3f}→{adaptive_w_b:.3f} "
                         f"(CV: waiting={cv_waiting:.3f}, cache={cv_cache:.3f})")
        
        # 3. 自适应分布归一化
        normalized_waiting = self._adaptive_distribution_normalize(waiting_queue_values, "waiting_queue")
        normalized_cache = self._adaptive_distribution_normalize(cache_usage_values, "cache_usage")
        
        # Log normalization details for debugging
        self.logger.debug(f"S1_ADVANCED 自适应分布归一化结果:")
        self.logger.debug(f"  Waiting: {waiting_queue_values} → {[f'{v:.3f}' for v in normalized_waiting]}")
        self.logger.debug(f"  Cache: {cache_usage_values} → {[f'{v:.3f}' for v in normalized_cache]}")
        
        # 4. Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # S1 Advanced algorithm: score = adaptive_w_a * (1 - normalized_waiting) + adaptive_w_b * (1 - normalized_cache)
                new_score = (
                    adaptive_w_a * (1.0 - normalized_waiting[i]) +
                    adaptive_w_b * (1.0 - normalized_cache[i])
                )
                
                # Ensure score is within reasonable range
                new_score = max(0.0, min(1.0, new_score))
                
                # Atomic score update
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum of all scores
        total_score = sum(new_scores)
        
        # Re-iterate through valid members to output logs with percentages
        for i, member in enumerate(valid_members):
            try:
                # Calculate this member's score percentage of total
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s2_advanced_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """
        Calculate scores using S2 Advanced algorithm
        自适应分布归一化 + 动态权重调整 (三指标版本)
        
        核心特点：
        1. 对三个指标都使用自适应分布归一化
        2. 根据变异系数动态调整三个权重
        3. 精确捕捉小差异，避免极值，适用于复杂场景
        """
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
        
        # 1. 计算变异系数用于动态权重调整
        def coefficient_of_variation(values):
            if len(values) <= 1:
                return 0.0
            mean = sum(values) / len(values)
            if abs(mean) < 1e-6:
                return 0.0
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            std_dev = math.sqrt(variance)
            return std_dev / abs(mean)
        
        cv_waiting = coefficient_of_variation(waiting_queue_values)
        cv_cache = coefficient_of_variation(cache_usage_values)
        cv_running = coefficient_of_variation(running_req_values)
        
        # 2. 动态权重调整
        total_cv = cv_waiting + cv_cache + cv_running
        if total_cv > 0:
            # 给变异系数高的指标更大权重
            adaptive_w_a = mode_config.w_a * (1 + cv_waiting / total_cv)
            adaptive_w_b = mode_config.w_b * (1 + cv_cache / total_cv)
            adaptive_w_g = mode_config.w_g * (1 + cv_running / total_cv)
            
            # 归一化权重和
            total_adaptive = adaptive_w_a + adaptive_w_b + adaptive_w_g
            original_sum = mode_config.w_a + mode_config.w_b + mode_config.w_g
            if total_adaptive > 0:
                adaptive_w_a = adaptive_w_a * original_sum / total_adaptive
                adaptive_w_b = adaptive_w_b * original_sum / total_adaptive
                adaptive_w_g = adaptive_w_g * original_sum / total_adaptive
        else:
            adaptive_w_a = mode_config.w_a
            adaptive_w_b = mode_config.w_b
            adaptive_w_g = mode_config.w_g
        
        self.logger.debug(f"S2_ADVANCED 动态权重调整: "
                         f"w_a={mode_config.w_a:.3f}→{adaptive_w_a:.3f}, "
                         f"w_b={mode_config.w_b:.3f}→{adaptive_w_b:.3f}, "
                         f"w_g={mode_config.w_g:.3f}→{adaptive_w_g:.3f} "
                         f"(CV: waiting={cv_waiting:.3f}, cache={cv_cache:.3f}, running={cv_running:.3f})")
        
        # 3. 自适应分布归一化
        normalized_waiting = self._adaptive_distribution_normalize(waiting_queue_values, "waiting_queue")
        normalized_cache = self._adaptive_distribution_normalize(cache_usage_values, "cache_usage")
        normalized_running = self._adaptive_distribution_normalize(running_req_values, "running_req")
        
        # Log normalization details for debugging
        self.logger.debug(f"S2_ADVANCED 自适应分布归一化结果:")
        self.logger.debug(f"  Waiting: {waiting_queue_values} → {[f'{v:.3f}' for v in normalized_waiting]}")
        self.logger.debug(f"  Cache: {cache_usage_values} → {[f'{v:.3f}' for v in normalized_cache]}")
        self.logger.debug(f"  Running: {running_req_values} → {[f'{v:.3f}' for v in normalized_running]}")
        
        # 4. Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                # S2 Advanced algorithm: score = adaptive_w_a * (1 - normalized_waiting) + adaptive_w_b * (1 - normalized_cache) + adaptive_w_g * (1 - normalized_running)
                new_score = (
                    adaptive_w_a * (1.0 - normalized_waiting[i]) +
                    adaptive_w_b * (1.0 - normalized_cache[i]) +
                    adaptive_w_g * (1.0 - normalized_running[i])
                )
                
                # Ensure score is within reasonable range
                new_score = max(0.0, min(1.0, new_score))
                
                # Atomic score update
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum of all scores
        total_score = sum(new_scores)
        
        # Re-iterate through valid members to output logs with percentages
        for i, member in enumerate(valid_members):
            try:
                # Calculate this member's score percentage of total
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"running={running_req_values[i]:.3f}(norm：{normalized_running[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}") 
    
    def _calculate_s1_dynamic_waiting_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """
        Calculate scores using S1 Dynamic Waiting algorithm (动态waiting权重调整)
        
        核心思想：
        1. 根据实际waiting request数量动态调整waiting权重
        2. 使用tanh数学函数实现平滑的权重过渡
        3. 避免硬阈值突变，数学上优雅
        4. 无等待时主要靠cache区分，有等待时逐步提升waiting权重
        """
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
        
        # 1. 计算整体waiting情况用于权重调整
        max_waiting = max(waiting_queue_values)
        avg_waiting = sum(waiting_queue_values) / len(waiting_queue_values)
        
        # 2. 渐进式权重调整函数
        # 使用tanh函数实现平滑过渡，避免硬阈值
        transition_point = mode_config.transition_point  # 过渡点：多少个等待请求作为权重调整的中心点
        steepness = mode_config.steepness  # 陡峭度：控制权重过渡的平滑程度
        
        # 计算权重调整因子 (0到1之间，0表示无等待，1表示重度等待)
        waiting_intensity = math.tanh(max_waiting * steepness / transition_point)
        
        # 3. 基于强度渐进调整权重
        # waiting_intensity=0时：更重视cache (0.2x waiting + 1.8x cache)
        # waiting_intensity=1时：更重视waiting (2.5x waiting + 0.3x cache)
        min_w_a_factor = 0.2
        max_w_a_factor = 2.5
        min_w_b_factor = 1.8
        max_w_b_factor = 0.3
        
        progressive_w_a = mode_config.w_a * (min_w_a_factor + (max_w_a_factor - min_w_a_factor) * waiting_intensity)
        progressive_w_b = mode_config.w_b * (min_w_b_factor + (max_w_b_factor - min_w_b_factor) * waiting_intensity)
        
        # 归一化权重
        total_progressive = progressive_w_a + progressive_w_b
        original_sum = mode_config.w_a + mode_config.w_b
        if total_progressive > 0:
            progressive_w_a = progressive_w_a * original_sum / total_progressive
            progressive_w_b = progressive_w_b * original_sum / total_progressive
        
        self.logger.info(f"S1_DYNAMIC_WAITING: max_waiting={max_waiting}, avg_waiting={avg_waiting:.1f}, "
                        f"intensity={waiting_intensity:.3f}")
        self.logger.debug(f"动态waiting权重: w_a={mode_config.w_a:.3f}→{progressive_w_a:.3f}, "
                         f"w_b={mode_config.w_b:.3f}→{progressive_w_b:.3f}")
        
        # 4. 使用自适应分布归一化
        normalized_waiting = self._adaptive_distribution_normalize(waiting_queue_values, "waiting_queue")
        normalized_cache = self._adaptive_distribution_normalize(cache_usage_values, "cache_usage")
        
        # 5. Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                new_score = (
                    progressive_w_a * (1.0 - normalized_waiting[i]) +
                    progressive_w_b * (1.0 - normalized_cache[i])
                )
                
                new_score = max(0.0, min(1.0, new_score))
                
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum and log results
        total_score = sum(new_scores)
        
        for i, member in enumerate(valid_members):
            try:
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]:.3f}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _calculate_s2_dynamic_waiting_scores(self, pool: Pool, mode_config: ModeConfig) -> None:
        """
        Calculate scores using S2 Dynamic Waiting algorithm (动态waiting权重调整-三指标版本)
        
        核心思想：
        1. 将S1的动态waiting权重思想扩展到三指标版本
        2. 根据实际waiting request数量动态调整三个权重
        3. 使用tanh数学函数实现平滑的权重过渡
        4. 在无等待时主要靠cache和running区分，有等待时逐步提升waiting权重
        """
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
        
        # 1. 计算整体waiting情况用于权重调整
        max_waiting = max(waiting_queue_values)
        avg_waiting = sum(waiting_queue_values) / len(waiting_queue_values)
        
        # 2. 渐进式权重调整函数（三指标版本）
        # 使用tanh函数实现平滑过渡，避免硬阈值
        transition_point = mode_config.transition_point  # 过渡点：多少个等待请求作为权重调整的中心点
        steepness = mode_config.steepness  # 陡峭度：控制权重过渡的平滑程度
        
        # 计算权重调整因子 (0到1之间，0表示无等待，1表示重度等待)
        waiting_intensity = math.tanh(max_waiting * steepness / transition_point)
        
        # 3. 基于强度渐进调整三个权重
        # waiting_intensity=0时：更重视cache和running (0.1x waiting + 1.5x cache + 1.4x running)
        # waiting_intensity=1时：更重视waiting (2.5x waiting + 0.4x cache + 0.6x running)
        min_w_a_factor = 0.1  # waiting最小权重因子
        max_w_a_factor = 2.5  # waiting最大权重因子
        min_w_b_factor = 1.5  # cache最小权重因子
        max_w_b_factor = 0.4  # cache最大权重因子
        min_w_g_factor = 1.4  # running最小权重因子
        max_w_g_factor = 0.6  # running最大权重因子
        
        progressive_w_a = mode_config.w_a * (min_w_a_factor + (max_w_a_factor - min_w_a_factor) * waiting_intensity)
        progressive_w_b = mode_config.w_b * (min_w_b_factor + (max_w_b_factor - min_w_b_factor) * waiting_intensity)
        progressive_w_g = mode_config.w_g * (min_w_g_factor + (max_w_g_factor - min_w_g_factor) * waiting_intensity)
        
        # 归一化权重
        total_progressive = progressive_w_a + progressive_w_b + progressive_w_g
        original_sum = mode_config.w_a + mode_config.w_b + mode_config.w_g
        if total_progressive > 0:
            progressive_w_a = progressive_w_a * original_sum / total_progressive
            progressive_w_b = progressive_w_b * original_sum / total_progressive
            progressive_w_g = progressive_w_g * original_sum / total_progressive
        
        self.logger.info(f"S2_DYNAMIC_WAITING: max_waiting={max_waiting}, avg_waiting={avg_waiting:.1f}, "
                        f"intensity={waiting_intensity:.3f}")
        self.logger.debug(f"动态waiting权重(三指标): w_a={mode_config.w_a:.3f}→{progressive_w_a:.3f}, "
                         f"w_b={mode_config.w_b:.3f}→{progressive_w_b:.3f}, "
                         f"w_g={mode_config.w_g:.3f}→{progressive_w_g:.3f}")
        
        # 4. 使用自适应分布归一化
        normalized_waiting = self._adaptive_distribution_normalize(waiting_queue_values, "waiting_queue")
        normalized_cache = self._adaptive_distribution_normalize(cache_usage_values, "cache_usage")
        normalized_running = self._adaptive_distribution_normalize(running_req_values, "running_req")
        
        # 5. Calculate score for each member
        new_scores = []
        old_scores = []
        
        for i, member in enumerate(valid_members):
            try:
                new_score = (
                    progressive_w_a * (1.0 - normalized_waiting[i]) +
                    progressive_w_b * (1.0 - normalized_cache[i]) +
                    progressive_w_g * (1.0 - normalized_running[i])
                )
                
                new_score = max(0.0, min(1.0, new_score))
                
                old_score = member.score
                member.score = new_score
                
                new_scores.append(new_score)
                old_scores.append(old_score)
                
            except Exception as e:
                self.logger.warning(f"Exception calculating score for member {member}: {e}, keeping original score: {member.score:.3f}")
                new_scores.append(member.score)
                old_scores.append(member.score)
        
        # Calculate total sum and log results
        total_score = sum(new_scores)
        
        for i, member in enumerate(valid_members):
            try:
                score_ratio = (new_scores[i] / total_score * 100) if total_score > 0 else 0.0
                
                self.logger.debug(
                    f"Member {member}: waiting={waiting_queue_values[i]}(norm：{normalized_waiting[i]:.3f}), "
                    f"cache={cache_usage_values[i]:.3f}(norm：{normalized_cache[i]:.3f}), "
                    f"running={running_req_values[i]}(norm：{normalized_running[i]:.3f}), "
                    f"score={old_scores[i]:.3f}→{new_scores[i]:.3f}({score_ratio:.1f}%)"
                )
                
            except Exception as e:
                self.logger.warning(f"Exception logging member {member}: {e}")
    
    def _precise_running_normalize(self, values: List[float]) -> List[float]:
        """
        精确running_req归一化 - 专门处理正在运行请求数的归一化
        
        核心思想：
        1. running_req通常是整数，需要精确反映微小差异
        2. 使用对数缩放来处理不同数量级的running请求
        3. 避免极值，保持较差选项的竞争力
        4. 适用于各种running请求分布情况
        """
        if not values:
            return []
        
        if len(values) == 1:
            return [0.5]  # Single value gets middle score
        
        min_val = min(values)
        max_val = max(values)
        
        if max_val == min_val:
            return [0.5] * len(values)
        
        # 策略1: 基于相对比例的对数缩放（适用于running_req）
        if min_val >= 0:  # running_req可以为0
            # 为了处理0值，给所有值加1
            adjusted_values = [val + 1 for val in values]
            min_adjusted = min(adjusted_values)
            
            ratios = [val / min_adjusted for val in adjusted_values]
            max_ratio = max(ratios)
            
            # 使用对数来压缩比例差异
            log_ratios = [math.log2(ratio) for ratio in ratios]
            max_log_ratio = max(log_ratios)
            
            if max_log_ratio > 0:
                # 将对数比例映射到 [0.15, 0.95] 范围
                # running_req差异通常比cache更明显，所以范围稍大
                base_range = 0.8  # [0.15, 0.95] 的范围是0.8
                normalized = []
                for log_ratio in log_ratios:
                    # 归一化到 [0, 1]，然后映射到 [0.15, 0.95]
                    norm_val = 0.15 + base_range * (log_ratio / max_log_ratio)
                    normalized.append(norm_val)
                return normalized
        
        # 策略2: 基于标准差的缩放（备用方案）
        mean_val = sum(values) / len(values)
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0
        
        # 使用3-sigma规则进行归一化
        normalized = []
        for val in values:
            z_score = (val - mean_val) / (std_dev * 3) if std_dev > 0 else 0
            # 将z-score转换为概率
            sigmoid_val = 1 / (1 + math.exp(-z_score * 2))  # 乘以2增加敏感度
            # 映射到 [0.15, 0.95] 范围
            norm_val = 0.15 + 0.8 * sigmoid_val
            normalized.append(norm_val)
        
        return normalized