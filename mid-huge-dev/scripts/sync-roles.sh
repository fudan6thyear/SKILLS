#!/usr/bin/env bash
# Regenerate references/roles/*.md from the canonical agent definitions.
#
# Canonical source: ~/.claude/agents/*.md  (override with AGENTS_DIR=...)
# Output:           <skill>/references/roles/{pm,architect,backend,qa}.md
#
# Why a copy instead of a symlink: Claude Code agent files carry tool-specific
# frontmatter (model: opus, tools: [...]). opencode and Codex reject or ignore
# those shapes, and the YAML `name:` field is not reliable when a file is read
# as plain instructions. The generated files are frontmatter-free prose that any
# tool can read, with a small tool-neutral header.
#
# Re-run this after editing any agent in ~/.claude/agents/.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENTS_DIR="${AGENTS_DIR:-$HOME/.claude/agents}"
OUT_DIR="$SKILL_DIR/references/roles"

if [ ! -d "$AGENTS_DIR" ]; then
  echo "✗ agents dir not found: $AGENTS_DIR" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# role-key : agent-file : 中文角色名 : 一句话职责
ROLES=(
  "pm:pm-agent:项目经理 (PM):任务编排、状态维护、验收管理、契约变更追踪"
  "architect:architect-agent:架构师 (Architect):系统设计、技术调研、接口契约、风险评估"
  "backend:backend-agent:后端工程师 (Backend):业务实现、数据层、第三方集成、单元测试"
  "qa:qa-agent:QA 工程师 (QA):E2E 测试、功能验收、缺陷记录、质量门禁"
)

generated=0
for entry in "${ROLES[@]}"; do
  IFS=':' read -r key file cname blurb <<< "$entry"
  src="$AGENTS_DIR/$file.md"

  if [ ! -f "$src" ]; then
    echo "⚠ skip $key — missing $src" >&2
    continue
  fi

  # Strip a leading YAML frontmatter block, if present.
  body="$(awk 'NR==1 && /^---[[:space:]]*$/ {fm=1; next} fm && /^---[[:space:]]*$/ {fm=0; next} !fm {print}' "$src")"

  {
    echo "# 角色：$cname"
    echo
    echo "> 本文件由 \`scripts/sync-roles.sh\` 从 \`$AGENTS_DIR/$file.md\` 生成，请勿手工编辑——"
    echo "> 修改请改源文件后重新运行同步脚本。"
    echo ">"
    echo "> 工具无关的角色指令：Claude Code 通过 \`$file\` 子代理加载，opencode 通过"
    echo "> \`~/.config/opencode/agent/$file.md\` 加载，Codex 没有具名子代理，由主代理直接读取本文件"
    echo "> 并在派发时把内容作为角色指令传给通用子代理。"
    echo
    printf '%s\n' "$body"
  } > "$OUT_DIR/$key.md"

  echo "  + references/roles/$key.md  ←  $file.md"
  generated=$((generated + 1))
done

echo
echo "已生成 $generated 个角色文件到 $OUT_DIR"
echo "源目录: $AGENTS_DIR"
