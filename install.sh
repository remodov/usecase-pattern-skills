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

CHECK_MODE=false
POSITIONAL=()
while [ $# -gt 0 ]; do
  case "$1" in
    --check)
      CHECK_MODE=true
      shift
      ;;
    -h|--help)
      cat <<USAGE
Использование: install.sh [--check] [PROJECT_DIR]

Без флагов: устанавливает скиллы / docs / agents / hooks в PROJECT_DIR
(симлинками), мерж settings.json, managed-блоки в CLAUDE.md и .gitignore.
По умолчанию PROJECT_DIR = текущая директория.

  --check       Диагностический режим. Ничего не меняет, только проверяет
                состояние установки в PROJECT_DIR. Exit 0 если всё OK,
                exit 1 если найдены проблемы.

Переменные окружения:
  UCP_PROFILE   full (по умолчанию) | rest | data — набор скиллов.
  UCP_SKILLS    Глоб-паттерн поверх UCP_PROFILE (например 'ucp-pattern-* ucp-api-*').
USAGE
      exit 0
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done

PROJECT_DIR="${POSITIONAL[0]:-.}"
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

# --- --check: диагностика без модификаций ---
if [ "$CHECK_MODE" = true ]; then
  echo "==> Проверка установки UCP-скиллов в $PROJECT_DIR"
  echo
  PROBLEMS=0

  check_dir() {
    local dir="$1"
    local label="$2"
    if [ ! -d "$dir" ]; then
      echo "  ✗ $label: директория $dir не существует"
      PROBLEMS=$((PROBLEMS + 1))
      return
    fi
    local broken=0
    local count=0
    while IFS= read -r -d '' link; do
      count=$((count + 1))
      if [ ! -e "$link" ]; then
        echo "  ✗ broken symlink: $link → $(readlink "$link")"
        broken=$((broken + 1))
      fi
    done < <(find "$dir" -maxdepth 1 -mindepth 1 -type l -print0 2>/dev/null)
    if [ "$broken" -eq 0 ] && [ "$count" -gt 0 ]; then
      echo "  ✓ $label: $count симлинков, всё на месте"
    elif [ "$count" -eq 0 ]; then
      echo "  ⚠ $label: пусто (ожидались симлинки из $SKILLS_DIR)"
      PROBLEMS=$((PROBLEMS + 1))
    else
      echo "  ✗ $label: $broken из $count симлинков broken (см. список выше)"
      PROBLEMS=$((PROBLEMS + broken))
    fi
  }

  check_dir "$PROJECT_DIR/.claude/skills" "Skills (ucp-*)"
  check_dir "$PROJECT_DIR/.claude/docs"   "Docs (style-guides)"
  check_dir "$PROJECT_DIR/.claude/agents" "Agents"
  check_dir "$PROJECT_DIR/.claude/hooks"  "Hooks"

  # CLAUDE.md managed block
  if [ -f "$PROJECT_DIR/CLAUDE.md" ] && grep -qF "<!-- BEGIN ucp-skills" "$PROJECT_DIR/CLAUDE.md"; then
    echo "  ✓ CLAUDE.md: managed-блок ucp-skills присутствует"
  else
    echo "  ✗ CLAUDE.md: managed-блок ucp-skills отсутствует"
    PROBLEMS=$((PROBLEMS + 1))
  fi

  # .gitignore managed block
  if [ -f "$PROJECT_DIR/.gitignore" ] && grep -qF "# BEGIN ucp-skills" "$PROJECT_DIR/.gitignore"; then
    echo "  ✓ .gitignore: managed-блок ucp-skills присутствует"
  else
    echo "  ✗ .gitignore: managed-блок ucp-skills отсутствует"
    PROBLEMS=$((PROBLEMS + 1))
  fi

  # .claude/settings.json hooks
  if [ -f "$PROJECT_DIR/.claude/settings.json" ]; then
    if command -v python3 >/dev/null 2>&1; then
      hooks_status="$(PROJECT_DIR="$PROJECT_DIR" python3 - <<'PY'
import json, os, sys
from pathlib import Path

settings = Path(os.environ["PROJECT_DIR"]) / ".claude" / "settings.json"
try:
    data = json.loads(settings.read_text())
except Exception as e:
    print(f"PARSE_ERROR:{e}")
    sys.exit(0)

expected = [
    ("UserPromptSubmit", ".claude/hooks/ucp-trigger-detect.sh"),
    ("UserPromptSubmit", ".claude/hooks/impl-task-detect.sh"),
    ("SessionStart",     ".claude/hooks/ucp-session-check.sh"),
    ("PostToolUse",      ".claude/hooks/ucp-post-skill-review.sh"),
]
hooks = data.get("hooks", {})
missing = []
for event, cmd in expected:
    groups = hooks.get(event, [])
    found = any(
        any(h.get("command") == cmd for h in group.get("hooks", []))
        for group in groups
    )
    if not found:
        missing.append(f"{event}:{cmd}")

if missing:
    print("MISSING:" + ",".join(missing))
else:
    print("OK")
PY
)"
      case "$hooks_status" in
        OK)
          echo "  ✓ settings.json: все 4 хука зарегистрированы"
          ;;
        PARSE_ERROR:*)
          echo "  ✗ settings.json: невалидный JSON — ${hooks_status#PARSE_ERROR:}"
          PROBLEMS=$((PROBLEMS + 1))
          ;;
        MISSING:*)
          echo "  ✗ settings.json: отсутствуют хуки — ${hooks_status#MISSING:}"
          PROBLEMS=$((PROBLEMS + 1))
          ;;
      esac
    else
      echo "  ⚠ settings.json: python3 не найден, пропускаю проверку хуков"
    fi
  else
    echo "  ✗ .claude/settings.json не существует — хуки не зарегистрированы"
    PROBLEMS=$((PROBLEMS + 1))
  fi

  echo
  if [ "$PROBLEMS" -eq 0 ]; then
    echo "✓ Установка в порядке."
    exit 0
  else
    echo "✗ Найдено $PROBLEMS проблем(ы). Запусти '$0' (без --check) чтобы починить."
    exit 1
  fi
fi

mkdir -p "$PROJECT_DIR/.claude/skills" "$PROJECT_DIR/.claude/docs" "$PROJECT_DIR/.claude/agents" "$PROJECT_DIR/.claude/hooks"

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

# Hooks — детерминированные обработчики событий, которые Claude Code запускает
# на стороне harness (не модель). Закрывают зазоры, где модель может проигнори-
# ровать инструкцию из CLAUDE.md: триггер-детект цепочки UCP, проверка установки
# на старте сессии, обязательное ревью DDL/миграций.
echo
echo "==> Подключаю хуки из $SKILLS_DIR/.claude/hooks/"
HOOK_COUNT=0
for hook in "$SKILLS_DIR"/.claude/hooks/*.sh; do
  [ -e "$hook" ] || continue
  name="$(basename "$hook")"
  ln -sfn "$hook" "$PROJECT_DIR/.claude/hooks/$name"
  HOOK_COUNT=$((HOOK_COUNT + 1))
  echo "    ✓ $name"
done
if [ "$HOOK_COUNT" -eq 0 ]; then
  echo "    (хуков в репо пока нет)"
fi

# Регистрация хуков в .claude/settings.json — managed через Python: читаем
# существующий JSON (или создаём пустой), удаляем все entries, у которых command
# указывает на наш .claude/hooks/ucp-*.sh (идемпотентность при reinstall),
# добавляем актуальные. Пользовательские хуки не трогаем.
if [ "$HOOK_COUNT" -gt 0 ]; then
  echo
  echo "==> Регистрирую хуки в $PROJECT_DIR/.claude/settings.json"
  if ! command -v python3 >/dev/null 2>&1; then
    echo "    ⚠ python3 не найден — пропускаю регистрацию (хуки симлинками есть, но не зарегистрированы)"
  else
    PROJECT_DIR="$PROJECT_DIR" python3 - <<'PY'
import json, os
from pathlib import Path

project = Path(os.environ["PROJECT_DIR"])
settings = project / ".claude" / "settings.json"

data = json.loads(settings.read_text()) if settings.exists() else {}
data.setdefault("hooks", {})

managed = [
    ("UserPromptSubmit", ".claude/hooks/ucp-trigger-detect.sh", None),
    ("UserPromptSubmit", ".claude/hooks/impl-task-detect.sh", None),
    ("SessionStart",     ".claude/hooks/ucp-session-check.sh", None),
    ("PostToolUse",      ".claude/hooks/ucp-post-skill-review.sh", "Skill"),
]
managed_paths = {p for _, p, _ in managed}

# Идемпотентность: вычищаем старые managed-entries по командному пути,
# потом добавляем актуальные. Пользовательские хуки не трогаем.
for event in list(data["hooks"].keys()):
    new_groups = []
    for group in data["hooks"][event]:
        new_hooks = [h for h in group.get("hooks", [])
                     if h.get("command", "") not in managed_paths]
        if new_hooks:
            new_groups.append({**group, "hooks": new_hooks})
    if new_groups:
        data["hooks"][event] = new_groups
    else:
        del data["hooks"][event]

for event, cmd, matcher in managed:
    entry = {"hooks": [{"type": "command", "command": cmd}]}
    if matcher:
        entry["matcher"] = matcher
    data["hooks"].setdefault(event, []).append(entry)

settings.parent.mkdir(parents=True, exist_ok=True)
settings.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
print(f"    ✓ зарегистрировано {len(managed)} хуков")
PY
  fi
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
# Папки .claude/docs/, .claude/agents/, .claude/hooks/ принадлежат install.sh
# целиком — свои файлы туда не клади (.claude/skills/ остаётся открытым для
# custom-скиллов; .claude/settings.json пользовательский, install.sh только
# управляет в нём блоком hooks через идемпотентный python-мерж).
.claude/skills/ucp-*
.claude/docs/
.claude/agents/
.claude/hooks/
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
echo "✓ Готово. $SKILL_COUNT скиллов, $AGENT_COUNT агентов, $HOOK_COUNT хуков и $DOC_COUNT style-guide-ов подключены к $PROJECT_DIR."
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
