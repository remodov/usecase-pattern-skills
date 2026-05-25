#!/usr/bin/env bash
#
# impl-task-detect.sh — UserPromptSubmit hook (глобальный).
#
# Гибридный детектор задач реализации Java/Spring-кода в UCP-проектах.
# Pass 1: keyword regex по implementation-фразам.
# Pass 2: claude -p Haiku-классификатор, если Pass 1 промахнулся.
#
# Срабатывает только в директориях, где есть `.claude/skills/ucp-*` —
# вне UCP-проектов молча выходит.
#
# Stdin: JSON от Claude Code (`{prompt, cwd, ...}`).
# Stdout: JSON `{hookSpecificOutput: {hookEventName, additionalContext}}` или пусто.

set -euo pipefail

input="$(cat)"
prompt="$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("prompt",""))')"
cwd="$(printf '%s' "$input" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("cwd",""))')"

# Только в UCP-проектах (есть симлинки на ucp-* скиллы).
[ -d "$cwd/.claude/skills" ] || exit 0
compgen -G "$cwd/.claude/skills/ucp-*" >/dev/null 2>&1 || exit 0

# Слишком короткие промпты — выходим.
[ "${#prompt}" -lt 15 ] && exit 0

# Не дублируем ucp-trigger-detect (фразы про «сделай сервис» — его зона).
if printf '%s' "$prompt" | grep -qiE '(сделай|сделаем|пишем|пиши|напиши|начн[еёa]м|сгенери[мт]?ь?|сгенерируй|собери)[^.!?]{0,30}сервис'; then
  exit 0
fi

emit_reminder() {
  cat <<'JSON'
{
  "hookSpecificOutput": {
    "hookEventName": "UserPromptSubmit",
    "additionalContext": "⚡ Похоже на задачу реализации Java/Spring-кода. До написания кода — вызови соответствующий `/ucp-*-design` скилл, не пиши от руки:\n- UseCase/Handler/Controller → `/ucp-pattern-design`\n- Новый агрегат / VO / Domain Event → `/ucp-ddd-tactical-design`\n- Новый REST-эндпоинт → `/ucp-api-design`\n- jOOQ-репозиторий → `/ucp-jooq-design`\n- DDL/миграция → `/ucp-pg-schema-design`\n- Outbound-интеграция → `/ucp-integration-design`\n\nТесты — TDD-first через `/ucp-test-design`, не после кода (см. `superpowers:test-driven-development`). Парный `/ucp-*-review` после design — для рукописного/изменённого кода обязательно, для DDL/миграций всегда.\n\nЕсли задача явно не подходит ни под один скилл — продолжай как обычно, этот reminder можно проигнорировать."
  }
}
JSON
}

# Pass 1: keyword regex.
pattern='(реализуй|реализовать|напиши|напишем|добавь|добавим|сделай|сделаем|создай|создадим|сгенери|сгенерируй)[^.!?]{0,60}(controller|контроллер|usecase|use[ -]?case|handler|хендлер|endpoint|эндпоинт|команд|запрос|агрегат|aggregate|repository|репозитор|сущност|valueobject|value[ -]?object|event|событие|миграц|migration|jooq|integration|интеграц|api|rest|dto|маппер|mapper)'
if printf '%s' "$prompt" | grep -qiE "$pattern"; then
  emit_reminder
  exit 0
fi

# Pass 2: LLM-классификатор только на «сомнительных» — длинный промпт + код-индикаторы.
[ "${#prompt}" -lt 40 ] && exit 0

code_hint='(java|spring|\.java|\.kt|class\s|method|метод|класс|пакет|package|src/main|src/test|gradle|maven|pom\.xml|@RestController|@Service|@Repository|@Component|bootstrap|liquibase|flyway|postgres|kafka|jooq|hexagonal|domain|агрегат|use[ -]?case|controller|handler|repository)'
if ! printf '%s' "$prompt" | grep -qiE "$code_hint"; then
  exit 0
fi

# Вызов Haiku — strict timeout, fail-silent.
classification="$(timeout 8 claude -p --model claude-haiku-4-5 --output-format text "В проекте Spring Boot/Java на UCP-методологии пользователь прислал следующий промпт. Это запрос на реализацию или модификацию кода (controller, handler, usecase, aggregate, repository, integration, DDL/миграция, тест)? Ответь СТРОГО одним словом: YES или NO.

Промпт: $prompt" 2>/dev/null || echo NO)"

if printf '%s' "$classification" | grep -qiE '^[[:space:]]*YES'; then
  emit_reminder
fi

exit 0
