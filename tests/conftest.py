"""Test isolation from live external services. src/agent.py calls
load_dotenv() at import time, so a real AMPLITUDE_API_KEY in .env would
otherwise leak into every test that constructs a runner, firing real
(fire-and-forget) events at production Amplitude on every test run.
Individual tests that want it back use monkeypatch.setenv, same pattern
already used for SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY in
tests/test_cloud_store.py."""

import pytest


@pytest.fixture(autouse=True)
def _no_live_amplitude(monkeypatch):
    monkeypatch.delenv("AMPLITUDE_API_KEY", raising=False)
