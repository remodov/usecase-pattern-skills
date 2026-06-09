---
name: ucp-new-service
lang: any
track: any
description: Оркестратор создания нового UCP-сервиса с нуля — определяет уровень зрелости 1/2/3, собирает бизнес-описание и запускает цепочку скиллов (spec → ddd → bootstrap → pattern → auth → test). Не пишет код сам.
when_to_use: Триггеры — «сделай сервис», «пишем сервис», «новый сервис», «напиши сервис», «начнём сервис». Запуск из директории сервиса.
allowed-tools: Read Glob Grep Bash(find*) Skill(ucp-spec-design) Skill(ucp-ddd-tactical-design) Skill(ucp-bootstrap-design) Skill(ucp-pattern-design) Skill(ucp-auth-design) Skill(ucp-test-design) Skill(superpowers:*)
---

# UCP New Service — оркестратор цепочки

Ты не пишешь код сам. Ты собираешь контекст и вызываешь downstream-скиллы в правильном порядке.

## Перед запуском цепочки

1. **Определи уровень зрелости** — спроси явно, если не указан в запросе:
   - **Уровень 1** — Controller → Service → Repository (без usecase-pattern)
   - **Уровень 2** — UseCase + Handler (usecase-pattern), опционально CQRS
   - **Уровень 3** — DDD + Hexagonal (агрегаты, доменные события, ports/adapters)

2. **Собери бизнес-описание.** Нужны минимум: акторы, операции, глоссарий. Если пользователь ещё не дал — попроси вставить текст. Без бизнес-описания `ucp-spec-design` не может написать спеку — не выдумывай факты.

3. **Проверь стартовую точку** — что уже есть в проекте (`docs/spec/`, `src/`, `migrations/`). Это определяет, какие шаги пропустить.

   ```bash
   find . -maxdepth 4 -name "*.md" -path "*/spec/*" | head -10
   ls src/main/java 2>/dev/null || echo "(src пусто)"
   ls migrations/db/changelog 2>/dev/null || echo "(migrations пусто)"
   ```

## Цепочка скиллов

Выполняй **последовательно** — каждый следующий шаг читает артефакты предыдущего. Параллельно не запускай.

### Шаг 1 — Спека
```
Skill("ucp-spec-design", "<уровень> + <бизнес-описание>")
```
Пропусти, если `docs/spec/<service>-spec.md` уже существует и актуален.

### Шаг 2 — DDD-слой (только Уровень 3)
```
Skill("ucp-ddd-tactical-design")
```
На Уровне 1 и 2 — пропусти, сообщи пользователю об этом.

### Шаг 3 — Bootstrap
```
Skill("ucp-bootstrap-design")
```
Пропусти, если `src/main/java` уже содержит рабочий Spring Boot-скелет с профилями.

### Шаг 4 — UseCase / Handler / Controller
```
Skill("ucp-pattern-design", "<операция из спеки §Use Cases>")
```
Вызывай по одной операции. Если операций несколько — уточни у пользователя, начинать ли с первой или с конкретной.

### Шаг 5 — Авторизация
```
Skill("ucp-auth-design")
```
Пропусти, если в спеке нет раздела «Роли и доступ» или доступ `permitAll`.

### Шаг 6 — Тесты
```
Skill("ucp-test-design")
```

## После каждого шага

- Коротко резюмируй что произведено (файлы, ключевые решения).
- Спрашивай подтверждение перед следующим шагом — пользователь может захотеть скорректировать.
- Если шаг вернул вопрос к пользователю — ответь на него, потом продолжи цепочку.

## Если что-то пропущено или сломано

- `ucp-spec-design` не может начать без бизнес-описания → собери и передай.
- `ucp-bootstrap-design` падает с ошибкой профилей → передай ошибку в аргументах.
- `ucp-pattern-design` не видит `usecase-pattern-starter` в `build.gradle` → передай заметку в аргументах.

## Структура вывода

После завершения цепочки:
1. Список созданных файлов по шагам.
2. Команда для первого запуска:
   ```bash
   docker compose up -d postgres
   ./gradlew :bootstrap:bootRun --args='--spring.profiles.active=local'
   ```
3. Следующие шаги (ревью, дополнительные операции, деплой).

$ARGUMENTS
