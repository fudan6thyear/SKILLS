# Quality Gates

A gate is a checkpoint where work either advances or goes back. Gates exist because the cost of a
defect grows roughly an order of magnitude per phase — a wrong interface caught at design is a
sentence, caught after three modules are built it's a rewrite.

Run the gate **before** updating state. If a gate fails, the card does not move.

---

## Gate 1 — Plan gate (before any card is dispatched)

- [ ] Requirement restated in `REQUIREMENTS.md` in one paragraph, in the user's own terms
- [ ] Explicit **out-of-scope** list (this is the section that prevents scope creep later)
- [ ] Open questions either answered by the user or logged as assumptions with a name
- [ ] Decomposition covers the requirement — walk each requirement line to a card number
- [ ] No card's 验收标准 contains an unfalsifiable phrase ("quality", "reasonable", "performant")
- [ ] Card dependency graph is acyclic

**Fails when:** you can't say which card delivers a given requirement line, or two cards claim the
same requirement.

## Gate 2 — Design gate (before implementation cards dispatch)

- [ ] `docs/architecture/API_CONTRACTS.md` exists and covers every interface implementation cards
      must implement
- [ ] Contracts specify return types **and** error modes (throw vs. return-union — pick one, state it)
- [ ] `docs/architecture/SYSTEM_DESIGN.md` names the module boundaries that map to card file bounds
- [ ] Risks listed with mitigations (not just "risk: it might be hard")
- [ ] No implementation card has been dispatched yet

**Fails when:** an implementer would have to invent an interface name, a return shape, or an error
convention. Any of those means the design isn't done.

## Gate 3 — Card completion gate (on every report)

Reject the report and keep the card in `active/` if any box is unchecked. Partial credit is fine —
the card moves only when all of them hold.

- [ ] Status is explicitly ✅/⚠️/❌
- [ ] Branch + commit SHA given
- [ ] File list matches the card's 允许修改 / 允许新建 (extras are a boundary violation, not a bonus)
- [ ] **Every** acceptance criterion has a checked result with actual output, not a claim
- [ ] Deviations from the card are stated, including ones that were improvements
- [ ] Contract changes listed, or "无" stated explicitly
- [ ] Blockers and tech debt surfaced

**Fails when:** the report says "完成 ✅" and the acceptance section says "均已实现". "均已实现" is
not a test result.

## Gate 4 — Independent verification gate (before a card enters `done/`)

- [ ] QA card exists and is dispatched to `qa-agent`, not the implementer
- [ ] Verifier re-ran the acceptance checks themselves, from a clean checkout/state
- [ ] Findings recorded in `docs/qa/TEST_REPORTS.md` with evidence (command output, screenshot path)
- [ ] P0/P1 bugs block the card; P2/P3 become new cards, not silent acceptance
- [ ] Test coverage meets the project's stated bar (ask if unstated — don't assume zero)

**Fails when:** the only evidence of correctness is the implementer's own test suite passing.

## Gate 5 — Milestone close gate

Run on `close`, or when a natural module boundary is reached.

- [ ] Card counts in `PROJECT_STATE.md` reconcile with files on disk across all four dirs
- [ ] No card sits in `blocked/` without a named decision and a candidate solution
- [ ] Every 契约变更记录 entry has an impact assessment and disposition
- [ ] All user-facing changes reflected in docs (README, API docs, migrations)
- [ ] Retro written: what the estimate missed, which card was mis-scoped, what to change next time
- [ ] Tech debt items listed with locations

**Fails when:** the state file and the filesystem disagree — that means some transition happened
without a state update, and the next session can't be trusted to resume.

---

## Severity definitions

| Level | Meaning | Effect |
|---|---|---|
| P0 | Data loss, security hole, wrong output on the happy path | Block the card; fix before anything else |
| P1 | Broken feature, crashes on a realistic input | Block the card |
| P2 | Wrong behavior on an edge case, poor error message | New card; card may proceed |
| P3 | Cosmetic, style, minor perf | New card or note in retro |

## Two-strike rule

If the same card fails QA twice, stop dispatching it again. Two failures usually mean the card was
mis-scoped or the design it implements is wrong — more attempts produce more churn. Escalate to the
user with both QA reports and the two candidate diagnoses.
