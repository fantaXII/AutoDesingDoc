import pytest
from src.config_loader import ThresholdConfig
from src.counter.hysteresis_evaluator import HysteresisDecision, HysteresisEvaluator


@pytest.fixture
def evaluator():
    return HysteresisEvaluator(ThresholdConfig(create=25, delete=10))


class TestHysteresisDecision:
    # CREATE
    def test_create_when_no_doc_and_count_at_threshold(self, evaluator):
        assert evaluator.decide(25, doc_exists=False) == HysteresisDecision.CREATE

    def test_create_when_no_doc_and_count_above_threshold(self, evaluator):
        assert evaluator.decide(50, doc_exists=False) == HysteresisDecision.CREATE

    # SKIP
    def test_skip_when_no_doc_and_count_below_threshold(self, evaluator):
        assert evaluator.decide(24, doc_exists=False) == HysteresisDecision.SKIP

    def test_skip_when_no_doc_and_count_at_delete_boundary(self, evaluator):
        assert evaluator.decide(10, doc_exists=False) == HysteresisDecision.SKIP

    def test_skip_when_no_doc_and_count_zero(self, evaluator):
        assert evaluator.decide(0, doc_exists=False) == HysteresisDecision.SKIP

    # DELETE
    def test_delete_when_doc_exists_and_count_at_delete_threshold(self, evaluator):
        assert evaluator.decide(10, doc_exists=True) == HysteresisDecision.DELETE

    def test_delete_when_doc_exists_and_count_below_delete_threshold(self, evaluator):
        assert evaluator.decide(5, doc_exists=True) == HysteresisDecision.DELETE

    def test_delete_when_doc_exists_and_count_zero(self, evaluator):
        assert evaluator.decide(0, doc_exists=True) == HysteresisDecision.DELETE

    # KEEP (Hysteresis 구간)
    def test_keep_in_hysteresis_zone_no_change(self, evaluator):
        assert evaluator.decide(15, doc_exists=True, has_structural_change=False) == HysteresisDecision.KEEP

    def test_update_in_hysteresis_zone_with_change(self, evaluator):
        assert evaluator.decide(15, doc_exists=True, has_structural_change=True) == HysteresisDecision.UPDATE

    # UPDATE
    def test_update_when_doc_exists_and_count_above_threshold(self, evaluator):
        assert evaluator.decide(30, doc_exists=True, has_structural_change=True) == HysteresisDecision.UPDATE

    def test_keep_when_doc_exists_and_no_structural_change(self, evaluator):
        assert evaluator.decide(30, doc_exists=True, has_structural_change=False) == HysteresisDecision.KEEP

    # 경계값
    def test_boundary_at_delete_plus_one(self, evaluator):
        assert evaluator.decide(11, doc_exists=True, has_structural_change=False) == HysteresisDecision.KEEP

    def test_boundary_at_create_minus_one_no_doc(self, evaluator):
        assert evaluator.decide(24, doc_exists=False) == HysteresisDecision.SKIP

    def test_boundary_at_create_minus_one_with_doc(self, evaluator):
        assert evaluator.decide(24, doc_exists=True, has_structural_change=True) == HysteresisDecision.UPDATE

    def test_exactly_at_create_with_doc_no_change(self, evaluator):
        assert evaluator.decide(25, doc_exists=True, has_structural_change=False) == HysteresisDecision.KEEP
