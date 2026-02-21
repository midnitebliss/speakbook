"""voice_setup.py — ElevenLabs voice selection, cloning, and persistence."""

import os
from pathlib import Path

from dotenv import load_dotenv, set_key

ENV_FILE = Path(".env")

# ElevenLabs default fallback voice (Aria - neutral, natural)
DEFAULT_VOICE_ID = "9BWtsMINqrJLrRacOk9x"


def load_voice_id() -> str | None:
    """Load VOICE_ID from .env file. Returns None if not set."""
    load_dotenv()
    vid = os.getenv("VOICE_ID", "").strip()
    return vid if vid else None


def save_voice_id(voice_id: str) -> None:
    """Persist voice_id to .env for future runs."""
    ENV_FILE.touch(exist_ok=True)
    set_key(str(ENV_FILE), "VOICE_ID", voice_id)
    print(f"  Saved VOICE_ID={voice_id} to {ENV_FILE}")


def search_voice_library(client, query: str = "narrator") -> str | None:
    """
    Search the ElevenLabs public Voice Library for a matching voice.
    Returns voice_id of the best match, or None if not found.
    The voice must be added to the user's account before use.
    """
    try:
        print(f"  Searching ElevenLabs Voice Library for '{query}'...")
        results = client.voices.get_shared(
            search=query,
            page_size=5,
        )
        voices = getattr(results, "voices", None) or []
        if not voices:
            print("  No voices found in library.")
            return None

        # Pick the first result
        voice = voices[0]
        public_user_id = getattr(voice, "public_owner_id", None) or getattr(voice, "public_user_id", None)
        voice_id = getattr(voice, "voice_id", None)
        voice_name = getattr(voice, "name", "unknown")

        if not voice_id:
            print("  Voice found but missing voice_id.")
            return None

        print(f"  Found: '{voice_name}' (id: {voice_id})")

        # Add the shared voice to the user's account so it can be used
        if public_user_id:
            try:
                client.voices.add_sharing_voice(
                    public_user_id=public_user_id,
                    voice_id=voice_id,
                    name=voice_name,
                )
                print(f"  Added '{voice_name}' to your account.")
            except Exception as e:
                # If it's already added, this may raise an error - that's fine
                if "already" in str(e).lower() or "exists" in str(e).lower():
                    print(f"  Voice already in your account.")
                else:
                    print(f"  Warning: could not add voice to account: {e}")

        return voice_id

    except Exception as e:
        print(f"  Voice Library search failed: {e}")
        return None


def clone_voice_from_sample(client, sample_path: Path, voice_name: str = "Cloned Voice") -> str:
    """
    Upload audio sample to ElevenLabs Instant Voice Cloning.
    Returns voice_id string.
    Requires Creator plan or above.
    """
    print(f"  Uploading voice sample: {sample_path.name} ({sample_path.stat().st_size // 1024} KB)")
    with sample_path.open("rb") as f:
        voice = client.clone(
            name=voice_name,
            description="Cloned from voice sample for audiobook narration",
            files=[f],
        )
    voice_id = voice.voice_id
    print(f"  Voice cloned successfully. ID: {voice_id}")
    return voice_id


def setup_voice(
    client,
    sample_path: Path | None = None,
    use_library: bool = True,
    search_query: str = "narrator",
) -> str:
    """
    Resolve a voice ID using the following priority:
    1. Existing VOICE_ID in .env
    2. ElevenLabs Voice Library search (if use_library=True)
    3. Instant Voice Cloning from sample_path (if provided)
    4. ElevenLabs default voice

    Saves the resolved voice_id to .env for future runs.
    Returns voice_id string.
    """
    # Priority 1: cached voice ID
    voice_id = load_voice_id()
    if voice_id:
        print(f"Using saved voice ID: {voice_id}")
        return voice_id

    print("Setting up voice...")

    # Priority 2: Voice Library
    if use_library:
        voice_id = search_voice_library(client, search_query)
        if voice_id:
            save_voice_id(voice_id)
            return voice_id

    # Priority 3: Voice cloning from sample
    if sample_path is not None:
        if not sample_path.exists():
            raise FileNotFoundError(f"Voice sample not found: {sample_path}")
        voice_id = clone_voice_from_sample(client, sample_path)
        save_voice_id(voice_id)
        return voice_id

    # Priority 4: Default voice
    print(f"  Using default ElevenLabs voice (Aria, id: {DEFAULT_VOICE_ID})")
    print("  Tip: Use --voice-sample to clone a custom voice for better results.")
    return DEFAULT_VOICE_ID
