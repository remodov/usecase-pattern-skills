# usecase-pattern-skills

Скиллы (slash-команды) для Claude Code, привязанные к статьям [vikulin-va.ru](https://vikulin-va.ru/use-case-pattern/) о методологии Use Case Pattern. Каждый скилл — компактный чек-лист для агента; полное описание правил с диаграммами и примерами — на сайте.

## Принцип

- **Сайт vikulin-va.ru — единственный источник истины.** Если правила в скилле и в статье расходятся, прав сайт.
- **Локальный `docs/*.md`** — снапшот соответствующей статьи (агент читает его быстро, без сетевого вызова).
- **Скиллы** — короткие инструкции для агента: что проверить, как отчитаться.

## Скиллы

### `/api-review`

Ревью REST API контракта или кода на соответствие [REST API Style Guide](https://vikulin-va.ru/rest-api-style-guide/).

**Что проверяет:**
- Формат URL (kebab-case, множественное число, вложенность)
- HTTP-методы и коды ответов
- Именование полей в JSON (camelCase, даты, enum)
- Формат ошибок (RFC 9457 ProblemDetails)
- Пагинация, сортировка, фильтрация
- OpenAPI-метаданные (`operationId`, `tags`, `summary`)
- Версионирование, deprecation, batch, async

**Использование:**

```
/api-review                              # ревью изменений из git diff
/api-review path/to/openapi.yaml         # ревью конкретного файла
/api-review src/.../OrderController.java
```

### `/api-design`

Проектирование новых REST API эндпоинтов по style guide. Генерирует OpenAPI-спеку и заметки по реализации.

**Что генерирует:**
- OpenAPI YAML с paths, schemas, error responses
- Примеры ошибок по RFC 9457
- Сигнатуры Spring-контроллеров
- Список DTO и error codes

**Использование:**

```
/api-design Управление заказами: CRUD + подтверждение + отмена
/api-design Эндпоинт загрузки аватара пользователя
/api-design Поиск товаров с фильтрами по категории, цене и наличию
```

## Подключение к проекту

### Симлинк всех скиллов (рекомендуется)

```bash
git clone https://github.com/remodov/usecase-pattern-skills.git ~/projects/usecase-pattern-skills

# из своего Java-проекта
mkdir -p .claude/skills
ln -s ~/projects/usecase-pattern-skills/.claude/skills/* .claude/skills/

# и скопировать или симлинк style guide:
mkdir -p docs
ln -s ~/projects/usecase-pattern-skills/docs/rest-api-style-guide.md docs/
```

### Глобально для всех проектов

```bash
mkdir -p ~/.claude/skills
ln -s ~/projects/usecase-pattern-skills/.claude/skills/* ~/.claude/skills/
```

## Структура

```
.claude/skills/
├── api-review/
│   └── SKILL.md        # ревью контракта
└── api-design/
    └── SKILL.md        # проектирование эндпоинтов

docs/
└── rest-api-style-guide.md   # снапшот статьи vikulin-va.ru/rest-api-style-guide/
```

## Связанные статьи

- [REST API Style Guide](https://vikulin-va.ru/rest-api-style-guide/) — полный свод правил с диаграммами.
- [Use Case Pattern](https://vikulin-va.ru/use-case-pattern/) — методология, частью которой является REST API контракт.

В планах — скиллы для остальных статей сайта (DDD, CQRS, Hexagonal, Distributed Patterns, Resilience, Kafka, Auth Patterns).

## Лицензия

MIT
