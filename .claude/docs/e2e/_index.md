# e2e-трек — карта требований

Сквозные сценарии и их прогон: чем набор отличается от интеграционных тестов,
что запускается после деплоя и откуда в регрессе берутся новые сценарии.
Трек язык-нейтрален — одинаково для проверки через интерфейс и через контракт.

Таблица собирается `spec_sync.py` из `spec.md` каждого домена и руками
не редактируется.

<!-- BEGIN:ucp-requirements -->

| Требование | Гейт | Покрытие |
| --- | --- | --- |
| [e2e-pipeline/environment-is-reproducible](.claude/docs/e2e/e2e-pipeline/spec.md) — Стенд для прогона восстановим | ревью | нет |
| [e2e-pipeline/flakiness-budget-is-declared](.claude/docs/e2e/e2e-pipeline/spec.md) — Доля нестабильных объявлена и наблюдается | ревью | нет |
| [e2e-pipeline/flaky-goes-to-quarantine](.claude/docs/e2e/e2e-pipeline/spec.md) — Нестабильный сценарий уходит в карантин со сроком | ревью | нет |
| [e2e-pipeline/incident-adds-a-scenario](.claude/docs/e2e/e2e-pipeline/spec.md) — Каждый инцидент добавляет сценарий | ревью | нет |
| [e2e-pipeline/new-scenario-fails-on-old-code](.claude/docs/e2e/e2e-pipeline/spec.md) — Новый сценарий проверяется падением на старом коде | ревью | нет |
| [e2e-pipeline/production-runs-are-safe](.claude/docs/e2e/e2e-pipeline/spec.md) — На промышленном стенде сценарии не меняют чужих данных | ревью | нет |
| [e2e-pipeline/red-smoke-blocks-promotion](.claude/docs/e2e/e2e-pipeline/spec.md) — Красный смоук останавливает продвижение | ci:e2e-smoke | частичное |
| [e2e-pipeline/regression-on-schedule-and-before-release](.claude/docs/e2e/e2e-pipeline/spec.md) — Полный регресс идёт по расписанию и перед релизом | ci:e2e-regression | частичное |
| [e2e-pipeline/removal-needs-a-reason](.claude/docs/e2e/e2e-pipeline/spec.md) — Удаление сценария — решение с причиной | ревью | нет |
| [e2e-pipeline/result-is-published-and-owned](.claude/docs/e2e/e2e-pipeline/spec.md) — Результат прогона публикуется и адресован | ревью | нет |
| [e2e-pipeline/runs-locally-with-one-command](.claude/docs/e2e/e2e-pipeline/spec.md) — Набор запускается локально одной командой | ревью | нет |
| [e2e-pipeline/smoke-after-every-deploy](.claude/docs/e2e/e2e-pipeline/spec.md) — После деплоя идёт смоук на том же стенде | ci:e2e-smoke | частичное |
| [e2e-suite/credentials-come-from-outside](.claude/docs/e2e/e2e-suite/spec.md) — Учётные записи и секреты приходят снаружи | gitleaks:default | частичное |
| [e2e-suite/failure-leaves-evidence](.claude/docs/e2e/e2e-suite/spec.md) — Падение оставляет след для разбора | ci:e2e-regression | частичное |
| [e2e-suite/goes-through-product-path](.claude/docs/e2e/e2e-suite/spec.md) — Сценарий ходит продуктовым путём | ревью | нет |
| [e2e-suite/name-states-path-and-outcome](.claude/docs/e2e/e2e-suite/spec.md) — Имя сценария называет путь и ожидаемый исход | ревью | нет |
| [e2e-suite/run-time-is-budgeted](.claude/docs/e2e/e2e-suite/spec.md) — Смоук укладывается в объявленный бюджет времени | ci:e2e-smoke | частичное |
| [e2e-suite/scenario-is-a-journey](.claude/docs/e2e/e2e-suite/spec.md) — Сценарий описывает бизнес-путь | ревью | нет |
| [e2e-suite/scenario-owns-its-data](.claude/docs/e2e/e2e-suite/spec.md) — Сценарий готовит и убирает свои данные | ревью | нет |
| [e2e-suite/scenario-traces-to-requirement](.claude/docs/e2e/e2e-suite/spec.md) — Сценарий прослеживается до требования | ревью | нет |
| [e2e-suite/scenarios-are-independent](.claude/docs/e2e/e2e-suite/spec.md) — Сценарий независим от других и от порядка | ревью | нет |
| [e2e-suite/selectors-are-stable](.claude/docs/e2e/e2e-suite/spec.md) — Цепляться можно за роль и метку, а не за вёрстку | ревью | нет |
| [e2e-suite/smoke-and-regression-are-tagged](.claude/docs/e2e/e2e-suite/spec.md) — Набор разделён на смоук и полный регресс | ревью | нет |
| [e2e-suite/stubs-only-at-the-perimeter](.claude/docs/e2e/e2e-suite/spec.md) — Внешние системы подменяются только на стенде и на границе | ревью | нет |
| [e2e-suite/waits-are-state-based](.claude/docs/e2e/e2e-suite/spec.md) — Ожидание идёт по состоянию, а не по времени | script:test-lint | частичное |

<!-- END:ucp-requirements -->
