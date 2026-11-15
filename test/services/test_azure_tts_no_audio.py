from pathlib import Path
import tempfile
from unittest.mock import patch

from edge_tts.exceptions import NoAudioReceived

from app.services import voice


def _run_tts(stream_side_effect):
    """Run azure_tts_v1 against a fake stream and return its observable effects.

    Directory contents are captured inside the TemporaryDirectory context
    because the directory is deleted before the caller sees the results.
    """

    def stream(_communicate, on_chunk, **_kwargs):
        stream_side_effect(on_chunk)

    with (
        tempfile.TemporaryDirectory() as temp_dir,
        patch.object(voice, "create_edge_tts_communicate") as communicate_factory,
        patch.object(voice, "stream_edge_tts_chunks", side_effect=stream),
    ):
        output = Path(temp_dir) / "voice.mp3"
        result = voice.azure_tts_v1(
            "个人智能代理正在改变学习。", "af-ZA-AdriNeural", 1.0, str(output)
        )
        return result, communicate_factory, output.exists(), list(Path(temp_dir).iterdir())


def test_no_audio_received_stops_retrying_immediately():
    # NoAudioReceived is deterministic — e.g. an Afrikaans voice asked to read
    # a Chinese script completes the stream with zero audio bytes. Retrying
    # cannot change the outcome, so only one attempt may hit the service.
    def raise_no_audio(_on_chunk):
        raise NoAudioReceived(
            "No audio was received. Please verify that your parameters are correct."
        )

    result, communicate_factory, output_exists, leftover = _run_tts(raise_no_audio)
    assert result is None
    assert communicate_factory.call_count == 1
    assert not output_exists
    assert leftover == []


def test_other_stream_failures_still_get_the_full_three_retries():
    # A transient transport error may succeed on a later attempt, so the
    # pre-existing three-retry behavior must be preserved for it.
    def raise_transient(_on_chunk):
        raise RuntimeError("connection reset")

    result, communicate_factory, output_exists, leftover = _run_tts(raise_transient)
    assert result is None
    assert communicate_factory.call_count == 3
    assert not output_exists
    assert leftover == []
