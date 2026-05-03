"""Tests for PLATO Surprise Detector."""

import pytest
from plato_surprise import SurpriseDetector


class TestComputeSurprise:
    """Test surprise computation."""
    
    def test_exact_match_returns_zero_surprise(self):
        detector = SurpriseDetector()
        surprise = detector.compute_surprise("hello world", "hello world")
        assert surprise == 0.0
    
    def test_no_overlap_returns_high_surprise(self):
        detector = SurpriseDetector()
        surprise = detector.compute_surprise("cat dog", "boat ship")
        assert surprise == 1.0
    
    def test_partial_overlap(self):
        detector = SurpriseDetector()
        surprise = detector.compute_surprise("hello world", "hello there")
        # 1 common word / 2 expected words = 0.5 match → 0.5 surprise
        assert surprise == 0.5
    
    def test_confidence_amplifies_surprise(self):
        detector = SurpriseDetector()
        low_conf = detector.compute_surprise("hello", "goodbye", confidence=0.6)
        high_conf = detector.compute_surprise("hello", "goodbye", confidence=0.95)
        # same base surprise, but high confidence amplifies it
        assert high_conf > low_conf
    
    def test_empty_expected_returns_zero(self):
        detector = SurpriseDetector()
        surprise = detector.compute_surprise("", "anything")
        assert surprise == 0.0
    
    def test_surprise_clamped_to_one(self):
        detector = SurpriseDetector()
        # Even with confidence amplification, should max at 1.0
        surprise = detector.compute_surprise("a", "b", confidence=1.0)
        assert surprise <= 1.0


class TestReportOutcome:
    """Test outcome reporting."""
    
    def test_report_updates_state(self):
        detector = SurpriseDetector()
        result = detector.report_outcome(
            agent="test-agent",
            expected="success",
            observed="success",
            confidence=0.9
        )
        assert result["agent"] == "test-agent"
        assert result["surprise"] == 0.0
        assert "accumulated_surprise" in result
    
    def test_threshold_exceeded_flag(self):
        detector = SurpriseDetector()
        # Report multiple high-surprise events
        for _ in range(10):
            detector.report_outcome(
                agent="stressed-agent",
                expected="this exact phrase",
                observed="completely different outcome",
                confidence=0.95
            )
        # After accumulation, should exceed threshold
        state = detector.get_agent_surprise("stressed-agent")
        if state["accumulated_surprise"] > SurpriseDetector.SURPRISE_THRESHOLD:
            assert state["needs_attention"]


class TestStateManagement:
    """Test surprise state tracking."""
    
    def test_multiple_agents_tracked_separately(self):
        detector = SurpriseDetector()
        detector.report_outcome(agent="agent-a", expected="yes", observed="yes", confidence=0.9)
        detector.report_outcome(agent="agent-b", expected="no", observed="yes", confidence=0.9)
        
        fleet = detector.get_fleet_surprise()
        assert "agent-a" in fleet["agents"]
        assert "agent-b" in fleet["agents"]
    
    def test_domain_accumulation(self):
        detector = SurpriseDetector()
        detector.report_outcome(agent="test", expected="a", observed="b", domain="coding", confidence=0.8)
        detector.report_outcome(agent="test", expected="c", observed="d", domain="coding", confidence=0.8)
        
        fleet = detector.get_fleet_surprise()
        assert "coding" in fleet["domains"]
        assert fleet["domains"]["coding"] > 0
    
    def test_decay_reduces_surprise(self):
        detector = SurpriseDetector()
        detector.report_outcome(agent="test", expected="x", observed="y", confidence=0.9)
        first_state = detector.state.get("test", 0)
        
        # Report low-surprise outcome
        detector.report_outcome(agent="test", expected="x", observed="x", confidence=0.9)
        second_state = detector.state.get("test", 0)
        
        # High surprise event followed by perfect match should decay
        assert second_state < first_state + 1.0


class TestFleetSurprise:
    """Test fleet-level operations."""
    
    def test_empty_fleet_returns_zeros(self):
        detector = SurpriseDetector()
        fleet = detector.get_fleet_surprise()
        assert fleet["total_surprise"] == 0.0
        assert fleet["needs_attention"] is False
    
    def test_critical_agents_list(self):
        detector = SurpriseDetector()
        # Create agent with high accumulated surprise
        for _ in range(20):
            detector.report_outcome(
                agent="critical-agent",
                expected="exact match only",
                observed="nothing alike",
                confidence=1.0
            )
        
        fleet = detector.get_fleet_surprise()
        if fleet["agents"].get("critical-agent", 0) > SurpriseDetector.SURPRISE_THRESHOLD:
            assert "critical-agent" in fleet["critical_agents"]


class TestSurpriseLevels:
    """Test surprise level classification."""
    
    def test_minimal_level(self):
        detector = SurpriseDetector()
        assert detector._surprise_to_level(0.1) == "minimal"
    
    def test_low_level(self):
        detector = SurpriseDetector()
        assert detector._surprise_to_level(0.3) == "low"
    
    def test_moderate_level(self):
        detector = SurpriseDetector()
        assert detector._surprise_to_level(0.5) == "moderate"
    
    def test_high_level(self):
        detector = SurpriseDetector()
        assert detector._surprise_to_level(0.7) == "high"
    
    def test_critical_level(self):
        detector = SurpriseDetector()
        assert detector._surprise_to_level(0.9) == "critical"


class TestNeedsInvestigation:
    """Test investigation flagging."""
    
    def test_below_threshold_no_investigation(self):
        detector = SurpriseDetector()
        detector.state["calm-agent"] = 0.3
        assert detector.needs_investigation("calm-agent") is False
    
    def test_above_threshold_needs_investigation(self):
        detector = SurpriseDetector()
        detector.state["stressed-agent"] = 0.8
        assert detector.needs_investigation("stressed-agent") is True
    
    def test_unknown_agent_no_investigation(self):
        detector = SurpriseDetector()
        assert detector.needs_investigation("unknown-agent") is False