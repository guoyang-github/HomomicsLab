"""Tests for the LLM Wiki layer."""

import pytest

from homomics_lab.knowledge.wiki import WikiEngine, WikiStore
from homomics_lab.knowledge.wiki.models import WikiLink, WikiPage


@pytest.fixture
def wiki_store(tmp_path):
    return WikiStore(db_path=tmp_path / "wiki.db")


@pytest.fixture
def wiki_engine(wiki_store):
    return WikiEngine(store=wiki_store, knowledge_index=None)


def test_create_and_get_page(wiki_store):
    page = WikiPage(
        page_id="p1",
        project_id="proj",
        title="UMAP",
        content="UMAP is a dimensionality reduction algorithm.",
        created_by="user",
    )
    wiki_store.create_page(page)
    fetched = wiki_store.get_page("p1")
    assert fetched is not None
    assert fetched.title == "UMAP"
    assert fetched.content.startswith("UMAP is")


def test_list_pages_with_full_text_search(wiki_store):
    wiki_store.create_page(
        WikiPage(
            page_id="p1",
            project_id="proj",
            title="PCA",
            content="Principal component analysis.",
        )
    )
    wiki_store.create_page(
        WikiPage(
            page_id="p2",
            project_id="proj",
            title="UMAP",
            content="Uniform manifold approximation.",
        )
    )
    results = wiki_store.list_pages("proj", query="manifold")
    assert len(results) == 1
    assert results[0].title == "UMAP"


def test_update_page(wiki_store):
    page = WikiPage(
        page_id="p1",
        project_id="proj",
        title="Old",
        content="Old content.",
    )
    wiki_store.create_page(page)
    updated = wiki_store.update_page("p1", title="New", content="New content.")
    assert updated is not None
    assert updated.title == "New"
    assert updated.version == 2


def test_links(wiki_store):
    wiki_store.create_page(
        WikiPage(page_id="a", project_id="proj", title="A", content="A page")
    )
    wiki_store.create_page(
        WikiPage(page_id="b", project_id="proj", title="B", content="B page")
    )
    wiki_store.create_or_update_link(
        WikiLink(source_id="a", target_id="b", relation="related", strength=0.9)
    )
    links = wiki_store.get_links("a")
    assert len(links) == 1
    assert links[0].target_id == "b"


@pytest.mark.asyncio
async def test_answer_without_index_returns_no_results(wiki_engine):
    result = await wiki_engine.answer("What is UMAP?", project_id="proj")
    assert "no relevant" in result.answer.lower() or "not found" in result.answer.lower()


@pytest.mark.asyncio
async def test_manual_page_creation(wiki_engine):
    page = await wiki_engine.create_manual_page(
        project_id="proj", title="Manual", content="Manual content."
    )
    assert page.title == "Manual"
    assert wiki_engine.store.get_page(page.page_id) is not None
