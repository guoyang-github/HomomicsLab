import pytest
import base64

from homomics_lab.viz.generator import PlotGenerator, PlotType


@pytest.fixture
def generator():
    return PlotGenerator()


class TestPlotGenerator:
    def test_generate_umap(self, generator):
        data = {
            "coordinates": [[1, 2], [2, 3], [3, 4], [1, 3], [2, 2]],
            "labels": ["A", "A", "B", "B", "A"],
        }
        result = generator.generate(PlotType.UMAP, data, title="Test UMAP")
        assert isinstance(result, str)
        # Verify it's valid base64
        decoded = base64.b64decode(result)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes

    def test_generate_heatmap(self, generator):
        data = {
            "matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            "row_labels": ["R1", "R2", "R3"],
            "col_labels": ["C1", "C2", "C3"],
        }
        result = generator.generate(PlotType.HEATMAP, data, title="Test Heatmap")
        assert isinstance(result, str)
        decoded = base64.b64decode(result)
        assert decoded[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_violin(self, generator):
        data = {
            "groups": {
                "A": [1, 2, 3, 4, 5],
                "B": [2, 3, 4, 5, 6],
            }
        }
        result = generator.generate(PlotType.VIOLIN, data, title="Test Violin")
        assert isinstance(result, str)
        assert base64.b64decode(result)[:8] == b"\x89PNG\r\n\x1a\n"

    def test_generate_bar(self, generator):
        data = {"categories": ["A", "B", "C"], "values": [10, 20, 15]}
        result = generator.generate(PlotType.BAR, data, title="Test Bar")
        assert isinstance(result, str)

    def test_generate_scatter(self, generator):
        data = {"x": [1, 2, 3, 4], "y": [1, 4, 9, 16]}
        result = generator.generate(PlotType.SCATTER, data, title="Test Scatter")
        assert isinstance(result, str)

    def test_generate_histogram(self, generator):
        data = {"values": [1, 2, 2, 3, 3, 3, 4, 4, 5]}
        result = generator.generate(PlotType.HISTOGRAM, data, title="Test Hist")
        assert isinstance(result, str)

    def test_generate_with_dummy_data(self, generator):
        """Test that dummy data is generated when no data provided."""
        result = generator.generate(PlotType.UMAP, {}, title="Empty UMAP")
        assert isinstance(result, str)
        assert len(result) > 100

    def test_invalid_plot_type(self, generator):
        with pytest.raises(ValueError):
            generator.generate("invalid_type", {})


class TestPlotAPI:
    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from homomics_lab.main import app
        return TestClient(app)

    def test_list_plot_types(self, client):
        response = client.get("/api/viz/plot/types")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 6
        types = [t["type"] for t in data]
        assert "umap" in types
        assert "heatmap" in types

    def test_generate_plot_endpoint(self, client):
        response = client.post(
            "/api/viz/plot",
            json={
                "plot_type": "bar",
                "data": {"categories": ["A", "B"], "values": [10, 20]},
                "title": "Test",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "image_base64" in data
        assert data["plot_type"] == "bar"
        assert data["title"] == "Test"
