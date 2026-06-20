"""Tests for intent decision logging and calibration."""



from homomics_lab.agent.intent.calibration import (
    ConfidenceCalibrator,
    IntentDecisionLogger,
    IntentDecisionRecord,
)


def test_logger_records_and_retrieves_decisions(tmp_path):
    logger = IntentDecisionLogger(db_path=tmp_path / "decisions.db")
    record = IntentDecisionRecord(
        timestamp="2026-01-01T00:00:00+00:00",
        message="analyze single cell",
        primary_intent="single_cell_analysis",
        confidence=0.9,
        needs_clarification=False,
    )
    logger.record(record)
    loaded = logger.recent_decisions(limit=10)
    assert len(loaded) == 1
    assert loaded[0].primary_intent == "single_cell_analysis"


def test_calibrator_returns_current_threshold_with_few_samples(tmp_path):
    logger = IntentDecisionLogger(db_path=tmp_path / "decisions.db")
    calibrator = ConfidenceCalibrator(logger, min_samples=5)
    assert calibrator.suggest_threshold(0.35) == 0.35


def test_calibrator_suggests_new_threshold(tmp_path):
    logger = IntentDecisionLogger(db_path=tmp_path / "decisions.db")
    # Create 50 decisions with very low confidence -> high clarification rate.
    for i in range(50):
        logger.record(
            IntentDecisionRecord(
                timestamp=f"2026-01-01T00:00:{i:02d}+00:00",
                message=f"msg {i}",
                primary_intent="qa",
                confidence=0.1,
                needs_clarification=False,
            )
        )
    calibrator = ConfidenceCalibrator(logger, min_samples=20, target_clarification_rate=0.1)
    suggested = calibrator.suggest_threshold(0.35)
    # Should move downward because most decisions are below any threshold.
    assert suggested < 0.35
