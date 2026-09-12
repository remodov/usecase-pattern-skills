# Общий слой — карта требований

Требования, не привязанные к треку: платформенная согласованность, формат
находки ревью, формат Use Case спецификации и формат её изменения. Таблица
собирается `spec_sync.py` из `spec.md` каждого домена и руками не
редактируется: правка потеряется при следующей пересборке, а `spec_check.py`
покраснеет раньше.

<!-- BEGIN:ucp-requirements -->

| Требование | Гейт | Покрытие |
| --- | --- | --- |
| [arch/archived-service-not-in-live-processes](.claude/docs/shared/arch/spec.md) — Архивный сервис не участвует в живых процессах | script:arch-check | частичное |
| [arch/breaking-changes-are-listed](.claude/docs/shared/arch/spec.md) — Ломающие изменения контракта перечислены | ревью | нет |
| [arch/context-links-are-symmetric](.claude/docs/shared/arch/spec.md) — Связь контекстов объявлена с обеих сторон | script:arch-check | частичное |
| [arch/contracts-are-versioned](.claude/docs/shared/arch/spec.md) — Контракты версионированы и описывают события полем | script:arch-check | частичное |
| [arch/failure-points-have-compensation](.claude/docs/shared/arch/spec.md) — У каждой точки отказа есть компенсация или явное решение | script:arch-check | частичное |
| [arch/index-documents-are-tables](.claude/docs/shared/arch/spec.md) — Индексные документы — таблицы со стабильным заголовком | script:arch-check | частичное |
| [arch/one-publisher-per-event](.claude/docs/shared/arch/spec.md) — У события ровно один публикующий сервис | script:arch-check | частичное |
| [arch/process-has-orchestrator-or-note](.claude/docs/shared/arch/spec.md) — У процесса есть ведущий или явная пометка о его отсутствии | script:arch-check | частичное |
| [arch/process-step-matches-service-use-case](.claude/docs/shared/arch/spec.md) — Шаг процесса соответствует операции сервиса | script:arch-check | частичное |
| [arch/registry-entry-is-complete](.claude/docs/shared/arch/spec.md) — Запись сервиса в реестре полна и однозначна | script:arch-check | частичное |
| [arch/service-card-matches-spec](.claude/docs/shared/arch/spec.md) — Карточка сервиса синхронизирована со спекой | script:arch-check | частичное |
| [arch/shared-kernel-needs-adr](.claude/docs/shared/arch/spec.md) — Общее ядро требует обоснования решением | script:arch-check | частичное |
| [arch/single-owner-per-entity](.claude/docs/shared/arch/spec.md) — У каждой сущности один владелец | script:arch-check | частичное |
| [arch/sync-steps-are-declared](.claude/docs/shared/arch/spec.md) — Синхронные связи между контекстами объявлены | script:arch-check | частичное |
| [arch/ubiquitous-language-is-consistent](.claude/docs/shared/arch/spec.md) — Термин единого языка означает одно и то же | ревью | нет |
| [review-format/finding-carries-line-and-rule](.claude/docs/shared/review-format/spec.md) — Находка несёт строку, правило и уровень | ревью | нет |
| [review-format/line-confirmed-by-read](.claude/docs/shared/review-format/spec.md) — Строка подтверждена чтением файла | ревью | нет |
| [review-format/one-finding-per-occurrence](.claude/docs/shared/review-format/spec.md) — Каждое вхождение — отдельная находка | ревью | нет |
| [review-format/quote-instead-of-guess](.claude/docs/shared/review-format/spec.md) — Неуверенность в номере разрешается цитатой | ревью | нет |
| [review-format/range-confirmed-at-both-ends](.claude/docs/shared/review-format/spec.md) — Диапазон подтверждён с обоих концов | ревью | нет |
| [review-format/report-ends-with-verdict](.claude/docs/shared/review-format/spec.md) — Отчёт заканчивается резюме и вердиктом | ревью | нет |
| [review-format/review-reports-not-edits](.claude/docs/shared/review-format/spec.md) — Ревью сообщает, а не правит | ревью | нет |
| [review-format/severity-scale-is-shared](.claude/docs/shared/review-format/spec.md) — Шкала серьёзности одна на все ревью | ревью | нет |
| [spec-change/archive-is-append-only](.claude/docs/shared/spec-change/spec.md) — Архив не чистится | ревью | нет |
| [spec-change/changes-point-at-sections](.claude/docs/shared/spec-change/spec.md) — «Что меняется» указывает файл и раздел | ревью | нет |
| [spec-change/class-drives-migration](.claude/docs/shared/spec-change/spec.md) — Класс изменения объявлен и определяет миграцию | ревью | нет |
| [spec-change/document-follows-contract-change](.claude/docs/shared/spec-change/spec.md) — Документ изменения заводится на смену контракта | ревью | нет |
| [spec-change/merge-is-a-separate-step](.claude/docs/shared/spec-change/spec.md) — Слияние — отдельный шаг с чек-листом | ревью | нет |
| [spec-change/one-document-one-change](.claude/docs/shared/spec-change/spec.md) — Один документ — одно изменение | ревью | нет |
| [spec-change/reason-is-stated](.claude/docs/shared/spec-change/spec.md) — Причина живёт в разделе «Зачем» | ревью | нет |
| [spec-change/semantic-break-is-not-compatible](.claude/docs/shared/spec-change/spec.md) — Изменение смысла классифицируется как ломающее смысл | ревью | нет |
| [spec-change/spec-is-the-source-after-merge](.claude/docs/shared/spec-change/spec.md) — После слияния источник правды — спека | ревью | нет |
| [spec-change/tasks-are-vertical-slices](.claude/docs/shared/spec-change/spec.md) — Задачи нарезаны вертикальными срезами | ревью | нет |
| [spec-format/business-rule-states-consequence](.claude/docs/shared/spec-format/spec.md) — Бизнес-правило называет последствие нарушения | ревью | нет |
| [spec-format/command-cards-carry-marked-fields](.claude/docs/shared/spec-format/spec.md) — Карточки команд и запросов держат размеченные поля | ревью | нет |
| [spec-format/context-is-the-unit](.claude/docs/shared/spec-format/spec.md) — Единица спеки — Bounded Context | ревью | нет |
| [spec-format/diagrams-split-by-purpose](.claude/docs/shared/spec-format/spec.md) — Диаграммы разделены по назначению | ревью | нет |
| [spec-format/document-opens-with-lead](.claude/docs/shared/spec-format/spec.md) — Документ открывается лидом | ревью | нет |
| [spec-format/domain-without-technology](.claude/docs/shared/spec-format/spec.md) — Домен без техники | ревью | нет |
| [spec-format/edge-links-the-contract](.claude/docs/shared/spec-format/spec.md) — Ребро ссылается на контракт, а не пересказывает его | ревью | нет |
| [spec-format/evidence-outside-the-sentence](.claude/docs/shared/spec-format/spec.md) — Источник факта стоит вне предложения | ревью | нет |
| [spec-format/file-ends-with-navigation](.claude/docs/shared/spec-format/spec.md) — Файл заканчивается навигацией «Куда дальше» | ревью | нет |
| [spec-format/frontmatter-is-minimal](.claude/docs/shared/spec-format/spec.md) — Frontmatter минимален | ревью | нет |
| [spec-format/gaps-collected-at-the-end](.claude/docs/shared/spec-format/spec.md) — Пробелы собраны в конце документа | ревью | нет |
| [spec-format/integration-vocabulary-is-closed](.claude/docs/shared/spec-format/spec.md) — Значения рёбер интеграций — из закрытого словаря | ревью | нет |
| [spec-format/intro-names-what-matters](.claude/docs/shared/spec-format/spec.md) — Вводная фраза называет главное, а не содержимое | ревью | нет |
| [spec-format/key-facts-box-after-lead](.claude/docs/shared/spec-format/spec.md) — После лида идёт врезка «Важно знать» | ревью | нет |
| [spec-format/language-is-plain](.claude/docs/shared/spec-format/spec.md) — Язык — как для коллеги | ревью | нет |
| [spec-format/lists-are-tables](.claude/docs/shared/spec-format/spec.md) — Перечень оформляется таблицей со стабильными заголовками | ревью | нет |
| [spec-format/mandatory-registries-in-technical-section](.claude/docs/shared/spec-format/spec.md) — Раздел «Техническая реализация» несёт два обязательных реестра | ревью | нет |
| [spec-format/maturity-level-is-declared](.claude/docs/shared/spec-format/spec.md) — Уровень зрелости объявлен и соблюдён | ревью | нет |
| [spec-format/no-separate-error-catalogue](.claude/docs/shared/spec-format/spec.md) — Каталога ошибок в спеке нет | ревью | нет |
| [spec-format/registry-extends-by-second-table](.claude/docs/shared/spec-format/spec.md) — Реестр дополняется связанной таблицей, а не колонкой | ревью | нет |
| [spec-format/rules-and-value-objects-named-by-meaning](.claude/docs/shared/spec-format/spec.md) — Бизнес-правила и value object'ы названы по своей сути | ревью | нет |
| [spec-format/section-numbering-is-stable](.claude/docs/shared/spec-format/spec.md) — Нумерация и состав разделов стабильны | ревью | нет |
| [spec-format/section-opens-with-prose](.claude/docs/shared/spec-format/spec.md) — Раздел открывается прозой | ревью | нет |
| [spec-format/single-place-per-fact](.claude/docs/shared/spec-format/spec.md) — Факт живёт в одном месте | ревью | нет |
| [spec-format/subheadings-are-statements](.claude/docs/shared/spec-format/spec.md) — Подзаголовки внутри разделов — утверждения | ревью | нет |
| [spec-format/table-fits-six-columns](.claude/docs/shared/spec-format/spec.md) — Таблица не шире шести колонок | ревью | нет |
| [spec-format/unit-lists-common-mistakes](.claude/docs/shared/spec-format/spec.md) — Файл домен-юнита несёт таблицу частых ошибок | ревью | нет |
| [spec-format/unknown-cell-is-marked](.claude/docs/shared/spec-format/spec.md) — Незаполненная ячейка помечается, а не пропускается | ревью | нет |

<!-- END:ucp-requirements -->
