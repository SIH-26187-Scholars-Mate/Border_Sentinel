"""
ai/tests/test_preview_server.py
Covers the evidence-frame bookkeeping added to PreviewServer.publish():
non-"live" channels accumulate (so each alert's snapshot survives past the
next frame) but are capped so a long-running worker's memory doesn't grow
forever as more alerts fire.
"""
import numpy as np

from ai.video.preview_server import MAX_EVIDENCE_FRAMES, PreviewServer


def _frame():
    return np.zeros((10, 10, 3), dtype=np.uint8)


def test_live_channel_is_overwritten_not_accumulated():
    server = PreviewServer.__new__(PreviewServer)  # skip binding a real socket
    from ai.video.preview_server import _State
    server.state = _State()

    server.publish(_frame(), channel="live")
    server.publish(_frame(), channel="live")

    assert list(server.state.jpeg_by_channel.keys()) == ["live"]


def test_evidence_channels_accumulate_independently():
    server = PreviewServer.__new__(PreviewServer)
    from ai.video.preview_server import _State
    server.state = _State()

    server.publish(_frame(), channel="live")
    server.publish(_frame(), channel="evidence-aaa")
    server.publish(_frame(), channel="evidence-bbb")

    assert set(server.state.jpeg_by_channel.keys()) == {"live", "evidence-aaa", "evidence-bbb"}


def test_evidence_channels_are_capped_evicting_oldest_first():
    server = PreviewServer.__new__(PreviewServer)
    from ai.video.preview_server import _State
    server.state = _State()

    server.publish(_frame(), channel="live")
    for i in range(MAX_EVIDENCE_FRAMES + 5):
        server.publish(_frame(), channel=f"evidence-{i}")

    keys = server.state.jpeg_by_channel.keys()
    assert "live" in keys  # never evicted
    assert len(keys) == MAX_EVIDENCE_FRAMES + 1  # +1 for "live"
    # The earliest evidence frames should be gone, the most recent kept.
    assert "evidence-0" not in keys
    assert f"evidence-{MAX_EVIDENCE_FRAMES + 4}" in keys
