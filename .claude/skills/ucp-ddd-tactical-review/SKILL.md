---
name: ucp-ddd-tactical-review
description: Ревью доменного кода Java по требованиям `ddd-tactical/*` и библиотеке ddd-building-blocks — агрегаты, сущности, value object'ы, доменные события, репозитории, доменные сервисы.
when_to_use: Ревью кода доменного слоя — Aggregate, Entity, VO, Domain Event, Repository, Domain Service.
allowed-tools: Read Glob Grep Bash(git diff*) Bash(./gradlew*) Bash(mvn*)
---

# Ревью тактических паттернов DDD

Ты ревьюишь код доменного слоя (агрегаты, сущности, value object'ы, доменные события, репозитории, доменные сервисы, спецификации, фабрики) на соответствие требованиям `ddd-tactical/*` и правильное использование библиотеки `ddd-building-blocks` (пакет `ru.vikulinva.ddd`).

## Инструкции

1. **Прочитай требования** из `.claude/docs/backend/ddd-tactical/spec.md` в корне проекта. Это единственный источник правды — у каждого правила есть код (`ddd-tactical/entity-equality-by-identity`, `ddd-tactical/transaction-boundary-equals-aggregate` и т.п.). Цитируй коды в замечаниях.

2. **Определи объект ревью.** Если пользователь назвал файлы — бери их. Иначе:
   - Используй `git diff` (working tree, staged, last commit), чтобы найти изменённые Java-файлы в доменных пакетах.
   - Смотри `**/domain/**/*.java` и любые пакеты, содержащие `aggregate/`, `entity/`, `valueobject/`, `event/`, `repository/`, `specification/`.
   - Прочитай `build.gradle` / `pom.xml` — убедись, что `ddd-building-blocks` подключён. Если нет — пометь как **Замечание** и продолжай ревью по гайду в любом случае.

3. **Прогон каждого файла по своей группе требований.** Покрой как минимум:

   - **Entity (`ddd-tactical/entity-*`, `identity-is-immutable`):** наследует `Entity<ID>`; `id` — `final`; не переопределены `equals` / `hashCode`; нет публичных setter-ов; фабрика проверяет инварианты создания, публичного конструктора нет; нет ссылок на другие агрегаты как на объекты (только по ID).
   - **Value Object (`ddd-tactical/value-*`):** реализует `ValueObject`; `final class` (или `record`); все поля `final`; equals по значению; инварианты в конструкторе; мутирующие операции возвращают новый экземпляр.
   - **Aggregate Root (`ddd-tactical/aggregate-*`):** наследует `AggregateRoot<ID>`; события регистрируются через `registerEvent(...)` внутри корня, не снаружи; транзакционная граница = агрегат; нет ссылок на объекты других агрегатов; методы принимают доменные типы, а не объект команды, и `domain` не импортирует `usecase` (`ddd-tactical/domain-does-not-know-operations`).
   - **Domain Event (`ddd-tactical/event-*`, `events-*`):** наследует `DomainEvent` с `super(aggregateType, aggregateId)`; имя в прошедшем времени; иммутабельный; несёт ID-ы / значения, не ссылки на агрегаты; `AFTER_COMMIT` не используется для критичных эффектов.
   - **Repository (`ddd-tactical/repository-*`):** наследует `AggregateRepository<T, ID>`; интерфейс в домене, реализация в адаптере; один корень на репозиторий; `save` публикует события через `DomainEventPublisher` и зовёт `clearDomainEvents()`; методы названы в доменных терминах; возвращает только доменные типы.
   - **Domain Service (`ddd-tactical/domain-service-only-across-aggregates`):** вводится только для логики на ≥ 2 агрегатах; без состояния; не оркестратор; работает с доменными типами.
   - **Factory (`ddd-tactical/factory-only-when-needed`):** у каждого агрегата и сущности — `@UtilityClass` с `create(...)`; проверяет инварианты, возвращает валидный агрегат с начальными событиями; `builder()` агрегата зовут только фабрика и persistence-маппер, публичных конструкторов нет (`AggregateBuildersUsedOnlyByFactoriesTest`).
   - **Specification (`ddd-tactical/specification-*`):** наследует `Specification<T>`; используется только при переиспользовании или композиции; не используется для генерации SQL.
   - **Раскладка (`ddd-tactical/packages-grouped-by-domain`, `hexagonal/core-structure`):** пакеты группируются по домену (не по типу — никаких корневых `entity/`, `service/`, `repository/`); доменные пакеты не импортируют Spring / JPA / jOOQ.

4. **Формат finding, локализация, серьёзность, резюме, запрет правок** — см. `.claude/docs/shared/review-format/spec.md` (правила `review-format/*`). Перед каждым finding обязательна Read-проверка строки (`review-format/*`), поле `Строка` в формате обязательно (`review-format/finding-carries-line-and-rule`).

5. **Доменные ориентиры для серьёзности** (`review-format/severity-scale-is-shared`):
   - **Критично** — ломает инвариант или правило корректности: мутабельный VO, события вне корня, переопределённый equals на Entity, ссылки между агрегатами как объекты, нарушение транзакционной границы.
   - **Предупреждение** — отклонение от конвенции: анемичная модель, отсутствие маркера `ValueObject`, нейминг, раскладка пакетов.
   - **Замечание** — улучшение / придирка: примитив можно поднять до VO; можно упростить с `record`; отсутствует зависимость.

$ARGUMENTS
