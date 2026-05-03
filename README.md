# PLATO Surprise Detector

Tracks prediction errors across the agent fleet and triggers the self-healing protocol when surprise exceeds threshold.

## Based on Free Energy Principle (Friston)

- The brain minimizes **surprise** (negative log-probability of outcomes)
- Unexpected outcomes create **prediction errors** (surprise)
- High surprise triggers **active inference** (exploration to resolve uncertainty)

This system monitors agent outputs, computes surprise scores, and alerts when agents deviate significantly from expected behavior.

## Installation

```bash
pip install plato-surprise-detector
```

## Quick Start

```python
from plato_surprise import SurpriseDetector

detector = SurpriseDetector(plato_url="http://localhost:8847")

# Agent reports an outcome
result = detector.report_outcome(
    agent="kimi-cli",
    expected="refactor completes in 30 minutes",
    observed="refactor still running after 2 hours",
    confidence=0.95
)

print(result)
# {'agent': 'kimi-cli', 'surprise': 0.714, 'accumulated_surprise': 0.679, 
#  'threshold_exceeded': False, 'write_status': 'written'}

# Check fleet surprise levels
surprise = detector.get_fleet_surprise()
print(surprise)
# {'total_surprise': 0.679, 'average_surprise': 0.679, 'agents': {'kimi-cli': 0.679}, 
#  'domains': {'fleet_orchestration': 0.679}, 'needs_attention': False, 'critical_agents': []}
```

## How Surprise Works

### Surprise Score Computation

```
surprise = 1.0 - match_ratio
```

Where `match_ratio` is the overlap between expected and observed outcomes. High confidence predictions that fail produce even higher surprise scores.

### Threshold & Decay

- **Threshold**: 0.7 — triggers attention when exceeded
- **Decay Rate**: 0.95 — surprise decays per time step

```
accumulated_surprise = previous_surprise * 0.95 + new_surprise
```

### Surprise Levels

| Score Range | Level |
|-------------|-------|
| 0.0 - 0.2 | minimal |
| 0.2 - 0.4 | low |
| 0.4 - 0.6 | moderate |
| 0.6 - 0.8 | high |
| 0.8 - 1.0 | critical |

## API Reference

### `SurpriseDetector(plato_url="http://localhost:8847")`

Initialize the detector.

### `report_outcome(agent, expected, observed, confidence=0.8, domain="fleet_orchestration")`

Report an agent outcome and compute surprise.

**Returns:**
```python
{
    "agent": str,
    "surprise": float,           # immediate surprise of this outcome
    "accumulated_surprise": float,  # after decay
    "threshold_exceeded": bool,
    "write_status": str          # "written" or "not_written"
}
```

### `get_fleet_surprise()`

Get surprise state for the entire fleet.

**Returns:**
```python
{
    "total_surprise": float,
    "average_surprise": float,
    "agents": {agent: score},
    "domains": {domain: score},
    "needs_attention": bool,
    "critical_agents": [agent, ...]
}
```

### `get_agent_surprise(agent)`

Get surprise state for a specific agent.

### `needs_investigation(agent)`

Returns `True` if agent's accumulated surprise exceeds threshold.

### `get_top_surprises(limit=5)`

Returns the highest surprise events from PLATO.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│   Agent     │────▶│ SurpriseDetector │────▶│    PLATO    │
│  (output)   │     │                  │     │ (fleet_surprise) │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Threshold  │
                    │  Exceeded?   │
                    └─────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
                   Yes            No
                    │             │
                    ▼             ▼
            ┌───────────────┐   ┌──────┐
            │ Self-Healing  │   │ Log  │
            │   Protocol    │   └──────┘
            └───────────────┘
```

## License

MIT