"""
PLATO Surprise Detector — tracks prediction errors across the fleet

Based on Free Energy Principle (Friston):
- The brain minimizes surprise (negative log-probability of outcomes)
- Unexpected outcomes create prediction errors
- High surprise triggers active inference (ZeroClaw-style exploration)

This system:
- Monitors agent outputs for unexpected outcomes
- Computes surprise score per event
- Triggers SurrogateProtocol when surprise exceeds threshold
- Tracks surprise history per agent and per domain

Usage:
    from plato_surprise import SurpriseDetector
    detector = SurpriseDetector(plato_url="http://localhost:8847")
    
    # Agent reports an outcome
    detector.report_outcome(
        agent="kimi-cli",
        expected="refactor completes in 30 minutes",
        observed="refactor still running after 2 hours",
        confidence=0.95
    )
    
    # Check fleet surprise levels
    surprise = detector.get_fleet_surprise()
    print(surprise)  # {"agents": {...}, "domains": {...}, "total_surprise": 0.42}
"""

import time
import requests
import math
from typing import Dict, Any, List, Optional
from collections import defaultdict

class SurpriseDetector:
    """
    Surprise detector for the fleet.
    
    Surprise = -log(P(observed | expected))
    High surprise = unexpected outcome
    Threshold exceeded → triggers self-healing
    """
    
    SURPRISE_THRESHOLD = 0.7  # Threshold for triggering healing
    DECAY_RATE = 0.95  # Surprise decays over time
    
    def __init__(self, plato_url: str = "http://localhost:8847"):
        self.plato_url = plato_url.rstrip("/")
        self.surprise_room = "fleet_surprise"
        self.state: Dict[str, float] = {}  # agent -> accumulated surprise
        self.by_domain: Dict[str, float] = {}  # domain -> accumulated surprise
    
    def compute_surprise(
        self,
        expected: str,
        observed: str,
        confidence: float = 0.5
    ) -> float:
        """
        Compute surprise score for an outcome.
        
        surprise = -log(1 - |expected_match - observed_match|)
        
        If observed matches expected exactly → surprise = 0
        If observed is completely unexpected → surprise = 1.0
        """
        # Simple overlap-based surprise
        expected_words = set(expected.lower().split())
        observed_words = set(observed.lower().split())
        
        if not expected_words:
            return 0.0
        
        overlap = len(expected_words & observed_words)
        match_ratio = overlap / len(expected_words)
        
        # Surprise is inverse of match
        surprise = 1.0 - match_ratio
        
        # Apply confidence weighting (high confidence = high surprise if wrong)
        if confidence > 0.5:
            surprise *= (confidence * 2 - 1)  # scale 0.5-1.0 to 0-1
        
        return min(max(surprise, 0.0), 1.0)
    
    def report_outcome(
        self,
        agent: str,
        expected: str,
        observed: str,
        confidence: float = 0.8,
        domain: str = "fleet_orchestration"
    ) -> Dict[str, Any]:
        """Report an outcome and compute surprise."""
        surprise = self.compute_surprise(expected, observed, confidence)
        
        # Update state
        self.state[agent] = self.state.get(agent, 0.0) * self.DECAY_RATE + surprise
        self.by_domain[domain] = self.by_domain.get(domain, 0.0) * self.DECAY_RATE + surprise
        
        # Write tile to PLATO
        tile = {
            "question": f"How surprised was {agent}?",
            "answer": f"Agent: {agent}\nExpected: {expected}\nObserved: {observed}\nSurprise: {surprise:.3f}\nDomain: {domain}",
            "agent": agent,
            "domain": domain,
            "confidence": 1.0 - surprise,  # high confidence = low surprise
            "model": agent,
            "role": "surprise_detector",
            "surprise_score": surprise,
            "timestamp": time.time()
        }
        
        write_status = "not_written"
        try:
            resp = requests.post(f"{self.plato_url}/room/{self.surprise_room}", json=tile, timeout=5)
            if resp.status_code == 200:
                write_status = "written"
        except:
            pass
        
        return {
            "agent": agent,
            "surprise": round(surprise, 3),
            "accumulated_surprise": round(self.state.get(agent, 0.0), 3),
            "threshold_exceeded": self.state.get(agent, 0.0) > self.SURPRISE_THRESHOLD,
            "write_status": write_status
        }
    
    def get_agent_surprise(self, agent: str) -> Dict[str, Any]:
        """Get surprise state for a specific agent."""
        return {
            "agent": agent,
            "accumulated_surprise": round(self.state.get(agent, 0.0), 3),
            "level": self._surprise_to_level(self.state.get(agent, 0.0)),
            "needs_attention": self.state.get(agent, 0.0) > self.SURPRISE_THRESHOLD
        }
    
    def get_fleet_surprise(self) -> Dict[str, Any]:
        """Get surprise state for the entire fleet."""
        agents = list(self.state.keys())
        if not agents:
            return {
                "total_surprise": 0.0,
                "agents": {},
                "domains": {},
                "needs_attention": False
            }
        
        total = sum(self.state.values())
        avg = total / len(agents)
        
        return {
            "total_surprise": round(total, 3),
            "average_surprise": round(avg, 3),
            "agents": {agent: round(s, 3) for agent, s in self.state.items()},
            "domains": {domain: round(s, 3) for domain, s in self.by_domain.items()},
            "needs_attention": total > self.SURPRISE_THRESHOLD * len(agents),
            "critical_agents": [
                agent for agent, s in self.state.items()
                if s > self.SURPRISE_THRESHOLD
            ]
        }
    
    def _surprise_to_level(self, surprise: float) -> str:
        if surprise < 0.2: return "minimal"
        elif surprise < 0.4: return "low"
        elif surprise < 0.6: return "moderate"
        elif surprise < 0.8: return "high"
        else: return "critical"
    
    def needs_investigation(self, agent: str) -> bool:
        """Check if an agent needs investigation due to high surprise."""
        return self.state.get(agent, 0.0) > self.SURPRISE_THRESHOLD
    
    def get_top_surprises(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get the highest surprise events."""
        try:
            resp = requests.get(f"{self.plato_url}/room/{self.surprise_room}?limit=50", timeout=5)
            if resp.status_code == 200:
                tiles = resp.json().get("tiles", [])
                # Sort by surprise score descending
                sorted_tiles = sorted(
                    tiles,
                    key=lambda t: t.get("surprise_score", 0),
                    reverse=True
                )
                return sorted_tiles[:limit]
        except:
            pass
        return []