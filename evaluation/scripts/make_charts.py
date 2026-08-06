"""Generates the charts referenced in EVALUATION_REPORT.md from
evaluation/results/metrics_summary.json. Requires matplotlib (not a product
dependency -- installed only in this dev venv for report generation; see
evaluation/README.md).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

RESULTS = Path(__file__).resolve().parents[1] / "results" / "metrics_summary.json"
CHARTS = Path(__file__).resolve().parents[1] / "charts"
CHARTS.mkdir(exist_ok=True)

CAT_ORDER = ["excellent", "star_explicit", "non_star", "average", "fabricated",
            "incomplete", "off_topic", "weak"]
COLORS = {"Solid": "#2e7d32", "NeedsWork": "#f9a825", "Gap": "#c62828"}


def chart_rubric_by_category(data):
    cats = [c for c in CAT_ORDER if c in data["rubric_by_category"]]
    solid_rates = [data["rubric_by_category"][c]["solid_rate"] * 100 for c in cats]

    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(cats, solid_rates, color="#3949ab")
    ax.set_ylabel("Solid rate across 6 dimensions (%)")
    ax.set_title("Grader Solid-rate by golden-set category (n=101, real LLM grading)")
    ax.set_ylim(0, 100)
    plt.xticks(rotation=30, ha="right")
    for bar, v in zip(bars, solid_rates):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 1.5, f"{v:.1f}%",
               ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(CHARTS / "solid_rate_by_category.png", dpi=150)
    plt.close(fig)


def chart_star_order_invariance(data):
    order = data["star_order_invariance"]
    cats = ["excellent", "star_explicit", "non_star"]
    labels = ["excellent\n(natural order)", "star_explicit\n(canonical S-T-A-R)",
             "non_star\n(same facts, reordered)"]
    struct_rates = [order[c]["structure_solid_rate"] * 100 for c in cats]
    probe_rates = [data["probe_by_category"][c]["triggered_rate"] * 100 for c in cats]

    x = range(len(cats))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar([i - width / 2 for i in x], struct_rates, width,
          label="LLM grader: Structure=Solid rate", color="#3949ab")
    ax.bar([i + width / 2 for i in x], probe_rates, width,
          label="Rule engine: probe-triggered rate", color="#c62828")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("%")
    ax.set_ylim(0, 105)
    ax.set_title("Same facts, different narrative order:\nLLM grader vs. rule-based probe engine")
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHARTS / "star_order_invariance.png", dpi=150)
    plt.close(fig)


def chart_fallback_distribution(data):
    dist = data["fallback_invocation_rate"]["provider_distribution"]
    labels = list(dist.keys())
    values = list(dist.values())
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.pie(values, labels=[f"{l}\n({v})" for l, v in zip(labels, values)],
          autopct="%1.1f%%", colors=["#3949ab", "#7986cb", "#c5cae9"][:len(labels)])
    ax.set_title(f"LLM provider distribution, this run (n={sum(values)} calls)")
    fig.tight_layout()
    fig.savefig(CHARTS / "provider_distribution.png", dpi=150)
    plt.close(fig)


def chart_latency(data):
    lat = data["grading_latency_s"]
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = ["mean", "median (p50)", "p95", "max"]
    values = [lat["mean"], lat["p50"], lat["p95"], lat["max"]]
    bars = ax.bar(labels, values, color="#00838f")
    ax.set_ylabel("seconds")
    ax.set_title(f"Grading-call latency, text-in/JSON-out (n={lat['n']} real LLM calls)")
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.15, f"{v:.2f}s", ha="center")
    fig.tight_layout()
    fig.savefig(CHARTS / "grading_latency.png", dpi=150)
    plt.close(fig)


def chart_voice_wer_cer(data):
    v = data["voice"]
    fig, ax = plt.subplots(figsize=(6, 5))
    labels = ["WER", "CER"]
    means = [v["wer_mean"] * 100, v["cer_mean"] * 100]
    medians = [v["wer_median"] * 100, v["cer_median"] * 100]
    maxes = [v["wer_max"] * 100, v["cer_max"] * 100]
    x = range(len(labels))
    width = 0.25
    ax.bar([i - width for i in x], means, width, label="mean", color="#00838f")
    ax.bar([i for i in x], medians, width, label="median", color="#4db6ac")
    ax.bar([i + width for i in x], maxes, width, label="max", color="#b2dfdb")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("%")
    ax.set_title(f"Voice round-trip WER/CER (Aura TTS -> nova-3 STT, n={v['n_success']})")
    ax.legend()
    fig.tight_layout()
    fig.savefig(CHARTS / "voice_wer_cer.png", dpi=150)
    plt.close(fig)


def chart_probe_trigger_rate(data):
    cats = [c for c in CAT_ORDER if c in data["probe_by_category"]]
    rates = [data["probe_by_category"][c]["triggered_rate"] * 100 for c in cats]
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(cats, rates, color="#6a1b9a")
    ax.set_ylabel("Probe-triggered rate (%)")
    ax.set_title("Rule-based probe engine trigger rate by category (n=101, no LLM)")
    ax.set_ylim(0, 105)
    plt.xticks(rotation=30, ha="right")
    for bar, v in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 1.5, f"{v:.0f}%", ha="center", fontsize=9)
    fig.tight_layout()
    fig.savefig(CHARTS / "probe_trigger_rate.png", dpi=150)
    plt.close(fig)


def main():
    data = json.loads(RESULTS.read_text())
    chart_rubric_by_category(data)
    chart_star_order_invariance(data)
    chart_fallback_distribution(data)
    chart_latency(data)
    chart_voice_wer_cer(data)
    chart_probe_trigger_rate(data)
    print(f"wrote 6 charts to {CHARTS}")


if __name__ == "__main__":
    main()
