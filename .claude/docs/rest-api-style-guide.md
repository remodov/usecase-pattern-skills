# REST API Style Guide

Свод правил для проектирования REST API: именование URL-путей, формат запросов и ответов, пагинация, обработка ошибок. Правила применимы к любому домену и стеку.

Каждое правило идентифицируется кодом (`R-URL-1`, `R-ERR-X3` и т. п.). Скиллы `ucp-api-design` и `ucp-api-review` цитируют эти коды в findings.

---

## Содержание

1. [Общие принципы — `R-PRIN-*`](#1-общие-принципы)
2. [Формат URL-пути — `R-URL-*`](#2-формат-url-пути)
3. [Ресурсы — `R-RES-*`](#3-ресурсы)
4. [HTTP-методы и семантика — `R-MTH-*`](#4-http-методы-и-семантика)
5. [Вложенность ресурсов — `R-NEST-*`](#5-вложенность-ресурсов)
6. [Alias-сегменты — `R-ALIAS-*`](#6-alias-сегменты)
7. [Action-эндпоинты — `R-ACT-*`](#7-action-эндпоинты)
8. [Версионирование — `R-VER-*`](#8-версионирование)
9. [Query-параметры — `R-QRY-*`](#9-query-параметры)
10. [Именование полей в JSON — `R-FLD-*`](#10-именование-полей-в-json)
11. [Формат ответов — `R-RSP-*`](#11-формат-ответов)
12. [Заголовки — `R-HDR-*`](#12-заголовки)
13. [Формат ошибок (RFC 9457) — `R-ERR-*`](#13-формат-ошибок----rfc-9457-problem-details)
14. [Rate limiting — `R-RATE-*`](#14-rate-limiting)
15. [Загрузка файлов — `R-FILE-*`](#15-загрузка-файлов)
16. [Deprecation — `R-DEP-*`](#16-deprecation)
17. [Batch-операции — `R-BATCH-*`](#17-batch-операции)
18. [Длительные операции (async) — `R-ASYNC-*`](#18-длительные-операции-async)
19. [Локализация — `R-LOC-*`](#19-локализация)
20. [OpenAPI-метаданные — `R-OAS-*`](#20-openapi-метаданные)
21. [Антипаттерны — сводка `R-*-X*`](#21-антипаттерны)

---

## 1. Общие принципы

### 1.1 Обязательно

- **R-PRIN-1.** Предсказуемость: разработчик, знающий один эндпоинт, должен угадать остальные.
- **R-PRIN-2.** Единообразие: одни и те же правила для всех контекстов и сервисов.
- **R-PRIN-3.** Читаемость: URL читается как фраза на английском (`GET /orders/{id}/items` = «get order's items»).
- **R-PRIN-4.** Стабильность: URL — часть публичного контракта; изменение = breaking change.

### 1.2 Запрещено

- **R-PRIN-X1.** HATEOAS-ссылки в теле ответа. Единственное исключение — заголовок `Location` при создании ресурса. Навигация между ресурсами описывается в OpenAPI-спецификации, а не встраивается в тело ответа.

---

## 2. Формат URL-пути

### 2.1 Обязательно

- **R-URL-1.** Только строчные буквы.
  ```
  /api/v1/order-items     -- правильно
  ```
- **R-URL-2.** Разделитель слов — дефис (kebab-case).
  ```
  /api/v1/delivery-addresses   -- правильно
  ```
- **R-URL-3.** Служебные эндпоинты живут вне `/api/v1/...`, не требуют аутентификации (или защищены отдельно через management-порт) и не версионируются:
  - `/health` или `/api/health` — проверка работоспособности
  - `/ready` — готовность принимать трафик (Kubernetes readiness)
  - `/info` — метаинформация о сервисе (версия, окружение)
  - `/metrics` — метрики (Prometheus, Micrometer)

### 2.2 Запрещено

- **R-URL-X1.** Заглавные буквы или snake_case в пути.
  ```
  /api/v1/OrderItems      -- неправильно
  /api/v1/order_items     -- неправильно
  /api/v1/deliveryAddresses    -- неправильно
  ```
- **R-URL-X2.** Завершающий слеш.
  ```
  /api/v1/orders/      -- неправильно
  ```
- **R-URL-X3.** Расширения файлов в пути.
  ```
  /api/v1/orders.json  -- неправильно
  ```
- **R-URL-X4.** Глаголы в пути для CRUD-операций (исключение — action-эндпоинты, см. раздел 7).
  ```
  GET /api/v1/getOrders       -- неправильно
  POST /api/v1/createOrder    -- неправильно
  ```

---

## 3. Ресурсы

### 3.1 Обязательно

- **R-RES-1.** Коллекция — имя существительное во множественном числе.
  ```
  /api/v1/orders              -- коллекция заказов
  /api/v1/orders/{id}         -- конкретный заказ
  /api/v1/users               -- коллекция пользователей
  /api/v1/users/{id}          -- конкретный пользователь
  ```
- **R-RES-2.** Singleton-ресурсы (существуют ровно в одном экземпляре в контексте родителя) — единственное число.
  ```
  /api/v1/users/{id}/profile       -- профиль пользователя (один на пользователя)
  /api/v1/settings                  -- глобальные настройки
  ```
- **R-RES-3.** Имя ресурса — доменный термин из Ubiquitous Language. Если в домене сущность называется `Order` — в URL `orders`, не `purchases`, не `transactions`.
  - **Order** → `/orders`, не `/purchases`, `/transactions`
  - **OrderItem** → `/items` (вложенный), не `/lines`, `/rows`, `/products`
  - **DeliveryAddress** → `/delivery-addresses`, не `/addresses`, `/shipping-info`
  - **Payment** → `/payments`, не `/charges`, `/billing`

### 3.2 Запрещено

- **R-RES-X1.** Единственное число для коллекций.
  ```
  /api/v1/order        -- неправильно
  ```
- **R-RES-X2.** Смешение единственного и множественного числа в одном дереве.
  ```
  /order/{id}/items    -- неправильно
  /orders/{id}/item    -- неправильно
  ```

---

## 4. HTTP-методы и семантика

### 4.1 Обязательно

- **R-MTH-1.** `GET` — чтение без побочных эффектов, идемпотентный. Пример: `GET /orders/{id}`.
- **R-MTH-2.** `POST` — создание ресурса или выполнение команды, неидемпотентный. Пример: `POST /orders`.
- **R-MTH-3.** `PUT` — полная замена ресурса, идемпотентный. Пример: `PUT /orders/{id}`.
- **R-MTH-4.** `PATCH` — частичное обновление ресурса. Формально неидемпотентный по [RFC 5789](https://www.rfc-editor.org/rfc/rfc5789), но при использовании JSON Merge Patch ([RFC 7396](https://www.rfc-editor.org/rfc/rfc7396.html)) идемпотентный на практике. Пример: `PATCH /orders/{id}`.
- **R-MTH-5.** `DELETE` — удаление ресурса, идемпотентный. Пример: `DELETE /orders/{id}/items/{id}`.
- **R-MTH-6.** Коды успешных ответов соответствуют семантике метода:
  - `GET` (один) → `200 OK`; ошибки: `404`
  - `GET` (список) → `200 OK`
  - `POST` (создание) → `201 Created` + заголовок `Location`; ошибки: `400`
  - `POST` (команда) → `200 OK` или `202 Accepted`; ошибки: `400`
  - `PUT` → `200 OK`; ошибки: `400`, `404`
  - `PATCH` → `200 OK`; ошибки: `400`, `404`
  - `DELETE` → `204 No Content`; ошибки: `404`

  Полный перечень допустимых кодов ошибок — в правиле `R-ERR-9`.

### 4.2 Запрещено

- **R-MTH-X1.** `GET` с побочным эффектом (изменение состояния).
  ```
  GET /api/v1/orders/{id}/cancel    -- НЕПРАВИЛЬНО (побочный эффект через GET)
  POST /api/v1/orders/{id}/cancel   -- правильно
  ```

---

## 5. Вложенность ресурсов

### 5.1 Обязательно

- **R-NEST-1.** Максимум два уровня вложенности.
  ```
  /api/v1/orders/{id}/items                       -- правильно (2 уровня)
  /api/v1/orders/{id}/items/{id}                  -- правильно (2 уровня + id)
  ```
  Если нужен третий уровень — вынеси ресурс на верхний уровень с фильтром:
  ```
  GET /api/v1/items?orderId={id}                  -- альтернатива глубокой вложенности
  ```
- **R-NEST-2.** Вложенность отражает принадлежность: дочерний ресурс не существует вне родителя.
  ```
  /api/v1/orders/{id}/items            -- OrderItem не существует без Order
  /api/v1/users/{id}/orders            -- допустимо, но лучше /orders?userId={id}
  ```
- **R-NEST-3.** Идентификатор — в пути, не в теле запроса.
  ```
  PUT /api/v1/orders/{id}              -- id из пути
  ```
- **R-NEST-4.** Path-переменная для идентификатора в дизайне URL всегда называется `{id}`. Контекст (имя ресурса в предыдущем сегменте) устраняет неоднозначность.
  ```
  /api/v1/orders/{id}              -- правильно
  /api/v1/orders/{id}/items/{id}   -- правильно (первый {id} = order, второй = item)
  ```

  > **Двойной стандарт с OpenAPI:** в спецификации OpenAPI параметры пути обязаны быть уникально именованы (`orderId`, `itemId`) — это требование инструмента (Swagger/Redoc не работают с одинаковыми именами). См. правило `R-OAS-3`.

### 5.2 Запрещено

- **R-NEST-X1.** Глубина вложенности более двух уровней.
  ```
  /api/v1/users/{id}/orders/{id}/items/{id}       -- неправильно (3 уровня)
  ```
- **R-NEST-X2.** ID в теле запроса вместо пути.
  ```
  PUT /api/v1/orders  { "id": "..." }    -- неправильно
  ```
- **R-NEST-X3.** Избыточное именование `{id}` в дизайне URL, когда контекст уже задан.
  ```
  /api/v1/orders/{orderId}         -- неправильно (имя ресурса уже в пути)
  ```

---

## 6. Alias-сегменты

В ряде случаев вместо конкретного идентификатора в path используется зарезервированное слово-алиас. Это серверный shortcut, который разрешается в конкретный ресурс на основе контекста (токен, сессия, бизнес-логика).

### 6.1 Обязательно

- **R-ALIAS-1.** `me` используется только в эндпоинтах, которые **могут принять и свой, и чужой ID** (admin scope, OAuth-приложения, сервис-аккаунты). `me` явно фиксирует «текущий пользователь из токена».
  ```
  GET /api/v1/users/{id}    -- общий эндпоинт; админ может смотреть любого
  GET /api/v1/users/me      -- тот же эндпоинт, но «свой профиль» через alias
  ```
  Граница: «может ли супер-админ обратиться по другому ID к этому же эндпоинту?» Да → `me` нужен.

  `me` — де-факто стандарт (GitHub API, Google API, Spotify API, Microsoft Graph). Альтернативы (`self`, `current-user`) допустимы, но менее распространены.

- **R-ALIAS-2.** Временные и порядковые alias-сегменты допустимы для singleton-выборки:
  - `latest` — `GET /api/v1/deployments/latest`
  - `current` — `GET /api/v1/subscriptions/current`
  - `next` — `GET /api/v1/invoices/next`
  - `previous` — `GET /api/v1/billing-periods/previous`
  - `first` — `GET /api/v1/versions/first`
  - `last` — `GET /api/v1/transactions/last`

- **R-ALIAS-3.** Логические alias по бизнес-признаку допустимы для singleton-выборки:
  - `default` — `GET /api/v1/payment-methods/default`
  - `primary` — `GET /api/v1/addresses/primary`
  - `active` — `GET /api/v1/plans/active`
  - `draft` — `GET /api/v1/documents/draft`

### 6.2 Запрещено

- **R-ALIAS-X1.** `me` в эндпоинтах, которые по дизайну работают только с ресурсами вызывающего. Контекст из токена — единственный источник, `me` избыточен.
  ```
  GET /api/v1/users/me/orders    -- неправильно (orders и так «его» из контекста токена)
  GET /api/v1/orders             -- правильно (заказы текущего пользователя из контекста)
  ```
  Тест: «может ли супер-админ обратиться по другому ID?» Нет → `me` не нужен, эндпоинт singleton (`/profile`, `/settings`).

- **R-ALIAS-X2.** `me` как самостоятельный путь без `users/` префикса.
  ```
  GET /api/v1/me      -- неправильно (me — alias для users/{id}, не отдельный ресурс)
  ```

---

## 7. Action-эндпоинты

Не все операции укладываются в CRUD. Доменные команды, меняющие состояние агрегата, оформляются как action-эндпоинты.

### 7.1 Обязательно

- **R-ACT-1.** Формат: ресурс + действие.
  ```
  POST /api/v1/orders/{id}/confirm
  POST /api/v1/orders/{id}/cancel
  POST /api/v1/orders/{id}/ship
  POST /api/v1/orders/{id}/refund
  ```
- **R-ACT-2.** Имя действия — глагол в инфинитиве.
  ```
  /orders/{id}/confirm      -- правильно
  ```
- **R-ACT-3.** Метод — `POST`. Даже если операция идемпотентна по факту (повторный `confirm` не изменит состояние), это команда, а не замена ресурса.
- **R-ACT-4.** Параметры действия (если нужны) — в теле запроса. Если параметров нет — пустое тело допустимо.
  ```http
  POST /api/v1/orders/{id}/ship
  Content-Type: application/json

  {
    "trackingNumber": "TR-123456",
    "carrier": "DHL"
  }
  ```

### 7.2 Запрещено

- **R-ACT-X1.** Существительное или причастие в имени действия.
  ```
  /orders/{id}/confirmation -- неправильно (существительное)
  /orders/{id},/confirmed   -- неправильно (причастие)
  ```
- **R-ACT-X2.** Любой метод кроме `POST` для action-эндпоинта.
  ```
  PUT /api/v1/orders/{id}/confirm    -- неправильно (PUT = замена ресурса)
  ```

---

## 8. Версионирование

### 8.1 Обязательно

- **R-VER-1.** Версия — в URL-пути.
  ```
  /api/v1/orders
  /api/v2/orders
  ```
- **R-VER-2.** Формат версии: `v` + целое число.
  ```
  /api/v1/...     -- правильно
  ```
- **R-VER-3.** Префикс `/api` обязателен для всех бизнес-эндпоинтов.
  ```
  /api/v1/orders       -- правильно
  ```
- **R-VER-4.** Новая версия (`v1` → `v2`) создаётся **только** при breaking change. Обратно-совместимые изменения допустимы в рамках текущей версии.
- **R-VER-5.** Клиент API ОБЯЗАН игнорировать (или явно обрабатывать как unknown) неизвестные значения enum и неизвестные поля в ответе. На этом обязательстве основано правило `R-VER-6`: добавление нового enum-значения или нового поля — non-breaking. Сервер развивает API без новой версии при условии, что клиенты следуют этому правилу.
- **R-VER-6.** Перечень изменений по типам.

  **Ломающие (требуют новую версию):**
  - Удаление эндпоинта
  - Удаление или переименование поля из ответа
  - Удаление или переименование query-параметра или path-переменной
  - Добавление нового **обязательного** параметра в запрос
  - Изменение типа поля (`string` → `number`, `object` → `array`)
  - Изменение формата поля (`date` → `date-time`, изменение формата enum)
  - Удаление значения из enum
  - Изменение HTTP-метода эндпоинта
  - Изменение URL-пути эндпоинта
  - Изменение кода успешного ответа (`200` → `201`)
  - Изменение семантики существующего поля
  - Добавление нового обязательного заголовка
  - Ужесточение валидации (было `maxLength: 100`, стало `maxLength: 50`)
  - Изменение Content-Type ответа

  **Не ломающие (допустимы в текущей версии, опираются на `R-VER-5`):**
  - Добавление нового необязательного поля в ответ
  - Добавление нового необязательного query-параметра
  - Добавление нового значения в enum
  - Добавление нового эндпоинта
  - Добавление нового необязательного заголовка
  - Ослабление валидации (было `maxLength: 50`, стало `maxLength: 100`)
  - Добавление нового кода ошибки в `ErrorCode` enum
  - Изменение текста в `detail` или `title` ошибки

### 8.2 Запрещено

- **R-VER-X1.** Минорная или дата-версия в пути.
  ```
  /api/v1.2/...   -- неправильно
  /api/2024/...   -- неправильно
  ```
- **R-VER-X2.** Версия в query-параметре.
  ```
  /orders?version=1   -- неправильно
  ```
- **R-VER-X3.** Эндпоинт без префикса `/api` или без версии.
  ```
  /v1/orders           -- неправильно (нет /api)
  /orders              -- неправильно (нет ни /api, ни версии)
  ```
- **R-VER-X4.** Создание новой версии для добавления необязательного поля.

---

## 9. Query-параметры

### 9.1 Обязательно

- **R-QRY-1.** Имена параметров — camelCase.
  ```
  GET /api/v1/orders?customerId=123&dateFrom=2025-01-01    -- правильно
  ```
- **R-QRY-2.** Фильтрация по полю — имя поля как параметр.
  ```
  GET /api/v1/orders?status=CONFIRMED
  GET /api/v1/orders?customerId=550e8400-e29b-41d4-a716-446655440000
  ```
- **R-QRY-3.** Диапазоны — суффиксы `From` / `To`.
  ```
  GET /api/v1/orders?dateFrom=2025-01-01&dateTo=2025-12-31
  GET /api/v1/orders?amountFrom=100&amountTo=500
  ```
- **R-QRY-4.** Offset-based пагинация: параметры `page` (1-based) и `size`.
  ```
  GET /api/v1/orders?page=1&size=20
  GET /api/v1/orders?page=3&size=50
  ```
  - `page` — номер страницы, 1-based: первая страница = 1.
  - `size` — количество элементов на странице. Значение по умолчанию задаётся сервером (например, 20).

  **Реализация:** контракт API — 1-based; в Spring Data конфигурируется `spring.data.web.pageable.one-indexed-parameters=true`. Ручная конвертация `page-1` в коде запрещена — теряется единая точка истины (детали — в bootstrap-style-guide).

  Пример ответа:
  ```json
  {
    "content": [
      { "orderId": "...", "status": "CREATED" }
    ],
    "page": 1,
    "size": 20,
    "totalElements": 243,
    "totalPages": 13
  }
  ```

  **Когда использовать:** произвольный переход на любую страницу; нужно знать общее количество (`totalElements`); данные относительно статичны; UI с номерами страниц.

  **Ограничения:** при вставке/удалении между запросами элементы могут дублироваться или пропускаться; `OFFSET` в SQL деградирует на больших смещениях.

- **R-QRY-5.** Cursor-based пагинация: параметры `cursor` (непрозрачный токен) и `size`.
  ```
  GET /api/v1/orders?size=20                              -- первая страница
  GET /api/v1/orders?size=20&cursor=eyJpZCI6MTAwfQ==      -- следующая страница
  ```
  - `cursor` — непрозрачный токен из предыдущего ответа. Клиент НЕ парсит и НЕ конструирует его.
  - `size` — количество элементов.

  Пример ответа:
  ```json
  {
    "content": [
      { "orderId": "...", "status": "CREATED" }
    ],
    "size": 20,
    "nextCursor": "eyJpZCI6MTIwfQ==",
    "prevCursor": "eyJpZCI6MTAwfQ==",
    "hasNext": true,
    "hasPrev": true
  }
  ```

  **Когда использовать:** часто меняющиеся данные (ленты, сообщения, уведомления); большие объёмы; infinite scroll; real-time потоки.

  **Ограничения:** нет произвольного перехода на страницу N; нельзя узнать общее количество без отдельного запроса.

- **R-QRY-6.** Сортировка — параметр `sort`, формат `имяПоля,направление`.
  ```
  GET /api/v1/orders?sort=createdAt,desc
  GET /api/v1/orders?sort=totalAmount,asc&sort=createdAt,desc
  ```
  Множественная сортировка через повтор параметра допустима, но должна быть обоснована (риск проблем с составными индексами).

- **R-QRY-7.** Полнотекстовый поиск — параметр `q`.
  ```
  GET /api/v1/orders?q=термин
  GET /api/v1/products?q=клавиатура
  ```

- **R-QRY-8.** Множественные значения — повтор параметра.
  ```
  GET /api/v1/orders?status=CREATED&status=CONFIRMED     -- правильно
  ```
  Это стандартный способ передачи массивов в query string. Поддерживается из коробки большинством фреймворков и корректно описывается в OpenAPI через `style: form, explode: true`.

- **R-QRY-9.** Сложные поисковые запросы — `POST /resources/search` с телом JSON.

  GET имеет практические ограничения: длина URL (~2000–8000 символов), невозможность передать вложенные структуры в query. Когда поисковый запрос не укладывается — `POST /resources/search`:
  ```http
  POST /api/v1/orders/search
  Content-Type: application/json

  {
    "statuses": ["CONFIRMED", "PAID", "SHIPPED"],
    "dateRange": { "from": "2025-01-01", "to": "2025-12-31" },
    "customer": { "regionIds": [1, 5, 12], "segment": "VIP" },
    "totalAmount": { "from": 1000, "to": 50000 },
    "sort": [
      { "field": "createdAt", "direction": "DESC" },
      { "field": "totalAmount", "direction": "ASC" }
    ],
    "page": 1,
    "size": 20
  }
  ```

  **Критерии перехода с GET на POST:**
  - Плоские поля (status, date) → GET достаточно
  - Вложенные объекты → POST
  - Массив 10+ значений в одном фильтре → POST
  - Спецсимволы или свободный текст → POST (GET ломает читаемость из-за кодирования)
  - AND/OR-комбинации → POST
  - Запрос нужно сохранять/переиспользовать → POST

  **Правила POST-поиска:**
  1. URL: `/resources/search` (не `/query`, не `/find`, не `/search/resources`).
  2. Метод: `POST` — GET с телом формально не запрещён RFC, но на практике тело игнорируется прокси, кешами и многими клиентами.
  3. Код ответа: `200 OK` (ресурс не создаётся).
  4. Формат ответа — тот же, что у `GET /resources` (пагинированный список).
  5. Идемпотентность: POST-поиск идемпотентен по факту, но HTTP этого не гарантирует — при необходимости кеширования добавь заголовок `Idempotency-Key` (см. `R-HDR-3`).

### 9.2 Запрещено

- **R-QRY-X1.** snake_case или PascalCase в именах параметров.
  ```
  ?customer_id=123     -- неправильно
  ?CustomerID=123      -- неправильно
  ```
- **R-QRY-X2.** `page=0` или 0-based нумерация в публичном контракте.
- **R-QRY-X3.** Comma-separated значения для массивов.
  ```
  ?status=CREATED,CONFIRMED            -- неправильно
  ```
  Причины: требует ручного парсинга на бэкенде; ломается, если значение содержит запятую; не соответствует поведению по умолчанию OpenAPI (`explode: true` в `style: form`).
- **R-QRY-X4.** Бизнес-логика в query-параметре вместо action-эндпоинта.
  ```
  /orders?action=cancel    -- неправильно
  POST /orders/{id}/cancel -- правильно
  ```
- **R-QRY-X5.** Парсинг или конструирование `cursor` на стороне клиента.

---

## 10. Именование полей в JSON

### 10.1 Обязательно

- **R-FLD-1.** camelCase для имён полей.
  ```json
  {
    "orderId": "550e8400-e29b-41d4-a716-446655440000",
    "createdAt": "2025-03-15T10:30:00Z",
    "totalAmount": 1500.00,
    "deliveryAddress": {
      "streetName": "Ленина",
      "zipCode": "123456"
    }
  }
  ```
- **R-FLD-2.** Даты и время — ISO 8601.
  ```json
  {
    "createdAt": "2025-03-15T10:30:00Z",
    "dateFrom": "2025-01-01",
    "dateTo": "2025-12-31"
  }
  ```
- **R-FLD-3.** Enum-значения — UPPER_SNAKE_CASE.
  ```json
  {
    "status": "IN_PROGRESS",
    "paymentMethod": "CREDIT_CARD"
  }
  ```
- **R-FLD-4.** Имена коллекций — множественное число.
  ```json
  {
    "items": [{ "itemId": "..." }],
    "errors": [{ "code": "...", "message": "..." }],
    "tags": ["electronics", "sale"]
  }
  ```
- **R-FLD-5.** Идентификаторы — суффикс `Id`.
  ```json
  {
    "orderId": "...",
    "customerId": "...",
    "parentCategoryId": "..."
  }
  ```
- **R-FLD-6.** В теле PATCH-запроса (JSON Merge Patch, [RFC 7396](https://www.rfc-editor.org/rfc/rfc7396.html)) явный `null` — команда удалить поле. Это семантика **запроса**, не нарушение `R-RSP-X1` (правило про `null` в ответе).
  ```http
  PATCH /api/v1/orders/{id}
  Content-Type: application/merge-patch+json

  { "comment": null }            -- удаляет поле comment
  ```

### 10.2 Допустимо (нейтрально)

- **R-FLD-7.** Boolean — префикс `is` / `has` / `can` опционально, главное единообразие в проекте.
  ```json
  {
    "active": true,
    "hasDiscount": false,
    "canCancel": true
  }
  ```

---

## 11. Формат ответов

### 11.1 Обязательно

- **R-RSP-1.** Единичный ресурс — плоский объект без обёртки.
  ```json
  {
    "orderId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "CONFIRMED",
    "totalAmount": 1500.00,
    "createdAt": "2025-03-15T10:30:00Z",
    "items": [
      {
        "itemId": "...",
        "productName": "Клавиатура",
        "quantity": 2,
        "price": 750.00
      }
    ]
  }
  ```
  Вложенные объекты и коллекции допустимы внутри ресурса.

- **R-RSP-2.** Коллекция — `{ "content": [...] }` плюс метаданные пагинации на том же уровне (см. `R-QRY-4`/`R-QRY-5`). Поле с данными всегда называется `content` — это не envelope, а структура пагинированного ответа.

- **R-RSP-3.** Создание ресурса (`POST`) — `201 Created`. Тело: созданный ресурс целиком. Заголовок `Location` — URL нового ресурса.
  ```http
  HTTP/1.1 201 Created
  Location: /api/v1/orders/550e8400-e29b-41d4-a716-446655440000

  {
    "orderId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "CREATED",
    "totalAmount": 0,
    "createdAt": "2025-03-15T10:30:00Z"
  }
  ```

- **R-RSP-4.** Обновление ресурса (`PUT` / `PATCH`) — `200 OK`. Тело: обновлённый ресурс целиком.
  ```http
  HTTP/1.1 200 OK

  {
    "orderId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "CONFIRMED",
    "totalAmount": 1500.00,
    "updatedAt": "2025-03-15T11:00:00Z"
  }
  ```

- **R-RSP-5.** Удаление ресурса (`DELETE`) — `204 No Content` с пустым телом.
  ```http
  HTTP/1.1 204 No Content
  ```

- **R-RSP-6.** Action-эндпоинты — `200 OK`. Тело: обновлённый ресурс. Для асинхронных действий — `202 Accepted` (см. раздел 18).
  ```http
  POST /api/v1/orders/{id}/confirm

  HTTP/1.1 200 OK

  {
    "orderId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "CONFIRMED",
    "confirmedAt": "2025-03-15T11:00:00Z"
  }
  ```

- **R-RSP-7.** Пустые коллекции — `[]`, не `null`, не отсутствие поля.
  ```json
  { "items": [] }     -- правильно
  ```

- **R-RSP-8.** В OpenAPI: поля, которые могут отсутствовать в ответе, не включаются в `required`. Поля, которые присутствуют всегда, — указываются в `required`.
  ```yaml
  OrderResponse:
    type: object
    required:
      - orderId
      - status
      - items
    properties:
      orderId:
        type: string
        format: uuid
      status:
        $ref: '#/components/schemas/OrderStatus'
      items:
        type: array
        items:
          $ref: '#/components/schemas/OrderItemResponse'
      discount:
        type: number
        description: 'Отсутствует если скидки нет'
      comment:
        type: string
        description: 'Отсутствует если не заполнен'
  ```

### 11.2 Запрещено

- **R-RSP-X1.** Поля со значением `null` в успешном ответе (2xx). Если поле не заполнено — оно отсутствует в JSON. Это уменьшает размер ответа и упрощает контракт.

  Пример: поле `discount` отсутствует, а не `"discount": null`.
  ```json
  {
    "orderId": "...",
    "status": "CREATED",
    "items": [],
    "comment": "Доставить до 18:00"
  }
  ```

  > Семантика `null` в **запросах** PATCH (JSON Merge Patch) — это команда удалить поле. См. `R-FLD-6`.

- **R-RSP-X2.** Пустые строки `""` вместо отсутствия поля.

- **R-RSP-X3.** `nullable: true` в OpenAPI — поле либо есть, либо отсутствует.

- **R-RSP-X4.** Envelope-обёртка для единичных ресурсов.

  Неправильно:
  ```json
  {
    "success": true,
    "data": { "orderId": "...", "status": "CREATED" },
    "error": null
  }
  ```
  Правильно:
  ```json
  {
    "orderId": "...",
    "status": "CREATED"
  }
  ```
  Причины: HTTP-статус уже сообщает об успехе/ошибке; ошибки возвращаются в формате RFC 9457 (раздел 13); коллекции оборачиваются в `{ "content": [...] }` — это не envelope, а структура пагинации.

---

## 12. Заголовки

### 12.1 Обязательно

- **R-HDR-1.** Стандартные HTTP-заголовки используются по назначению:
  - `Content-Type` — тип тела запроса/ответа (`application/json`)
  - `Accept` — ожидаемый тип ответа (`application/json`)
  - `Authorization` — аутентификация (`Bearer eyJhbGci...`)
  - `Location` — URL созданного ресурса при `201 Created`
  - `ETag` — версия ресурса для кеширования (`"33a64df5"`)
  - `If-None-Match` — условный GET (`"33a64df5"`)

- **R-HDR-2.** Кастомные заголовки используют доменный префикс, единый для всех сервисов проекта/компании. Префикс выбирается один раз и фиксируется в стандартах команды (в примере — `Shop-`):
  ```
  Shop-Request-Id: 550e8400-e29b-41d4-a716-446655440000
  Shop-Client-Version: 2.1.0
  ```
  - `Shop-Request-Id` — идентификатор конкретного запроса от клиента (для дедупликации и логирования). Не путать с `traceparent` (см. `R-HDR-4`).

- **R-HDR-3.** Для POST-запросов, которые должны быть безопасны при повторной отправке, используется заголовок `Idempotency-Key`.
  ```
  POST /api/v1/orders
  Idempotency-Key: 550e8400-e29b-41d4-a716-446655440000
  ```

- **R-HDR-4.** Для распределённой трассировки используется стандарт [W3C Trace Context](https://www.w3.org/TR/trace-context/). Заголовок `traceparent` передаётся клиентом или генерируется на входе и прокидывается через все сервисы в цепочке.

  Формат: `traceparent: {version}-{trace-id}-{parent-id}-{trace-flags}`
  - `version` — версия формата, сейчас всегда `00`
  - `trace-id` — 32 hex-символа, уникальный ID всей цепочки вызовов
  - `parent-id` — 16 hex-символов, ID текущего span'а
  - `trace-flags` — 2 hex-символа (например, `01` = sampled)

  Пример:
  ```
  traceparent: 00-1f2a8b6c7d3e4f5a9b0c1d2e3f4a5b6c-7a8b9c0d1e2f3a4b-01
  ```

  Правила:
  - Если клиент прислал `traceparent` — сервис использует его `trace-id` и создаёт новый `parent-id` для своего span'а.
  - Если клиент не прислал — сервис генерирует `traceparent` на входе.
  - `trace-id` из `traceparent` используется как `traceId` в теле ошибки RFC 9457 (см. `R-ERR-1`).
  - Опциональный `tracestate` — для vendor-специфичных данных.
  ```
  traceparent: 00-1f2a8b6c7d3e4f5a9b0c1d2e3f4a5b6c-7a8b9c0d1e2f3a4b-01
  tracestate: vendor1=value1,vendor2=value2
  ```

### 12.2 Запрещено

- **R-HDR-X1.** Префикс `X-` в кастомных заголовках. Устарел по [RFC 6648](https://www.rfc-editor.org/rfc/rfc6648.html).

---

## 13. Формат ошибок — RFC 9457 Problem Details

Для кодов ответа НЕ 2xx используется единая структура по [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457.html). Допустимо добавлять кастомные атрибуты под нужды проекта.

### 13.1 Обязательно

- **R-ERR-1.** Тело ошибки соответствует структуре RFC 9457:
  ```json
  {
    "type": "urn:problem:order-service:validation-error",
    "status": 400,
    "title": "Validation Error",
    "detail": "Поле amount должно быть больше 0.",
    "instance": "urn:uuid:9f2d6c22-8e6d-4c2a-9b41-6b9a5e2f6c10",
    "traceId": "00-1f2a8b6c7d3e4f5a9b0c1d2e3f4a5b6c-7a8b9c0d1e2f3a4b-01",
    "code": "VALIDATION_ERROR"
  }
  ```

  Атрибуты:
  - **`type`** — стабильный URI/URN, идентифицирующий **категорию** ошибки. Подробнее в `R-ERR-2`.
  - **`status`** — HTTP-статус ответа.
  - **`title`** — короткое описание (обычно совпадает с названием статуса).
  - **`instance`** — уникальный идентификатор инцидента (URI/URN).
  - **`traceId`** — ID трассировки (из заголовка `traceparent`, см. `R-HDR-4`).
  - **`code`** — символьный enum-код для программной логики. Все возможные коды ошибок указаны как enum в контракте.
  - **`detail`** — человекочитаемое сообщение для отображения пользователю (может быть на русском). Допустимо динамическое формирование по маске; допустимо несколько вариантов `detail` для одного `code`.

- **R-ERR-2.** `type` — стабильный идентификатор **категории** ошибки. Одна и та же категория всегда возвращает один и тот же `type`. Это не ссылка на Swagger/OpenAPI, не JSON-схема, не динамический URL.

  **Допустимые формы:**

  1. **URL на резолвимую страницу документации:**
     ```
     "type": "https://errors.example.com/order/not-found"
     "type": "https://developer.example.com/errors/insufficient-stock"
     ```
     Страница описывает: что за ошибка, почему возникает, как исправить. Может располагаться на developer-портале, wiki, внутреннем портале документации.

  2. **URN формы `urn:problem:<service>:<code>`** — используется, если портала документации ошибок нет:
     ```
     "type": "urn:problem:order-service:order-not-found"
     "type": "urn:problem:catalog:product-archived"
     ```
     URN сохраняет машиночитаемую категорию ошибки и не требует deployment портала.

  Отношение к другим полям:
  - `type` — категория ошибки, стабильная (стандарт RFC).
  - `code` — enum для программной логики на клиенте (`ORDER_NOT_FOUND`). Удобная работа в коде без парсинга URI.
  - `instance` — уникальный URN конкретного инцидента, меняется при каждом вызове.
  - `detail` — текст для отображения пользователю.

- **R-ERR-3.** Content-Type ответа с ошибкой — `application/problem+json`.

- **R-ERR-4.** `code` формируется как UPPER_SNAKE_CASE. Все возможные коды перечислены в OpenAPI как enum.
  ```
  INTERNAL_SERVER_ERROR
  MISSING_DEFAULT_CARD
  APPLICATION_ALREADY_SENT
  ORDER_EMPTY
  EXT_SYSTEM_UNAVAILABLE
  ```

- **R-ERR-5.** Ошибки валидации полей возвращаются с HTTP-кодом `400 Bad Request`, `code = VALIDATION_ERROR` и расширением `violations` — массивом ошибок по конкретным полям:
  ```json
  {
    "type": "urn:problem:order-service:validation-error",
    "status": 400,
    "title": "Bad Request",
    "detail": "Ошибка валидации входных данных",
    "instance": "urn:uuid:9f2d6c22-8e6d-4c2a-9b41-6b9a5e2f6c10",
    "traceId": "00-1f2a8b6c7d3e4f5a9b0c1d2e3f4a5b6c-7a8b9c0d1e2f3a4b-01",
    "code": "VALIDATION_ERROR",
    "violations": [
      { "field": "amount", "message": "Сумма должна быть больше 0" },
      { "field": "deliveryAddress.zipCode", "message": "Почтовый индекс обязателен" },
      { "field": "items[0].quantity", "message": "Количество должно быть от 1 до 99" }
    ]
  }
  ```

- **R-ERR-6.** Правила формирования `violations`:
  - **`field`** — путь к полю в теле запроса. Dot-notation для вложенных объектов (`deliveryAddress.zipCode`), индексы для массивов (`items[0].quantity`).
  - **`message`** — человекочитаемое описание ошибки для отображения рядом с полем.
  - Массив содержит **все** ошибки валидации, а не только первую — клиент должен подсветить все невалидные поля за один запрос.
  - Если ошибка относится к объекту целиком (не к конкретному полю) — `field` не указывается или равен пустой строке.

- **R-ERR-7.** OpenAPI-схема `ProblemDetails` и `Violation`. ENUM-список `ErrorCode` формируется один на контракт.
  ```yaml
  ErrorCode:
    type: string
    description: 'Символьный код ошибки'
    enum:
      - INTERNAL_SERVER_ERROR

  ProblemDetails:
    type: object
    description: 'Problem Details (RFC 9457)'
    properties:
      type:
        type: string
        format: uri
        description: 'URI или URN, идентифицирующий тип ошибки'
      status:
        type: integer
        format: int32
        description: 'HTTP статус'
      title:
        type: string
        description: 'Краткое описание ошибки'
      detail:
        type: string
        description: 'Подробности ошибки'
      instance:
        type: string
        format: uri
        description: 'URI конкретного экземпляра ошибки'
      traceId:
        type: string
      code:
        $ref: '#/components/schemas/ErrorCode'
      violations:
        type: array
        description: 'Ошибки валидации по полям. Присутствует только при code=VALIDATION_ERROR'
        items:
          $ref: '#/components/schemas/Violation'

  Violation:
    type: object
    required:
      - message
    properties:
      field:
        type: string
        description: 'Путь к полю (dot-notation). Отсутствует если ошибка относится к объекту целиком'
        example: 'deliveryAddress.zipCode'
      message:
        type: string
        description: 'Описание ошибки для отображения пользователю'
        example: 'Почтовый индекс обязателен'
  ```

- **R-ERR-8.** Все доступные ошибки указаны как `examples` в объектах ответа каждого метода. Полные перечни ниже.

- **R-ERR-9.** Используемые HTTP-коды ошибок:
  - `400` и `500` — всегда
  - `401` и `403` — если есть аутентификация и авторизация
  - `404` — если обращение к конкретному объекту по ID
  - `409` — конфликт при конкурентном обновлении (оптимистичная блокировка, дубликат)
  - `410` — для удалённых deprecated-эндпоинтов (см. раздел 16)
  - `429` — при превышении лимита запросов (см. раздел 14)

### 13.2 Запрещено

- **R-ERR-X1.** Content-Type `application/json` для тела ошибки. Используй `application/problem+json`.

- **R-ERR-X2.** `type: "about:blank"`. Теряется машиночитаемая категория ошибки. Если портала документации нет — используй URN формы `urn:problem:<service>:<code>` (см. `R-ERR-2`).

- **R-ERR-X3.** HTTP-коды ошибок вне списка `R-ERR-9` (например, `418`, `422`, `451`). Если возникает потребность — обсуждай в архитектурном комитете.

- **R-ERR-X4.** Stack traces, SQL-запросы, внутренние пути в теле ошибки `500`.

### 13.3 Examples в OpenAPI (для копирования в контракт)

#### `400 Bad Request` — всегда

```yaml
"400":
  description: 'Bad Request'
  content:
    application/problem+json:
      schema:
        $ref: "#/components/schemas/ProblemDetails"
      examples:
        validation:
          summary: 'Ошибка валидации полей'
          value:
            type: "urn:problem:order-service:validation-error"
            status: 400
            title: "Bad Request"
            detail: "Ошибка валидации входных данных"
            code: VALIDATION_ERROR
            violations:
              - field: "amount"
                message: "Сумма должна быть больше 0"
              - field: "deliveryAddress.zipCode"
                message: "Почтовый индекс обязателен"
        malformed:
          summary: 'Некорректный формат запроса'
          value:
            type: "urn:problem:order-service:malformed-request"
            status: 400
            title: "Bad Request"
            detail: "Невозможно разобрать тело запроса"
            code: MALFORMED_REQUEST
```

#### `401 Unauthorized` — если есть аутентификация

```yaml
"401":
  description: 'Unauthorized'
  content:
    application/problem+json:
      schema:
        $ref: "#/components/schemas/ProblemDetails"
      examples:
        expired:
          summary: 'Токен истёк'
          value:
            type: "urn:problem:order-service:token-expired"
            status: 401
            title: "Unauthorized"
            detail: "Токен доступа истёк. Получите новый токен."
            code: TOKEN_EXPIRED
        missing:
          summary: 'Токен отсутствует'
          value:
            type: "urn:problem:order-service:token-missing"
            status: 401
            title: "Unauthorized"
            detail: "Заголовок Authorization отсутствует"
            code: TOKEN_MISSING
```

#### `403 Forbidden` — если есть авторизация

```yaml
"403":
  description: 'Forbidden'
  content:
    application/problem+json:
      schema:
        $ref: "#/components/schemas/ProblemDetails"
      examples:
        forbidden:
          summary: 'Нет прав'
          value:
            type: "urn:problem:order-service:access-denied"
            status: 403
            title: "Forbidden"
            detail: "Недостаточно прав для выполнения операции"
            code: ACCESS_DENIED
```

#### `404 Not Found` — если обращение к конкретному объекту по ID

Также возвращается, если ресурс существует, но не принадлежит текущему пользователю (чтобы не подтверждать существование чужих ресурсов).

```yaml
"404":
  description: 'Not Found'
  content:
    application/problem+json:
      schema:
        $ref: "#/components/schemas/ProblemDetails"
      examples:
        notfound:
          summary: 'Объект не найден'
          value:
            type: "urn:problem:order-service:order-not-found"
            status: 404
            title: "Not Found"
            detail: "Заказ не найден"
            code: ORDER_NOT_FOUND
```

#### `409 Conflict` — при конкурентном обновлении или дубликате

```yaml
"409":
  description: 'Conflict'
  content:
    application/problem+json:
      schema:
        $ref: "#/components/schemas/ProblemDetails"
      examples:
        concurrent:
          summary: 'Конкурентное обновление'
          value:
            type: "urn:problem:order-service:concurrent-modification"
            status: 409
            title: "Conflict"
            detail: "Ресурс был изменён другим запросом. Повторите операцию с актуальной версией."
            code: CONCURRENT_MODIFICATION
        duplicate:
          summary: 'Дубликат ресурса'
          value:
            type: "urn:problem:order-service:duplicate-order"
            status: 409
            title: "Conflict"
            detail: "Заказ с таким номером уже существует"
            code: DUPLICATE_ORDER
```

#### `410 Gone` — для удалённых deprecated-эндпоинтов

Эндпоинт удалён после прохождения даты `Sunset` (см. раздел 16).

```yaml
"410":
  description: 'Gone'
  content:
    application/problem+json:
      schema:
        $ref: "#/components/schemas/ProblemDetails"
      examples:
        removed:
          summary: 'Эндпоинт удалён'
          value:
            type: "urn:problem:order-service:endpoint-removed"
            status: 410
            title: "Gone"
            detail: "Эндпоинт удалён. Используйте GET /api/v2/orders/{id}."
            code: ENDPOINT_REMOVED
```

#### `429 Too Many Requests` — если есть rate limiting

```yaml
"429":
  description: 'Too Many Requests'
  headers:
    Retry-After:
      schema:
        type: integer
      description: 'Секунд до сброса лимита'
    RateLimit-Limit:
      schema:
        type: integer
      description: 'Максимальное количество запросов в окне'
    RateLimit-Remaining:
      schema:
        type: integer
      description: 'Оставшееся количество запросов'
    RateLimit-Reset:
      schema:
        type: integer
      description: 'Unix timestamp сброса окна'
  content:
    application/problem+json:
      schema:
        $ref: "#/components/schemas/ProblemDetails"
      examples:
        ratelimit:
          summary: 'Превышен лимит запросов'
          value:
            type: "urn:problem:order-service:rate-limit-exceeded"
            status: 429
            title: "Too Many Requests"
            detail: "Превышен лимит запросов. Повторите через 30 секунд."
            code: RATE_LIMIT_EXCEEDED
```

#### `500 Internal Server Error` — всегда

```yaml
"500":
  description: 'Internal Server Error'
  content:
    application/problem+json:
      schema:
        $ref: "#/components/schemas/ProblemDetails"
      examples:
        internal:
          summary: 'Внутренняя ошибка'
          value:
            type: "urn:problem:order-service:internal"
            status: 500
            title: "Internal Server Error"
            detail: "Внутренняя ошибка, попробуйте позже."
            code: INTERNAL_SERVER_ERROR
        extsystem:
          summary: 'Внешняя система недоступна'
          value:
            type: "urn:problem:order-service:ext-system-unavailable"
            status: 500
            title: "Internal Server Error"
            detail: "Внешняя система недоступна, попробуйте позже."
            code: EXT_SYSTEM_UNAVAILABLE
```

Все существующие бизнес-ошибки должны быть отражены в `examples` контракта. Указывать пример всех атрибутов, формируемых аналитиками: `code`, `detail`.

---

## 14. Rate limiting

### 14.1 Обязательно

- **R-RATE-1.** При превышении лимита — `429 Too Many Requests` с заголовком `Retry-After`:
  ```http
  HTTP/1.1 429 Too Many Requests
  Retry-After: 30
  Content-Type: application/problem+json

  {
    "type": "urn:problem:order-service:rate-limit-exceeded",
    "status": 429,
    "title": "Too Many Requests",
    "detail": "Превышен лимит запросов. Повторите через 30 секунд.",
    "code": "RATE_LIMIT_EXCEEDED"
  }
  ```

- **R-RATE-2.** В каждый успешный ответ включаются заголовки информирования о лимитах:
  ```http
  HTTP/1.1 200 OK
  RateLimit-Limit: 100
  RateLimit-Remaining: 57
  RateLimit-Reset: 1719849600
  ```
  - `RateLimit-Limit` — максимальное количество запросов в окне
  - `RateLimit-Remaining` — сколько запросов осталось в текущем окне
  - `RateLimit-Reset` — Unix timestamp когда окно сбрасывается

- **R-RATE-3.** В OpenAPI указывается `429` для эндпоинтов с rate limiting:
  ```yaml
  "429":
    description: 'Too Many Requests'
    headers:
      Retry-After:
        schema:
          type: integer
        description: 'Секунд до сброса лимита'
    content:
      application/problem+json:
        schema:
          $ref: "#/components/schemas/ProblemDetails"
  ```

### 14.2 Запрещено

- **R-RATE-X1.** `429` без заголовка `Retry-After` и/или `RateLimit-*`. Клиент не сможет корректно ретраить.

---

## 15. Загрузка файлов

### 15.1 Обязательно

- **R-FILE-1.** Файлы загружаются как вложенный ресурс через `POST` с `multipart/form-data`.
  ```
  POST /api/v1/documents/{id}/attachments
  POST /api/v1/users/me/avatar
  ```

- **R-FILE-2.** Формат запроса — `multipart/form-data`:
  ```http
  POST /api/v1/documents/{id}/attachments
  Content-Type: multipart/form-data; boundary=----Boundary

  ------Boundary
  Content-Disposition: form-data; name="file"; filename="report.pdf"
  Content-Type: application/pdf

  <binary data>
  ------Boundary
  Content-Disposition: form-data; name="description"

  Отчет за март
  ------Boundary--
  ```

- **R-FILE-3.** Ограничения на размер и тип файлов указаны в OpenAPI и документации:
  ```yaml
  requestBody:
    content:
      multipart/form-data:
        schema:
          type: object
          required:
            - file
          properties:
            file:
              type: string
              format: binary
              description: 'Файл. Максимум 10 МБ. Допустимые типы: PDF, PNG, JPG'
            description:
              type: string
              maxLength: 500
  ```

- **R-FILE-4.** Ответ загрузки — `201 Created`. Тело — метаданные загруженного файла.
  ```json
  {
    "attachmentId": "550e8400-e29b-41d4-a716-446655440000",
    "fileName": "report.pdf",
    "contentType": "application/pdf",
    "size": 1048576,
    "uploadedAt": "2025-03-15T10:30:00Z"
  }
  ```

- **R-FILE-5.** Скачивание — `GET` c бинарным `Content-Type` и заголовком `Content-Disposition`:
  ```http
  GET /api/v1/documents/{id}/attachments/{id}

  HTTP/1.1 200 OK
  Content-Type: application/pdf
  Content-Disposition: attachment; filename="report.pdf"
  Content-Length: 1048576

  <binary data>
  ```

---

## 16. Deprecation

### 16.1 Обязательно

- **R-DEP-1.** Устаревший эндпоинт помечается `deprecated: true` в OpenAPI с указанием альтернативы и даты отключения в `description`:
  ```yaml
  /api/v1/orders/{id}/status:
    get:
      deprecated: true
      summary: 'Получить статус заказа'
      description: 'DEPRECATED: используйте GET /api/v2/orders/{id}. Будет удалён после 2025-09-01.'
  ```

- **R-DEP-2.** Устаревший эндпоинт возвращает заголовок `Sunset` ([RFC 8594](https://www.rfc-editor.org/rfc/rfc8594.html)) с датой отключения, заголовок `Deprecation: true` и `Link` с `rel="successor-version"`:
  ```http
  HTTP/1.1 200 OK
  Sunset: Sat, 01 Sep 2025 00:00:00 GMT
  Deprecation: true
  Link: </api/v2/orders/{id}>; rel="successor-version"
  ```

- **R-DEP-3.** Процесс вывода из эксплуатации:
  1. Пометить `deprecated: true` в OpenAPI, добавить заголовки `Sunset` и `Deprecation`.
  2. Уведомить потребителей (changelog, рассылка, Slack).
  3. Мониторить трафик на устаревший эндпоинт.
  4. После даты `Sunset` — вернуть `410 Gone`:
     ```json
     {
       "type": "urn:problem:order-service:endpoint-removed",
       "status": 410,
       "title": "Gone",
       "detail": "Эндпоинт удалён. Используйте GET /api/v2/orders/{id}.",
       "code": "ENDPOINT_REMOVED"
     }
     ```

### 16.2 Запрещено

- **R-DEP-X1.** `deprecated: true` в OpenAPI без заголовка `Sunset` и даты отключения. Клиент не знает, когда нужно мигрировать.

---

## 17. Batch-операции

Batch-операции обрабатываются **поэлементно** (partial success): ошибка одного элемента не отменяет обработку остальных. Если требуется атомарность (all-or-nothing), это явно указывается в документации эндпоинта и реализуется через транзакцию на стороне сервера.

### 17.1 Обязательно

- **R-BATCH-1.** Эндпоинт оформляется как `POST /resources/batch` (или `POST /resources/batch/<action>` для batch-команд):
  ```
  POST /api/v1/orders/batch
  POST /api/v1/notifications/batch/send
  ```

- **R-BATCH-2.** Формат запроса — `{ "items": [...] }`:
  ```json
  {
    "items": [
      { "productId": "aaa", "quantity": 2 },
      { "productId": "bbb", "quantity": 1 },
      { "productId": "ccc", "quantity": 5 }
    ]
  }
  ```

- **R-BATCH-3.** Код ответа — `200 OK` (даже если часть элементов не прошла). Тело содержит результат по каждому элементу и агрегированный `summary`:
  ```json
  {
    "results": [
      { "index": 0, "status": "SUCCESS", "orderId": "..." },
      { "index": 1, "status": "ERROR", "error": { "code": "INSUFFICIENT_STOCK", "detail": "Товар bbb отсутствует на складе" } },
      { "index": 2, "status": "SUCCESS", "orderId": "..." }
    ],
    "summary": {
      "total": 3,
      "succeeded": 2,
      "failed": 1
    }
  }
  ```
  - `index` — позиция элемента в исходном массиве (0-based).
  - `status` — `SUCCESS` или `ERROR`.
  - При `ERROR` — упрощённый объект `error` с `code` и `detail` (не полный `ProblemDetails`, т. к. ошибка относится к элементу batch, а не к HTTP-запросу).
  - `summary` — агрегация: `total`, `succeeded`, `failed`.

- **R-BATCH-4.** Максимальный размер batch указывается в документации (например, 100 элементов).

- **R-BATCH-5.** При превышении размера — `400 Bad Request` с `code: BATCH_SIZE_EXCEEDED`.

---

## 18. Длительные операции (async)

Для операций, которые не могут завершиться за время HTTP-запроса.

### 18.1 Обязательно

- **R-ASYNC-1.** Паттерн polling:
  1. Клиент отправляет запрос.
  2. Сервер возвращает `202 Accepted` с заголовком `Location` на задачу и телом, содержащим `taskId`, `status`, `statusUrl`.
  3. Клиент периодически опрашивает задачу до завершения.
  ```http
  POST /api/v1/reports/generate
  Content-Type: application/json

  { "dateFrom": "2025-01-01", "dateTo": "2025-12-31" }
  ```
  Ответ:
  ```http
  HTTP/1.1 202 Accepted
  Location: /api/v1/tasks/550e8400-e29b-41d4-a716-446655440000

  {
    "taskId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "PENDING",
    "createdAt": "2025-03-15T10:30:00Z",
    "statusUrl": "/api/v1/tasks/550e8400-e29b-41d4-a716-446655440000"
  }
  ```

- **R-ASYNC-2.** Опрос статуса — `GET /api/v1/tasks/{id}`.

  Пока задача выполняется:
  ```json
  {
    "taskId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "PROCESSING",
    "progress": 45,
    "createdAt": "2025-03-15T10:30:00Z"
  }
  ```

  После завершения:
  ```json
  {
    "taskId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "COMPLETED",
    "progress": 100,
    "createdAt": "2025-03-15T10:30:00Z",
    "completedAt": "2025-03-15T10:35:00Z",
    "resultUrl": "/api/v1/reports/550e8400-e29b-41d4-a716-446655440000"
  }
  ```

  При ошибке:
  ```json
  {
    "taskId": "550e8400-e29b-41d4-a716-446655440000",
    "status": "FAILED",
    "createdAt": "2025-03-15T10:30:00Z",
    "completedAt": "2025-03-15T10:32:00Z",
    "error": {
      "code": "REPORT_GENERATION_FAILED",
      "detail": "Не удалось сформировать отчет: данные за период отсутствуют"
    }
  }
  ```

- **R-ASYNC-3.** Допустимые статусы задачи:
  - `PENDING` — задача создана, ожидает обработки
  - `PROCESSING` — выполняется
  - `COMPLETED` — завершена, результат доступен по `resultUrl`
  - `FAILED` — завершена с ошибкой, подробности в `error`

- **R-ASYNC-4.** При `COMPLETED` — поле `resultUrl` обязательно. При `FAILED` — поле `error` обязательно.

---

## 19. Локализация

### 19.1 Обязательно

- **R-LOC-1.** Клиент указывает предпочитаемый язык через заголовок `Accept-Language`:
  ```http
  GET /api/v1/orders/{id}
  Accept-Language: ru
  ```

- **R-LOC-2.** Если `Accept-Language` не указан — сервер использует язык по умолчанию, определённый для проекта (например, `ru`).

- **R-LOC-3.** Локализуются:
  - `detail` в ProblemDetails
  - `message` в `violations`

### 19.2 Запрещено

- **R-LOC-X1.** Локализация enum-кодов и URI:
  - `code` — всегда на английском (`ORDER_EMPTY`, не `ЗАКАЗ_ПУСТОЙ`)
  - `title` — стандартное название HTTP-статуса на английском (`Bad Request`, `Not Found`)
  - `type` — URI/URN, всегда на английском
  - Имена полей в JSON — `orderId`, не `идЗаказа`

---

## 20. OpenAPI-метаданные

### 20.1 Обязательно

- **R-OAS-1.** Каждый эндпоинт имеет уникальный `operationId` в `camelCase`. Паттерн: `действие` + `ресурс`.
  ```yaml
  /api/v1/orders:
    get:
      operationId: getOrders
    post:
      operationId: createOrder

  /api/v1/orders/{id}:
    get:
      operationId: getOrder
    put:
      operationId: updateOrder
    delete:
      operationId: deleteOrder

  /api/v1/orders/{id}/confirm:
    post:
      operationId: confirmOrder

  /api/v1/orders/search:
    post:
      operationId: searchOrders
  ```

- **R-OAS-2.** Группировка эндпоинтов через `tags`. Один тег на ресурс, имя — множественное число с заглавной. Action-эндпоинты относятся к тегу родительского ресурса (`confirm` → `Orders`).
  ```yaml
  tags:
    - name: Orders
      description: 'Управление заказами'
    - name: Users
      description: 'Управление пользователями'

  /api/v1/orders:
    get:
      tags: [Orders]
    post:
      tags: [Orders]

  /api/v1/orders/{id}/confirm:
    post:
      tags: [Orders]
  ```

- **R-OAS-3.** Параметры пути в OpenAPI именуются уникально по контексту: `{orderId}`, `{itemId}`. В дизайн-документации (см. `R-NEST-4`) используется `{id}` — контекст устраняет неоднозначность; в OpenAPI это требование инструмента (Swagger/Redoc не работают с одинаковыми именами параметров).
  ```yaml
  /api/v1/orders/{orderId}/items/{itemId}:
    get:
      parameters:
        - name: orderId
          in: path
          required: true
          schema:
            type: string
            format: uuid
        - name: itemId
          in: path
          required: true
          schema:
            type: string
            format: uuid
  ```

- **R-OAS-4.** Каждый эндпоинт имеет `summary` (короткая фраза, до 80 символов). `description` — по необходимости, если логика неочевидна.
  ```yaml
  /api/v1/orders/{id}/confirm:
    post:
      summary: 'Подтвердить заказ'
      description: |
        Переводит заказ из статуса CREATED в CONFIRMED.
        Заказ должен содержать хотя бы одну позицию.
        После подтверждения изменение состава заказа невозможно.
  ```

---

## 21. Антипаттерны

Сводка ссылок на запрещающие правила (X-коды) — единая точка для быстрой проверки.

| Антипаттерн | Правило | Корректно |
|---|---|---|
| Глагол в URL для CRUD | `R-URL-X4` | `POST /api/v1/orders` |
| CamelCase в пути | `R-URL-X1` | `/order-items` |
| snake_case в пути | `R-URL-X1` | `/order-items` |
| Завершающий слеш | `R-URL-X2` | `/api/v1/orders` |
| Расширение файла в пути | `R-URL-X3` | `/api/v1/orders` |
| ID в теле вместо пути | `R-NEST-X2` | `PUT /orders/{id}` |
| Глубокая вложенность | `R-NEST-X1` | `/comments?itemId={id}` |
| Множественное/единственное число вперемешку | `R-RES-X2` | `/orders/{id}/items` |
| GET с побочным эффектом | `R-MTH-X1` | `POST /orders/{id}/cancel` |
| Версия в query | `R-VER-X2` | `/api/v1/orders` |
| Минорная версия в пути | `R-VER-X1` | `/api/v1/...` |
| Бизнес-логика в query | `R-QRY-X4` | `POST /orders/{id}/cancel` |
| Comma-separated массивы в query | `R-QRY-X3` | повтор параметра |
| `page=0` в публичном контракте | `R-QRY-X2` | `page=1` |
| Префикс `X-` в заголовках | `R-HDR-X1` | доменный префикс (`Shop-`) |
| Envelope-обёртка | `R-RSP-X4` | плоский ресурс |
| `null` в успешном ответе | `R-RSP-X1` | отсутствие поля |
| `nullable: true` в OpenAPI | `R-RSP-X3` | `required` или отсутствие |
| `application/json` для ошибок | `R-ERR-X1` | `application/problem+json` |
| `type: "about:blank"` в ошибках | `R-ERR-X2` | URN `urn:problem:<service>:<code>` |
| Stack traces в теле `500` | `R-ERR-X4` | `code` + общий `detail` |
| Rate limiting без заголовков | `R-RATE-X1` | `Retry-After` + `RateLimit-*` |
| Deprecation без `Sunset` | `R-DEP-X1` | заголовок `Sunset` с датой |
| `me` для собственных ресурсов | `R-ALIAS-X1` | контекст из токена |
| HATEOAS-ссылки в теле | `R-PRIN-X1` | OpenAPI-описание навигации |
| Любой метод кроме POST для action | `R-ACT-X2` | `POST /orders/{id}/confirm` |

Финальная сводка: правил «Обязательно» — около 75, «Запрещено» — около 35. На любое нарушение ревью цитирует конкретный код, чтобы автор PR мог быстро найти контекст.
