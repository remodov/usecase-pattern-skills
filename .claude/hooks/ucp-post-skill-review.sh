#!/usr/bin/env bash
#
# ucp-post-skill-review.sh — PostToolUse hook на Skill.
#
# После завершения design-скилла, для которого ревью обязательно (DDL и миграции
# по claude-block.md: «всегда для DDL и миграций»), инжектит подсказку вызвать
# парный *-review скилл. Для остальных design-скиллов авто-подсказка не выдаётся
# — там самопроверка достаточна, а ревью идёт по запросу.
#
# Список «всегда review»:
#   ucp-pg-schema-design   → ucp-pg-schema-review
#   ucp-pg-migration-design → ucp-pg-migration-review
#
# Stdin: JSON от Claude Code (`{tool_name, tool_input, tool_response, ...}`).
# Stdout: JSON `{hookSpecificOutput: {hookEventName, additionalContext}}` —
#   или ничего, если триггер не сработал.

set -euo pipefail

payload="$(cat)"

parsed="$(python3 -c '
import json, sys
data = json.loads(sys.stdin.read())
tool = data.get("tool_name", "")
skill = (data.get("tool_input") or {}).get("skill", "")
print(f"{tool}\t{skill}")
' <<<"$payload")"

tool_name="${parsed%%$'\t'*}"
skill_name="${parsed#*$'\t'}"

if [ "$tool_name" != "Skill" ]; then
  exit 0
fi

case "$skill_name" in
  ucp-pg-schema-design)    review="ucp-pg-schema-review" ;;
  ucp-pg-migration-design) review="ucp-pg-migration-review" ;;
  *) exit 0 ;;
esac

python3 -c "
import json
print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PostToolUse',
        'additionalContext': '⚠ После \`$skill_name\` ревью обязательно (DDL/миграции — claude-block.md): вызови \`/$review\` на сгенерированных файлах перед тем, как двигаться дальше.',
    }
}, ensure_ascii=False))
"
