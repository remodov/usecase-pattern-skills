#!/usr/bin/env bash
#
# ucp-trigger-detect.sh — UserPromptSubmit hook.
#
# Распознаёт фразы-триггеры цепочки UCP в промпте пользователя и инжектит
# additionalContext с прямой инструкцией. Жёстче CLAUDE.md: harness гарантирует
# доставку контекста модели, в отличие от строчки в always-loaded файле, которую
# модель может проигнорировать.
#
# Триггеры: «сделай/пишем/пиши/напиши/начнём/сгенерим … сервис».
#
# Stdin: JSON от Claude Code (`{prompt, cwd, session_id, ...}`).
# Stdout: JSON `{hookSpecificOutput: {hookEventName, additionalContext}}` —
#   или ничего, если триггер не сработал.

set -euo pipefail

prompt="$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("prompt",""))')"

# (?i)-эквивалент через grep -i; не привязываемся к началу строки, разрешаем
# до ~30 символов между глаголом и словом «сервис» (например: «давай напиши
# мне сервис учёта заявок»).
pattern='(сделай|сделаем|пишем|пиши|напиши|начн[еёa]м|сгенери[мт]?ь?|сгенерируй|собери)[^.!?]{0,30}сервис'

if ! printf '%s' "$prompt" | grep -qiE "$pattern"; then
  exit 0
fi

cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "⚡ Триггер цепочки UCP обнаружен в промпте.\n\nНемедленно:\n1. Если `ucp-*` скиллы видны в available-skills — вызови `/ucp-new-service` (он оркестрирует spec → ddd-tactical → bootstrap → pattern → auth → test). Не пиши код от руки, не задавай вопросов про архитектуру до запуска скилла.\n2. Если `ucp-*` скиллов в available-skills нет — сессия запущена не из директории сервиса. Сразу скажи пользователю: «перезапусти Claude из директории сервиса, скиллы подключаются через симлинки в `.claude/skills/`». Не изобретай структуру по аналогии с соседними проектами."
  }
}
JSON
