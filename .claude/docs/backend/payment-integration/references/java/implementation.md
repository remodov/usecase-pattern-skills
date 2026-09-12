# Платёжная интеграция — реализация на Java (Spring Boot / jOOQ)

Реализация требований `../../spec.md` (`payment-integration/*`, коды `R-PAYINT-*`). Стек по умолчанию:
Spring Boot, jOOQ, PostgreSQL, сгенерированный из контракта клиент провайдера, Resilience4j на адаптере.

## 1. Идемпотентный флоу (`payment-integration/idempotent-by-natural-key`, `read-before-write`, `act-only-if-not-terminal`)

Три шага: зарегистрировать намерение, списать, зафиксировать исход. Каждый — по естественному ключу.

```java
@Transactional
public PaymentResult pay(OrderId orderId, Money amount) {
    Payment payment = payments.findByOrderId(orderId)
        .orElseGet(() -> payments.register(Payment.intent(orderId, amount)));

    if (payment.isTerminal()) {
        return payment.result();
    }

    ProviderCharge charge = provider.chargeIfAbsent(payment.naturalKey(), amount);

    return payments.finalize(payment, statusMapper.toDomain(charge.status()));
}
```

- **PREFER** естественный ключ (`orderId` плюс тип операции) как идентификатор у провайдера: он переживает
  перезапуск и не зависит от идентификатора запроса.
- **AVOID** создание операции без предварительного чтения — повтор даст второй платёж.

## 2. Сериализация конкурентных попыток (`payment-integration/concurrent-attempts-serialized`)

```java
dsl.select(field("pg_advisory_xact_lock(?)", Long.class, orderId.hash())).execute();
```

- **PREFER** блокировку уровня транзакции по заказу либо `SELECT … FOR UPDATE` по строке платежа.
- **AVOID** проверку «уже платят?» отдельным запросом без блокировки: два нажатия проходят обе проверки.

## 3. Отображение статусов (`payment-integration/single-status-mapper`, `domain-values-outside-adapter`)

- Один класс `ProviderStatusMapper` переводит коды провайдера в доменное состояние; больше нигде эти коды
  не интерпретируются.
- Наружу адаптера уходят доменные значения, не строки провайдера и не сгенерированные DTO.
- Неизвестный код — не «отказ», а явное «неизвестно» с последующим дозабором.

## 4. Транспорт против бизнеса (`payment-integration/transport-error-keeps-operation-retryable`, `business-decline-is-terminal`, `transport-and-business-errors-differ`)

| Что случилось | Тип исключения | Состояние операции |
|---|---|---|
| Тайм-аут, разрыв, отказ предохранителя | `PaymentTransportException` | остаётся незавершённой, попадёт в дозабор |
| Провайдер ответил отказом | `PaymentDeclinedException` | конечное, повтор бесполезен |
| Ответ не разобран | `PaymentTransportException` | незавершённая, требует дозабора |

- **AVOID** перевод тайм-аута в отказ: провайдер мог списать деньги, а заказ будет отменён.

## 5. Дозабор и сроки (`payment-integration/reconciliation-pass`, `stale-operations-closed-by-ttl`)

- Регламентное задание проходит по незавершённым операциям и спрашивает провайдера об их судьбе;
  механика — из требований `scheduler/*`.
- Операция старше срока закрывается явным состоянием, а не остаётся висеть.

## 6. Деньги и след (`payment-integration/money-is-decimal`, `money-operations-leave-trace`, `no-sensitive-payment-data-in-logs`)

- Суммы — `BigDecimal` и колонка `numeric`, округление задаётся явно; `double` не применяется.
- Каждая денежная операция оставляет запись в журнале действий: кто, что, когда, какой ответ провайдера.
- Номер карты, коды подтверждения и полные ответы провайдера не выходят за пределы адаптера
  (`auth-patterns/no-pii-in-logs-and-events`).

## Чеклист подключения (Java / Spring Boot)

1. Таблица платежей: естественный ключ, состояние, сумма `numeric`, отметки времени `timestamptz`.
2. Клиент провайдера сгенерирован из контракта; адаптер обвязан предохранителем и тайм-аутами.
3. `ProviderStatusMapper` — единственное место интерпретации кодов.
4. Два типа исключений: транспортное и бизнес-отказ.
5. Блокировка по заказу на время попытки.
6. Регламентный дозабор незавершённых и закрытие по сроку.
7. Тест: повтор запроса не создаёт второй платёж; тайм-аут оставляет операцию незавершённой.
