# Authoring Contract — как писать гайды и скиллы в этой методологии

Единый стиль обеспечивается **не структурой папок, а этим контрактом** + парным `ucp-meta-review`.
Любой новый гайд / скилл (на любом языке) обязан ему соответствовать. Питон-лид (и любой контрибьютор
другого языка) пишет строго по нему; meta-review гейтит каждый PR.

---

## 1. Два слоя методологии

| Слой | Что | Где живёт |
|---|---|---|
| **Методология (язык-нейтральная)** | UCP-концепт, DDD-tactical, формат спеки + оси зрелости 0–3, REST-контракт, error/validation/security/observability **интент**, cqrs/saga/distributed/kafka **концепты**, все `pg-*` (это про сам PostgreSQL) | shared `backend/<concern>/<concern>-rules.md` |
| **Языковой биндинг (реализация)** | как концепт реализуется: Java (Spring/jOOQ/Jakarta), Python (FastAPI/SQLAlchemy/Pydantic), Node (NestJS/TypeORM/class-validator), Go (net/http+chi/sqlc/validator). NB: парадигма может отличаться — в Go ошибки-значения вместо исключений; контракт даёт интент, биндинг — идиому | `backend/<concern>/<lang>/<concern>-style-guide.md` |

Правило: **rules-index — общий контракт, style-guide — языковая реализация.**

## 2. Раскладка docs/

```
docs/                                       # сгруппировано по специализации (track)
├── _meta/                                  # governance (контракт + реестр + check-shared-neutral.py)
├── shared/                                 # кросс-трековое (track: any): arch/, review-finding-format.md, usecase-spec-template.md
├── backend/                                # backend-трек (ось lang)
│   ├── <concern>/                          # язык-нейтральный shared-concern
│   │   ├── <concern>-rules.md              #   SHARED индекс правил (один на все языки)
│   │   ├── java/<concern>-style-guide.md   #   реализация Spring
│   │   └── python/<concern>-style-guide.md #   реализация FastAPI
│   ├── pg-*/                               # PostgreSQL (нейтрально, плоско)
│   ├── java/<langspecific>/                # langspecific java: jooq, java-style, spring-bootstrap, test-strategy
│   └── python/<langspecific>/              # langspecific python: sqlalchemy, python-style, python-bootstrap, python-test-strategy
├── frontend/<concern>/<concern>-rules.md   # frontend-трек (React+TS, single-stack, плоско)
└── e2e/...                                  # e2e-трек (Playwright) — каркас по запросу
```

**Что чисто языко-специфично** (нет shared rules-index, у каждого языка свой набор):
`<lang>-style` (Java JS-* ↔ Python ruff/black/mypy), `bootstrap` (Spring ↔ FastAPI app-factory),
persistence-impl (`jooq` ↔ `sqlalchemy`), `test-strategy` (JUnit+Testcontainers ↔ pytest+testcontainers-python).

**Форма langspecific-concern'а — на выбор по объёму:** (а) пара `<concern>-rules.md` (индекс) + `<concern>-style-guide.md`
(полный, как Java `jooq`/`java-style`); **либо** (б) **одиночный `<concern>-rules.md` с код-примерами внутри**
(без отдельного style-guide) для компактных concern'ов — так сделаны Python `sqlalchemy`/`python-bootstrap`/
`python-test-strategy`/`python-style`. Это сознательно допустимо; скилл тогда читает единственный rules-файл.

**Что shared** (один rules-index + per-lang style-guide): rest-api, error-handling, validation, cqrs,
distributed, kafka, caching, resilience, observability, security, usecase-pattern, ddd-tactical, **все pg-***
(инструмент миграций — Liquibase для Java и Python; конкретика — в style-guide).

Всё выше — **backend-трек** (ось `lang`), живёт под `docs/backend/`. Для frontend/e2e и других специализаций
есть вторая ось — `track` (см. **§10**); раскладка `docs/<track>/<concern>/...`. Кросс-трековое — в `docs/shared/`.

## 3. Формат rules-index (`<concern>-rules.md`)

- Заголовок `# <Concern> — индекс правил (язык-нейтральный)` (для shared) или `# … — Python Style Guide` (для языкового).
- Шапка-blockquote: что это, на какие per-language style-guide ссылаться, конвенция кодов, сшивки с другими гайдами.
- Разделы `## N. <Раздел>` (совпадают между языками для одного concern).
- Внутри — `**MUST:**` / `**MUST NOT:**`, буллеты `- **<CODE>.** однострочная формулировка.`
- Интент формулируется **язык-нейтрально**; framework-токены — нейтральным концептом, конкретика — в style-guide.
- Размер индекса — ~15–45% полного.

## 4. Формат языкового style-guide (`<lang>/<concern>-style-guide.md`)

- Заголовок `# <Concern> — <Lang> Style Guide (<стек>)`.
- Первая строка — ссылка на shared rules-index: «Реализация контракта `../<concern>-rules.md`».
- **Те же коды и разделы**, что в shared rules; под каждым кодом — реализация на языке + PREFER/AVOID.
- В конце — «Чеклист подключения к новому сервису (<Lang>/<framework>)».

## 5. Коды правил

- **Общая таксономия для shared-concern'ов**: код `R-ERR-WHERE-X1` означает одно и то же на всех языках — меняется только реализация. Не плодить параллельные коды на язык для одного концепта.
- **Языко-специфичные concern'ы** — свой префикс (`JS-*` Java style; Python style получит свой, напр. `PY-*`; `R-JOOQ-*` ↔ `R-SQLA-*`).
- Каждый префикс зарегистрирован в `rule-code-registry.md` (shared / per-lang, владелец). Новый код — сначала запись в реестр, потом использование.
- Конвенция: `<PREFIX>-<N>` — обязательно (MUST), `<PREFIX>-X<N>` — антипаттерн (MUST NOT).

## 6. Скиллы (design ↔ review пары)

- Каждый design-скилл имеет парный review.
- **Нейминг:** bare `ucp-<concern>-{design,review}` = **Java по умолчанию** (инкумбент, не переименовываем — завязаны цепочки `ucp-new-service` и хуки). Другие языки — `ucp-<lang>-<concern>-{design,review}` (напр. `ucp-py-error-handling-review`).
- Скилл **читает shared rules-index** (`<concern>/<concern>-rules.md`) + **свой языковой style-guide** (`<concern>/<lang>/<concern>-style-guide.md`); цитирует коды; on-demand-указатель на полный гайд в скобках.
- SKILL.md — **человекочитаемый текст по-русски**, идентификаторы/тулы/коды — латиницей (см. `feedback_skills_in_russian`).
- Скиллы вызываются через `Skill`-tool в текущей сессии, не через `Agent`-форк (прогретый кэш).
- Формат findings review-скилла — по `shared/review-finding-format.md` (`RFF-*`).
- **Frontmatter-метка `lang:`** — обязательна для языкового выбора при установке. Значения: `any` (agnostic — spec/arch/meta/new-service, ставится всегда), `java`, `python`, `node`, `go`. **Без метки = `java`** (back-compat для инкумбентных bare-скиллов). `install.sh` читает её (`UCP_LANG=java|python|node|go`, дефолт java) и ставит только подходящие. Новый языковой скилл обязан проставить свою метку.
- **Frontmatter-метка `track:`** (ось специализации, §10) — `backend` (по умолчанию, можно опустить), `frontend`, `e2e`, `any`. Frontend/e2e-скиллы обязаны её проставить; `install.sh` фильтрует по `UCP_TRACK` (× `UCP_LANG` внутри backend).
- **Бюджет листинга:** `description` ≤ 250 символов, `when_to_use` ≤ 160. Оба поля показываются в листинге скиллов и считаются в общий cap — листинг-бюджет сессии делится на все установленные скиллы, переполнение роняет авто-триггер реже-используемых. В `description` — суть: глагол + объект + стек-маркер + код-префикс правил; триггер-фразы и файловый контекст — в `when_to_use`; перечни подгрупп правил, cross-ref'ы и сценарии — в теле SKILL.md. Эталон формулировок — пара `ucp-py-sqlalchemy-*`.

## 7. Оси зрелости 0–3

Спека и гайды используют единую ось: Уровень 0 (as-is из кода), 1, 2, 3 (DDD+Hexagonal). `level` во frontmatter спеки. Один и тот же словарь на всех языках.

## 8. Поток контрибуции (как питон-лид добавляет concern)

1. Берёт shared `backend/<concern>/<concern>-rules.md` (если concern уже есть) — **не меняет коды/интент** без архитектурного ревью.
2. Пишет `backend/<concern>/python/<concern>-style-guide.md` по §4 — те же коды, Python-реализация.
3. Создаёт пару `ucp-py-<concern>-{design,review}` по §6.
4. Регистрирует любые новые языко-специфичные коды в `rule-code-registry.md`.
5. **Прогоняет `ucp-meta-review`** на свой diff — гейт соответствия контракту.
6. PR; CODEOWNERS: `**/python/**` + `ucp-py-*` — владелец питон-лид; `_meta/**` + shared `*-rules.md` — архитектурный владелец.

## 9. Что НЕ делать

- Не дублировать shared-интент в языковом style-guide (там только реализация + ссылка на коды).
- Не заводить параллельные коды на язык для общего концепта (нарушает cross-language единство).
- Не писать гайд без парного rules-index (для shared) или без пары style-guide (для языко-специфичного).
- Не писать SKILL.md-прозу на английском (кроме явного запроса).
- Не натягивать backend-паттерны (UseCase/aggregate/CQRS) на frontend-трек — у него свой набор concern'ов (см. §10).

## 11. Классификация concern'ов и граница «методология ↔ реализация» (C + D)

«Shared» — спектр, не бинарность. Каждый concern имеет **kind** (в `rule-code-registry.md`), задающий, сколько
должно быть в shared-слое и насколько строго держать нейтральность:

| Kind | Что это | Shared-слой | Биндинг |
|---|---|---|---|
| **NEUTRAL** | архитектура/протокол: ddd, cqrs, distributed, rest-api, usecase-pattern, error-handling, validation, pg-* | полный нейтральный `<concern>-rules.md` (коды + интент) | тонкий: маппинг идиом |
| **IMPL-SHAPED** | завязан на инструмент: resilience, kafka, caching, observability, graceful-shutdown, hexagonal, auth-patterns, security | тонкий — **принципы/инварианты**; тюнинг и механизм НЕ дублировать в shared | толстый: механизм, тюнинг, идиомы |
| **LANG-SPECIFIC** | сам биндинг: backend/java/jooq/sqlalchemy, java-style/python-style, bootstrap, test-strategy | нет shared | single-file (§2) или пара |

**Граница нейтральности (D — enforced):** shared `<concern>-rules.md` (kind NEUTRAL/IMPL-SHAPED) **не содержит
framework-токенов** (аннотации, имена классов/продуктов фреймворка, `spring.*`). Проверяется машинно —
`_meta/check-shared-neutral.py` (CI-гейт + прогон в `ucp-meta-review`). Denylist курируемый: ловит явные токены,
не доказывает полную нейтральность (IMPL-SHAPED по природе несут остаточный mechanism-вокабуляр — это ок, если
это принцип, а не дубль реализации).

**Дуальная иллюстрация разрешена:** нейтральный интент можно проиллюстрировать обоими биндингами в скобках —
`(Java: @ConfigurationProperties; Python: BaseSettings)`. Это НЕ нарушение D (whitelist по co-occurrence
Java-токена с python-маркером). Так нейтральность сохраняется, а пример не теряется.

**Правило авторинга:** тюнинг-значения (размер окна CB, TTL, размеры пула) и имена классов/аннотаций — в биндинг,
не в shared-индекс. Shared-код формулирует инвариант («count-based окно с разумным порогом»), биндинг — числа и API.

## 10. Ось специализации (track) — расширение за пределы backend

Методология имеет **две ортогональные оси**: **язык** (`lang`, §6) и **специализацию** (`track`). Backend был
единственным треком (инкумбент) — теперь добавляются frontend, e2e и далее. Это **не новые языки и не новые
concern'ы под backend** — у каждой специализации свой набор concern'ов.

**Значения `track`:** `backend` (implicit-default — метка отсутствует, как `lang`-инкумбент java), `frontend`
(React + TypeScript), `e2e` (Playwright), `any` (кросс-трековое ядро). Дальше — `mobile`, `data`, `infra` по
тому же рецепту.

**Что кросс-трековое (`track: any`)** — живёт в корне `docs/`, ставится всегда: `_meta/` (этот контракт +
реестр), `spec`/`arch` (описание контекста/платформы), `review-finding-format` (`RFF-*`), оси зрелости 0–3,
**сама форма методологии** (rules-index + per-binding + пара design/review). NB: UseCase Pattern, DDD-tactical,
CQRS — это **backend-concern'ы, не кросс-трековое ядро**; не тащить их во frontend.

**Раскладка docs/ с осью track:**

```
docs/
├── _meta/                                           # governance
├── shared/                                          # track: any — arch/, review-finding-format.md, usecase-spec-template.md
├── backend/<concern>/                               # BACKEND-трек
│   ├── <concern>-rules.md
│   ├── java/ python/                                # биндинги shared-concern'а
│   ├── pg-*/                                         # PostgreSQL (плоско)
│   └── java/<ls>/ python/<ls>/                       # langspecific (jooq/sqlalchemy/style/bootstrap/test)
├── frontend/<concern>/                              # component/state/data-fetching/forms/a11y/styling/fe-test
│   └── <concern>-rules.md                           # React+TS single-stack → плоско
└── e2e/<concern>/                                    # journeys/fixtures/network-mock/ci/flakiness
    ├── <concern>-rules.md
    └── playwright/<concern>-style-guide.md
```

**Frontmatter:** к `lang` добавляется `track`. Backend-скилл — `track` отсутствует (= backend) + `lang:`.
Frontend/e2e — `track: frontend|e2e`; стек один (React+TS / Playwright), поэтому `lang`-под-фильтр не нужен.

**Нейминг скиллов** (короткий токен трека, как у языков): backend — `ucp-<concern>` / `ucp-<lang>-<concern>`
(инкумбент); frontend — `ucp-fe-<concern>-{design,review}`; e2e — `ucp-e2e-<concern>-{design,review}`.

**Коды:** трек резервирует префиксы в `rule-code-registry.md` — `FE-*` (frontend), `E2E-*` (e2e). Концерны
внутри трека следуют §3–§5 (shared rules-index + биндинг, если стеков >1; иначе плоская пара (§2)).

**Установка:** `UCP_TRACK=backend,frontend,e2e` (multi) **×** `UCP_LANG` (фильтр только внутри backend). Проект
берёт срез: `UCP_TRACK=backend,frontend,e2e UCP_LANG=python`. `track: any` ставится всегда. install.sh фильтрует
скиллы и docs по `track` (как уже делает по `lang`).

**E2E — кросс-трековый трек:** проверяет систему целиком, **потребляет контракты** backend (`rest-api`/`auth`) и
frontend (сценарии) через cross-ref, **не дублирует** их. Backend-e2e (`TS-28`) и UI-e2e сводятся в один e2e-трек
с разделением API-e2e / UI-e2e.

### Рецепт «добавить специализацию» (это и есть расширяемость)

1. Зарезервировать `track` + код-префикс (`<TRACK>-*`) в `rule-code-registry.md` — **до** использования.
2. Создать `docs/<track>/<concern>/` — shared rules-index (§3) + биндинг (§4), или плоскую пару при одном стеке.
3. Скиллы `ucp-<track-token>-<concern>-{design,review}` (§6) с frontmatter `track:`.
4. Прогнать `ucp-meta-review` на diff — гейт контракта.
5. CODEOWNERS: `docs/<track>/**` + `ucp-<track-token>-*` — владелец трека.

Mobile/data/ML/infra добавляются по этой же колее без переархитектуры.
