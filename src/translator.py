"""Translation service using Claude API for large PDF content."""

import anthropic

from src.config import ANTHROPIC_API_KEY, CLAUDE_MODEL, SOURCE_LANGUAGE, TARGET_LANGUAGE

# Maximum characters per translation request to stay within token limits
MAX_CHUNK_CHARS = 15000


def get_client() -> anthropic.Anthropic:
    """Create and return an Anthropic client."""
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def translate_text(client: anthropic.Anthropic, text: str) -> str:
    """Translate a chunk of text from source to target language using Claude."""
    if not text.strip():
        return ""

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Translate the following text from {SOURCE_LANGUAGE} to {TARGET_LANGUAGE}. "
                    f"Preserve the original formatting, paragraph structure, and meaning as closely as possible. "
                    f"Only output the translated text, nothing else.\n\n"
                    f"---\n{text}\n---"
                ),
            }
        ],
    )
    return message.content[0].text


def translate_pages(pages: list[dict]) -> list[dict]:
    """Translate all extracted pages, chunking large pages as needed.

    Takes a list of {"page": int, "text": str} and returns the same structure
    with translated text.
    """
    client = get_client()
    translated_pages = []

    for page_data in pages:
        page_num = page_data["page"]
        text = page_data["text"]

        if not text.strip():
            translated_pages.append({"page": page_num, "text": ""})
            continue

        # Split into chunks if the text is very large
        chunks = _split_text(text, MAX_CHUNK_CHARS)
        translated_chunks = []

        for i, chunk in enumerate(chunks):
            chunk_label = f"page {page_num}"
            if len(chunks) > 1:
                chunk_label += f" chunk {i + 1}/{len(chunks)}"
            print(f"  Translating {chunk_label}...")
            translated = translate_text(client, chunk)
            translated_chunks.append(translated)

        translated_pages.append({
            "page": page_num,
            "text": "\n".join(translated_chunks),
        })

    return translated_pages


def _split_text(text: str, max_chars: int) -> list[str]:
    """Split text into chunks, breaking at paragraph boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > max_chars and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk = current_chunk + "\n\n" + para if current_chunk else para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [text]
