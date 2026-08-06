"""Real, measured voice-pipeline evaluation: synthesizes each sampled golden
item's text with Deepgram Aura TTS (the exact model family production uses,
src/persona/resolve.py VOICE_LIBRARY), then transcribes the resulting audio
with Deepgram nova-3 STT (the exact model production uses, src/agent.py
`deepgram.STT(model="nova-3", ...)`), and computes WER/CER between the
original text and the round-trip transcript.

This measures STT accuracy against a TTS-synthesized voice, not a real human
speaker -- see the report for why this is the only reproducible option
without a recorded-human-speech dataset, and what it can and cannot claim.

Uses the Deepgram REST API directly via httpx (already a project dependency,
see src/session/cloud_store.py) -- no LiveKit session, no new dependency.

Writes evaluation/results/voice_eval_results.json.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from evaluation.scripts.generate_golden_dataset import build_full_dataset  # noqa: E402

RESULTS_PATH = Path(__file__).resolve().parents[1] / "results" / "voice_eval_results.json"
DEEPGRAM_KEY = os.environ["DEEPGRAM_API_KEY"]
TTS_MODEL = "aura-2-thalia-en"  # VOICE_LIBRARY["brisk_neutral"], the default preset
STT_MODEL = "nova-3"            # matches src/agent.py deepgram.STT(model="nova-3", ...)

TTS_URL = f"https://api.deepgram.com/v1/speak?model={TTS_MODEL}&encoding=linear16&sample_rate=24000"
STT_URL = f"https://api.deepgram.com/v1/listen?model={STT_MODEL}&smart_format=true"


def _normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9' ]", " ", text)
    return " ".join(text.split())


def _levenshtein(a: list, b: list) -> int:
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    prev = list(range(m + 1))
    for i in range(1, n + 1):
        cur = [i] + [0] * m
        for j in range(1, m + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[m]


def wer(reference: str, hypothesis: str) -> float | None:
    ref_words = _normalize(reference).split()
    hyp_words = _normalize(hypothesis).split()
    if not ref_words:
        return None
    return _levenshtein(ref_words, hyp_words) / len(ref_words)


def cer(reference: str, hypothesis: str) -> float | None:
    ref_chars = list(_normalize(reference).replace(" ", ""))
    hyp_chars = list(_normalize(hypothesis).replace(" ", ""))
    if not ref_chars:
        return None
    return _levenshtein(ref_chars, hyp_chars) / len(ref_chars)


def synthesize(text: str) -> tuple[bytes, float]:
    t0 = time.perf_counter()
    resp = httpx.post(
        TTS_URL,
        headers={"Authorization": f"Token {DEEPGRAM_KEY}",
                "Content-Type": "application/json"},
        json={"text": text}, timeout=60.0,
    )
    resp.raise_for_status()
    return resp.content, time.perf_counter() - t0


def transcribe(audio_bytes: bytes) -> tuple[str, float]:
    t0 = time.perf_counter()
    resp = httpx.post(
        STT_URL,
        headers={"Authorization": f"Token {DEEPGRAM_KEY}",
                "Content-Type": "audio/l16;rate=24000"},
        content=audio_bytes, timeout=60.0,
    )
    resp.raise_for_status()
    data = resp.json()
    transcript = (data["results"]["channels"][0]["alternatives"][0]["transcript"])
    return transcript, time.perf_counter() - t0


def run_item(item) -> dict:
    result = {"id": item.id, "category": item.category,
              "word_count": item.word_count}
    try:
        audio, tts_latency_s = synthesize(item.text)
        result["tts_latency_s"] = tts_latency_s
        result["audio_bytes"] = len(audio)
        transcript, stt_latency_s = transcribe(audio)
        result["stt_latency_s"] = stt_latency_s
        result["transcript"] = transcript
        result["reference"] = item.text
        result["wer"] = wer(item.text, transcript)
        result["cer"] = cer(item.text, transcript)
        result["status"] = "success"
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def select_sample(items, per_category: int = 3):
    by_cat: dict[str, list] = {}
    for it in items:
        by_cat.setdefault(it.category, []).append(it)
    sample = []
    for cat, lst in sorted(by_cat.items()):
        sample.extend(lst[:per_category])
    return sample


def main() -> None:
    limit_per_cat = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    items = build_full_dataset()
    sample = select_sample(items, per_category=limit_per_cat)
    print(f"voice eval sample: {len(sample)} items ({limit_per_cat}/category), "
          f"TTS={TTS_MODEL} STT={STT_MODEL}")

    results = []
    for i, item in enumerate(sample, 1):
        r = run_item(item)
        results.append(r)
        if r["status"] == "success":
            print(f"  [{i}/{len(sample)}] {item.id:16s} -> WER={r['wer']:.3f} "
                  f"CER={r['cer']:.3f} tts={r['tts_latency_s']:.2f}s "
                  f"stt={r['stt_latency_s']:.2f}s")
        else:
            print(f"  [{i}/{len(sample)}] {item.id:16s} -> ERROR: {r['error']}")

    out = {"tts_model": TTS_MODEL, "stt_model": STT_MODEL,
          "n_items": len(sample), "results": results}
    RESULTS_PATH.parent.mkdir(exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
