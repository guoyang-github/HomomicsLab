import pytest

from homomics_lab.skills.evolution import SkillEvolution


@pytest.fixture
def evolution(tmp_path):
    db = tmp_path / "test_evolution.db"
    return SkillEvolution(db_path=db)


class TestSkillEvolution:
    def test_create_test(self, evolution):
        test_id = evolution.create_test(
            test_name="qc-method-comparison",
            skill_id="bio-single-cell-preprocessing",
            variant_a="scanpy_qc_v1",
            variant_b="scanpy_qc_v2",
        )
        assert test_id > 0

    def test_record_comparison(self, evolution):
        test_id = evolution.create_test("test", "skill", "a", "b")

        evolution.record_comparison(test_id, winner="a", reason="Faster execution")
        evolution.record_comparison(test_id, winner="a", reason="Better output")
        evolution.record_comparison(test_id, winner="b", reason="Lower memory")

        results = evolution.get_test_results(test_id)
        assert results["variant_a_wins"] == 2
        assert results["variant_b_wins"] == 1
        assert results["total_comparisons"] == 3

    def test_get_test_results_not_significant(self, evolution):
        test_id = evolution.create_test("test", "skill", "a", "b")

        # Only 5 comparisons, not enough for significance
        for _ in range(5):
            evolution.record_comparison(test_id, winner="a")

        results = evolution.get_test_results(test_id)
        assert results["significant"] is False
        assert "More comparisons needed" in results["recommendation"]

    def test_get_test_results_significant(self, evolution):
        test_id = evolution.create_test("test", "skill", "a", "b")

        # 10 comparisons with clear winner
        for _ in range(7):
            evolution.record_comparison(test_id, winner="a")
        for _ in range(3):
            evolution.record_comparison(test_id, winner="b")

        results = evolution.get_test_results(test_id)
        assert results["significant"] is True
        assert "Variant A" in results["recommendation"]

    def test_list_tests(self, evolution):
        evolution.create_test("test1", "skill-a", "v1", "v2")
        evolution.create_test("test2", "skill-b", "v1", "v2")

        all_tests = evolution.list_tests()
        assert len(all_tests) == 2

        filtered = evolution.list_tests(skill_id="skill-a")
        assert len(filtered) == 1
        assert filtered[0]["skill_id"] == "skill-a"

    def test_tie_recordings(self, evolution):
        test_id = evolution.create_test("test", "skill", "a", "b")

        evolution.record_comparison(test_id, winner=None, reason="Equivalent results")
        evolution.record_comparison(test_id, winner="a")

        results = evolution.get_test_results(test_id)
        assert results["ties"] == 1
        assert results["variant_a_wins"] == 1
