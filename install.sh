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

mkdir -p "$PROJECT_DIR/.claude/skills" "$PROJECT_DIR/docs"

# Skills — симлинк всех 12 (или сколько есть на момент установки) ucp-* скиллов.
echo "==> Подключаю скиллы из $SKILLS_DIR/.claude/skills/"
SKILL_COUNT=0
for skill in "$SKILLS_DIR"/.claude/skills/*/; do
  name="$(basename "$skill")"
  ln -sfn "$skill" "$PROJECT_DIR/.claude/skills/$name"
  SKILL_COUNT=$((SKILL_COUNT + 1))
  echo "    ✓ $name"
done

# Docs — снапшоты style-guide-ов, которые скиллы читают по docs/*.md.
echo
echo "==> Подключаю style-guide-снапшоты из $SKILLS_DIR/docs/"
DOC_COUNT=0
for doc in "$SKILLS_DIR"/docs/*.md; do
  name="$(basename "$doc")"
  ln -sfn "$doc" "$PROJECT_DIR/docs/$name"
  DOC_COUNT=$((DOC_COUNT + 1))
  echo "    ✓ $name"
done

echo
echo "✓ Готово. $SKILL_COUNT скиллов и $DOC_COUNT style-guide-ов подключены к $PROJECT_DIR."
echo
echo "Проверка:"
echo "    ls -la $PROJECT_DIR/.claude/skills"
echo "    ls -la $PROJECT_DIR/docs"
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
