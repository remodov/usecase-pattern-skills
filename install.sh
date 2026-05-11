#!/usr/bin/env bash
#
# install.sh — подключение скиллов и style-guide-снапшотов в проект.
#
# Использование:
#   ./install.sh [PROJECT_DIR]
#
# Если PROJECT_DIR не указан, используется текущая директория.
# Скрипт создаёт симлинки на .claude/skills/* и .claude/docs/*.md из этого репо
# в указанный проект. Симлинки означают, что обновления в этом репо
# автоматически прилетят в проект — без ручного re-копирования.
# Дополнительно — регистрирует GitLab MCP, если есть токен.
#
# Профиль скиллов (опционально) — чтобы не тащить все ~45 ucp-* скиллов в проект,
# которому нужна часть (меньше скилл-описаний в always-loaded контексте каждой
# сессии):
#   UCP_PROFILE=rest  ./install.sh ~/proj   # REST/UCP-сервис: spec+pattern+api+auth+jooq+pg+validation+test+java-style
#   UCP_PROFILE=data  ./install.sh ~/proj   # data-heavy: pg-*+jooq+caching+observability+java-style
#   UCP_PROFILE=full  ./install.sh ~/proj   # всё (по умолчанию)
#   UCP_SKILLS='ucp-pattern-* ucp-api-* ucp-jooq-*'  ./install.sh ~/proj   # произвольный набор глобов
# UCP_SKILLS перекрывает UCP_PROFILE. Реви-пары устанавливаются вместе со своими
# design-скиллами автоматически (для glob 'ucp-api-*' попадут и design, и review).
#
set -euo pipefail

PROJECT_DIR="${1:-.}"
SKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- профиль скиллов: резолвим в список glob-паттернов в $SKILL_GLOBS ---
case "${UCP_PROFILE:-full}" in
  full) PROFILE_GLOBS='*' ;;
  rest) PROFILE_GLOBS='ucp-spec-* ucp-pattern-* ucp-api-* ucp-auth-* ucp-bootstrap-* ucp-jooq-* ucp-pg-* ucp-validation-* ucp-error-handling-* ucp-test-* ucp-java-style-*' ;;
  data) PROFILE_GLOBS='ucp-pg-* ucp-jooq-* ucp-caching-* ucp-observability-* ucp-bootstrap-* ucp-java-style-*' ;;
  *) echo "ERROR: неизвестный UCP_PROFILE='$UCP_PROFILE' (full|rest|data или используйте UCP_SKILLS)" >&2; exit 1 ;;
esac
SKILL_GLOBS="${UCP_SKILLS:-$PROFILE_GLOBS}"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: $PROJECT_DIR не существует" >&2
  exit 1
fi

PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

if [ "$PROJECT_DIR" = "$SKILLS_DIR" ]; then
  echo "ERROR: PROJECT_DIR совпадает с папкой репо. Передайте путь до своего проекта." >&2
  exit 1
fi

mkdir -p "$PROJECT_DIR/.claude/skills" "$PROJECT_DIR/.claude/docs" "$PROJECT_DIR/.claude/agents"

# Skills — симлинк ucp-* скиллов по выбранному профилю (по умолчанию — все).
# Сначала чистим существующие ucp-* симлинки, указывающие в этот репо, — иначе
# при смене профиля (full -> rest) останутся stale-симлинки на лишние скиллы.
echo "==> Подключаю скиллы из $SKILLS_DIR/.claude/skills/ (профиль: ${UCP_SKILLS:+custom}${UCP_SKILLS:-${UCP_PROFILE:-full}})"
for old in "$PROJECT_DIR"/.claude/skills/ucp-*; do
  [ -L "$old" ] || continue
  case "$(readlink "$old")" in "$SKILLS_DIR"/.claude/skills/*) rm "$old" ;; esac
done
SKILL_COUNT=0
_seen_skills=" "
set -f                          # отключаем pathname-expansion: '*' в SKILL_GLOBS — это паттерн,
_glob_patterns=( $SKILL_GLOBS ) #   а не маска для cwd; раскрываем его только против skills/
set +f
for glob in "${_glob_patterns[@]}"; do
  for skill in "$SKILLS_DIR"/.claude/skills/$glob/; do
    [ -d "$skill" ] || continue
    name="$(basename "$skill")"
    case "$_seen_skills" in *" $name "*) continue ;; esac
    _seen_skills="$_seen_skills$name "
    ln -sfn "$skill" "$PROJECT_DIR/.claude/skills/$name"
    SKILL_COUNT=$((SKILL_COUNT + 1))
    echo "    ✓ $name"
  done
done
if [ "$SKILL_COUNT" -eq 0 ]; then
  echo "ERROR: ни один скилл не подошёл под '$SKILL_GLOBS'" >&2
  exit 1
fi

# Agents — кастомные субагенты Claude Code (например ucp-implementer:
# Sonnet-исполнитель, который пишет код по плану от Opus).
echo
echo "==> Подключаю агентов из $SKILLS_DIR/.claude/agents/"
AGENT_COUNT=0
for agent in "$SKILLS_DIR"/.claude/agents/*.md; do
  [ -e "$agent" ] || continue
  name="$(basename "$agent")"
  ln -sfn "$agent" "$PROJECT_DIR/.claude/agents/$name"
  AGENT_COUNT=$((AGENT_COUNT + 1))
  echo "    ✓ $name"
done
if [ "$AGENT_COUNT" -eq 0 ]; then
  echo "    (агентов в репо пока нет)"
fi

# Cleanup: старые версии install.sh симлинковали style-guide-ы в <project>/docs/.
# Это засоряло пользовательскую docs/ — теперь они переехали в .claude/docs/.
# Удаляем старые симлинки если они есть и указывают именно на наши snapshot-ы.
echo
echo "==> Чищу старые симлинки в $PROJECT_DIR/docs/ (если есть)"
CLEANED=0
for doc in "$SKILLS_DIR"/.claude/docs/*.md; do
  name="$(basename "$doc")"
  old_link="$PROJECT_DIR/docs/$name"
  if [ -L "$old_link" ] && [ "$(readlink "$old_link")" = "$doc" ]; then
    rm "$old_link"
    CLEANED=$((CLEANED + 1))
    echo "    × removed $old_link"
  fi
done
if [ "$CLEANED" -eq 0 ]; then
  echo "    (старых симлинков нет — чистая установка)"
fi

# Docs — снапшоты style-guide-ов, которые скиллы читают по .claude/docs/*.md.
# Они инструментальные (не часть проектной документации), поэтому идут под
# .claude/docs/, рядом со скиллами, а не в пользовательскую docs/.
echo
echo "==> Подключаю style-guide-снапшоты в $PROJECT_DIR/.claude/docs/"
DOC_COUNT=0
for doc in "$SKILLS_DIR"/.claude/docs/*.md; do
  name="$(basename "$doc")"
  ln -sfn "$doc" "$PROJECT_DIR/.claude/docs/$name"
  DOC_COUNT=$((DOC_COUNT + 1))
  echo "    ✓ $name"
done

# Obsidian vault bootstrap — конфигурация .obsidian/ для папки docs/spec/.
# Делаем симлинк на бутстрап-директорию; ucp-spec-design при генерации
# спеки скопирует её содержимое в docs/spec/.obsidian/.
echo
echo "==> Подключаю Obsidian-bootstrap в $PROJECT_DIR/.claude/docs/obsidian-vault-bootstrap"
ln -sfn "$SKILLS_DIR/.claude/docs/obsidian-vault-bootstrap" \
        "$PROJECT_DIR/.claude/docs/obsidian-vault-bootstrap"
echo "    ✓ obsidian-vault-bootstrap (.obsidian/types.json + Dataview + Graph)"

# CLAUDE.md — точка входа для Claude в проекте-потребителе. install.sh
# управляет блоком между маркерами BEGIN ucp-skills / END ucp-skills:
# создаёт файл, дописывает блок, либо in-place заменяет существующий блок.
# Контент вне маркеров сохраняется — это место пользователя.
echo
echo "==> Управляю блоком ucp-skills в $PROJECT_DIR/CLAUDE.md"

CLAUDE_MD="$PROJECT_DIR/CLAUDE.md"
CLAUDE_TEMPLATE="$SKILLS_DIR/templates/claude-block.md"
BEGIN_MARKER="<!-- BEGIN ucp-skills (managed by claude-code-java/install.sh) -->"
END_MARKER="<!-- END ucp-skills -->"

if [ ! -f "$CLAUDE_TEMPLATE" ]; then
  echo "ERROR: шаблон $CLAUDE_TEMPLATE не найден" >&2
  exit 1
fi

if [ ! -f "$CLAUDE_MD" ]; then
  cp "$CLAUDE_TEMPLATE" "$CLAUDE_MD"
  echo "    ✓ создан $CLAUDE_MD с блоком ucp-skills"
elif grep -qF "$BEGIN_MARKER" "$CLAUDE_MD"; then
  TMP="$(mktemp)"
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" -v block_file="$CLAUDE_TEMPLATE" '
    BEGIN {
      while ((getline line < block_file) > 0) {
        block = block (block_loaded ? "\n" : "") line
        block_loaded = 1
      }
      close(block_file)
    }
    index($0, begin) && !replaced {
      print block
      replaced = 1
      in_block = 1
      next
    }
    in_block {
      if (index($0, end)) in_block = 0
      next
    }
    { print }
  ' "$CLAUDE_MD" > "$TMP"
  mv "$TMP" "$CLAUDE_MD"
  echo "    ✓ обновлён блок ucp-skills в $CLAUDE_MD (контент вне маркеров сохранён)"
else
  printf '\n' >> "$CLAUDE_MD"
  cat "$CLAUDE_TEMPLATE" >> "$CLAUDE_MD"
  echo "    ✓ блок ucp-skills дописан в $CLAUDE_MD (существующий контент сохранён)"
fi

# GitLab MCP (zereight/mcp-gitlab) — личный токен. Читаем из env или
# защищённого файла. Никогда не храним токен в этом скрипте — репо публичный.
CLAUDE_BIN="$(command -v claude 2>/dev/null || true)"
echo
echo "==> Регистрирую GitLab MCP для $PROJECT_DIR"

GITLAB_API_URL_DEFAULT="https://gitlab.mosmetro.tech/api/v4"
GITLAB_API_URL="${GITLAB_API_URL:-$GITLAB_API_URL_DEFAULT}"
GITLAB_TOKEN_FILE="${GITLAB_TOKEN_FILE:-$HOME/.config/usecase-pattern-skills/gitlab-token}"

GITLAB_TOKEN=""
if [ -n "${GITLAB_PERSONAL_ACCESS_TOKEN:-}" ]; then
  GITLAB_TOKEN="$GITLAB_PERSONAL_ACCESS_TOKEN"
elif [ -r "$GITLAB_TOKEN_FILE" ]; then
  GITLAB_TOKEN="$(cat "$GITLAB_TOKEN_FILE")"
fi

if [ -z "$CLAUDE_BIN" ]; then
  echo "    ⚠ claude CLI не найден — пропускаю регистрацию GitLab MCP"
elif [ -z "$GITLAB_TOKEN" ]; then
  echo "    ⚠ GitLab token не найден. Положите его в файл (read для пользователя):"
  echo "      mkdir -p \"$(dirname "$GITLAB_TOKEN_FILE")\""
  echo "      printf 'glpat-XXXXXXXX' > \"$GITLAB_TOKEN_FILE\" && chmod 600 \"$GITLAB_TOKEN_FILE\""
  echo "    Или передайте через env:"
  echo "      GITLAB_PERSONAL_ACCESS_TOKEN=glpat-XXXX ./install.sh $PROJECT_DIR"
  echo "    Альтернативный API URL — переменная GITLAB_API_URL (по умолчанию $GITLAB_API_URL_DEFAULT)."
elif ! command -v npx >/dev/null 2>&1; then
  echo "    ⚠ npx не найден (нужен для @zereight/mcp-gitlab). Установите Node.js (brew install node)."
else
  # remove + add — идемпотентно (если уже зарегистрирован, чистим и ставим заново)
  (
    cd "$PROJECT_DIR"
    "$CLAUDE_BIN" mcp remove gitlab >/dev/null 2>&1 || true
    "$CLAUDE_BIN" mcp add gitlab \
      -e "GITLAB_API_URL=$GITLAB_API_URL" \
      -e "GITLAB_PERSONAL_ACCESS_TOKEN=$GITLAB_TOKEN" \
      -- npx -y --registry https://registry.npmjs.org @zereight/mcp-gitlab
  ) >/tmp/mcp-gitlab-add.log 2>&1
  if [ $? -eq 0 ]; then
    echo "    ✓ GitLab MCP зарегистрирован ($GITLAB_API_URL)"
  else
    echo "    ⚠ claude mcp add gitlab упал — лог: /tmp/mcp-gitlab-add.log"
  fi
fi

echo
echo "✓ Готово. $SKILL_COUNT скиллов, $AGENT_COUNT агентов и $DOC_COUNT style-guide-ов подключены к $PROJECT_DIR."
echo
echo "Проверка:"
echo "    ls -la $PROJECT_DIR/.claude/skills"
echo "    ls -la $PROJECT_DIR/.claude/docs"
echo
echo "─────────────────────────────────────────────────────────────────────"
echo "ОПЦИОНАЛЬНО: плагины Claude Code, которые улучшают ucp-spec-design"
echo "─────────────────────────────────────────────────────────────────────"
echo
echo "  • superpowers — TodoWrite, планирование, TDD."
echo "    claude plugin marketplace add obra/superpowers-marketplace"
echo "    claude plugin install superpowers@superpowers-marketplace"
echo
echo "  • context7 (MCP) — актуальная документация библиотек"
echo "    (Spring Boot, jOOQ и т.п.), чтобы не протухала в спеке."
echo "    claude mcp add context7 -- npx -y @upstash/context7-mcp"
echo
echo "Почти все скиллы работают без внешних плагинов. ucp-spec-design без"
echo "superpowers/context7 тоже работает — просто без TodoWrite-планирования"
echo "и без проверки актуальности версий библиотек."
echo
echo "─────────────────────────────────────────────────────────────────────"
echo "Дальше: запускайте скиллы из своего проекта — например /ucp-pattern-review"
echo "из чата Claude Code в $PROJECT_DIR."
echo "─────────────────────────────────────────────────────────────────────"
