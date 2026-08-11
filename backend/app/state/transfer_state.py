"""
backend/app/state/transfer_state.py

Single global state object for the entire server process.
Only one transfer is active at a time — a new upload via POST /api/upload
replaces whatever was previously active by calling reset().

The generation counter is the only guard against stale-symbol contamination:
when a re-upload happens mid-transfer, any in-flight /api/symbol POSTs from
the old receiver will see a changed generation and be dropped silently.
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

from app.core.chunker import chunk_data
from app.core.fountain import FountainEncoder
from app.core.peeling_decoder import PeelingDecoder

# ── Named constants ────────────────────────────────────────────────────────────
# Change these to tune performance. Both FountainEncoder and PeelingDecoder
# are always initialized from these values so they can never drift apart.

BLOCK_SIZE: int = 400      # bytes per source block
FOUNTAIN_C: float = 0.03   # Robust Soliton c parameter
FOUNTAIN_DELTA: float = 0.05  # Robust Soliton delta parameter
MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024  # 10 MB hard cap on uploads


@dataclass
class TransferState:
    # Sender side
    filename: str
    file_size: int
    sha256_hash: str
    blocks: list
    encoder: FountainEncoder

    # Receiver side
    decoder: PeelingDecoder

    # Internal-only generation counter — never exposed in the API or packet format.
    # Bumped by reset() so symbol.py can detect mid-request re-uploads and drop
    # symbols that belong to a now-dead transfer.
    generation: int = 0

    @property
    def k(self) -> int:
        return len(self.blocks)


# Module-level singleton — None until the first upload.
_state: Optional[TransferState] = None

# Module-level lock — NEVER replaced, so upload.py and symbol.py always
# acquire the same object regardless of how many resets have happened.
# This is what makes the generation-counter double-check meaningful.
lock: asyncio.Lock = asyncio.Lock()


def reset(filename: str, file_size: int, blocks: list, sha256_hash: str) -> None:
    """
    Replace the active transfer with a new one. Bumps the generation counter
    so any in-flight symbol POSTs from the old receiver get dropped cleanly.
    Called by routes/upload.py while holding the module-level `lock`.
    """
    global _state
    new_generation = (_state.generation + 1) if _state is not None else 0
    encoder = FountainEncoder(blocks, c=FOUNTAIN_C, delta=FOUNTAIN_DELTA)
    decoder = PeelingDecoder(
        k=len(blocks),
        block_size=BLOCK_SIZE,
        c=FOUNTAIN_C,
        delta=FOUNTAIN_DELTA,
    )
    _state = TransferState(
        filename=filename,
        file_size=file_size,
        sha256_hash=sha256_hash,
        blocks=blocks,
        encoder=encoder,
        decoder=decoder,
        generation=new_generation,
        # Note: lock lives at module level, NOT inside TransferState
    )


def reset_decoder() -> None:
    """
    Replace only the decoder with a fresh PeelingDecoder (same k/c/delta),
    keeping all sender-side state intact. Called by routes/download.py on a
    hash mismatch so the receiver can keep feeding symbols without re-uploading.
    Must be called while holding the asyncio.Lock.
    """
    global _state
    if _state is None:
        return
    _state.decoder = PeelingDecoder(
        k=_state.k,
        block_size=BLOCK_SIZE,
        c=FOUNTAIN_C,
        delta=FOUNTAIN_DELTA,
    )


def get_state() -> Optional[TransferState]:
    """Return the active TransferState, or None if no upload has happened yet."""
    return _state


def is_ready() -> bool:
    """True if a file has been uploaded and the transfer is initialized."""
    return _state is not None


def get_generation() -> int:
    """
    Return the current generation counter.
    Routes read this before and after acquiring the lock to detect re-uploads.
    Returns -1 if no state exists yet (will never match a valid snapshot).
    """
    return _state.generation if _state is not None else -1
