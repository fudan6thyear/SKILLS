# Dispatch Matrix

Four roles drive the workflow. Their full instructions live in `references/roles/*.md` — generated
from `~/.claude/agents/` by `scripts/sync-roles.sh`, so the same text drives every tool.

| Role file | Agent (Claude Code) | Agent (opencode) | Codex |
|---|---|---|---|
| `references/roles/pm.md` | `pm-agent` | `pm-agent` | read the file, inline into a generic subagent |
| `references/roles/architect.md` | `architect-agent` | `architect-agent` | same |
| `references/roles/backend.md` | `backend-agent` | `backend-agent` | same |
| `references/roles/qa.md` | `qa-agent` | `qa-agent` | same |

## Which role gets which card

| Card kind | Role | Output lands in | Parallel-safe with |
|---|---|---|---|
| Requirement clarification → scope | (you, with the user) | `docs/pm/REQUIREMENTS.md` | nothing — gate for everything |
| Planning, decomposition, state upkeep | `pm` | `docs/pm/**` | nothing — it owns the state file |
| System design, research, interface contracts | `architect` | `docs/architecture/**` | nothing — it *defines* what others build against |
| Implementation, disjoint file sets | `backend` × N | files named in the card | other backend cards with disjoint file sets |
| Acceptance verification | `qa` | `docs/qa/**` + `tests/` | verification of a *different* card only |

## Why these boundaries

- **Architect doesn't implement.** If the designer also builds, the design quietly bends toward
  whatever was easiest to code, and the contract stops being an independent reference.
- **QA doesn't verify its own work.** The implementer's tests answer "does it do what I intended?"
  QA answers "does it do what the card said?" Different question, different failure modes.
- **Only PM writes state.** Two writers on `PROJECT_STATE.md` in one turn means one overwrites the
  other, and the survivor is whichever wrote last — not whichever was right.
- **File bounds are per card, not per role.** A backend agent may edit `src/shared/types.ts` when a
  card says so, and must not when it doesn't.

## Dispatching per tool

### Claude Code

```
Agent({
  subagent_type: "architect-agent",     # or backend-agent / qa-agent / pm-agent
  description: "001 auth architecture",
  prompt: "<the card-pointing prompt below>"
})
```

Role instructions load automatically from `~/.claude/agents/`. Do not paste `references/roles/*.md`
into the prompt here — it would duplicate what the subagent already has.

### opencode

```
task({
  subagent_type: "architect-agent",     # loaded from ~/.config/opencode/agent/
  description: "001 auth architecture",
  prompt: "<the card-pointing prompt below>"
})
```

Same shape. If the agent type isn't registered, fall back to `general-purpose` and prepend the
contents of the matching `references/roles/*.md`.

### Codex

Codex has no named-agent registry — subagents are generic, so the role has to travel in the prompt.
Read the role file, then dispatch with it inlined:

```
1. 读取 ~/.claude/skills/mid-huge-dev/references/roles/architect.md
2. 将全文作为角色指令，连同下面的任务卡提示一起交给子代理：

   你现在扮演上述角色。执行任务卡 docs/pm/tasks/001-auth-architecture.md。
   ...
```

`features.multi_agent_v2` in `~/.codex/config.toml` also controls the subagent budget
(`max_concurrent_threads_per_session`, `max_depth`, `default_subagent_model`). Check it before
expecting parallel dispatch to work; raise `max_concurrent_threads_per_session` to at least the
number of cards you intend to run at once.

## The dispatch prompt

Keep it short and point at the card. A fresh agent has none of this conversation's context, and
pasting a summary in creates a second, drifting source of truth.

```
执行任务卡 docs/pm/tasks/002-auth-api.md。

要求：
1. 先完整读取卡片，包括修改范围和验收标准
2. 读取卡片引用的架构文档与契约
3. 在卡片允许的范围内工作，不要扩大范围
4. 逐条运行验收标准中的检查，不要凭印象判断通过
5. 按卡片末尾的"完工回报格式"提交结构化回报，包含每一条验收标准的实际结果
6. 如果发现卡片本身有问题（范围/契约矛盾），回报"受阻"并说明，不要自行改设计
```

Point 6 matters: without it, agents resolve ambiguity by guessing, and the guess stays invisible
until QA.

## Fallbacks

- Agent type missing from the registry → use `general-purpose` and inline the role file plus the
  card's 修改范围 + 验收标准 verbatim. The card still bounds the work.
- Card needs two roles → split into two cards. Multi-role prompts produce work that satisfies
  neither role's standard.
- Long-running card → still one invocation. If it dies mid-way, the partial branch plus the card is
  enough to resume; a resumed agent re-reads the card.
