"""Dual-threshold PASS / REVIEW / FAIL decision logic (scores normalised to 0..1)."""
import math

from app.models.models import Decision


class ThresholdError(ValueError):
    pass


class DecisionEngine:
    @staticmethod
    def validate_thresholds(review: float, fail: float) -> None:
        for v in (review, fail):
            if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v):
                raise ThresholdError("Thresholds must be numbers")
        if not (0 <= review < fail <= 1):
            raise ThresholdError("Thresholds must satisfy 0 <= review_threshold < fail_threshold <= 1")

    @classmethod
    def decide(cls, score: float, review: float, fail: float) -> Decision:
        cls.validate_thresholds(review, fail)
        if math.isnan(score) or not (0 <= score <= 1):
            raise ThresholdError("Score must be within 0..1")
        if score < review:
            return Decision.PASS
        if score < fail:
            return Decision.REVIEW
        return Decision.FAIL
