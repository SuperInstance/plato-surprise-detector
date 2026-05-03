#!/usr/bin/env python3
"""
plato-surprise-detector — Detect surprising events in the fleet
Surprise = high information content = low predictability.
Flag unexpected patterns, outliers, and anomalies.
"""

import json, time, math
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class SurpriseEvent:
    category: str
    description: str
    surprisal: float  # bits of information
    timestamp: float
    context: Dict

class SurpriseDetector:
    def __init__(self, plato_url="http://147.224.38.131:8847"):
        self.plato_url = plato_url
        self.history: Dict[str, List[float]] = {}  # Category -> values
        self.surprises: List[SurpriseEvent] = []
    
    def observe(self, category: str, value: float, context: Dict = None):
        """Observe a value and detect if it's surprising."""
        if category not in self.history:
            self.history[category] = []
        
        history = self.history[category]
        
        # Calculate surprisal: -log2(p(value))
        # Simple model: Gaussian approx
        if len(history) >= 5:
            mean = sum(history) / len(history)
            variance = sum((x - mean) ** 2 for x in history) / len(history)
            std = math.sqrt(variance) if variance > 0 else 1.0
            
            # Z-score -> approximate probability
            z = abs(value - mean) / std if std > 0 else 0
            # Surprisal in bits
            surprisal = max(0, z * 0.5)  # Approximation
            
            if z > 2.0:  # More than 2 sigma = surprising
                event = SurpriseEvent(
                    category=category,
                    description=f"Unexpected value: {value:.2f} (expected ~{mean:.2f} ±{std:.2f})",
                    surprisal=surprisal,
                    timestamp=time.time(),
                    context=context or {}
                )
                self.surprises.append(event)
                self._submit(f"Surprise in {category}", f"Surprisal: {surprisal:.2f} bits. {event.description}")
                return event
        
        history.append(value)
        if len(history) > 50:
            history.pop(0)
        
        return None
    
    def get_recent_surprises(self, limit: int = 10) -> List[SurpriseEvent]:
        return sorted(self.surprises, key=lambda e: e.timestamp, reverse=True)[:limit]
    
    def get_surprise_report(self) -> Dict:
        if not self.surprises:
            return {"status": "quiet", "surprises": 0}
        
        by_category = {}
        for s in self.surprises:
            c = s.category
            if c not in by_category:
                by_category[c] = []
            by_category[c].append(s.surprisal)
        
        return {
            "total_surprises": len(self.surprises),
            "avg_surprisal": round(sum(s.surprisal for s in self.surprises) / len(self.surprises), 2),
            "by_category": {c: {"count": len(v), "max_surprisal": round(max(v), 2)} for c, v in by_category.items()},
            "recent": [{"category": s.category, "description": s.description, "surprisal": round(s.surprisal, 2)} 
                      for s in self.get_recent_surprises(5)]
        }
    
    def _submit(self, q: str, a: str):
        try:
            import urllib.request
            urllib.request.urlopen(urllib.request.Request(f"{self.plato_url}/submit", data=json.dumps({"question": q, "answer": a, "agent": "plato-surprise-detector", "room": "surprise"}).encode(), headers={"Content-Type": "application/json"}), timeout=5)
        except: pass

def demo():
    detector = SurpriseDetector()
    
    # Normal pattern
    for i in range(10):
        detector.observe("tile_rate", 5.0 + (i % 3))
    
    # Surprise!
    detector.observe("tile_rate", 25.0, {"event": "viral_post"})
    detector.observe("tile_rate", 3.0, {"event": "system_maintenance"})
    
    print("=== Surprise Report ===")
    print(json.dumps(detector.get_surprise_report(), indent=2))

if __name__ == "__main__": demo()
