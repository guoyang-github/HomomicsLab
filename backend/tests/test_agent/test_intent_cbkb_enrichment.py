"""Tests for CBKB enrichment of intent analysis."""

import pytest

from homomics_lab.agent.intent.analyzer import CascadeIntentAnalyzer
from homomics_lab.knowledge.cbkb import AnomalyRecord, CBKB, LabSOP


@pytest.fixture
def cbkb(tmp_path):
    return CBKB(base_dir=tmp_path)


@pytest.mark.asyncio
async def test_intent_enriched_with_sops_and_anomalies(cbkb):
    cbkb.create_sop(
        LabSOP(
            id="sop_sc",
            name="Standard PBMC QC",
            category="single-cell-transcriptomics",
            template={"min_genes": 200},
            derived_from_bundle_ids=["b1"],
            version="1.0",
            locked=False,
        )
    )
    cbkb.archive_anomaly(
        AnomalyRecord(
            id="a1",
            project_id="p1",
            phase_type="single_cell_analysis",
            summary="High filter rate",
            flags=["filter_rate > 0.5"],
            recommendations=["Check data quality"],
            severity="warning",
            created_at="2024-01-01T00:00:00+00:00",
        )
    )

    analyzer = CascadeIntentAnalyzer(use_domain_registry=False, cbkb=cbkb)
    intent = await analyzer.analyze("帮我分析这组单细胞数据")

    assert intent.analysis_type == "single_cell_analysis"
    enrichment = intent.metadata.get("cbkb")
    assert enrichment is not None
    assert len(enrichment["sops"]) == 1
    assert enrichment["sops"][0]["id"] == "sop_sc"
    assert len(enrichment["anomalies"]) == 1
    assert enrichment["anomalies"][0]["phase_type"] == "single_cell_analysis"


@pytest.mark.asyncio
async def test_intent_enrichment_disabled_without_cbkb():
    analyzer = CascadeIntentAnalyzer(use_domain_registry=False)
    intent = await analyzer.analyze("帮我分析这组单细胞数据")
    assert "cbkb" not in intent.metadata
