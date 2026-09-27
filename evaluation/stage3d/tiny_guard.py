"""
Stage 3D — Tiny-input guard (evaluation/runtime, no semantic change).

Threshold: <300 characters (stripped text length).
- Tiny inputs consistently stall qwen2.5:3b past the 90s timeout (Stage 3C:
  Commercial forms.txt 217 chars timed out twice at 92.1s).
- Guard records explicit SKIPPED_TINY_INPUT, never claims LLM success,
  never silently falls back to deterministic output as LLM output.
- Normal-sized chunks (>=300 chars) are unaffected.
"""
TINY_THRESHOLD = 300
SKIPPED_TINY_INPUT = "SKIPPED_TINY_INPUT"


def tiny_guard_status(chunk: dict, threshold: int = TINY_THRESHOLD) -> str:
    """
    Returns "OK" if the chunk should be sent to the LLM,
    SKIPPED_TINY_INPUT if it must be skipped, or other explicit statuses
    for empty/whitespace inputs.

    - None / missing text -> "EMPTY_INPUT"
    - whitespace-only -> "WHITESPACE_ONLY"
    - stripped len < threshold -> SKIPPED_TINY_INPUT
    - otherwise -> "OK"
    """
    if chunk is None:
        return "EMPTY_INPUT"
    text = chunk.get("text", None)
    if text is None:
        return "EMPTY_INPUT"
    if not isinstance(text, str):
        text = str(text)
    stripped = text.strip()
    if len(stripped) == 0:
        if len(text) == 0:
            return "EMPTY_INPUT"
        return "WHITESPACE_ONLY"
    if len(stripped) < threshold:
        return SKIPPED_TINY_INPUT
    return "OK"
