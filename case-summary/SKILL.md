---
name: case-summary
description: Summarizes legal, regulatory, enforcement, and court cases using a primary-source-first method. Extracts a case summary, enterprise implications from a DPO perspective, key facts, and original legal text with key points. Use when the user asks for a case summary, case brief, enforcement summary, judgment summary, administrative penalty analysis, regulator action analysis, 案例总结, 判例分析, 处罚决定总结, or 执法案例分析.
---

# Case Summary / 案例总结

## Instructions / 使用说明

Apply this skill when summarizing a legal case, regulatory action, enforcement decision, administrative penalty, court judgment, or similar authority document.

在总结法律案例、监管执法、行政处罚、法院判决或类似权威文件时，使用本 skill。

### Core standards / 核心标准

- Use primary and authoritative sources first.
- 优先使用一手、权威来源。
- Be precise, concise, and explicit about uncertainty.
- 保持准确、简洁，并明确说明不确定性。
- Do not invent parties, facts, dates, holdings, penalties, or legal text.
- 不要编造主体、事实、日期、裁判要旨、处罚结果或法条原文。
- Separate verified facts from inference and recommendations.
- 区分已核实事实、推论和建议。
- If the official case document or legal text is unavailable, say so directly.
- 如果官方案例文书或法条原文不可得，要直接说明。

### Source hierarchy / 来源优先级

Use sources in this order:

按以下顺序使用来源：

1. Official decision, judgment, penalty notice, or authority release.
2. Official laws, regulations, directives, rules, or guidance cited in the case.
3. Official court, regulator, or government guidance explaining the rule.
4. Reliable secondary summaries only if primary sources are unavailable or incomplete.

1. 官方裁判文书、处罚决定书、监管公告或机关发布材料。
2. 案件所依据的官方法律、法规、规章、指令、规则或指南。
3. 法院、监管机关或政府对相关规则的官方解释材料。
4. 仅在一手来源缺失或不完整时，才使用可靠的二手总结。

### Workflow / 工作流

1. Identify the jurisdiction, authority or court, date, document type, and scope.
2. Determine whether the matter is judicial, regulatory, administrative, or mixed.
3. Extract the core facts, timeline, actors, conduct, data categories, and outcome.
4. Identify the exact legal provisions materially relied on in the decision.
5. Quote the original legal text when available. If not available, say what source was used instead.
6. Translate the case into practical enterprise implications from a DPO perspective.

1. 识别法域、机关或法院、日期、文书类型和分析范围。
2. 判断案件属于司法、监管、行政还是混合性质。
3. 提取核心事实、时间线、主体、行为、数据类型和处理结果。
4. 识别决定中实质依赖的具体法律条文。
5. 法条原文可得时尽量引用原文；不可得时说明替代来源。
6. 从 DPO 视角把案例转化为对企业的实务启示。

### DPO lens / DPO 视角

When deriving enterprise implications, check only the issues that are relevant:

在提炼企业启示时，只检查与案件相关的问题：

- lawful basis and purpose limitation
- transparency and notice
- minimization and retention
- security and access control
- processor/vendor management
- cross-border transfer
- DPIA, ROPA, policy, and evidence of accountability
- incident response, breach handling, and escalation
- training, governance, and internal controls

- 合法性基础与目的限制
- 透明度与告知
- 数据最少化与保存期限
- 安全措施与访问控制
- 处理者或供应商管理
- 跨境传输
- DPIA、ROPA、制度文件与问责证据
- 事件响应、泄露处置与升级机制
- 培训、治理与内部控制

## Required output / 必备输出

Always include these three sections unless the user explicitly asks for a different format.

除非用户明确要求其他格式，否则始终包含以下三个部分。

### 1. Case summary and DPO implications / 案情总结及从 DPO 角度触发对于企业的启示

- Start with a short case summary: who did what, what went wrong, what the authority decided.
- Then explain the enterprise implications from a DPO perspective.
- Keep the implications practical. Focus on controls, governance, documentation, and risk reduction.
- If the implication depends on missing facts, say so.

- 先用短段落总结案情：谁做了什么、问题出在哪里、机关或法院作出什么结论。
- 再从 DPO 角度说明对企业的启示。
- 启示要落到控制措施、治理机制、留痕文档和风险降低动作。
- 如果启示依赖未披露事实，要明确说明。

### 2. Key facts / 关键事实

List only the facts that materially affect the conclusion, such as:

仅列出会影响结论的重要事实，例如：

- jurisdiction, authority, date, and document type
- parties or roles
- processing activity and business context
- categories of personal data involved
- timeline of relevant events
- failure, violation, dispute, or compliance gap
- outcome, penalty, remedy, or court holding

- 法域、机关、日期和文书类型
- 当事方或角色
- 处理活动与业务背景
- 涉及的个人数据类别
- 关键事件时间线
- 失误、违法点、争议点或合规缺口
- 处理结果、处罚、救济或裁判结论

### 3. Original legal text and key points / 法条原文及要点

For each key provision:

对于每个关键条文：

- name the law, article, and source
- provide the original legal text or an official excerpt when available
- summarize the key point in plain language
- explain why that provision mattered in this case

- 写明法律名称、条号和来源
- 在可得时提供法条原文或官方节录
- 用简洁语言提炼条文要点
- 说明该条文为何在本案中重要

If the original text cannot be verified, say `Original legal text not verified / 法条原文未核实` and do not fabricate it.

如果法条原文无法核实，写明 `Original legal text not verified / 法条原文未核实`，不要编造。

## Default response skeleton / 默认输出骨架

Use this structure by default:

默认使用以下结构：

```markdown
Case summary and DPO implications / 案情总结及从 DPO 角度触发对于企业的启示
- [Short case summary]
- [DPO implication 1]
- [DPO implication 2]

Key facts / 关键事实
- [Fact 1]
- [Fact 2]
- [Fact 3]

Original legal text and key points / 法条原文及要点
- [Law + article + source]
  - Original text / 原文: [quoted text or "not verified"]
  - Key point / 要点: [plain-language summary]
  - Relevance / 关联性: [why it mattered here]

Limitations / 局限
- [missing facts, missing source text, translation limits, or jurisdiction limits]
```

## Writing style / 写作风格

- Prefer short sentences, plain wording, and consistent terminology.
- Prefer direct analysis over background narration.
- Omit irrelevant sections and irrelevant legal history.
- When useful, distinguish `Fact`, `Inference`, and `Recommendation`.

- 优先使用短句、朴素措辞和一致术语。
- 以直接分析为主，少写无关背景。
- 省略无关段落和无关法制史背景。
- 在有帮助时区分 `Fact`、`Inference` 和 `Recommendation`。
