import pytest
from codelens.retrieval.confidence import check_confidence


class TestConfidenceGate:
    def test_high_score_passes(self):
        # threshold default is -3.0; 0.0 is well above
        assert check_confidence(0.0, threshold=-3.0) is True

    def test_low_score_fails(self):
        assert check_confidence(-10.0, threshold=-3.0) is False

    def test_exact_threshold_passes(self):
        assert check_confidence(-3.0, threshold=-3.0) is True

    def test_just_below_threshold_fails(self):
        assert check_confidence(-3.01, threshold=-3.0) is False
