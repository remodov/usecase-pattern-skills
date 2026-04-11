# Claude Code Java Skills

Набор скиллов (slash-команд) для Claude Code, помогающих проектировать и ревьюить REST API по стандартам отдела.

## Скиллы

### `/api-review`

Ревью REST API контракта или кода на соответствие [REST API Style Guide](docs/rest-api-style-guide.md).

**Что проверяет:**
- Формат URL (kebab-case, множественное число, вложенность)
- HTTP-методы и коды ответов
- Именование полей в JSON (camelCase, даты, enum)
- Формат ошибок (RFC 9457 ProblemDetails)
- Пагинация, сортировка, фильтрация
- OpenAPI-метаданные (operationId, tags, summary)
- Версионирование, deprecation, batch, async

**Использование:**
```
/api-review                          # ревью изменений из git diff
/api-review path/to/openapi.yaml    # ревью конкретного файла
/api-review src/main/java/com/example/controller/OrderController.java
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

## Структура

```
.claude/skills/
├── api-review/
│   └── SKILL.md        # ревью контракта
└── api-design/
    └── SKILL.md        # проектирование эндпоинтов

docs/
└── rest-api-style-guide.md   # свод правил (источник истины для скиллов)
```

## Документация

- [REST API Style Guide](docs/rest-api-style-guide.md) — свод правил проектирования REST API
