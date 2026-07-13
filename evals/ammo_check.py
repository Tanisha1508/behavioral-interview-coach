"""Missed-ammo accuracy eval (spec Section 6). Seeded test: a doc with 10
known facts, a scripted answer using 6. Pass: the report flags exactly the
4 absent facts, every flagged fact string-matches the doc, zero
hallucinated items.
"""

from __future__ import annotations

from src.grading.ammo import Doc, missed_ammo

# 10 known facts as distinctive verbatim spans.
FACTS = {
    1: "cut cart abandonment from 31% to 22%",
    2: "2.1M monthly users",
    3: "used by 4,800 pickers",
    4: "cut mispicks 38%",
    5: "reallocated 6 engineers",
    6: "integrating 14 payer APIs",
    7: "reduced claim denials 19%",
    8: "zero appointment loss across 900 clinics",
    9: "6-week standoff",
    10: "negative LTV impact",
}
USED = {1, 2, 5, 6, 9, 10}
ABSENT = set(FACTS) - USED

DOC = Doc(name="stories", text=f"""MY FACT SHEET

At FreshCart I led the checkout redesign that {FACTS[1]} for {FACTS[2]}.
I shipped the dark-store picking app {FACTS[3]} which {FACTS[4]}.
I killed the loyalty program after tests showed {FACTS[10]} and {FACTS[5]}.
At TeleWell I launched the eligibility checker {FACTS[6]} which {FACTS[7]}.
I ran the scheduling migration with {FACTS[8]}.
I resolved a {FACTS[9]} between clinical ops and engineering.
""")

# Scripted answer that uses exactly the 6 USED facts.
ANSWER = """
[  0.0s] CANDIDATE: my biggest wins came at FreshCart and TeleWell. i led the
checkout redesign that cut cart abandonment from 31% to 22%, and that was
across 2.1M monthly users, so the volume made it matter.
[ 30.0s] CANDIDATE: i also made the call to kill our loyalty program when the
tests showed negative LTV impact, and i reallocated 6 engineers to
fulfillment where they shipped real value.
[ 60.0s] CANDIDATE: at TeleWell i launched an eligibility checker integrating
14 payer APIs, and separately i resolved a 6-week standoff between clinical
ops and engineering that had blocked our triage bot.
"""

QUESTION = "Walk me through your biggest product wins and what made them work."


def run() -> dict:
    items = missed_ammo(ANSWER, [DOC], QUESTION)
    flagged = [i.fact for i in items]

    doc_norm = " ".join(DOC.text.split()).lower()
    all_verbatim = all(" ".join(f.split()).lower() in doc_norm for f in flagged)

    hits = set()
    extras = []
    for fact in flagged:
        fact_norm = " ".join(fact.split()).lower()
        matched = [k for k in ABSENT
                   if FACTS[k].lower() in fact_norm or fact_norm in
                   (" ".join(FACTS[k].split()).lower())]
        # A flagged span counts as one of the 4 if it contains that fact.
        broad = [k for k in ABSENT if FACTS[k].lower() in fact_norm]
        if broad:
            hits.update(broad)
        elif not matched:
            extras.append(fact)

    # A USED fact flagged as missed is a false positive.
    false_used = [f for f in extras
                  if any(FACTS[k].lower() in " ".join(f.split()).lower()
                         for k in USED)]

    passed = (hits == ABSENT and not false_used and all_verbatim
              and len(extras) == len(false_used))
    return {"flagged": flagged, "hits": sorted(hits),
            "expected": sorted(ABSENT), "extras": extras,
            "all_verbatim": all_verbatim, "passed": passed}


if __name__ == "__main__":
    result = run()
    print("expected absent facts:", result["expected"])
    print("correctly flagged:    ", result["hits"])
    print("flagged spans:")
    for f in result["flagged"]:
        print(f"  - {f!r}")
    if result["extras"]:
        print("unexpected extras:", result["extras"])
    print("all flagged spans verbatim in doc:", result["all_verbatim"])
    print("PASS" if result["passed"] else "FAIL")
