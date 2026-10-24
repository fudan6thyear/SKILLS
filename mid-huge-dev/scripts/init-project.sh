#!/usr/bin/env bash
# Scaffold the mid-huge-dev docs/ tree in a project root.
# Usage: init-project.sh [target-dir] [project-name]
#   target-dir   defaults to $PWD
#   project-name defaults to basename of target-dir
# Idempotent: existing files are never overwritten.

set -euo pipefail

TARGET="${1:-$PWD}"
NAME="${2:-$(basename "$TARGET")}"

if [ ! -d "$TARGET" ]; then
  echo "✗ target dir does not exist: $TARGET" >&2
  exit 1
fi

cd "$TARGET"

created=()
skipped=()

mkfile() {
  local path="$1"
  if [ -e "$path" ]; then
    skipped+=("$path")
  else
    mkdir -p "$(dirname "$path")"
    cat > "$path"
    created+=("$path")
  fi
}

mkdir -p docs/pm/tasks/{active,done,blocked} docs/architecture docs/qa/screenshots

TODAY="$(date '+%Y-%m-%d %H:%M')"

mkfile docs/pm/PROJECT_STATE.md <<EOF
# 项目状态总览 — ${NAME}

**最后更新**: ${TODAY}
**当前阶段**: 初始化完成，待需求澄清与任务拆解

## 任务统计
- 已完成: 0 | 进行中: 0 | 待开始: 0 | 受阻: 0

## 当前阶段说明
docs/ 骨架已建立，尚无任务卡。
下一步：运行 \`/mid-huge-dev plan\` 澄清需求并拆解为任务卡。

> 状态规则：卡片所在目录即卡片状态（tasks/ = 待开始，active/ = 进行中，
> done/ = 已完成，blocked/ = 受阻）。统计数字必须与磁盘上的卡片数一致。

---

## 已完成任务
（无）

---

## 进行中任务
（无）

---

## 待办任务
（无）

---

## 阻塞问题
（无）

---

## 契约变更记录
（无）

---

## 决策日志
（无）
EOF

mkfile docs/pm/REQUIREMENTS.md <<EOF
# 需求 — ${NAME}

**记录时间**: ${TODAY}

## 原始需求
<逐字记录用户的原话，不要润色、不要补充。后面的澄清结果记在下一节。>

## 澄清结果
<plan 阶段与用户确认后的理解，用自己的话复述一遍需求。>

## 明确不做（Out of Scope）
<这一节最值钱。"暂时不做"和"永不做"都记在这里，并注明原因。>

## 假设
<未能向用户确认、但必须现在决定的点。每条注明"若假设不成立，影响是……"。>

## 待用户回答
<阻塞拆解的问题，按重要性排序。>

## 验收视角的成功定义
<可观测的：哪条命令、哪个页面、哪份输出能证明这东西成了。>
EOF

mkfile docs/architecture/SYSTEM_DESIGN.md <<'EOF'
# 系统设计

> 由 architect-agent 填写。初始化时为空占位，说明设计尚未开始——
> 实现类任务卡不得在设计完成前派发。

## 模块划分

## 关键流程

## 技术选型与理由

## 风险与缓解
EOF

mkfile docs/architecture/API_CONTRACTS.md <<'EOF'
# 接口契约

> 由 architect-agent 维护。实现类任务卡必须引用此文件中的具体条目。
> 契约变更必须同步到 docs/pm/PROJECT_STATE.md 的"契约变更记录"。

## 接口清单

### <IExample>
```typescript
interface IExample {
  /** 说明 */
  doThing(input: Input): Promise<Output>;
}
```

**错误模式**: 抛异常 `ExampleError` / 返回联合类型 `Output | ExampleError`
**变更影响**: 列出依赖此契约的卡片编号
EOF

mkfile docs/qa/TEST_REPORTS.md <<'EOF'
# 测试报告

> 由 qa-agent 填写。每个任务卡一节，必须包含实际命令输出或截图路径，
> 不接受"已验证通过"这类无证据结论。

EOF

cat > docs/qa/screenshots/.gitkeep <<'EOF'
EOF

echo "mid-huge-dev 初始化完成: $TARGET"
echo
if [ ${#created[@]} -gt 0 ]; then
  echo "已创建:"
  printf '  + %s\n' "${created[@]}"
fi
if [ ${#skipped[@]} -gt 0 ]; then
  echo "已存在（跳过，未覆盖）:"
  printf '  = %s\n' "${skipped[@]}"
fi
echo
echo "目录结构:"
echo "  docs/pm/PROJECT_STATE.md     项目状态（唯一事实来源）"
echo "  docs/pm/REQUIREMENTS.md      需求与边界"
echo "  docs/pm/tasks/{,active,done,blocked}/"
echo "  docs/architecture/           设计与契约"
echo "  docs/qa/                     测试报告与截图"
echo
echo "下一步: /mid-huge-dev plan"
