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
    labels = ["mean", "median (p50)", "p95", "p99", "max"]
    values = [lat["mean"], lat["p50"], lat["p95"], lat["p99"], lat["max"]]
    bars = ax.bar(labels, values, color="#00838f")
    ax.set_ylabel("seconds")
    ax.set_title(f"Grading-call latency, text-in/JSON-out (n={lat['n']} real LLM calls)")
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.15, f"{v:.2f}s", ha="center")
    fig.tight_layout()
    fig.savefig(CHARTS / "grading_latency.png", dpi=150)
    plt.close(fig)


def chart_accuracy_vs_latency_by_provider(data):
    block = data.get("accuracy_vs_latency_by_provider")
    if not block or not block.get("by_provider"):
        return
    by_prov = block["by_provider"]
    by_prov_cat = block["by_provider_and_category"]
    comparable = block["categories_covered_by_every_provider"]
    providers = sorted(by_prov.keys(), key=lambda p: by_prov[p]["latency_s_p50"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: latency by provider (not confounded by category mix).
    x = range(len(providers))
    width = 0.25
    p50s = [by_prov[p]["latency_s_p50"] for p in providers]
    p95s = [by_prov[p]["latency_s_p95"] for p in providers]
    p99s = [by_prov[p]["latency_s_p99"] for p in providers]
    ax1.bar([i - width for i in x], p50s, width, label="p50", color="#00838f")
    ax1.bar([i for i in x], p95s, width, label="p95", color="#4db6ac")
    ax1.bar([i + width for i in x], p99s, width, label="p99", color="#b2dfdb")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels([f"{p}\n(n={by_prov[p]['n']})" for p in providers])
    ax1.set_ylabel("seconds")
    ax1.set_title("Latency by provider (all calls)")
    ax1.legend()

    # Right: solid_rate, but ONLY on categories every provider actually
    # covered -- the raw all-category solid_rate is confounded whenever
    # providers didn't see the same category mix (see note in
    # metrics_summary.json). If nothing is comparable, say so instead of
    # plotting a misleading number.
    if comparable:
        cat = comparable[0]  # this run: only "excellent" overlaps
        rates = [by_prov_cat[p][cat]["solid_rate"] * 100 for p in providers]
        ns = [by_prov_cat[p][cat]["n"] for p in providers]
        bars = ax2.bar(providers, rates, color="#3949ab")
        ax2.set_ylim(0, 122)
        ax2.set_yticks(range(0, 101, 20))
        ax2.set_ylabel("Solid rate (%)")
        ax2.set_title(f'Accuracy by provider\n(category-controlled: "{cat}" only)')
        for bar, v, n in zip(bars, rates, ns):
            ax2.text(bar.get_x() + bar.get_width() / 2, v + 4,
                     f"{v:.1f}%\n(n={n})", ha="center", fontsize=9)
    else:
        ax2.text(0.5, 0.5, "No category was covered\nby every provider this run",
                 ha="center", va="center", transform=ax2.transAxes)
        ax2.set_title("Accuracy by provider (not comparable this run)")
        ax2.axis("off")

    fig.suptitle("LLM accuracy vs latency, by provider "
                 "(real free-tier routing determines who gets which calls)")
    fig.tight_layout()
    fig.savefig(CHARTS / "accuracy_vs_latency_by_provider.png", dpi=150)
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
    chart_accuracy_vs_latency_by_provider(data)
    print(f"wrote 7 charts to {CHARTS}")


if __name__ == "__main__":
    main()
