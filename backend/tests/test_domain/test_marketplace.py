"""Tests for domain template marketplace."""


import pytest

from homomics_lab.domain.marketplace import DomainMarketplace


@pytest.fixture
def marketplace(tmp_path):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "single_cell").mkdir()
    (builtin / "single_cell" / "domain.yaml").write_text(
        "domain: single_cell\nversion: \"1.0.0\"\ndescription: scRNA-seq\n",
        encoding="utf-8",
    )
    marketplace_dir = tmp_path / "marketplace"
    marketplace_dir.mkdir()
    return DomainMarketplace(
        builtin_domains_dir=builtin,
        marketplace_dir=marketplace_dir,
    )


def test_list_domains(marketplace):
    domains = marketplace.list_domains()
    assert len(domains) == 1
    assert domains[0].domain_id == "single_cell"
    assert domains[0].source == "builtin"


def test_export_and_import_zip(marketplace, tmp_path):
    zip_path = marketplace.export_domain("single_cell", output_path=tmp_path / "sc.zip")
    assert zip_path.exists()

    target = marketplace.import_domain(str(zip_path), target_name="imported_sc")
    assert target.exists()
    assert (target / "domain.yaml").exists()


def test_import_code_templates(marketplace):
    marketplace.import_code_templates(
        "single_cell",
        {
            "my_template": {
                "language": "python",
                "skeleton": "print('hello')",
            }
        },
    )
    text = (marketplace.builtin_domains_dir / "single_cell" / "domain.yaml").read_text()
    assert "my_template" in text
