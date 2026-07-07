"""Tests for the unified v2 DataState."""

from homomics_lab.agent.plan.models import DataState


class TestDataStateV2:
    def test_legacy_direct_attributes(self):
        ds = DataState(
            has_qc=True,
            n_cells=5000,
            batch_detected=True,
        )
        assert ds.has_qc is True
        assert ds.n_cells == 5000
        assert ds.batch_detected is True

    def test_get_universal_field(self):
        ds = DataState(n_samples=10)
        assert ds.get("n_samples") == 10
        assert ds.get("missing_field") is None
        assert ds.get("missing_field", default="default") == "default"

    def test_get_legacy_field(self):
        ds = DataState(n_cells=5000)
        assert ds.get("n_cells") == 5000

    def test_domain_namespace_isolation(self):
        ds = DataState()
        ds.set("host_contamination", 0.05, domain="metagenomics")
        ds.set("n_asvs", 5000, domain="metagenomics")
        ds.set("n_cells", 3000, domain="single-cell-transcriptomics")

        assert ds.get("host_contamination", domain="metagenomics") == 0.05
        assert ds.get("n_asvs", domain="metagenomics") == 5000
        assert ds.get("n_cells", domain="single-cell-transcriptomics") == 3000
        # Cross-domain lookup without domain returns the first found key
        assert ds.get("n_cells") == 3000
        assert ds.get("host_contamination") == 0.05
        # Missing in namespace returns default
        assert ds.get("host_contamination", domain="single-cell-transcriptomics") is None

    def test_set_universal_field(self):
        ds = DataState()
        ds.set("has_qc", True)
        assert ds.has_qc is True
        assert ds.get("has_qc") is True

    def test_set_unknown_field_goes_to_general_namespace(self):
        ds = DataState()
        ds.set("custom_field", "custom_value")
        assert ds.get("custom_field") == "custom_value"
        assert ds.domain_state["_general"]["custom_field"] == "custom_value"

    def test_has_field(self):
        ds = DataState(n_cells=1000)
        ds.set("host_contamination", 0.05, domain="metagenomics")
        assert ds.has_field("n_cells") is True
        assert ds.has_field("host_contamination") is True
        assert ds.has_field("missing") is False

    def test_to_context(self):
        ds = DataState(
            has_qc=True,
            n_samples=10,
            low_quality=True,
        )
        ds.set("host_contamination", 0.05, domain="metagenomics")
        context = ds.to_context()
        assert "QC completed" in context
        assert "10 samples" in context
        assert "low data quality" in context
        assert "metagenomics.host_contamination=0.05" in context
