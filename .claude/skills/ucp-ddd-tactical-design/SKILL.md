---
name: ucp-ddd-tactical-design
description: Спроектировать доменную модель для Java (требования `ddd-tactical/*`, коды R-AGG-*, R-VO-*, R-EVT-*, R-REP-*) с библиотекой ddd-building-blocks — агрегат, сущности, value object'ы, доменные события, репозиторий.
when_to_use: Моделирование нового bounded context, добавление агрегата или доменного события. После ucp-spec-design, до ucp-pg-schema-design.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# DDD Tactical Patterns — проектирование

Ты проектируешь или генерируешь шаблон новой доменной модели: bounded context, агрегат, value object или доменное событие. Реализация должна следовать требованиям `ddd-tactical/*` и использовать абстракции из библиотеки `ddd-building-blocks` (пакет `ru.vikulinva.ddd`).

## Инструкции

1. **Прочитай требования** из `.claude/docs/backend/ddd-tactical/spec.md`. Считай каждое правило `R-*` обязательным. Цитируй правила, на которые опираешься, **в design-обосновании ответа пользователю** — но **не в комментариях сгенерированного кода** (`java-style/no-rule-codes-or-history-in-code` в `backend/java/java-style/spec.md`). Никаких `// R-AGG-1`, `// R-VO-2` в исходниках; соответствие выражается через типы (`extends AggregateRoot<ID>`, `implements ValueObject`), имена и структуру.

2. **Подтверди наличие библиотеки.** Проверь `build.gradle` / `pom.xml` на `ru.vikulinva:ddd-building-blocks`. Если нет — попроси пользователя добавить (предложи сниппет зависимости) — не выдумывай локальные копии `Entity` / `AggregateRoot` / `ValueObject`.

3. **Уточни модель из описания пользователя.** Определи:
   - Имя bounded context — для документации и persistence-адаптера; в `core/` слоя контекстов нет (`hexagonal/core-structure`).
   - Корень агрегата: какой бизнес-инвариант он защищает?
   - Внутренние сущности (если есть) и их жизненный цикл внутри корня.
   - Value Objects, которые надо выделить (бьём примитивную одержимость: `Money`, `Email`, `OrderId` и т.п.).
   - Доменные события, которые публикует корень, в прошедшем времени.
   - Ссылки между агрегатами — только по ID.
   - Фабрика — всегда (`<X>Factory.create(...)` — единственная точка создания); оправданы ли Domain Service или Specification (по умолчанию — нет).

4. **Произведи код.** Для каждого класса напиши полный Java-файл (Java 21+). Lombok — как в эталоне: на агрегатах и сущностях `@Builder` + `@Getter` (builder — проводка для фабрики и persistence-маппера, публичных конструкторов нет — `java-style/builder-used-sparingly`); на VO-записях — `@Builder` только при многих необязательных полях, остальной Lombok на records лишний (`java-style/no-generation-on-records`); `@Data` / `@Setter` в `domain/` — нет.

   - **Value Objects** — Java `record`'ы, реализующие `ValueObject`, с compact-конструктором, проверяющим инварианты. Если record не подходит (мутирующие алгоритмы, кастомный equals), используй `final class` с `final` полями.
   - **Entities** — наследуют `Entity<ID>`, `id` — `final`, только бизнес-методы (без setter-ов), валидация в конструкторе. Не переопределяй `equals` / `hashCode`.
   - **Aggregate Roots** — наследуют `AggregateRoot<ID>`, мутирующие методы держат инварианты и зовут `registerEvent(new SomethingHappened(...))`. Параметры методов — доменные типы: значения, идентификаторы, перечисления. Объект команды в домен не передаётся, пакет `domain` не импортирует `usecase` (`ddd-tactical/domain-does-not-know-operations`); набор атрибутов, приходящий целиком (снимок из внешней системы) — запись `<Aggregate>Snapshot implements ValueObject`.
   - **Domain Events** — `final class`, наследует `DomainEvent`, зовёт `super(aggregateType, aggregateId)`; все поля `final`; имя в прошедшем времени (`OrderPaid`, не `PayOrder`).
   - **Repository** — интерфейс в `domain/repository/`, наследует `AggregateRepository<T, ID>`, методы названы в доменных терминах. Реализация — в `adapter/out/<storage>/`.
   - **Factory** — на каждый агрегат и сущность: `@UtilityClass` в `core/domain/factory/`, статический `create(...)` проверяет инварианты создания, собирает объект builder'ом, регистрирует начальные события. **Domain Service / Specification** — только если правила требования говорят, что оправдано. Укажи обоснование.

5. **Раскладывай пакеты по роли элемента, без слоя bounded context'ов** (`hexagonal/core-structure`):

   ```
   core/domain/
     aggregate/<Root>.java
     entity/<InnerEntity>.java
     valueobject/<VO>.java
     event/<Event>.java
     factory/<Root>Factory.java
   core/port/out/repository/<Repository>.java
   core/usecase/
     command/<фича>/<Operation>Command.java
     command/<фича>/<Operation>CommandHandler.java
     query/<фича>/<Operation>Query.java
     query/<фича>/<Operation>QueryHandler.java
   <system>-in-adapter/…/adapter/in/<system>/<Controller>.java
   postgres-out-adapter/…/adapter/out/postgres/<bc>/<entity>/Jooq<Repository>.java
   ```

   Доменные пакеты не должны импортировать Spring, JPA, jOOQ или схему персистенса.

6. **Самопроверка перед выдачей** — выдавай только когда проходят:
   - Entity не переопределяет equals / hashCode; ID — `final`.
   - Каждый VO иммутабельный и equals по значению.
   - Все изменения состояния идут через методы корня агрегата.
   - События создаются внутри корня, не в сервисах или репозиториях.
   - Ссылки между агрегатами — только ID.
   - Интерфейс репозитория в домене, реализация в адаптере, возвращает доменные типы, публикует и очищает события на `save`.
   - Раскладка пакетов сгруппирована по домену.

7. **Вывод** — по общему правилу: размер ответа равен размеру вопроса; решения и затронутые файлы — всегда, полные файлы — только когда просят сгенерировать; ревью — по запросу, не автоматически.

$ARGUMENTS
