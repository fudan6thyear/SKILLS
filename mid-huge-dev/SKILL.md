---
name: mid-huge-dev
description: "Task-driven development workflow for mid-to-large projects (multi-day, multi-module, multi-session). Turns a requirement into a persisted task graph under docs/, dispatches each task to a role agent (pm / architect / backend / qa), enforces handoff gates, and keeps state in the repo so any session can resume. Triggers on: mid-huge dev, mid-huge-dev, 中大型项目开发, 任务驱动开发, task-driven, task driven dev, 派发任务给架构师, 建立项目任务图, /mid-huge-dev, initialize task-driven project, 初始化任务驱动流程, 프로젝트 태스크 관리, 태스크 기반 개발."
metadata:
  version: "1.0.0"
  last_updated: "2026-09-16"
  status: active
  task_type: orchestration
  depends_on: "references/roles/{pm,architect,backend,qa}.md (synced from ~/.claude/agents/)"
  related_skills:
    - deep-research
    - ui-ux-pro-max
---

# Mid-Huge Dev — Task-Driven Workflow

A **persisted task graph** for work too big for one session and too small for a program office. The
unit of work is a **task card** in the repo, not a message in a chat. The agent roles are the four
in `~/.claude/agents/`; this skill is the protocol that connects them.

**The one rule that matters:** state lives in `docs/`, never only in the conversation. If the
context window is wiped mid-project, `docs/pm/` must be enough to resume.

## When to use it / when not to

| Use it | Don't use it |
|---|---|
| 3+ modules or services, work spanning days | One file, one sitting — just do it |
| Multiple roles genuinely needed (design → build → test) | You're the only writer and the design is obvious |
| You'll lose context and need to resume | Throwaway prototype, no handoff |
| Contract/schema changes ripple across tasks | Single-shot script |

If the task is under roughly half a day, skip the ceremony and answer directly.

## Directory contract

Everything lives under the **project root**, not the skill directory:

```
docs/
├── pm/
│   ├── PROJECT_STATE.md        # single source of truth: phase, counts, blockers, contracts
│   ├── REQUIREMENTS.md         # (init) raw ask + clarified scope + out-of-scope + open questions
│   └── tasks/
│       ├── 001-<slug>.md       # pending   — created, not yet accepted by a role
│       ├── active/             # claimed   — someone is working on it now
│       ├── done/               # accepted  — report present, acceptance criteria checked
│       └── blocked/            # stopped   — needs a decision; reason is in the card
├── architecture/
│   ├── SYSTEM_DESIGN.md        # architect output
│   ├── API_CONTRACTS.md        # interface + type + error-mode definitions
│   └── <TOPIC>_RESEARCH.md     # one per investigation
└── qa/
    ├── TEST_REPORTS.md
    └── screenshots/
```

**Card location is card status.** Moving a file between `tasks/`, `tasks/active/`, `tasks/done/`,
`tasks/blocked/` is the state transition — no separate tracker to drift out of sync.

## Commands

Invoke as `/mid-huge-dev <command> [args]`. With no command, infer from `docs/pm/PROJECT_STATE.md`:
missing → `init`; present → `status`.

| Command | What it does | Writes |
|---|---|---|
| `init [项目名]` | Scaffold `docs/` tree, write REQUIREMENTS.md stub + empty PROJECT_STATE.md | layout + 2 files |
| `plan` | Clarify the requirement with the user, then decompose into task cards | `REQUIREMENTS.md`, `tasks/NNN-*.md` |
| `dispatch NNN` | Hand a card to its role agent; move card to `active/` | card move + state update |
| `report NNN` | Collect a role's completion report, run the acceptance checklist | card content + state |
| `verify NNN` | Dispatch QA sign-off for a built card | `qa/TEST_REPORTS.md` |
| `status` | Print the project dashboard from disk | nothing |
| `next` | Recommend the next dispatchable card (deps satisfied, unblocked) | nothing |
| `block NNN <原因>` | Mark blocked, record the decision needed | card move + state |
| `close` | Milestone gate: verify all cards closed, contracts consistent, write retro | `PROJECT_STATE.md` |

Never claim a command ran if it didn't write the file. Read back what you wrote when the write
matters.

## Phase flow

```
init → plan → [ architect ] → [ backend ∥ backend ∥ ... ] → [ qa ] → close
                #001              #002  #003                  #004
```

1. **init** — scaffold.
2. **plan** — interview the user (see `references/intake-questions.md`). Ambiguity resolved *here*
   is cheap; ambiguity discovered after dispatch costs a rebuild.
3. **design** — the architect card comes first and always. Nothing parallelizes before
   `API_CONTRACTS.md` exists, or two implementers will invent two incompatible interfaces.
4. **build** — dispatch independent cards in the same turn (multiple `Agent` calls in one block) so
   they actually run concurrently. Dependencies are declared in the card's `depends_on`.
5. **verify** — QA never on the author's own card. Tests written by the implementer are evidence,
   not acceptance.
6. **close** — the milestone gate in `references/quality-gates.md`.

Full gate definitions: `references/quality-gates.md`. Card format:
`references/task-card-template.md`. State file schema: `references/project-state-schema.md`. Role
dispatch table: `references/dispatch-matrix.md`.

## Roles and how to dispatch them

Four role files live in `references/roles/` — `pm.md`, `architect.md`, `backend.md`, `qa.md`. They
are generated from `~/.claude/agents/*.md` by `scripts/sync-roles.sh`, so every tool reads the same
role instructions from the same place.

| Tool | How a role reaches the subagent |
|---|---|
| **Claude Code** | `Agent({subagent_type: "architect-agent", …})` — the role file is already installed as a native agent; don't paste it |
| **opencode** | `task({subagent_type: "architect-agent", …})` — native agent installed at `~/.config/opencode/agent/`; don't paste it |
| **Codex** | No named-agent registry. Read `references/roles/<role>.md` yourself and inline it into a generic subagent prompt |

In all three, the prompt is the same shape — point at the card, not at the conversation:

```
执行任务卡 docs/pm/tasks/002-auth-api.md。
先完整读取卡片（含修改范围与验收标准）及卡片引用的架构文档与契约；
只在允许范围内工作；逐条运行验收标准中的检查；
按卡片末尾的"完工回报格式"提交结构化回报；
若发现卡片本身有问题，回报"受阻"并说明，不要自行改设计。
```

Rules that keep this from becoming mush:

- **One card per agent invocation.** A card that needs two roles is two cards.
- **The card is self-contained.** The agent gets the card path, not a summary of the conversation —
  a fresh agent has no memory of what you discussed, and shouldn't need it.
- **Cards carry their own boundaries** (allowed files / forbidden files / new files). This is what
  prevents a backend agent from "helpfully" refactoring the frontend.
- **If a role agent isn't installed**, fall back to the tool's `general-purpose` subagent and prepend
  the matching `references/roles/*.md` — the card still bounds the work.
- **Parallel dispatch requires disjoint file sets.** Two cards touching the same file must be
  sequential, regardless of dependency declarations.
- **Don't re-derive roles from the tool's own agent files.** `references/roles/` is the portable
  copy; edit `~/.claude/agents/` and re-run `scripts/sync-roles.sh`.

## Failure handling

| Symptom | Response |
|---|---|
| Report missing acceptance results | Reject. Ask for the missing sections only. Don't accept "done ✅" as a report. |
| Card blocked on a technical unknown | Spawn an architect card scoped to the question; suspend the dependent card. |
| Contract changed mid-flight | Record in `PROJECT_STATE.md` → 契约变更记录, then enumerate every card that depends on it and either re-dispatch or add a follow-up card. |
| Same card fails QA twice | Stop. The card is probably mis-scoped or the design is wrong — escalate to the user with both failure reports. |
| Scope creep discovered | New card. Never widen an active card's file boundary. |

## Anti-patterns

- ❌ Assigning work in prose ("now implement auth") with no card → nothing to verify against.
- ❌ Marking a card done from memory of the conversation → read the card file.
- ❌ Skipping the architect because "the design is obvious" → you'll pay for it at card #003.
- ❌ Letting the implementer also be the verifier → self-graded work.
- ❌ Parallel dispatch of cards that touch the same file → merge conflicts the agent will "fix"
  by deleting someone's work.

## Bootstrapping a new project

```bash
bash ~/.claude/skills/mid-huge-dev/scripts/init-project.sh [target-dir] [project-name]
```

Creates the `docs/` tree and seeds `PROJECT_STATE.md` + `REQUIREMENTS.md`. Then run `plan`.

## Installing into another tool

This skill directory is the single source of truth. Other tools get a symlink, not a copy — editing
here updates every tool at once.

```bash
bash scripts/install.sh          # idempotent; symlinks skill + agents, prints what it did
bash scripts/install.sh --check  # report state only, change nothing
```

Where things land:

| Tool | Skill | Roles |
|---|---|---|
| Claude Code | `~/.claude/skills/mid-huge-dev/` (native) | `~/.claude/agents/*.md` (native) |
| opencode | reads `~/.claude/skills/` directly — no install needed | `~/.config/opencode/agent/{pm,architect,backend,qa}-agent.md` |
| Codex | `~/.codex/skills/mid-huge-dev` → symlink | no registry; read `references/roles/*.md` at dispatch time |

Which files actually resolve per tool is in `references/tool-install.md`.
