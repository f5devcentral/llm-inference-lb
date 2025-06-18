"""
Scheduler core module
Implements optimal member selection and weighted random algorithms
"""

import asyncio
import random
from typing import Dict, List, Optional, Set, Tuple

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.logger import get_logger
from utils.exceptions import SchedulingError
from core.models import Pool, PoolMember, get_pool_by_key


class WeightedRandomSelector:
    """Weighted random selector"""
    
    def __init__(self):
        self.logger = get_logger()
    
    def select(self, members: List[PoolMember]) -> Optional[PoolMember]:
        """Select optimal member using weighted random algorithm"""
        if not members:
            self.logger.warning("Member list is empty, unable to select")
            return None
        self.logger.debug(f"Start selection, member list: {[f'{m} score={m.score}' for m in members]}")

        # Filter out members with score 0 (should rarely occur now, unless explicitly set to 0)
        valid_members = [m for m in members if m.score > 0]
        self.logger.debug(f"Valid member list: {[f'{m} score={m.score}' for m in valid_members]}")
        
        if not valid_members:
            self.logger.warning("No valid members (score > 0), this situation should rarely occur")
            return None
        
        # If only one valid member, return directly
        if len(valid_members) == 1:
            return valid_members[0]
        
        try:
            # Choose algorithm version here, currently using optimized version to improve calculation precision and avoid floating point accumulation errors
            return self._weighted_random_choice(valid_members)
        except Exception as e:
            self.logger.error(f"Weighted random selection exception: {e}")
            return valid_members[0]
    
    def _weighted_random_choice(self, members: List[PoolMember]) -> PoolMember:
        """Execute weighted random selection - optimized version using Decimal to improve calculation precision and avoid floating point accumulation errors"""
        # Use Decimal to improve calculation precision and avoid floating point accumulation errors
        from decimal import Decimal, getcontext
        
        # Set sufficient precision
        getcontext().prec = 28
        
        # Convert to Decimal type for precise calculation
        member_weights = [(member, Decimal(str(member.score))) for member in members]
        total_weight = sum(weight for _, weight in member_weights)
        
        if total_weight <= 0:
            self.logger.warning("Total weight is 0, randomly selecting a member")
            return random.choice(members)
        
        # Use high-precision random number generation
        random_point = Decimal(str(random.uniform(0, 1))) * total_weight
        
        # Find corresponding member - use strict interval division
        cumulative_weight = Decimal('0')
        
        for i, (member, weight) in enumerate(member_weights):
            # Calculate current member's interval [cumulative_weight, cumulative_weight + weight)
            interval_start = cumulative_weight
            interval_end = cumulative_weight + weight
            
            # Check if random point falls within current member's interval
            # Note: last member uses <= to handle boundary cases
            if (i == len(member_weights) - 1 and random_point <= interval_end) or \
               (i < len(member_weights) - 1 and interval_start <= random_point < interval_end):
                
                # Calculate theoretical selection probability for verification
                theoretical_prob = float(weight / total_weight)
                
                self.logger.debug(
                    f"Selected member {member}, score={member.score:.6f}, "
                    f"theoretical_prob={theoretical_prob:.4f}({theoretical_prob*100:.2f}%), "
                    f"random_point={float(random_point):.6f}, total_weight={float(total_weight):.6f}, "
                    f"interval=[{float(interval_start):.6f}, {float(interval_end):.6f})"
                )
                return member
            
            cumulative_weight = interval_end
        
        # Should not reach here theoretically, but for safety
        self.logger.warning(
            f"Weighted random selection did not find member, returning last one. "
            f"random_point={float(random_point):.6f}, total_weight={float(total_weight):.6f}"
        )
        return members[-1]
    
    def _weighted_random_choice_alternative(self, members: List[PoolMember]) -> PoolMember:
        """Alternative weighted random selection algorithm - implementation based on probability array"""
        import numpy as np
        
        # Extract weights
        weights = np.array([member.score for member in members], dtype=np.float64)
        
        # Check weight validity
        if np.sum(weights) <= 0:
            self.logger.warning("Total weight is 0, randomly selecting a member")
            return random.choice(members)
        
        # Normalize weights to probabilities
        probabilities = weights / np.sum(weights)
        
        # Use numpy's random choice
        selected_index = np.random.choice(len(members), p=probabilities)
        selected_member = members[selected_index]
        
        self.logger.debug(
            f"Selected member {selected_member}, score={selected_member.score:.6f}, "
            f"theoretical_prob={probabilities[selected_index]:.4f}({probabilities[selected_index]*100:.2f}%)"
        )
        
        return selected_member
    
    def _weighted_random_choice_original(self, members: List[PoolMember]) -> PoolMember:
        """Original version of weighted random selection - using original floating point implementation"""
        # Calculate total weight - using original floating point implementation
        total_weight = sum(member.score for member in members)
        
        if total_weight <= 0:
            self.logger.warning("Total weight is 0, randomly selecting a member")
            return random.choice(members)
        
        # Generate random number - original implementation
        random_point = random.uniform(0, total_weight)
        
        # Find corresponding member - original accumulation method
        cumulative_weight = 0.0
        for member in members:
            cumulative_weight += member.score
            if random_point <= cumulative_weight:
                self.logger.debug(
                    f"[Original algorithm] Selected member {member}, score={member.score:.3f}, "
                    f"random_point={random_point:.3f}, total_weight={total_weight:.3f}"
                )
                return member
        
        # Should not reach here theoretically, but for safety
        self.logger.warning("[Original algorithm] Weighted random selection did not find member, returning last one")
        return members[-1]
    
    def select_with_algorithm(self, members: List[PoolMember], algorithm: str = "optimized") -> Optional[PoolMember]:
        """Select using specified algorithm"""
        if not members:
            self.logger.warning("Member list is empty, unable to select")
            return None

        # Filter out members with score 0
        valid_members = [m for m in members if m.score > 0]
        
        if not valid_members:
            self.logger.warning("No valid members (score > 0)")
            return None
        
        # If only one valid member, return directly
        if len(valid_members) == 1:
            return valid_members[0]
        
        try:
            if algorithm == "original":
                return self._weighted_random_choice_original(valid_members)
            elif algorithm == "alternative":
                return self._weighted_random_choice_alternative(valid_members)
            else:  # optimized
                return self._weighted_random_choice(valid_members)
        except Exception as e:
            self.logger.error(f"Weighted random selection exception ({algorithm}): {e}")
            return valid_members[0]
    



class Scheduler:
    """Scheduler"""
    
    def __init__(self):
        self.logger = get_logger()
        self.selector = WeightedRandomSelector()
    
    async def select_optimal_member(
        self,
        pool_name: str,
        partition: str,
        candidate_members: List[str]
    ) -> Optional[str]:
        """Select optimal member - non-blocking version"""
        try:
            return await self._do_select_optimal_member(pool_name, partition, candidate_members)
                
        except Exception as e:
            self.logger.error(f"Select optimal member exception: {e}")
            raise SchedulingError(f"Failed to select optimal member: {e}")
    
    async def _do_select_optimal_member(
        self,
        pool_name: str,
        partition: str,
        candidate_members: List[str]
    ) -> Optional[str]:
        """Execute core logic for selecting optimal member"""
        # Find corresponding Pool
        pool = get_pool_by_key(pool_name, partition)
        if not pool:
            self.logger.error(f"Pool not found: {pool_name}:{partition}")
            return None
        
        # Parse candidate members
        candidates = self._parse_candidate_members(candidate_members)
        if not candidates:
            self.logger.error("Candidate member list is empty or has wrong format")
            return None
        
        # Get intersection of pool members and candidate members
        intersection = self._get_intersection(pool, candidates)
        if not intersection:
            self.logger.warning(f"No matching candidate members in Pool {pool_name}")
            return None
        
        # Use weighted random algorithm to select optimal member
        selected_member = self.selector.select(intersection)
        if selected_member:
            result = str(selected_member)
            self.logger.info(
                f"Selected optimal member for Pool {pool_name}: {result}, "
                f"score={selected_member.score:.3f}"
            )
            return result
        else:
            self.logger.warning(f"Failed to select optimal member for Pool {pool_name}")
            return None
    
    def _parse_candidate_members(self, candidate_members: List[str]) -> List[Tuple[str, int]]:
        """Parse candidate member list"""
        candidates = []
        
        for member_str in candidate_members:
            if not member_str or ":" not in member_str:
                self.logger.warning(f"Invalid member format: {member_str}")
                continue
            
            try:
                ip, port_str = member_str.rsplit(":", 1)
                port = int(port_str)
                candidates.append((ip, port))
            except ValueError:
                self.logger.warning(f"Unable to parse member: {member_str}")
                continue
        
        return candidates
    
    def _get_intersection(
        self,
        pool: Pool,
        candidates: List[Tuple[str, int]]
    ) -> List[PoolMember]:
        """Get intersection of pool members and candidate members"""
        intersection = []
        
        # Create candidate member set for quick lookup
        candidate_set = set(candidates)
        
        for member in pool.members:
            member_tuple = (member.ip, member.port)
            if member_tuple in candidate_set:
                intersection.append(member)
        
        self.logger.debug(
            f"Pool {pool.name} has {len(pool.members)} members, "
            f"candidate members {len(candidates)}, intersection {len(intersection)}"
        )
        
        return intersection
    
    def get_pool_status(self, pool_name: str, partition: str) -> Optional[Dict]:
        """Get pool status information"""
        pool = get_pool_by_key(pool_name, partition)
        if not pool:
            return None
        
        status = {
            "name": pool.name,
            "partition": pool.partition,
            "engine_type": pool.engine_type.value,
            "member_count": len(pool.members),
            "members": []
        }
        
        # Calculate total score of all members
        total_score = sum(member.score for member in pool.members)
        
        for member in pool.members:
            # Calculate member's score percentage
            if total_score > 0:
                percent = (member.score / total_score) * 100
            else:
                percent = 0.0
            
            member_info = {
                "ip": member.ip,
                "port": member.port,
                "score": member.score,
                "percent": round(percent, 2),  # Keep 2 decimal places
                "metrics": member.metrics
            }
            status["members"].append(member_info)
        
        return status
    
    def get_all_pools_status(self) -> List[Dict]:
        """Get status information for all pools"""
        from core.models import get_all_pools
        
        pools = get_all_pools()
        status_list = []
        
        for pool in pools:
            status = self.get_pool_status(pool.name, pool.partition)
            if status:
                status_list.append(status)
        
        return status_list
    
    async def simulate_selection(
        self,
        pool_name: str,
        partition: str,
        candidate_members: List[str],
        iterations: int = 100
    ) -> Dict[str, int]:
        """Simulate selection process for testing weighted random algorithm"""
        results = {}
        
        for _ in range(iterations):
            selected = await self.select_optimal_member(pool_name, partition, candidate_members)
            if selected:
                results[selected] = results.get(selected, 0) + 1
        
        # Calculate selection probabilities
        total = sum(results.values())
        probabilities = {member: count / total for member, count in results.items()}
        
        self.logger.info(f"Simulation selection results ({iterations} times): {probabilities}")
        
        return results
    
    async def analyze_selection_accuracy(
        self,
        pool_name: str,
        partition: str,
        candidate_members: List[str],
        iterations: int = 1000
    ) -> Dict:
        """Advanced probability analysis - detailed analysis of selection accuracy and deviation"""
        import statistics
        from decimal import Decimal
        
        # Get pool and intersection members
        pool = get_pool_by_key(pool_name, partition)
        if not pool:
            return {"error": f"Pool not found: {pool_name}:{partition}"}
        
        candidates = self._parse_candidate_members(candidate_members)
        intersection = self._get_intersection(pool, candidates)
        
        if not intersection:
            return {"error": "No valid intersection members"}
        
        # Calculate theoretical probabilities
        total_score = sum(member.score for member in intersection)
        theoretical_probs = {}
        for member in intersection:
            member_key = str(member)
            theoretical_probs[member_key] = (member.score / total_score) * 100
        
        # Execute multiple simulations
        results = {}
        detailed_results = []  # Record detailed data for each simulation
        
        for round_num in range(iterations):
            selected = await self.select_optimal_member(pool_name, partition, candidate_members)
            if selected:
                results[selected] = results.get(selected, 0) + 1
                detailed_results.append({
                    "round": round_num + 1,
                    "selected": selected,
                    "timestamp": round_num
                })
        
        # Calculate actual probabilities
        total_selections = sum(results.values())
        actual_probs = {}
        for member_key in theoretical_probs.keys():
            count = results.get(member_key, 0)
            actual_probs[member_key] = (count / total_selections) * 100 if total_selections > 0 else 0
        
        # Calculate deviation analysis
        deviation_analysis = {}
        for member_key in theoretical_probs.keys():
            theoretical = theoretical_probs[member_key]
            actual = actual_probs[member_key]
            absolute_deviation = abs(actual - theoretical)
            relative_deviation = (absolute_deviation / theoretical * 100) if theoretical > 0 else 0
            
            deviation_analysis[member_key] = {
                "theoretical_percent": round(theoretical, 4),
                "actual_percent": round(actual, 4),
                "absolute_deviation": round(absolute_deviation, 4),
                "relative_deviation_percent": round(relative_deviation, 4),
                "selection_count": results.get(member_key, 0)
            }
        
        # Calculate overall statistical indicators
        all_deviations = [data["absolute_deviation"] for data in deviation_analysis.values()]
        overall_stats = {
            "total_iterations": iterations,
            "successful_selections": total_selections,
            "success_rate": (total_selections / iterations) * 100,
            "mean_absolute_deviation": round(statistics.mean(all_deviations), 4),
            "max_absolute_deviation": round(max(all_deviations), 4),
            "min_absolute_deviation": round(min(all_deviations), 4),
            "std_deviation": round(statistics.stdev(all_deviations) if len(all_deviations) > 1 else 0, 4)
        }
        
        # Quality assessment
        quality_assessment = self._assess_selection_quality(deviation_analysis, overall_stats)
        
        return {
            "pool_info": {
                "name": pool_name,
                "partition": partition,
                "member_count": len(intersection),
                "total_score": round(total_score, 6)
            },
            "theoretical_probabilities": theoretical_probs,
            "actual_probabilities": actual_probs,
            "deviation_analysis": deviation_analysis,
            "overall_statistics": overall_stats,
            "quality_assessment": quality_assessment,
            "detailed_results": detailed_results[-50:] if len(detailed_results) > 50 else detailed_results  # Last 50 detailed results
        }
    
    def _assess_selection_quality(self, deviation_analysis: Dict, overall_stats: Dict) -> Dict:
        """Assess quality of selection algorithm"""
        mean_deviation = overall_stats["mean_absolute_deviation"]
        max_deviation = overall_stats["max_absolute_deviation"]
        success_rate = overall_stats["success_rate"]
        
        # Quality grade assessment
        if mean_deviation < 1.0 and max_deviation < 2.0 and success_rate > 99:
            quality_grade = "Excellent"
            quality_score = 95 + (5 - mean_deviation) if mean_deviation < 5 else 95
        elif mean_deviation < 2.0 and max_deviation < 5.0 and success_rate > 95:
            quality_grade = "Good"
            quality_score = 80 + (15 - mean_deviation * 3) if mean_deviation * 3 < 15 else 80
        elif mean_deviation < 5.0 and max_deviation < 10.0 and success_rate > 90:
            quality_grade = "Fair"
            quality_score = 60 + (20 - mean_deviation * 4) if mean_deviation * 4 < 20 else 60
        else:
            quality_grade = "Needs optimization"
            quality_score = max(0, 60 - mean_deviation * 5)
        
        # Recommendations
        recommendations = []
        if mean_deviation > 3.0:
            recommendations.append("Consider increasing test iterations for more stable results")
        if max_deviation > 8.0:
            recommendations.append("Check if score value distribution is too extreme")
        if success_rate < 95:
            recommendations.append("Check system for concurrency or other abnormal issues")
        if overall_stats["std_deviation"] > 2.0:
            recommendations.append("Large deviation fluctuation, recommend checking algorithm stability")
        
        return {
            "quality_grade": quality_grade,
            "quality_score": round(quality_score, 2),
            "is_acceptable": quality_grade in ["Excellent", "Good"],
            "recommendations": recommendations,
            "summary": f"Mean deviation {mean_deviation}%, max deviation {max_deviation}%, quality grade: {quality_grade}"
        } 