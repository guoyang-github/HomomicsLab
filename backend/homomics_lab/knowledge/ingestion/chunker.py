"""Semantic-ish text chunking for ingestion."""

import uuid
from dataclasses import dataclass
from typing import List, Optional

from homomics_lab.knowledge.ingestion.models import ParsedDocument, TextChunk


def _estimate_tokens(text: str) -> int:
    """Estimate tokens; prefer tiktoken, fall back to character heuristic."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4 + 1


def _split_paragraph(paragraph: str, max_tokens: int) -> List[str]:
    """Split a paragraph into pieces that fit within max_tokens."""
    if _estimate_tokens(paragraph) <= max_tokens:
        return [paragraph]

    sentences = []
    current = ""
    for sentence in paragraph.replace(". ", ".\n").replace("? ", "?\n").replace("! ", "!\n").split("\n"):
        sentence = sentence.strip()
        if not sentence:
            continue
        if not current:
            current = sentence
        elif _estimate_tokens(current + " " + sentence) <= max_tokens:
            current += " " + sentence
        else:
            sentences.append(current)
            current = sentence
    if current:
        sentences.append(current)

    # If a single sentence is still too long, hard-split by words.
    result: List[str] = []
    for piece in sentences:
        if _estimate_tokens(piece) <= max_tokens:
            result.append(piece)
            continue
        words = piece.split(" ")
        current = ""
        for word in words:
            if not current:
                current = word
            elif _estimate_tokens(current + " " + word) <= max_tokens:
                current += " " + word
            else:
                result.append(current)
                current = word
        if current:
            result.append(current)
    return result


@dataclass
class ChunkerOptions:
    max_tokens_per_chunk: int = 512
    overlap_tokens: int = 50


class TextChunker:
    """Split parsed documents into overlapping semantic chunks."""

    def __init__(self, options: Optional[ChunkerOptions] = None) -> None:
        self.options = options or ChunkerOptions()

    def chunk(self, document: ParsedDocument, document_id: str) -> List[TextChunk]:
        chunks: List[TextChunk] = []
        index = 0
        for paragraph in document.paragraphs:
            pieces = _split_paragraph(paragraph, self.options.max_tokens_per_chunk)
            for piece in pieces:
                chunk_id = f"{document_id}:chunk:{uuid.uuid4().hex[:12]}"
                chunks.append(
                    TextChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        text=piece,
                        index=index,
                        estimated_tokens=_estimate_tokens(piece),
                    )
                )
                index += 1

        # Add simple overlap between adjacent chunks by duplicating trailing text.
        if self.options.overlap_tokens > 0 and len(chunks) > 1:
            overlapped: List[TextChunk] = []
            for i, chunk in enumerate(chunks):
                prefix = ""
                if i > 0:
                    prev = chunks[i - 1].text
                    words = prev.split(" ")
                    prefix_words = []
                    approx = 0
                    for w in reversed(words):
                        approx += len(w) // 4 + 1
                        if approx > self.options.overlap_tokens:
                            break
                        prefix_words.append(w)
                    if prefix_words:
                        prefix = " ".join(reversed(prefix_words)) + " "
                overlapped.append(
                    TextChunk(
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        text=(prefix + chunk.text).strip(),
                        index=chunk.index,
                        estimated_tokens=_estimate_tokens(prefix + chunk.text),
                        metadata=chunk.metadata,
                    )
                )
            chunks = overlapped

        return chunks
