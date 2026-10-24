# Intake — the questions `plan` asks

Ask these **before** decomposing. Ambiguity resolved here costs one message; ambiguity discovered
after dispatch costs a rebuild, because cards carry explicit file boundaries and acceptance criteria
that a changed requirement invalidates.

Ask in batches, not one at a time. If the user says "you decide", make the call, write it into
`REQUIREMENTS.md` under **假设**, and move on — an assumption on record can be corrected later; a
silent one cannot.

## Tier 1 — always ask (4 questions)

1. **成品是什么形态？** Web app / CLI / library / service / script? Who runs it, and where?
2. **这次交付包含什么，明确不包含什么？** Push for the out-of-scope list. "Not yet" items are the
   most valuable part of this answer.
3. **怎么算成功？** The observable thing that will be true when this works. Not "it works" — what
   command, page, or output proves it?
4. **有什么现成的东西必须接？** Existing code, APIs, schema, auth, design system, deployment target.

## Tier 2 — ask when the answer changes the plan

- **技术栈有没有约束？** Language, framework, DB. If unconstrained, the architect card answers this
  — don't decide it in `plan`.
- **有没有必须遵守的既有契约？** Existing interface, API version, DB schema other services read.
- **数据从哪来、存哪去？** Especially: is there real data, or does it need to be mocked?
- **谁能碰代码？** Solo, or does someone else review/merge? Affects branch strategy in cards.
- **时间盒？** Not for precision — for choosing card granularity. One week wants 4-6 cards; one
  month wants 15-25.

## Tier 3 — ask only if the project will live long

- **部署到哪、怎么发版？**
- **要不要 CI？** Which checks are mandatory before merge?
- **有没有合规/安全约束？** PII, secrets handling, license restrictions.
- **这套东西谁维护？** Affects how much documentation the architect owes.

## Requirement → card coverage check

After decomposing, walk the requirement paragraph sentence by sentence and name the card that
delivers each. Anything unmapped is either a missing card or actually out of scope — decide which,
and write it down.

```
需求: "用户能注册、登录、查看自己的资料，管理员能禁用账号"

注册        → #002
登录        → #003
查看资料    → #004
管理员禁用  → #005
管理界面    → ⚠️ 未覆盖 — 是缺口还是 out-of-scope？→ 问用户
```

## Anti-patterns at intake

- ❌ Decomposing from the first sentence before asking anything → the cards encode your guesses.
- ❌ "I'll figure out the details while implementing" → the implementer agent has no context to
  figure it out with, and will invent an interface.
- ❌ Treating "simple" as "specified" → simple requirements are often the vaguest.
- ❌ Skipping the out-of-scope list → every later "can you also…" has no basis for a no.
