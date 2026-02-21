"""tts_engine.py — ElevenLabs TTS synthesis with chunking and resumability."""

import re
import time
from pathlib import Path

from tqdm import tqdm

CHUNK_SIZE_CHARS = 4800
MAX_RETRIES = 3


def split_into_sentence_chunks(text: str, max_chars: int = CHUNK_SIZE_CHARS) -> list[str]:
    """
    Split text into chunks of at most max_chars, breaking at sentence boundaries.
    Uses paragraph breaks (double newlines) as primary split points first,
    then sentence boundaries within long paragraphs.
    """
    # First split on paragraph breaks
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        # If the paragraph itself is too long, split at sentence boundaries
        if len(para) > max_chars:
            sentences = _split_sentences(para)
        else:
            sentences = [para]

        for sentence in sentences:
            if not sentence:
                continue
            # If adding this sentence would exceed the limit, flush current chunk
            if current_chunk and len(current_chunk) + len(sentence) + 2 > max_chars:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            elif not current_chunk:
                current_chunk = sentence
            else:
                current_chunk += " " + sentence

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    # Last-resort hard split for any chunk still over the limit
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            # Hard split at word boundaries
            while len(chunk) > max_chars:
                split_at = chunk.rfind(" ", 0, max_chars)
                if split_at == -1:
                    split_at = max_chars
                final_chunks.append(chunk[:split_at].strip())
                chunk = chunk[split_at:].strip()
            if chunk:
                final_chunks.append(chunk)

    return [c for c in final_chunks if c]


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences using punctuation-based heuristics."""
    # Split after .!? followed by whitespace before capital letter or quote
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"\u2018\u201c\u2019])', text)
    return [p.strip() for p in parts if p.strip()]


def synthesize_chunk(
    client,
    text: str,
    voice_id: str,
    model_id: str,
    output_path: Path,
) -> Path:
    """Call ElevenLabs TTS API for a single chunk, save as MP3."""
    from elevenlabs import VoiceSettings

    delay = RETRY_DELAY = 5
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            audio_generator = client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=model_id,
                voice_settings=VoiceSettings(
                    stability=0.5,
                    similarity_boost=0.75,
                    style=0.0,
                    use_speaker_boost=True,
                ),
                output_format="mp3_44100_128",
            )
            audio_bytes = b"".join(audio_generator)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_bytes)
            return output_path

        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            # Retry on rate limits or server errors
            if "429" in error_str or "rate" in error_str or "5" in error_str[:3]:
                print(f"\n  Rate limit / server error (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(delay)
                delay *= 2
            else:
                raise

    raise RuntimeError(f"TTS failed after {MAX_RETRIES} attempts: {last_error}")


def synthesize_chapter(
    client,
    chapter_index: int,
    chapter_title: str,
    tts_title: str,
    chapter_text: str,
    voice_id: str,
    model_id: str,
    chunks_dir: Path,
    progress: dict,
    save_progress_fn,
) -> list[Path]:
    """
    Synthesize all chunks for one chapter. Returns list of chunk MP3 paths in order.
    Skips chunks already marked complete in progress dict.
    """
    # Prepend a chapter title announcement for natural narration
    full_text = f"{tts_title}.\n\n{chapter_text}"
    chunks = split_into_sentence_chunks(full_text)

    chunk_paths = []
    completed = set(progress.get("completed_chunks", []))

    with tqdm(total=len(chunks), desc=f"  {chapter_title[:50]}", unit="chunk") as pbar:
        for chunk_idx, chunk_text in enumerate(chunks):
            chunk_key = f"ch{chapter_index:02d}_chunk{chunk_idx:03d}"
            output_path = chunks_dir / f"{chunk_key}.mp3"

            if chunk_key in completed and output_path.exists():
                chunk_paths.append(output_path)
                pbar.update(1)
                continue

            synthesize_chunk(client, chunk_text, voice_id, model_id, output_path)

            completed.add(chunk_key)
            progress["completed_chunks"] = list(completed)
            save_progress_fn(progress)

            chunk_paths.append(output_path)
            pbar.update(1)

            # Small pause to be respectful of rate limits
            time.sleep(0.3)

    return chunk_paths
