"""Amplitude server-side tracking (scope item 16, checkpoint 2): active
only when AMPLITUDE_API_KEY is set, posts the right payload shape to the
HTTP API V2 endpoint, and never lets a network failure reach the live
session, same rule as tests/test_cloud_store.py."""

import asyncio

import httpx

from src.analytics import amplitude


class FakeRoom:
    def __init__(self, name):
        self.name = name


def mock_http(monkeypatch, requests, status=200):
    def handler(request):
        requests.append(request)
        return httpx.Response(status, json={"code": status})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        amplitude.httpx, "AsyncClient",
        lambda **kw: real_client(
            transport=httpx.MockTransport(handler), **kw))


def test_device_id_from_room_uses_room_name():
    assert amplitude.device_id_from_room(FakeRoom("room-abc123")) == "room-abc123"


def test_device_id_from_room_pads_short_names():
    # Amplitude drops ids under 5 chars; console mode room names can be short.
    assert amplitude.device_id_from_room(FakeRoom("cs")) == "agent-cs"
    assert amplitude.device_id_from_room(FakeRoom("")) == "agent-unknown"
    assert amplitude.device_id_from_room(None) == "agent-unknown"


def test_track_noop_without_api_key(monkeypatch):
    monkeypatch.delenv("AMPLITUDE_API_KEY", raising=False)

    async def run():
        requests = []
        mock_http(monkeypatch, requests)
        await amplitude.track("session_started", device_id="device-1")
        assert not requests, "no network call without an API key configured"
    asyncio.run(run())


def test_track_posts_the_right_payload(monkeypatch):
    monkeypatch.setenv("AMPLITUDE_API_KEY", "unit-key")

    async def run():
        requests = []
        mock_http(monkeypatch, requests)
        await amplitude.track(
            "answer_graded", device_id="device-1", user_id="user-1",
            event_properties={"evidence_violations": 2})
        assert len(requests) == 1
        req = requests[0]
        assert req.url == httpx.URL(amplitude.INGEST_URL)
        import json
        body = json.loads(req.content)
        assert body["api_key"] == "unit-key"
        assert len(body["events"]) == 1
        event = body["events"][0]
        assert event["event_type"] == "answer_graded"
        assert event["device_id"] == "device-1"
        assert event["user_id"] == "user-1"
        assert event["event_properties"] == {"evidence_violations": 2}
        assert isinstance(event["time"], int)
    asyncio.run(run())


def test_track_omits_short_user_id(monkeypatch):
    monkeypatch.setenv("AMPLITUDE_API_KEY", "unit-key")

    async def run():
        requests = []
        mock_http(monkeypatch, requests)
        # Guests: user_id_from_room returns None upstream, but even a
        # too-short id (Amplitude's min_id_length) must not ride the event.
        await amplitude.track("session_started", device_id="device-1",
                              user_id="ab")
        import json
        event = json.loads(requests[0].content)["events"][0]
        assert "user_id" not in event
    asyncio.run(run())


def test_track_network_failure_never_raises(monkeypatch):
    monkeypatch.setenv("AMPLITUDE_API_KEY", "unit-key")

    async def run():
        requests = []
        mock_http(monkeypatch, requests, status=500)
        await amplitude.track("session_started", device_id="device-1")
        assert requests, "the call was attempted"
    asyncio.run(run())
