#!/usr/bin/env bash
#
# install.sh — подключение скиллов и style-guide-снапшотов в проект.
#
# Использование:
#   ./install.sh [PROJECT_DIR]
#
# Если PROJECT_DIR не указан, используется текущая директория.
# Скрипт создаёт симлинки на .claude/skills/* и docs/*.md из этого репо
# в указанный проект. Симлинки означают, что обновления в этом репо
# автоматически прилетят в проект — без ручного re-копирования.
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
for doc in "$SKILLS_DIR"/docs/*.md; do
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
for doc in "$SKILLS_DIR"/docs/*.md; do
  name="$(basename "$doc")"
  ln -sfn "$doc" "$PROJECT_DIR/.claude/docs/$name"
  DOC_COUNT=$((DOC_COUNT + 1))
  echo "    ✓ $name"
done

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
echo "  • superpowers — добавляет TodoWrite и общие практики планирования."
echo "    Установка: claude plugins install superpowers"
echo
echo "  • context7 (MCP) — подтягивает актуальные версии библиотек"
echo "    (Spring Boot, jOOQ и т.п.) в спеку, чтобы не протухали."
echo "    Установка: claude mcp add context7"
echo
echo "Без них работают 11 скиллов из 12 без потерь."
echo "ucp-spec-design без superpowers/context7 тоже работает — просто без"
echo "TodoWrite-планирования и без проверки актуальности версий библиотек."
echo
echo "─────────────────────────────────────────────────────────────────────"
echo "Дальше: запускайте скиллы из своего проекта — например /ucp-pattern-review"
echo "из чата Claude Code в $PROJECT_DIR."
echo "─────────────────────────────────────────────────────────────────────"
