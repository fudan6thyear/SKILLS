# Task Card Template

A card is a contract. Every field exists because omitting it caused a failure somewhere: vague
boundaries cause cross-module edits, unverifiable acceptance criteria cause arguments at review
time, and missing contract constraints cause two implementers to build incompatible interfaces.

Cards are numbered `NNN` (zero-padded, monotonic, never reused) and live in
`docs/pm/tasks/NNN-<slug>.md`. Slug is kebab-case and ≤5 words. The number is the card's identity —
it goes in branch names, commit messages, and reports.

---

```markdown
# 任务卡 #NNN: <标题>

## 元信息
- **分配给**: architect-agent | backend-agent | qa-agent
- **优先级**: P0-紧急 | P1-高 | P2-中 | P3-低
- **依赖**: #NNN, #NNN  (无则写"无")
- **预计工作量**: 小 (<2h) | 中 (半天) | 大 (1-3 天)
- **创建时间**: YYYY-MM-DD

## 背景
<为什么有这张卡。2-4 句。链接到上游卡片/架构文档的路径。>

## 目标
<一句话说清完成后世界变成什么样。用可观测的动词。>

## 修改范围

### ✅ 允许修改
- `src/server/auth.ts`
- `src/server/auth.test.ts`

### ➕ 允许新建
- `src/server/session.ts`

### ❌ 禁止修改
- `src/shared/types.ts`（类型变更需走契约流程，另开卡）
- 任何 `docs/pm/` 下的文件（PM 专属）

> 路径必须精确到文件。禁止出现"相关文件""涉及的模块"这类模糊表述——
> 模糊的边界等于没有边界。

## 契约约束
<必须遵守的既有约定。引用 docs/architecture/API_CONTRACTS.md 的具体条目。>

- 必须 `implements IAuthService`
- 错误必须抛出 `AuthError`，不得返回 null
- 命名遵循 `verbNoun` 风格

无约束时写"无——本卡不涉及接口变更"。

## 验收标准
<每一条都必须能被一条命令或一次操作验证。>

- [ ] `tsc --noEmit` 通过，无类型错误
- [ ] `npm test` 通过，新增测试 ≥4 个（正常 1 + 错误 ≥2 + 边界 ≥1）
- [ ] `POST /api/login` 用错误密码返回 401，响应体为 `{ error: "INVALID_CREDENTIALS" }`
- [ ] 手动验证：用测试账号登录后 `GET /api/me` 返回该用户资料

❌ 不合格的标准："代码质量良好"、"合理实现功能"、"性能可接受"——主观、无法判定通过与否。

## 参考
- 设计文档: `docs/architecture/SYSTEM_DESIGN.md#认证流程`
- 接口契约: `docs/architecture/API_CONTRACTS.md#IAuthService`
- 上游卡片: `docs/pm/tasks/done/001-auth-architecture.md`

---

## 完工回报格式
<执行者按此格式回报，缺任何一节都不算完工。>

### 状态
✅ 完成 | ⚠️ 部分完成 | ❌ 受阻

### 代码变更
**分支**: `feature/task-NNN-<slug>`
**提交**: `<sha>`

**修改文件**:
- `src/server/auth.ts` (修改, +120 行)
- `src/server/auth.test.ts` (新建, 95 行)

### 验收标准检查
- [x] ✅ `tsc --noEmit` 通过 — 无输出
- [x] ✅ `npm test` 通过 — 8/8，覆盖率 91%
- [ ] ❌ `POST /api/login` 401 响应体 — 实际返回 `{ message: ... }`，与契约不符（见偏离说明）

### 偏离说明
<未按卡执行的地方 + 原因。完全按卡执行写"无"。>
第 3 条验收标准未通过：契约要求 `{ error: ... }`，现有错误处理中间件统一输出 `{ message: ... }`。
未擅自改动中间件（超出本卡修改范围）。建议另开卡统一错误响应格式。

### 契约变更
<新增/修改的接口、类型、数据结构。无则写"无"。>
无。

### 阻塞问题
<阻塞本卡或后续卡的问题。>
无。

### 技术债务
<为赶进度留下的坑，写明位置和建议处理时机。>
无。

### 建议下一步
1. 另开卡 #NNN+1: 统一错误响应格式为 `{ error: code }`
2. 或先验收本卡，错误格式单独排期
```

---

## Granularity

Aim for **half a day to 3 days** per card.

| | Symptom | Fix |
|---|---|---|
| Too big | Acceptance criteria need "and" three times;允许修改 lists 10+ files | Split by module or by contract boundary |
| Too small | Card is "add a dependency", "rename a function" | Fold into the feature card that needs it |
| Indivisible | Card genuinely can't split and is 5 days | Say so in 预计工作量; that's a legitimate design card |

## Parallelism check

Before dispatching two cards in the same turn, compare their **允许修改 / 允许新建** sets. Any
overlap → serialize them. Dependencies declared in 依赖 are necessary but not sufficient; file
overlap is the real constraint.
