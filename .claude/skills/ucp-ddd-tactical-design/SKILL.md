---
name: ucp-ddd-tactical-design
description: Спроектировать доменную модель для Java (DDD Tactical Style Guide, коды R-AGG-*, R-VO-*, R-EVT-*, R-REP-*) с библиотекой ddd-building-blocks — агрегат, сущности, value object'ы, доменные события, репозиторий.
when_to_use: Моделирование нового bounded context, добавление агрегата или доменного события. После ucp-spec-design, до ucp-pg-schema-design.
allowed-tools: Read Glob Grep Write Edit Bash(./gradlew*) Bash(mvn*)
---

# DDD Tactical Patterns — проектирование

Ты проектируешь или генерируешь шаблон новой доменной модели: bounded context, агрегат, value object или доменное событие. Реализация должна следовать командному DDD Tactical Patterns Style Guide и использовать абстракции из библиотеки `ddd-building-blocks` (пакет `ru.vikulinva.ddd`).

## Инструкции

1. **Прочитай style guide** из `.claude/docs/backend/ddd-tactical/ddd-tactical-rules.md`. Считай каждое правило `R-*` обязательным. Цитируй правила, на которые опираешься, **в design-обосновании ответа пользователю** — но **не в комментариях сгенерированного кода** (`JS-7.3` в `backend/java/java-style/java-rules.md`). Никаких `// R-AGG-1`, `// R-VO-2` в исходниках; соответствие выражается через типы (`extends AggregateRoot<ID>`, `implements ValueObject`), имена и структуру.

2. **Подтверди наличие библиотеки.** Проверь `build.gradle` / `pom.xml` на `ru.vikulinva:ddd-building-blocks`. Если нет — попроси пользователя добавить (предложи сниппет зависимости) — не выдумывай локальные копии `Entity` / `AggregateRoot` / `ValueObject`.

3. **Уточни модель из описания пользователя.** Определи:
   - Имя bounded context и корневой пакет под него (`core/<bc>/domain/...`).
   - Корень агрегата: какой бизнес-инвариант он защищает?
   - Внутренние сущности (если есть) и их жизненный цикл внутри корня.
   - Value Objects, которые надо выделить (бьём примитивную одержимость: `Money`, `Email`, `OrderId` и т.п.).
   - Доменные события, которые публикует корень, в прошедшем времени.
   - Ссылки между агрегатами — только по ID.
   - Оправдана ли Factory, Domain Service или Specification (по умолчанию — нет).

4. **Произведи код.** Для каждого класса напиши полный Java-файл (Java 21+). На VO / Entity / Aggregate Lombok **не** применяем (`JS-6.4` — records уже дают ctor / accessors / equals; на агрегатах `@Builder` обходит инварианты, см. `JS-6.7`). Lombok оправдан только на **handler-ах / сервисах** в слое UseCase, не в `domain/`.

   - **Value Objects** — Java `record`'ы, реализующие `ValueObject`, с compact-конструктором, проверяющим инварианты. Если record не подходит (мутирующие алгоритмы, кастомный equals), используй `final class` с `final` полями.
   - **Entities** — наследуют `Entity<ID>`, `id` — `final`, только бизнес-методы (без setter-ов), валидация в конструкторе. Не переопределяй `equals` / `hashCode`.
   - **Aggregate Roots** — наследуют `AggregateRoot<ID>`, мутирующие методы держат инварианты и зовут `registerEvent(new SomethingHappened(...))`.
   - **Domain Events** — `final class`, наследует `DomainEvent`, зовёт `super(aggregateType, aggregateId)`; все поля `final`; имя в прошедшем времени (`OrderPaid`, не `PayOrder`).
   - **Repository** — интерфейс в `domain/repository/`, наследует `AggregateRepository<T, ID>`, методы названы в доменных терминах. Реализация — в `adapter/out/<storage>/`.
   - **Domain Service / Factory / Specification** — только если правила style guide говорят, что оправдано. Укажи обоснование.

5. **Раскладывай пакеты по домену, не по типу** (style guide §10):

   ```
   core/<bc>/domain/
     aggregate/<Root>.java
     entity/<InnerEntity>.java
     valueobject/<VO>.java
     event/<Event>.java
     repository/<Repository>.java
   core/<bc>/usecase/
     command/<Operation>Command.java
     command/<Operation>CommandHandler.java
     query/<Operation>Query.java
     query/<Operation>QueryHandler.java
   adapter/in/rest/<Controller>.java
   adapter/out/<storage>/<RepositoryImpl>.java
   ```

   Доменные пакеты не должны импортировать Spring, JPA, jOOQ или схему персистенса.

6. **Самопроверка перед выдачей.** Пройди эти проверки (style guide §11) и выдавай только когда они проходят:
   - Entity не переопределяет equals / hashCode; ID — `final`.
   - Каждый VO иммутабельный и equals по значению.
   - Все изменения состояния идут через методы корня агрегата.
   - События создаются внутри корня, не в сервисах или репозиториях.
   - Ссылки между агрегатами — только ID.
   - Интерфейс репозитория в домене, реализация в адаптере, возвращает доменные типы, публикует и очищает события на `save`.
   - Раскладка пакетов сгруппирована по домену.

7. **Структура вывода:**
   1. Краткий обзор дизайна (3–8 буллетов): агрегат, защищаемые инварианты, публикуемые события, репозитории, что намеренно опущено.
   2. Дерево новых файлов.
   3. Каждый файл — отдельный code block с путём в заголовке.
   4. **Заметки по реализации**: нужные зависимости, предлагаемые тест-кейсы (по одному на инвариант + по одному на событие).

$ARGUMENTS
