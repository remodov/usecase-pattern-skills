---
name: ucp-install
description: Установить или обновить UCP-скиллы в проект — выбрать coding-агента, детект языка и track, подтвердить профиль, запустить install.sh и проверить результат.
when_to_use: Явный запрос установки/обновления — «поставь/обнови UCP-скиллы», «добавь методологию в проект», «установи скиллы в эту папку».
lang: any
track: any
argument-hint: [target-dir]
allowed-tools: Read Glob Grep Bash
---

# Установка UCP-скиллов в проект

Ты ставишь UCP-скиллы в проект пользователя, сам проводя «интервью» вместо bash-`--wizard`: выбираешь целевого агента, детектишь параметры проекта, показываешь dry-run и только после подтверждения запускаешь `install.sh`. Аргумент — каталог-цель (если не задан — спроси или возьми текущий проект).

## Шаги

1. **Найди `install.sh` репозитория скиллов.** Возьми реальный путь текущего `SKILL.md` из каталога скиллов агента и разреши симлинки (`realpath` или `Path.resolve()`). Канонический путь — `<repo>/.claude/skills/ucp-install/SKILL.md`, поэтому `install.sh` находится на три уровня выше каталога `ucp-install`. Проверь существование; если раскладка отличается, спроси путь к репозиторию у пользователя.

2. **Определи каталог-цель и целевого агента.** Каталог бери из `$ARGUMENTS`, иначе используй текущий проект. По умолчанию выбирай агента, в котором выполняется текущая сессия; если он не определяется или нужен другой — спроси. Список целей: `python3 <repo>/tools/agent_targets.py list`.

3. **Авто-детект (не спрашивай то, что видно):**
   - **Язык:** `pyproject.toml`/`uv.lock`/`setup.py` → `python`; `build.gradle*`/`pom.xml` → `java`; `go.mod` → `go`; `package.json`+`tsconfig.json` → `node`.
   - **Специализация (track):** `playwright.config.*`/`cypress.config.*` → `e2e`; `package.json` с `react`/`vue` + `index.html`/`src/components` → `frontend`; иначе → `backend`.
   - Несколько маркеров (моно-репо: backend и frontend) — предложи мульти-трек через запятую.

4. **Покажи срез через dry-run и подтверди.** Выполни:
   ```bash
   UCP_TRACK=<track> UCP_LANG=<lang> bash <repo>/install.sh --target <agent> --dry-run <target-dir>
   ```
   Dry-run ничего не меняет и показывает целевые пути, выбранные скиллы и неподдерживаемые capabilities. Спроси **design-генераторы**: `UCP_DESIGN=all` (для всех включённых concern'ов) или `chain` (только цепочка `ucp-new-service`; review ставится всегда). Ручные поправки — `UCP_CONCERNS_ON` / `UCP_CONCERNS_OFF`. Фиксированные профили `full` / `rest` / `data` — только если пользователь их просит.

5. **Покажи команду и запусти после явного подтверждения:**
   ```bash
   UCP_TRACK=<track> UCP_LANG=<lang> UCP_DESIGN=<all|chain> bash <repo>/install.sh --target <agent> <target-dir>
   ```

6. **Проверь результат:**
   ```bash
   UCP_TRACK=<track> UCP_LANG=<lang> bash <repo>/install.sh --target <agent> --check <target-dir>
   ```
   Кратко резюмируй: целевого агента, количество скиллов, срез (track/lang/profile), native paths и какие capabilities не поддерживаются адаптером.

## Важно

- **Это side-effecting** — install.sh создаёт симлинки или target-specific agent files, меняет native instruction file и `.gitignore`; для Claude также обновляет hooks и при наличии доступа регистрирует MCP. Запускай только после подтверждения.
- **Холодная установка:** `ucp-install` должен быть доступен до проектной установки. Можно один раз подключить его в user skills текущего агента: Claude — `~/.claude/skills/`, Kimi — `~/.kimi-code/skills/` или `~/.agents/skills/`, Codex и совместимые клиенты — `~/.agents/skills/`.
- **Смена конфигурации** (агент, трек, язык, профиль) — повторный запуск с новыми параметрами; install.sh идемпотентен и чистит свои прежние managed-файлы.
- Не редактируй install.sh из этого скилла — только запускай. Меняется install.sh отдельно.

$ARGUMENTS
