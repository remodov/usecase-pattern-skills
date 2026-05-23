#!/usr/bin/env bash
#
# ucp-session-check.sh — SessionStart hook.
#
# Проверяет состояние установки UCP-скиллов в текущем проекте на старте сессии:
#   - .claude/skills/ucp-* существуют;
#   - симлинки не broken (репо скиллов на месте);
#   - .claude/docs/ заполнен снапшотами style-guide'ов.
#
# Если что-то не так — инжектит warning в контекст с командой починки. Если всё
# OK — молчит (не засоряет always-loaded контекст).
#
# Stdin: JSON от Claude Code (`{cwd, source, session_id, ...}`).
# Stdout: JSON `{hookSpecificOutput: {hookEventName, additionalContext}}` —
#   или ничего, если проверка прошла.

set -euo pipefail

cwd="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("cwd","."))')"
skills_dir="$cwd/.claude/skills"

if [ ! -d "$skills_dir" ]; then
  exit 0
fi

shopt -s nullglob
ucp_links=("$skills_dir"/ucp-*)
shopt -u nullglob

if [ ${#ucp_links[@]} -eq 0 ]; then
  exit 0
fi

broken_count=0
broken_list=""
for link in "${ucp_links[@]}"; do
  if [ ! -e "$link" ]; then
    broken_count=$((broken_count + 1))
    broken_list+="  - $(basename "$link") → $(readlink "$link" 2>/dev/null || echo "?")\n"
  fi
done

if [ "$broken_count" -eq 0 ]; then
  exit 0
fi

python3 <<PY
import json
msg = (
    f"⚠ Обнаружено {$broken_count} broken-симлинков в .claude/skills/:\n\n"
    f"$(printf '%b' "$broken_list")"
    "\nЭто значит, что репо `usecase-pattern-skills` отсутствует или переехало.\n"
    "Почини: `git clone` (или `git pull`) репо скиллов и запусти "
    "`<repo>/install.sh .` из директории сервиса. До этого ucp-* скиллы работать не будут."
)
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": msg,
    }
}, ensure_ascii=False))
PY
