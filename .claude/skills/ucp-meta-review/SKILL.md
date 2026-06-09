---
name: ucp-meta-review
lang: any
track: any
description: Ревью контрибуции в корпус методологии на соответствие authoring-contract (коды R-META-*) — раскладка docs/, формат rules-index, нейтральность shared-индекса, реестр кодов, парность/нейминг и frontmatter-бюджет скиллов.
when_to_use: Изменения в .claude/docs/** или .claude/skills/** — гейт каждого PR в репо методологии, особенно при добавлении нового языка или трека.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(git log*)
---

# Ревью соответствия методологии (meta-review)

Ты ревьюишь **сам корпус методологии** — новый/изменённый гайд или скилл — на соответствие
`authoring-contract.md`. Это не ревью прикладного кода сервиса; это проверка, что контрибуция
(на любом языке) написана в едином стиле и не разъедет методологию. Главный сценарий — когда
лид другого языка (Python и т.п.) добавляет свою часть.

## Зависимости

- **`.claude/docs/_meta/authoring-contract.md`** — контракт, против которого ревьюишь (источник правды по стилю).
- **`.claude/docs/_meta/rule-code-registry.md`** — реестр префиксов (shared / per-lang).
- **`.claude/docs/shared/review-finding-format.md`** — формат findings (`RFF-*`).

## Инструкции

1. **Прочти** `authoring-contract.md` и `rule-code-registry.md` целиком. Это критерии. Цитируй коды `R-META-*` ниже в каждой находке, плюс ссылайся на §-пункт контракта.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе `git diff` против main/master — изменения в `.claude/docs/**` и `.claude/skills/**`.

3. **Прогон по правилам R-META-*** (ниже). Для каждой находки — формат по `RFF-*` (обязательна Read-проверка строки).

   3a. **Сначала прогони D-гейт** (граница нейтральности, machine-check для `R-META-FMT-X1`):
   `python3 .claude/docs/_meta/check-shared-neutral.py` — он ловит framework-токены в shared rules-index
   (с учётом dual-illustration whitelist). Все его находки включи в отчёт как `R-META-FMT-X1`. Помни про
   классификацию kind (`authoring-contract` §11): для IMPL-SHAPED concern'ов остаточный mechanism-вокабуляр
   допустим (это принцип, не дубль реализации), для NEUTRAL — нет.

4. **Сгруппируй вывод**: критично (ломает единство — параллельные коды, нет пары, не тот нейминг), важно (формат, генерализация), мелкое (стиль формулировок).

## Правила

### Раскладка и парность — `R-META-LAYOUT-*`
- **R-META-LAYOUT-1.** Shared-concern: `<concern>/<concern>-rules.md` (индекс) + `<concern>/<lang>/<concern>-style-guide.md` на каждый язык (§2).
- **R-META-LAYOUT-2.** Языко-специфичный concern (style/bootstrap/persistence-impl/test-strategy): пара `<lang>/...` без shared rules-index (§2).
- **R-META-LAYOUT-3.** Standalone без пары (`review-finding-format`, `usecase-spec-template`) — плоско в корне docs/.
- **R-META-LAYOUT-X1.** ❌ Гайд без парного rules-index (для shared) или без пары style-guide (§9).

### Формат rules-index — `R-META-FMT-*`
- **R-META-FMT-1.** Шапка-blockquote: что это, ссылки на per-language style-guide, конвенция кодов, сшивки (§3).
- **R-META-FMT-2.** Разделы `## N.`, внутри `**MUST:**` / `**MUST NOT:**`, буллеты `- **<CODE>.** формулировка` (§3).
- **R-META-FMT-3.** Конвенция кодов: `<PREFIX>-<N>` обязательно, `<PREFIX>-X<N>` антипаттерн (§5).
- **R-META-FMT-X1.** ❌ Shared rules-index содержит framework-специфичные токены (аннотации, имена классов фреймворка) вместо нейтрального интента — должно уйти в per-language style-guide (§3, пример — `error-handling`).

### Языковой style-guide — `R-META-LANG-*`
- **R-META-LANG-1.** Первая строка ссылается на shared rules-index («Реализация контракта `../<concern>-rules.md`») (§4).
- **R-META-LANG-2.** Те же коды и разделы, что в shared rules; под кодом — реализация + PREFER/AVOID (§4).
- **R-META-LANG-3.** В конце — «Чеклист подключения (<Lang>/<framework>)» (§4).

### Коды правил — `R-META-CODE-*`
- **R-META-CODE-1.** Каждый используемый префикс зарегистрирован в `rule-code-registry.md` со scope (shared/lang) (§5).
- **R-META-CODE-2.** Новый код — сначала запись в реестр, потом использование.
- **R-META-CODE-X1.** ❌ Параллельные коды на язык для одного shared-концепта (напр. отдельный `R-ERR-PY-*` вместо переиспользования `R-ERR-*`) — нарушает cross-language единство (§5, §9).

### Скиллы — `R-META-SKILL-*`
- **R-META-SKILL-1.** Нейминг: bare `ucp-<concern>-{design,review}` = Java по умолчанию; другие языки — `ucp-<lang>-<concern>-{design,review}` (§6).
- **R-META-SKILL-2.** Парность: каждый design имеет review (§6).
- **R-META-SKILL-3.** Скилл читает shared rules-index + свой языковой style-guide, цитирует коды, on-demand-указатель на полный гайд (§6).
- **R-META-SKILL-4.** SKILL.md: человекочитаемый текст по-русски, идентификаторы/тулы/коды — латиницей (§6).
- **R-META-SKILL-5.** Frontmatter-метка `lang:` (`any`/`java`/`python`/`node`/`go`) проставлена корректно: agnostic (spec/arch/meta/new-service) → `any`; языковой скилл → свой язык; bare java-скилл — можно без метки (= java) (§6). Языковой скилл без метки или с чужим значением — нарушение.
- **R-META-SKILL-6.** Листинг-бюджет: `description` ≤ 250 символов (суть: глагол + объект + стек-маркер + код-префикс), `when_to_use` ≤ 160 (триггер-фразы, файловый контекст); перечни подгрупп правил и cross-ref'ы — в теле SKILL.md, не во frontmatter (§6).
- **R-META-SKILL-X1.** ❌ design-скилл без парного review.

### Ось зрелости — `R-META-TIER-1`
- **R-META-TIER-1.** Используется единый словарь уровней 0–3, не параллельные шкалы (§7).

## Формат вывода

Список findings по `RFF-*` (с полем `Строка`, Read-проверкой), затем сводка `критично/важно/мелкое`
и вердикт: можно ли мёржить контрибуцию или нужны правки. Не вноси правки сам — только ревью.

$ARGUMENTS
