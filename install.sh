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
#
# Дополнительно — устанавливает Eclipse jdtls (Java LSP) и mcp-language-server
# (LSP→MCP bridge) на машину один раз. В связке они дают Claude Code
# структурный анализ Java: find references, type hierarchy, refactoring.
# На macOS jdtls — через brew, mcp-language-server — через `go install`.
#
set -euo pipefail

PROJECT_DIR="${1:-.}"
SKILLS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$PROJECT_DIR" ]; then
  echo "ERROR: $PROJECT_DIR не существует" >&2
  exit 1
fi

PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"

if [ "$PROJECT_DIR" = "$SKILLS_DIR" ]; then
  echo "ERROR: PROJECT_DIR совпадает с папкой репо. Передайте путь до своего проекта." >&2
  exit 1
fi

mkdir -p "$PROJECT_DIR/.claude/skills" "$PROJECT_DIR/.claude/docs"

# Skills — симлинк всех 12 (или сколько есть на момент установки) ucp-* скиллов.
echo "==> Подключаю скиллы из $SKILLS_DIR/.claude/skills/"
SKILL_COUNT=0
for skill in "$SKILLS_DIR"/.claude/skills/*/; do
  name="$(basename "$skill")"
  ln -sfn "$skill" "$PROJECT_DIR/.claude/skills/$name"
  SKILL_COUNT=$((SKILL_COUNT + 1))
  echo "    ✓ $name"
done

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

# jdtls — Eclipse Java Language Server. Устанавливается ОДИН РАЗ на машину
# (не per project), поэтому проверка идемпотентная. Java-LSP даёт инструментам
# (Claude через MCP-bridge, IntelliJ, VS Code) структурный анализ кода:
# find references, type hierarchy, переименования с проверкой использований.
echo
echo "==> Проверяю Eclipse jdtls (Java LSP)"

if command -v jdtls >/dev/null 2>&1; then
  echo "    ✓ jdtls уже установлен: $(command -v jdtls)"
elif [ "$(uname)" = "Darwin" ]; then
  if command -v brew >/dev/null 2>&1; then
    echo "    устанавливаю через Homebrew (brew install jdtls) ..."
    if brew install jdtls >/tmp/jdtls-install.log 2>&1; then
      echo "    ✓ jdtls установлен: $(command -v jdtls)"
    else
      echo "    ⚠ brew install jdtls упал — лог: /tmp/jdtls-install.log"
      echo "      продолжаем без jdtls (скиллы работают, но без LSP-навигации)"
    fi
  else
    echo "    ⚠ Homebrew не найден. Установите brew, затем: brew install jdtls"
  fi
else
  echo "    ⚠ jdtls не установлен. На Linux:"
  echo "      • Arch:    sudo pacman -S jdtls"
  echo "      • Debian:  загрузите с https://download.eclipse.org/jdtls/snapshots/"
  echo "      • Прочее:  https://github.com/eclipse-jdtls/eclipse.jdt.ls#installation"
fi

# mcp-language-server — bridge между LSP-серверами (jdtls и др.) и Claude Code
# через MCP. Без него Claude jdtls сам не вызывает. Устанавливается через
# `go install` (других дистрибуций пока нет).
echo
echo "==> Проверяю mcp-language-server (LSP→MCP bridge)"

GOBIN="$(go env GOBIN 2>/dev/null || true)"
GOPATH_BIN="$(go env GOPATH 2>/dev/null || true)/bin"
MCP_LS_PATH=""
if command -v mcp-language-server >/dev/null 2>&1; then
  MCP_LS_PATH="$(command -v mcp-language-server)"
elif [ -n "$GOBIN" ] && [ -x "$GOBIN/mcp-language-server" ]; then
  MCP_LS_PATH="$GOBIN/mcp-language-server"
elif [ -n "$GOPATH_BIN" ] && [ -x "$GOPATH_BIN/mcp-language-server" ]; then
  MCP_LS_PATH="$GOPATH_BIN/mcp-language-server"
fi

if [ -n "$MCP_LS_PATH" ]; then
  echo "    ✓ mcp-language-server уже установлен: $MCP_LS_PATH"
elif command -v go >/dev/null 2>&1; then
  echo "    устанавливаю через go install ..."
  if go install github.com/isaacphi/mcp-language-server@latest >/tmp/mcp-ls-install.log 2>&1; then
    NEW_PATH="${GOBIN:-$GOPATH_BIN}/mcp-language-server"
    echo "    ✓ mcp-language-server установлен: $NEW_PATH"
    if ! command -v mcp-language-server >/dev/null 2>&1; then
      echo "    ⚠ ${GOBIN:-$GOPATH_BIN} не в PATH — добавьте: export PATH=\"\$PATH:${GOBIN:-$GOPATH_BIN}\""
    fi
  else
    echo "    ⚠ go install упал — лог: /tmp/mcp-ls-install.log"
  fi
else
  echo "    ⚠ Go не найден. Установите Go 1.21+ и затем:"
  echo "      go install github.com/isaacphi/mcp-language-server@latest"
  echo "      на macOS: brew install go"
fi

# Регистрация MCP в Claude Code для конкретного проекта (project scope).
# Записывается в $PROJECT_DIR/.mcp.json — коммитится с проектом.
# Используем $MCP_LS_PATH (учитывает $GOBIN/$GOPATH/bin), а не только PATH —
# go install часто кладёт бинарник вне PATH пользователя.
JDTLS_PATH="$(command -v jdtls 2>/dev/null || true)"
CLAUDE_BIN="$(command -v claude 2>/dev/null || true)"

echo
echo "==> Регистрирую language-server как MCP для $PROJECT_DIR"
if [ -z "$CLAUDE_BIN" ]; then
  echo "    ⚠ claude CLI не найден — пропускаю регистрацию. После установки Claude Code:"
  echo "      cd $PROJECT_DIR && claude mcp add language-server --scope project -- ${MCP_LS_PATH:-mcp-language-server} --workspace . --lsp ${JDTLS_PATH:-jdtls}"
elif [ -z "$MCP_LS_PATH" ] || [ -z "$JDTLS_PATH" ]; then
  echo "    ⚠ нет $([ -z "$MCP_LS_PATH" ] && echo "mcp-language-server")$([ -z "$MCP_LS_PATH" ] && [ -z "$JDTLS_PATH" ] && echo " и ")$([ -z "$JDTLS_PATH" ] && echo "jdtls") — пропускаю регистрацию"
elif [ -f "$PROJECT_DIR/.mcp.json" ] && grep -q '"language-server"' "$PROJECT_DIR/.mcp.json" 2>/dev/null; then
  echo "    ✓ MCP language-server уже зарегистрирован в .mcp.json"
else
  if (cd "$PROJECT_DIR" && "$CLAUDE_BIN" mcp add language-server --scope project \
        -- "$MCP_LS_PATH" --workspace "$PROJECT_DIR" --lsp "$JDTLS_PATH") >/tmp/mcp-add.log 2>&1; then
    echo "    ✓ MCP language-server зарегистрирован (project scope, .mcp.json)"
  else
    echo "    ⚠ claude mcp add упал — лог: /tmp/mcp-add.log. Зарегистрируйте вручную:"
    echo "      cd $PROJECT_DIR && claude mcp add language-server --scope project -- $MCP_LS_PATH --workspace . --lsp $JDTLS_PATH"
  fi
fi

echo
echo "✓ Готово. $SKILL_COUNT скиллов и $DOC_COUNT style-guide-ов подключены к $PROJECT_DIR."
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
echo "Без них работают 11 скиллов из 12 без потерь."
echo "ucp-spec-design без superpowers/context7 тоже работает — просто без"
echo "TodoWrite-планирования и без проверки актуальности версий библиотек."
echo
echo "─────────────────────────────────────────────────────────────────────"
echo "Дальше: запускайте скиллы из своего проекта — например /ucp-pattern-review"
echo "из чата Claude Code в $PROJECT_DIR."
echo "─────────────────────────────────────────────────────────────────────"
