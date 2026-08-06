"""Golden dataset for resume-metric evaluation (not part of the product spec's
numbered scope items). 50 hand-authored behavioral-interview answers spanning
excellent / average / weak / off-topic, built from parameterized templates so
each item is lexically distinct while the category's defining traits (concrete
detail, vague generic-claim phrases, we-heavy pronoun ratio, topical relevance)
are deliberately controlled and known at authoring time.

These are author-authored category labels, not independent human ratings.
Anything derived from them must be reported as such, never as "human-labeled
ground truth."
"""

from __future__ import annotations

from dataclasses import dataclass, field

WORDS_PER_SECOND = 2.5
QUESTION = "Tell me about a time you had to influence a decision you didn't control."


@dataclass
class GoldenItem:
    id: str
    category: str  # excellent | average | weak | off_topic
    question: str
    text: str
    word_count: int = 0
    duration_s: float = 0.0
    segments: list[tuple[int, str]] = field(default_factory=list)
    rendered_transcript: str = ""


def _finalize(item_id: str, category: str, text: str) -> GoldenItem:
    text = " ".join(text.split())
    sentences = [s.strip() for s in text.split(". ") if s.strip()]
    # group sentences into ~4 chunks to simulate STT speech-burst fragments
    n_chunks = max(1, min(4, len(sentences)))
    chunk_size = max(1, -(-len(sentences) // n_chunks))
    chunks = [sentences[i:i + chunk_size] for i in range(0, len(sentences), chunk_size)]

    segments: list[tuple[int, str]] = []
    words_so_far = 0
    rendered_lines: list[str] = []
    for chunk in chunks:
        chunk_text = ". ".join(chunk)
        if not chunk_text.endswith((".", "?", "!")):
            chunk_text += "."
        start_s = int(words_so_far / WORDS_PER_SECOND)
        segments.append((start_s, chunk_text))
        rendered_lines.append(f"[{start_s:6.1f}s] CANDIDATE: {chunk_text}")
        words_so_far += len(chunk_text.split())

    duration_s = round(words_so_far / WORDS_PER_SECOND, 1)
    return GoldenItem(
        id=item_id, category=category, question=QUESTION, text=text,
        word_count=words_so_far, duration_s=duration_s, segments=segments,
        rendered_transcript="\n".join(rendered_lines),
    )


# ---------------------------------------------------------------------------
# EXCELLENT: full arc, concrete nouns/numbers throughout, first-person
# ownership, no rubric generic-claim phrases. All 5 HSCARR markers present
# verbatim so the structure tracker sees a complete arc.
# ---------------------------------------------------------------------------

T_EXCELLENT = (
    "sure. the situation was I was the {role} on {product} at {company}, which "
    "had {scale} at the time. the problem was {problem}, and it had been "
    "getting worse for {duration_phrase}. before that i had already tried a "
    "couple of quick fixes myself, and neither one moved the number, so i "
    "knew this needed a real investigation, not another patch. so what i did "
    "was pull {evidence} and I found {finding}. i built a proposal and i went "
    "to {colleague}, our {colleague_role}, with {num_options} specific "
    "options. i also walked {colleague} through exactly how each option would "
    "land differently for our highest-value customers, since that was the "
    "group leadership cared about most. i decided to {decision}, and i wrote "
    "the rollout plan myself with {safeguard}. i checked in with {colleague} "
    "twice a week during the rollout so we could react fast if anything "
    "looked off. as a result, {metric_before} improved to {metric_after} "
    "within {outcome_timeframe}, and we verified it across {verify_scope}. "
    "what i learned is {learning}, and i have used that rule {reuse_count} "
    "times since."
)

EXCELLENT_PARAMS = [
    dict(role="PM", product="checkout", company="a grocery delivery app",
         scale="2.1 million weekly orders", problem="cart abandonment had sat at 31 percent for 3 straight quarters",
         duration_phrase="9 months", evidence="14 session recordings",
         finding="mobile users hit a 9-field address form right before payment",
         colleague="Priya", colleague_role="design lead", num_options="3",
         decision="ship a single-page flow behind a feature flag to 5 percent of users",
         safeguard="2 rollback triggers at 15-minute intervals",
         metric_before="abandonment", metric_after="22 percent",
         outcome_timeframe="6 weeks", verify_scope="2 regions",
         learning="to size the fix to the evidence I actually had",
         reuse_count="3"),
    dict(role="PM", product="the notifications platform", company="a fintech app",
         scale="800 thousand daily actives", problem="the unsubscribe rate had crept from 1.2 to 1.9 percent that quarter",
         duration_phrase="one full quarter", evidence="6 weeks of cohort data",
         finding="users getting more than 5 pushes a week churned off notifications at 3 times the baseline",
         colleague="Marcus", colleague_role="growth lead", num_options="2",
         decision="cap frequency at 2 sends per user with a holdout on a third slot",
         safeguard="a weekly unsubscribe-rate tripwire",
         metric_before="unsubscribes", metric_after="1.3 percent",
         outcome_timeframe="8 weeks", verify_scope="both platforms",
         learning="that data beats opinions in a room",
         reuse_count="4"),
    dict(role="consultant", product="the claims workflow", company="a regional health insurer",
         scale="40 thousand claims a month", problem="claim denials were running 19 percent above the industry benchmark",
         duration_phrase="2 quarters", evidence="120 denied claim files",
         finding="60 percent of denials traced back to 4 missing fields at intake",
         colleague="Dana", colleague_role="operations director", num_options="3",
         decision="redesign the intake form and add a 4-field validation step",
         safeguard="a weekly denial-rate dashboard reviewed with the intake team",
         metric_before="denials", metric_after="11 percent",
         outcome_timeframe="10 weeks", verify_scope="3 regional offices",
         learning="that small structural fixes beat big process rewrites",
         reuse_count="2"),
    dict(role="PM", product="search", company="a marketplace app",
         scale="500 thousand monthly searches", problem="click-through rate had dropped 12 percent after a ranking change",
         duration_phrase="2 weeks", evidence="200 top queries before and after the change",
         finding="the drop concentrated almost entirely in long-tail queries",
         colleague="Alex", colleague_role="search engineer", num_options="2",
         decision="roll back ranking for long-tail queries only, keep it for head queries",
         safeguard="a daily CTR alert split by query length",
         metric_before="click-through rate", metric_after="its prior baseline",
         outcome_timeframe="9 days", verify_scope="all query segments",
         learning="to segment a metric before trusting the aggregate number",
         reuse_count="5"),
    dict(role="PM", product="the onboarding flow", company="a B2B logistics company",
         scale="1,200 new accounts a month", problem="only 40 percent of new accounts finished setup in the first week",
         duration_phrase="6 months", evidence="35 recorded onboarding calls",
         finding="accounts stalled almost every time at the carrier-integration step",
         colleague="Wen", colleague_role="engineering manager", num_options="3",
         decision="ship a guided setup wizard for the carrier-integration step first",
         safeguard="a rollback plan if completion dropped for any cohort",
         metric_before="week-one completion", metric_after="71 percent",
         outcome_timeframe="5 weeks", verify_scope="every account tier",
         learning="to fix the single worst step before touching anything else",
         reuse_count="3"),
    dict(role="PM", product="billing", company="an enterprise SaaS company",
         scale="14 thousand paying accounts", problem="failed payment retries were causing 8 percent involuntary churn a quarter",
         duration_phrase="3 quarters", evidence="every failed-charge log for a full quarter",
         finding="72 percent of failures were expired cards, not insufficient funds",
         colleague="Sofia", colleague_role="finance lead", num_options="2",
         decision="add card-expiration email nudges 14 days before the charge date",
         safeguard="an opt-out for accounts on manual invoicing",
         metric_before="involuntary churn", metric_after="3 percent",
         outcome_timeframe="one quarter", verify_scope="both billing tiers",
         learning="that the boring root cause is usually the real one",
         reuse_count="2"),
    dict(role="consultant", product="the hiring pipeline", company="a mid-size logistics firm",
         scale="300 open roles a year", problem="time-to-fill had grown to 61 days, well past the 40-day target",
         duration_phrase="4 months", evidence="hiring-manager interviews across 12 teams",
         finding="most of the delay sat in a single unscheduled feedback step",
         colleague="Tom", colleague_role="head of talent", num_options="3",
         decision="add a 48-hour feedback SLA enforced by the applicant tracking system",
         safeguard="a weekly overdue-feedback report to hiring managers",
         metric_before="time-to-fill", metric_after="38 days",
         outcome_timeframe="2 hiring cycles", verify_scope="all 12 teams",
         learning="that one enforced SLA beats ten polite reminders",
         reuse_count="3"),
    dict(role="PM", product="the mobile app", company="a home services marketplace",
         scale="90 thousand monthly active users", problem="app store rating had fallen to 3.1 stars after a redesign",
         duration_phrase="5 weeks", evidence="400 one- and two-star reviews",
         finding="80 percent of complaints named a single missing filter option",
         colleague="Grace", colleague_role="mobile lead", num_options="2",
         decision="ship the filter back in a patch release ahead of the next milestone",
         safeguard="a review-sentiment check before and after the patch",
         metric_before="the app rating", metric_after="4.2 stars",
         outcome_timeframe="3 weeks", verify_scope="iOS and Android",
         learning="to read the actual complaints before proposing a fix",
         reuse_count="4"),
    dict(role="PM", product="fraud review", company="a consumer banking app",
         scale="25 thousand flagged transactions a month", problem="manual review queues were running 3 days behind, delaying legitimate transfers",
         duration_phrase="6 weeks", evidence="a sample of 500 queued reviews",
         finding="65 percent of the backlog was low-risk transactions under a fixed dollar threshold",
         colleague="Elena", colleague_role="risk lead", num_options="2",
         decision="auto-clear low-risk transactions under that threshold with a daily audit sample",
         safeguard="a fraud-rate ceiling that would auto-revert the rule",
         metric_before="review backlog", metric_after="same-day",
         outcome_timeframe="4 weeks", verify_scope="every region",
         learning="that not every review needs a human in the loop",
         reuse_count="2"),
    dict(role="PM", product="the support ticket system", company="an edtech platform",
         scale="8 thousand tickets a month", problem="average resolution time had climbed to 30 hours",
         duration_phrase="one semester", evidence="ticket logs for 3 months",
         finding="a single ticket category, password resets, made up 22 percent of volume",
         colleague="Ben", colleague_role="support lead", num_options="2",
         decision="build a self-serve reset flow and route the rest to a faster queue",
         safeguard="a weekly resolution-time review with support leads",
         metric_before="resolution time", metric_after="11 hours",
         outcome_timeframe="6 weeks", verify_scope="every ticket category",
         learning="that removing one category can move the whole average",
         reuse_count="3"),
    dict(role="PM", product="the integrations catalog", company="a cybersecurity vendor",
         scale="60 partner integrations", problem="only 15 percent of customers had activated any integration",
         duration_phrase="2 quarters", evidence="usage logs across every account tier",
         finding="the setup flow required 7 manual steps most admins abandoned",
         colleague="Noor", colleague_role="partnerships lead", num_options="3",
         decision="cut the setup flow to 2 steps for the 5 most-used integrations",
         safeguard="an activation-rate check before extending it further",
         metric_before="activation", metric_after="41 percent",
         outcome_timeframe="7 weeks", verify_scope="every account tier",
         learning="to fix the top 5 before trying to fix all 60",
         reuse_count="2"),
    dict(role="PM", product="video quality", company="a media streaming service",
         scale="3 million daily streams", problem="buffering complaints had doubled after a CDN migration",
         duration_phrase="3 weeks", evidence="playback logs from 50 thousand sessions",
         finding="the buffering concentrated on one CDN region serving 18 percent of traffic",
         colleague="Diego", colleague_role="infrastructure lead", num_options="2",
         decision="route that region's traffic back to the prior CDN while the new one was tuned",
         safeguard="a buffering-rate alert per region",
         metric_before="buffering complaints", metric_after="pre-migration levels",
         outcome_timeframe="5 days", verify_scope="every region",
         learning="that a migration should roll out region by region, not all at once",
         reuse_count="2"),
    dict(role="PM", product="the booking flow", company="a travel booking site",
         scale="200 thousand monthly bookings", problem="mobile conversion was 40 percent below desktop",
         duration_phrase="one quarter", evidence="60 recorded mobile sessions",
         finding="the date picker required 6 taps most users gave up on",
         colleague="Layla", colleague_role="product designer", num_options="2",
         decision="replace the date picker with a single-screen calendar and ship it to half of mobile traffic",
         safeguard="a conversion-rate check against the control group",
         metric_before="mobile conversion", metric_after="within 8 points of desktop",
         outcome_timeframe="4 weeks", verify_scope="iOS and Android",
         learning="that the smallest UI element can gate the whole funnel",
         reuse_count="3"),
]

# ---------------------------------------------------------------------------
# WEAK: rubric generic-claim phrases verbatim (config/rubric.yaml auto-rule
# list), no numbers, heavy "we", thin/no reflection, short.
# ---------------------------------------------------------------------------

T_WEAK = (
    "so basically there was a project around {topic} and it needed a lot of "
    "work honestly. what we did was we aligned stakeholders and drove "
    "consensus across the teams involved, and we worked closely with everyone "
    "to keep things moving along. we communicated effectively so nothing fell "
    "through the cracks, and we collaborated cross-functionally the whole "
    "time on it. we took ownership of the overall outcome together and just "
    "kept pushing until it came together in the end. it was a good "
    "experience overall for the team."
)

WEAK_TOPICS = [
    "the quarterly planning process", "the vendor onboarding process",
    "the annual budget cycle", "the platform migration effort",
    "the hiring loop redesign", "the customer escalation process",
    "the internal tools rollout", "the compliance review process",
    "the offsite planning effort", "the reorg communication plan",
    "the vendor contract renewal", "the support ticket backlog",
]

# ---------------------------------------------------------------------------
# AVERAGE: partial arc, one generic phrase, mixed I/we, a mix of concrete and
# hand-waved numbers, generic reflection. Deliberately NOT engineered to force
# a specific probe outcome per item -- the trigger rate is measured, not set.
# ---------------------------------------------------------------------------

T_AVERAGE = (
    "at the time i was working on {product} at {company}. the situation was "
    "{situation}, and the problem was {problem}. it had been sitting there "
    "for a while before anyone really owned it, so a few of us on the team "
    "started poking at it in our spare time between other projects. what i "
    "did was i aligned stakeholders on a plan, and then {action_detail}. it "
    "took a couple of tries to get buy-in from everyone since not everyone "
    "agreed on the approach at first, but we eventually got there. we tested "
    "it with {test_group} and {result_desc}. there was some back and forth "
    "about whether to roll it out further, but the general feeling was "
    "positive. as a result, {outcome}, and the team felt good about where "
    "things landed. i think the big thing i took away is that communication "
    "matters a lot in situations like this."
)

AVERAGE_PARAMS = [
    dict(product="the referral program", company="a consumer app",
         situation="referral signups had been flat for a while",
         problem="nobody on the team owned the program full time",
         action_detail="Sam and I redesigned the invite email",
         test_group="a small group of users", result_desc="the lift was noticeable, though I don't remember the exact number offhand",
         outcome="referral signups picked back up"),
    dict(product="the pricing page", company="a SaaS startup",
         situation="trial-to-paid conversion had been under target for a couple months",
         problem="the pricing tiers were confusing based on support tickets",
         action_detail="we simplified it down to 3 tiers with clearer names",
         test_group="new signups over a few weeks", result_desc="conversion went up a decent amount",
         outcome="conversion improved"),
    dict(product="the internal wiki", company="an enterprise software company",
         situation="new hires kept asking the same onboarding questions",
         problem="documentation was scattered across a few different tools",
         action_detail="I consolidated the most-asked topics into one space",
         test_group="the next onboarding cohort", result_desc="fewer repeat questions came up, roughly",
         outcome="onboarding felt smoother"),
    dict(product="the checkout flow", company="a fashion retailer's app",
         situation="cart abandonment had crept up over the holidays",
         problem="shipping costs weren't shown until the last step",
         action_detail="we moved the shipping estimate earlier in the flow",
         test_group="half of holiday traffic", result_desc="abandonment dropped some amount, hard to say exactly how much",
         outcome="the checkout felt less surprising to customers"),
    dict(product="the sales handoff process", company="a B2B software vendor",
         situation="deals were getting lost between sales and onboarding",
         problem="there wasn't a clear owner during the handoff window",
         action_detail="I set up a shared checklist between the two teams",
         test_group="deals closing that quarter", result_desc="fewer deals seemed to slip through, at least anecdotally",
         outcome="the handoff felt tighter"),
    dict(product="the feature request board", company="a project-management tool",
         situation="customers felt like their feedback disappeared into a void",
         problem="requests weren't triaged on any regular cadence",
         action_detail="Priya and I set a biweekly triage meeting",
         test_group="the top requesters", result_desc="a few customers mentioned it felt more responsive",
         outcome="the board felt more alive"),
    dict(product="the mobile notifications", company="a fitness app",
         situation="opt-out rates for push notifications were climbing",
         problem="users were getting the same reminder multiple times a day",
         action_detail="we capped reminders to once per day per category",
         test_group="a rollout group", result_desc="opt-outs came down a fair bit",
         outcome="engagement held steady instead of dropping further"),
    dict(product="the returns process", company="an online furniture retailer",
         situation="customer complaints about returns had been rising",
         problem="the return label process took several manual steps",
         action_detail="I worked with support to cut it down to one form",
         test_group="returns over the following month", result_desc="the process felt faster, based on the feedback we got",
         outcome="complaint volume eased off"),
    dict(product="the internal reporting dashboard", company="a logistics startup",
         situation="leadership kept asking for numbers that took days to pull",
         problem="data lived across a few disconnected spreadsheets",
         action_detail="we built one shared dashboard pulling from the main systems",
         test_group="the ops leadership team", result_desc="people said it saved them real time",
         outcome="reporting requests slowed down a lot"),
    dict(product="the API documentation", company="a developer tools company",
         situation="support tickets about integration errors kept coming in",
         problem="the docs hadn't been updated since the last API version",
         action_detail="Marcus and I rewrote the getting-started section",
         test_group="developers integrating that month", result_desc="ticket volume for that category dropped noticeably",
         outcome="the integration felt less painful for new developers"),
    dict(product="the employee survey process", company="a mid-size tech company",
         situation="survey response rates had been declining every cycle",
         problem="the survey had grown to over 40 questions",
         action_detail="I cut it down to the 12 questions leadership actually acted on",
         test_group="the next survey cycle", result_desc="response rates went up by a good margin",
         outcome="the survey felt worth people's time again"),
    dict(product="the vendor evaluation process", company="a healthcare scheduling platform",
         situation="vendor selection was taking months longer than planned",
         problem="every stakeholder had a different unwritten priority list",
         action_detail="we ran one structured scoring session with all stakeholders",
         test_group="the current vendor shortlist", result_desc="the decision came together noticeably faster",
         outcome="the team picked a vendor everyone could stand behind"),
    dict(product="the release notes process", company="a fintech app",
         situation="customers kept getting surprised by changes after release",
         problem="release notes were written after launch, not before",
         action_detail="I moved the writing step to a week before each release",
         test_group="the next few releases", result_desc="fewer surprised-customer tickets came in",
         outcome="releases felt less disruptive"),
]

# ---------------------------------------------------------------------------
# OFF_TOPIC: does not engage with the interview question at all. No STAR
# structure, no generic-claim phrases, short. No detector in the codebase
# targets topical relevance -- this category exists to test that gap.
# ---------------------------------------------------------------------------

OFF_TOPIC_TEXTS = [
    "honestly this weekend i mostly just relaxed, watched a couple episodes "
    "of a show my roommate recommended, and tried a new pasta recipe that "
    "didn't really turn out that well. traffic on the way here was pretty "
    "bad too, there was construction on the highway the whole way.",

    "oh, funny you ask, i was actually just thinking about this recipe i "
    "tried last night, a lemon chicken thing, it needed a lot more salt than "
    "the recipe said. i think i'll try it again this weekend with some "
    "changes.",

    "my commute has been rough lately, the train's been delayed almost every "
    "morning this month. i've started leaving twenty minutes earlier just to "
    "be safe, which honestly cuts into my morning routine a bit.",

    "we just got back from a trip to the coast, the weather was really "
    "nice the whole time. we mostly just walked around and tried a few "
    "restaurants, nothing too eventful but it was relaxing.",

    "my dog has been having some trouble with the stairs lately, so we've "
    "been carrying him up and down, which is a whole thing in the morning. "
    "the vet says it's probably just his age catching up with him.",

    "i watched the game last night, it went into overtime, pretty "
    "exciting finish honestly. i was up way later than i meant to be, so "
    "i'm running a bit low on sleep today.",

    "i've been reading this book my coworker lent me, it's a mystery novel, "
    "pretty good so far though the pacing is a little slow in the middle. "
    "i'm hoping to finish it by the end of the week.",

    "there's a new coffee place that opened up near my apartment, the "
    "espresso is honestly pretty good, though it's a little pricier than "
    "where i usually go. i've been there a few times already this month.",

    "i just upgraded my phone last week, still getting used to the new "
    "camera settings honestly. the battery life seems better so far, which "
    "is nice since my old one barely made it through the day.",

    "i've been trying to get back into a gym routine, going a few mornings "
    "a week before work. it's been tough to keep up with honestly, mostly "
    "just trying to build the habit back up.",

    "the weather's been so unpredictable lately, sunny one day and pouring "
    "the next. i keep forgetting to check before i leave the house, so i've "
    "gotten caught without an umbrella more than once.",

    "i tried a new grocery delivery service this week, the app was a little "
    "confusing to use at first but the delivery itself showed up on time. "
    "not sure if i'll stick with it long term though.",
]


def build_golden_set() -> list[GoldenItem]:
    items: list[GoldenItem] = []

    for i, p in enumerate(EXCELLENT_PARAMS, start=1):
        items.append(_finalize(f"excellent_{i:02d}", "excellent", T_EXCELLENT.format(**p)))

    for i, topic in enumerate(WEAK_TOPICS, start=1):
        items.append(_finalize(f"weak_{i:02d}", "weak", T_WEAK.format(topic=topic)))

    for i, p in enumerate(AVERAGE_PARAMS, start=1):
        items.append(_finalize(f"average_{i:02d}", "average", T_AVERAGE.format(**p)))

    for i, text in enumerate(OFF_TOPIC_TEXTS, start=1):
        items.append(_finalize(f"off_topic_{i:02d}", "off_topic", text))

    return items


if __name__ == "__main__":
    items = build_golden_set()
    by_cat: dict[str, int] = {}
    for it in items:
        by_cat[it.category] = by_cat.get(it.category, 0) + 1
    print(f"total items: {len(items)}")
    for cat, n in by_cat.items():
        print(f"  {cat}: {n}")
    print("\nsample (excellent_01):")
    print(items[0].rendered_transcript)
    print(f"duration_s={items[0].duration_s} word_count={items[0].word_count}")
