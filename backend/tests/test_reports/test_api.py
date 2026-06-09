"""Tests for reports API endpoints."""

import pytest
from fastapi.testclient import TestClient

from homomics_lab.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestReportsAPI:
    def test_create_report(self, client):
        response = client.post(
            "/api/reports/create",
            json={
                "title": "Test Report",
                "project_name": "Project A",
                "analysis_type": "single_cell",
                "tags": ["test"],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "report_id" in data
        assert data["title"] == "Test Report"

    def test_list_reports(self, client):
        # Create a report first
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "List Test Report"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.get("/api/reports/list")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert any(r["id"] == report_id for r in data)

    def test_get_report(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "Get Test Report"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.get(f"/api/reports/{report_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == report_id
        assert data["title"] == "Get Test Report"

    def test_get_report_not_found(self, client):
        response = client.get("/api/reports/nonexistent")
        assert response.status_code == 404

    def test_add_section(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "Section Test"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.post(
            f"/api/reports/{report_id}/section",
            json={
                "title": "Results",
                "content": "Some results",
                "section_type": "results",
            },
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Section added"

    def test_add_step(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "Step Test"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.post(
            f"/api/reports/{report_id}/step",
            json={
                "name": "QC",
                "skill_id": "qc_skill",
                "status": "completed",
                "duration_seconds": 10.5,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["step_number"] == 1

    def test_set_summary(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "Summary Test"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.post(
            f"/api/reports/{report_id}/summary",
            params={"summary": "This is the summary."},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Summary updated"

    def test_add_plot_to_report(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "Plot Test"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.post(
            f"/api/reports/{report_id}/plot",
            json={
                "plot_type": "bar",
                "data": {"categories": ["A", "B"], "values": [10, 20]},
                "caption": "Test bar chart",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Plot added to report"
        assert data["figure_type"] == "bar"

    def test_add_plot_invalid_type(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "Plot Error Test"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.post(
            f"/api/reports/{report_id}/plot",
            json={
                "plot_type": "invalid_type",
                "data": {},
            },
        )
        assert response.status_code == 400

    def test_export_html(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "HTML Export Test"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.get(f"/api/reports/{report_id}/html")
        assert response.status_code == 200
        data = response.json()
        assert "html" in data
        assert "<!DOCTYPE html>" in data["html"]
        assert data["title"] == "HTML Export Test"

    def test_export_markdown(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "MD Export Test"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.get(f"/api/reports/{report_id}/markdown")
        assert response.status_code == 200
        data = response.json()
        assert "markdown" in data
        assert "# MD Export Test" in data["markdown"]

    def test_export_pdf(self, client):
        create_resp = client.post(
            "/api/reports/create",
            json={"title": "PDF Export Test"},
        )
        report_id = create_resp.json()["report_id"]

        response = client.get(f"/api/reports/{report_id}/pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert b"%PDF" in response.content
        assert len(response.content) > 100

    def test_export_pdf_nonexistent(self, client):
        response = client.get("/api/reports/nonexistent/pdf")
        assert response.status_code == 404

    def test_build_from_pipeline(self, client):
        response = client.post(
            "/api/reports/build-from-pipeline",
            json={
                "title": "Pipeline Report",
                "project_name": "Test",
                "analysis_type": "single_cell",
                "steps": [
                    {
                        "name": "QC",
                        "status": "completed",
                        "duration_seconds": 10.0,
                    },
                    {
                        "name": "Clustering",
                        "status": "completed",
                        "duration_seconds": 30.0,
                    },
                ],
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "report_id" in data
        assert data["title"] == "Pipeline Report"

    def test_add_section_to_nonexistent_report(self, client):
        response = client.post(
            "/api/reports/nonexistent/section",
            json={"title": "Section"},
        )
        assert response.status_code == 404

    def test_add_step_to_nonexistent_report(self, client):
        response = client.post(
            "/api/reports/nonexistent/step",
            json={"name": "Step"},
        )
        assert response.status_code == 404

    def test_export_nonexistent_report(self, client):
        response = client.get("/api/reports/nonexistent/html")
        assert response.status_code == 404
