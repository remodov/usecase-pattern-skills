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

# --- helpers ---

# manage_block <target_path> <begin_marker> <end_marker> <block_content>
# Идемпотентно управляет marker-managed-блоком в текстовом файле:
#   - target отсутствует → создаём файл с блоком как единственным содержимым;
#   - target есть, маркеров нет → дописываем блок в конец (с разделителем);
#   - маркеры есть → in-place заменяем содержимое между маркерами (включая
#     сами маркеры), остальной контент файла сохраняется без изменений.
# Контент блока ($4) передаётся строкой (heredoc / $(cat file)), а не путём.
# Через awk-ENVIRON, чтобы избежать интерпретации escape-последовательностей
# в значениях, передаваемых через awk -v.
manage_block() {
  local target="$1"
  local begin="$2"
  local end="$3"
  local block="$4"

  if [ ! -f "$target" ]; then
    printf '%s\n' "$block" > "$target"
    echo "    ✓ создан $target с блоком"
    return
  fi

  if grep -qF -- "$begin" "$target"; then
    local tmp
    tmp="$(mktemp)"
    BLOCK="$block" awk -v begin="$begin" -v end="$end" '
      index($0, begin) && !replaced {
        print ENVIRON["BLOCK"]
        replaced = 1
        in_block = 1
        next
      }
      in_block {
        if (index($0, end)) in_block = 0
        next
      }
      { print }
    ' "$target" > "$tmp"
    mv "$tmp" "$target"
    echo "    ✓ обновлён блок в $target (контент вне маркеров сохранён)"
  else
    printf '\n%s\n' "$block" >> "$target"
    echo "    ✓ блок дописан в $target (существующий контент сохранён)"
  fi
}

PROJECT_DIR="${1:-.}"
SKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- профиль скиллов: резолвим UCP_PROFILE/UCP_SKILLS в список glob-паттернов ---
# UCP_SKILLS, если задан, перекрывает UCP_PROFILE.
if [ -n "${UCP_SKILLS:-}" ]; then
  SKILL_GLOBS="$UCP_SKILLS"
  SKILL_PROFILE_LABEL="custom: $UCP_SKILLS"
else
  case "${UCP_PROFILE:-full}" in
    full) SKILL_GLOBS='*' ;;
    rest) SKILL_GLOBS='ucp-spec-* ucp-pattern-* ucp-api-* ucp-auth-* ucp-bootstrap-* ucp-jooq-* ucp-pg-* ucp-validation-* ucp-error-handling-* ucp-test-* ucp-java-style-*' ;;
    data) SKILL_GLOBS='ucp-pg-* ucp-jooq-* ucp-caching-* ucp-observability-* ucp-bootstrap-* ucp-java-style-*' ;;
    *) echo "ERROR: неизвестный UCP_PROFILE='$UCP_PROFILE' (full|rest|data или используйте UCP_SKILLS)" >&2; exit 1 ;;
  esac
  SKILL_PROFILE_LABEL="${UCP_PROFILE:-full}"
fi

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
echo "==> Подключаю скиллы из $SKILLS_DIR/.claude/skills/ (профиль: $SKILL_PROFILE_LABEL)"
for old in "$PROJECT_DIR"/.claude/skills/ucp-*; do
  [ -L "$old" ] || continue
  case "$(readlink "$old")" in "$SKILLS_DIR"/.claude/skills/*) rm "$old" ;; esac
done
SKILL_COUNT=0
_seen_skills=" "
# read -ra сплитит по IFS (whitespace) без glob-expansion против cwd:
# `*` в SKILL_GLOBS — это паттерн для skills/, не маска для текущей директории.
read -ra _glob_patterns <<< "$SKILL_GLOBS"
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

CLAUDE_BLOCK_CONTENT="$(cat "$CLAUDE_TEMPLATE")"
manage_block "$CLAUDE_MD" "$BEGIN_MARKER" "$END_MARKER" "$CLAUDE_BLOCK_CONTENT"

# .gitignore — managed-блок. install.sh раскладывает в $PROJECT_DIR/.claude/
# симлинки на скиллы, агентов и style-guide-снапшоты. В git-репо проекта они
# появляются как untracked и засоряют статус. Управляемый блок исключает их
# из git, не трогая остальной .gitignore проекта.
echo
echo "==> Управляю блоком ucp-skills в $PROJECT_DIR/.gitignore"

GITIGNORE_BEGIN_MARKER="# BEGIN ucp-skills (managed by claude-code-java/install.sh)"
GITIGNORE_END_MARKER="# END ucp-skills"
GITIGNORE_BLOCK="$(cat <<'EOF'
# BEGIN ucp-skills (managed by claude-code-java/install.sh)
# Папки .claude/docs/ и .claude/agents/ принадлежат install.sh целиком —
# свои файлы туда не клади (.claude/skills/ остаётся открытым для custom-скиллов).
.claude/skills/ucp-*
.claude/docs/
.claude/agents/
# END ucp-skills
EOF
)"

manage_block "$PROJECT_DIR/.gitignore" \
  "$GITIGNORE_BEGIN_MARKER" \
  "$GITIGNORE_END_MARKER" \
  "$GITIGNORE_BLOCK"

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
  # remove + add — идемпотентно (если уже зарегистрирован, чистим и ставим заново).
  # if (...) — чтобы set -e в subshell не убивал внешний скрипт при падении
  # claude mcp add, а else-ветка с warn-сообщением была достижимой.
  if (
    cd "$PROJECT_DIR"
    "$CLAUDE_BIN" mcp remove gitlab >/dev/null 2>&1 || true
    "$CLAUDE_BIN" mcp add gitlab \
      -e "GITLAB_API_URL=$GITLAB_API_URL" \
      -e "GITLAB_PERSONAL_ACCESS_TOKEN=$GITLAB_TOKEN" \
      -- npx -y --registry https://registry.npmjs.org @zereight/mcp-gitlab
  ) >/tmp/mcp-gitlab-add.log 2>&1; then
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
