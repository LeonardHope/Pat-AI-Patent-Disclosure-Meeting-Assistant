"""Token-aware text chunking for document context."""


def chunk_text(
    text: str,
    max_chunk_chars: int = 2000,
    overlap_chars: int = 200,
) -> list[str]:
    """Split text into overlapping chunks.

    Uses character count as a proxy for tokens (~4 chars per token).
    This is simpler than tiktoken and good enough for context building.

    Args:
        text: The text to chunk.
        max_chunk_chars: Maximum characters per chunk.
        overlap_chars: Characters of overlap between chunks.

    Returns:
        List of text chunks.
    """
    if len(text) <= max_chunk_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chunk_chars

        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start + max_chunk_chars // 2, end)
            if para_break > start:
                end = para_break + 2
            else:
                # Look for sentence end
                for sep in [". ", ".\n", "! ", "? "]:
                    sent_break = text.rfind(sep, start + max_chunk_chars // 2, end)
                    if sent_break > start:
                        end = sent_break + len(sep)
                        break

        chunks.append(text[start:end].strip())
        start = end - overlap_chars

    return [c for c in chunks if c]
