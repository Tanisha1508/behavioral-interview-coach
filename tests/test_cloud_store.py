"""Supabase persistence (scope item 15): CloudSession activates only for
signed-in users with env configured, writes sessions/answers rows with the
right payloads, and never lets a network failure reach the live session."""

import asyncio

import httpx

from src.session import cloud_store
from src.session.cloud_store import CloudSession


class FakeParticipant:
    def __init__(self, attributes):
        self.attributes = attributes


class FakeRoom:
    def __init__(self, attrs):
        self.remote_participants = {"p1": FakeParticipant(attrs)}


def set_env(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://unit.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "unit-key")


def mock_http(monkeypatch, requests, status=201):
    def handler(request):
        requests.append(request)
        if status >= 400:
            return httpx.Response(status, json={"message": "boom"})
        if request.method == "POST" and request.url.path.endswith("/sessions"):
            return httpx.Response(status, json=[{"id": "sess-1"}])
        if request.method == "POST" and request.url.path.endswith("/answers"):
            return httpx.Response(status, json=[{"id": "ans-1"}])
        return httpx.Response(204)

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        cloud_store.httpx, "AsyncClient",
        lambda **kw: real_client(
            transport=httpx.MockTransport(handler), **kw))


def make_cloud():
    return CloudSession("u-1", "drill", "pm",
                        "https://unit.supabase.co", "unit-key")


def test_activation_requires_env_and_user_id(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    signed_in = FakeRoom({"user_id": "u-1"})
    assert CloudSession.create_if_configured(signed_in, "drill", "pm") is None

    set_env(monkeypatch)
    assert CloudSession.create_if_configured(None, "drill", "pm") is None, \
        "console mode (no room) must stay local-only"
    assert CloudSession.create_if_configured(
        FakeRoom({}), "drill", "pm") is None, "guests must stay local-only"

    cloud = CloudSession.create_if_configured(signed_in, "drill", "pm")
    assert cloud is not None and cloud.user_id == "u-1"


def test_record_attach_finish_write_the_right_rows(monkeypatch):
    async def run():
        requests = []
        mock_http(monkeypatch, requests)
        cloud = make_cloud()
        await cloud.record_answer(question="Q?", transcript="T",
                                  duration_s=42.7,
                                  scores={"dimensions": {}})
        await cloud.attach_rewrite("Better answer.")
        await cloud.finish(dropped=1, patterns=["we-heavy"],
                           raw={"type": "drill"})

        assert [(r.method, r.url.path) for r in requests] == [
            ("POST", "/rest/v1/sessions"),
            ("POST", "/rest/v1/answers"),
            ("PATCH", "/rest/v1/answers"),
            ("PATCH", "/rest/v1/sessions"),
        ]
        import json
        session_row = json.loads(requests[0].content)
        assert session_row == {"user_id": "u-1", "type": "drill",
                               "round": "pm"}
        answer_row = json.loads(requests[1].content)
        assert answer_row["session_id"] == "sess-1"
        assert answer_row["user_id"] == "u-1"
        assert answer_row["duration_s"] == 42
        assert answer_row["scores"] == {"dimensions": {}}
        assert requests[2].url.params["id"] == "eq.ans-1"
        assert json.loads(requests[2].content) == {
            "rewrite": "Better answer."}
        assert requests[3].url.params["id"] == "eq.sess-1"
        finish_row = json.loads(requests[3].content)
        assert finish_row["dropped"] == 1
        assert finish_row["patterns"] == ["we-heavy"]
        assert finish_row["raw"] == {"type": "drill"}
        assert isinstance(finish_row["duration_s"], int)
        # The service role key must ride every request.
        assert all(r.headers["apikey"] == "unit-key" for r in requests)
    asyncio.run(run())


def test_network_failure_never_raises(monkeypatch):
    async def run():
        requests = []
        mock_http(monkeypatch, requests, status=500)
        cloud = make_cloud()
        await cloud.record_answer(question="Q?", transcript="T",
                                  duration_s=1, scores=None)
        await cloud.attach_rewrite("x")
        await cloud.finish()
        assert requests, "calls were attempted"
    asyncio.run(run())


def test_finish_without_answers_writes_nothing(monkeypatch):
    async def run():
        requests = []
        mock_http(monkeypatch, requests)
        cloud = make_cloud()
        await cloud.finish()
        assert not requests, \
            "a session with no answers must not create a history row"
    asyncio.run(run())


def test_rewrite_before_any_answer_is_a_noop(monkeypatch):
    async def run():
        requests = []
        mock_http(monkeypatch, requests)
        cloud = make_cloud()
        await cloud.attach_rewrite("orphan rewrite")
        assert not requests
    asyncio.run(run())
