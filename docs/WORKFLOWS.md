# User workflows

Every path a user can take through the product as of 2026-07-12. The web app is the primary surface; the console paths remain for development and offline use.

## The full map

```mermaid
flowchart TD
    A[Open the app] --> B{Choose mode}

    B -->|Practice interview| C[Interview setup]
    B -->|Coach session| D[Coach setup]

    C --> C1[Round: PM / Consulting / MBA / Tech / Others]
    C1 --> C2{Interview mode}
    C2 -->|Listen| C3[Full answer, then feedback]
    C2 -->|Probing| C4[Up to 2 follow-ups after answer, then feedback]
    C3 --> C5{Question source}
    C4 --> C5
    C5 -->|Question bank| C6[Pick 1 to 6 curated questions]
    C5 -->|My resume: pack| C7[Questions generated from resume, resume required]
    C5 -->|My own questions| C8[Type questions, one per line]
    C5 -->|Pasted intel| C9[Paste questions the company asks]
    C6 --> C10[Optional documents: resume, JD, stories, interviewer bio]
    C7 --> C10
    C8 --> C10
    C9 --> C10
    C10 --> E[Start interview]

    E --> E1[Interviewer greets and asks question<br/>question pinned on screen]
    E1 --> E2[Speak your answer<br/>pause freely, it waits<br/>say repeat the question to hear it again]
    E2 --> E3[Say: that's my answer]
    E3 --> E4{Probing mode?}
    E4 -->|Yes, budget left| E5[Follow-up question<br/>answer it, say done again]
    E5 --> E4
    E4 -->|No| E6[Scoring: 6 dimensions + missed ammo]
    E6 --> E7[Score card on screen + spoken feedback]
    E7 --> E8{Say a verdict}
    E8 -->|retry| E1
    E8 -->|next| E9{Questions left?}
    E9 -->|Yes| E1
    E9 -->|No| F[Session ends]
    E8 -->|end| F

    D --> D1[Documents: resume required,<br/>JD recommended, stories optional]
    D1 --> G[Start coaching]
    G --> G1[Coach reads materials<br/>pack + coverage map appear on screen]
    G1 --> G2{Work the panel or talk}
    G2 -->|Click a question| G3[Expands: resume line, covering story, coverage strength]
    G3 --> G4[Get game plan: coach speaks it,<br/>plan saved into the panel]
    G3 --> G5[Practice this in Drill:<br/>restarts as a 1-question graded rep,<br/>documents carried over]
    G5 --> E1
    G2 -->|Ask by voice| G6[Which story fits? How do I open?<br/>Where am I thin?]
    G6 --> G2
    G4 --> G2
    G2 -->|Say: end session| F
```

## Interview workflows in words

**1. Quick rep, zero setup.** Practice interview, defaults untouched (PM, listen, 2 bank questions), no documents. Fastest path to speaking practice. Feedback still scores all 6 dimensions; missed ammo stays empty without documents.

**2. The full-feedback rep.** Same as above plus resume, JD, and stories uploaded (.pdf, .md, .txt, or paste). The score card gains the missed ammo section: verbatim facts from your documents your answer left out. The live interviewer never sees your documents; only the grader does.

**3. Resume-tailored session (pack).** Question source: my resume. Questions are generated from your actual resume lines against the JD. Every question is verifiably grounded: a question is dropped unless its resume line appears verbatim in your resume.

**4. Known-questions session.** Source: my own questions (paste a list) or pasted intel (paste a forum thread or recruiter notes; questions get extracted). For rehearsing a specific loop.

**5. Probing rep.** Interview mode: probing. After you finish, the interviewer asks up to 2 follow-ups picked by the analyzers (ownership, quantification, depth, specificity, emotional per round), each answered at your own pace. Then one combined scoring pass. Length is graded on the main answer only.

**6. Persona rep.** Paste an interviewer bio (their LinkedIn About text). Firm type and seniority are extracted, with every tag citing a verbatim bio phrase, and they shape probe mix, intensity, pacing, and the interviewer voice. Combine with any of the above.

**7. The retry loop.** After any score card: say "retry" to re-answer the same question immediately, "next" to move on, "end" to stop. Hearing "I versus We was a Gap" and re-answering right away is the fastest learning loop in the product.

**7b. The rewrite.** On any score card, press "Show me the rewrite". The coach produces dimension-tagged notes (your words, then the fix) plus a full rewritten answer built from your transcript and documents, on screen; the biggest fix is spoken. Read it, say "retry", and deliver the better version while it is fresh.

## Coach workflows in words

**8. Prep-map session.** Coach mode with resume + JD. The pack (8 to 12 likely questions, each tied to a resume line) and the coverage map (STRONG / PARTIAL / GAP per question, needs a stories doc) render in the side panel. The coach speaks a standing summary: how many questions, how many gaps.

**9. Game-plan drilling.** Click any question in the panel, press Get game plan. The coach speaks the plan (which story, the opening line, the one number to include) and writes it into the panel. Work through the pack question by question; by session end the panel is a filled-in prep sheet.

**10. Free voice consult.** Just talk: "which story fits the conflict question", "how should I open question three", "where am I thin against this JD". Answers come from your documents; the coach says so when your documents cannot answer. The coach never quizzes you.

**11. Gap-to-rep loop (the product in one motion).** Coverage map shows a GAP, click the question, get the game plan, press Practice this in Drill. The session restarts as a one-question graded rep with your documents carried over. Score card shows whether the plan landed. Retry until it does.

## Console workflows (development and offline)

**12. Console drill.** `python -m src.session.setup` (interactive wizard, stages config) then `python -m src.agent console`. Same engine, terminal audio.

**13. Coach CLI.** `python -m src.coach.cli --resume path --jd path [--stories path]`. Prints pack and coverage map. With `--answer path --question "text"` it produces rewrite notes for a written answer; the web equivalent is the score card's rewrite button (workflow 7b).

## Session rules that hold everywhere

- The interviewer never interrupts you and no timer ends your answer. Only "that's my answer" (or "I'm done", "that's it"), a structurally complete answer, or dodging a probe twice moves the session forward.
- "Repeat the question" (or "say that again") re-asks without touching your answer or the clock.
- All interviewer and coach speech also appears as text on screen.
- Documents never reach the live interviewer. Grader and coach only.
- Free-tier models: when Gemini quota is exhausted, replies fail over to Groq, which is noticeably weaker in the coach conversation.

## Not built yet

- **Simulation**: the timed 15 to 60 minute full mock with question pacing, no per-question feedback, and one end-of-session debrief. Config plumbing exists; the session loop does not.
- **Hosting**: everything above currently runs locally (scope items 12 to 14).
