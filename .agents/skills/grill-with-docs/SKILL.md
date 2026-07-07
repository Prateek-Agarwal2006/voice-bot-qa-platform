---
name: grill-with-docs
description: A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go. Always shows a Grill Board; ends with an implementation plan before any code.
disable-model-invocation: true
---

Run a `/grilling` session using the `/domain-modeling` skill.

## Workflow (strict order)

1. **Grill** — one question at a time (see `/grilling` skill).
2. **Grill Board** — show on every turn (see below).
3. **Docs** — update `CONTEXT.md` / offer ADRs as terms and decisions lock (domain-modeling skill).
4. **Implementation plan** — when grilling is complete, produce a structured plan (Plan-mode style). **Do not implement code yet.**
5. **Implement** — only after the user explicitly says to implement (e.g. "go ahead", "implement the plan").

Never skip the Grill Board. Never start coding at the end of a grill session unless the user explicitly asks.

---

## Grill Board (required every response)

Start each grilling response with a **Grill Board** table. Update it as decisions lock (`✓`) or stay open (`?`).

```markdown
### Grill board

| # | Topic | Status | Decision |
|---|--------|--------|----------|
| 1 | … | ✓ or ? | One-line decision or "open" |
| 2 | … | ? | … |
```

Rules:

- Add a new row when a new topic appears.
- Mark `✓` only when the user confirms (or clearly agrees with your recommendation).
- Keep a short **Still open** list under the table if helpful.
- After the board, ask **one** question (with your recommended answer) unless the session is complete.

When the board has no `?` rows (or the user says "done grilling"), stop asking questions and move to **Implementation plan**.

---

## Implementation plan (required before code)

When grilling is complete, output a plan with:

```markdown
## Implementation plan

### Goal
One sentence.

### Locked decisions
Bullets from the Grill Board (✓ rows only).

### Out of scope
What we are not doing in this pass.

### Steps
Numbered, ordered, concrete (files/modules touched).

### Open questions for stakeholder
Anything still blocked on sir/Sprinklr/etc.

### Test plan
How we will verify.

---
**Ready to implement when you say so** — no code until then.
```

Use Plan-mode quality: specific files, migrations, env vars, API shape — but **no edits** until the user approves implementation.

---

## Domain docs

Follow `/domain-modeling`:

- Update `CONTEXT.md` when glossary terms change (no implementation detail in CONTEXT).
- Offer ADRs only when hard to reverse, surprising, and trade-off driven.

---

## Cross-reference codebase

If a question is answerable from the repo, read the code instead of asking the user.
