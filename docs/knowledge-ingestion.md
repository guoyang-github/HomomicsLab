# Knowledge Ingestion (Extract → Cognify → Load)

HomomicsLab now includes a lightweight, cognee-inspired **Extract-Cognify-Load**
pipeline that turns unstructured documents into a searchable knowledge graph.

## Supported content

| Source | Status | Parser |
|--------|--------|--------|
| Plain text / Markdown / JSON / YAML / CSV | ✅ | stdlib |
| PDF | ✅ | `pypdf` (optional) |
| DOCX | ✅ | `python-docx` (optional) |
| HTML / URL | ✅ | `beautifulsoup4` + `httpx` (optional) |
| Images (PNG/JPG/…) | ⚠️ placeholder | `Pillow` metadata + OCR/vision hook |

## Enabling optional parsers

```bash
uv pip install -e ".[knowledge]"
```

or individually:

```bash
uv pip install pypdf python-docx beautifulsoup4 httpx
```

## Pipeline stages

1. **Extract** – parse the document into clean text, paragraphs and metadata.
2. **Chunk** – split text into semantic chunks (paragraph boundary + token limit).
3. **Summarize** – generate a document summary and per-chunk summaries via LLM.
4. **Cognify** – use an LLM to extract entities and relationships as JSON.
5. **Load** – write into:
   - `GraphBackend`: `Document`, `DocumentChunk`, `Entity` nodes and typed edges.
   - `VectorStoreBackend`: `knowledge_chunks` collection for semantic search.
   - `MemoryBackend`: a `note` memory so chat retrieval can recall documents.
   - `CapabilityIndex`: the document is registered as a `DATA_SOURCE`.

## API

All endpoints are under `/api/knowledge`.

### Ingest inline text

```bash
curl -X POST http://localhost:8080/api/knowledge/ingest \
  -H "Content-Type: application/json" \
  -d '{"source_type":"text","source":"RNA-seq is...","project_id":"demo"}'
```

### Ingest an uploaded file

```bash
curl -X POST http://localhost:8080/api/knowledge/ingest-upload \
  -F "file=@paper.pdf" \
  -F "project_id=demo"
```

### Ingest a whole project

```bash
curl -X POST "http://localhost:8080/api/knowledge/cognify-project?project_id=demo"
```

### Search ingested knowledge

```bash
curl "http://localhost:8080/api/knowledge/search?q=single-cell&project_id=demo"
```

## Configuration

The pipeline is controlled via `CognifyOptions`:

- `skip_existing` – skip documents whose content hash was already processed.
- `max_concurrent_extractions` – throttle parallel LLM calls.
- `chunker.max_tokens_per_chunk` – chunk size.
- `extractor.enable_extraction` – toggle LLM entity/relation extraction.
- `extractor.enable_summarization` – toggle LLM summarization.

## Relation to cognee

We deliberately did **not** add the `cognee` package as a dependency. Instead,
HomomicsLab uses its existing pluggable backends (`GraphBackend`,
`VectorStoreBackend`, `EmbeddingProvider`, `LLMClient`) to provide a cognify-
equivalent pipeline that is lighter, offline-friendly, and consistent with the
rest of the codebase.
