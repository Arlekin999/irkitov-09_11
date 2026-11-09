# Диаграмма деятельности

## Переходы

| Из | В | Условие |
|----|---|---------|
| Start | ValidateCart | - |
| ValidateCart | ReserveStock | cart.items > 0 AND NOT customer.blocked |
| ValidateCart | ShowEmptyCart | NOT (cart.items > 0 AND NOT customer.blocked) |
| ReserveStock | ChargeCard | stock.available == true OR stock.backorder == true |
| ReserveStock | NotifyOutOfStock | NOT (stock.available == true OR stock.backorder == true) |
| ChargeCard | FulfillOrder | payment.status == 'paid' |
| ChargeCard | RetryPayment | NOT payment.status == 'paid' |
| RetryPayment | NotifyRetry | attempts < 3 |
| RetryPayment | CancelOrder | NOT attempts < 3 |
| FulfillOrder | ShipOrder | - |
| FulfillOrder | SendReceipt | - |
| ShipOrder | EndSuccess | - |
| SendReceipt | EndSuccess | - |
| NotifyRetry | EndRetry | - |
| ShowEmptyCart | EndEmpty | - |
| NotifyOutOfStock | EndOutOfStock | - |
| CancelOrder | EndCancelled | - |

## Текстовое представление

```text
Activity Diagram:
Start -> ValidateCart
ValidateCart -> ReserveStock (if cart.items > 0 AND NOT customer.blocked)
ValidateCart -> ShowEmptyCart (if NOT (cart.items > 0 AND NOT customer.blocked))
ReserveStock -> ChargeCard (if stock.available == true OR stock.backorder == true)
ReserveStock -> NotifyOutOfStock (if NOT (stock.available == true OR stock.backorder == true))
ChargeCard -> FulfillOrder (if payment.status == 'paid')
ChargeCard -> RetryPayment (if NOT payment.status == 'paid')
RetryPayment -> NotifyRetry (if attempts < 3)
RetryPayment -> CancelOrder (if NOT attempts < 3)
FulfillOrder -> ShipOrder
FulfillOrder -> SendReceipt
ShipOrder -> EndSuccess
SendReceipt -> EndSuccess
NotifyRetry -> EndRetry
ShowEmptyCart -> EndEmpty
NotifyOutOfStock -> EndOutOfStock
CancelOrder -> EndCancelled
```

## Анализ

- Начальные узлы: Start
- Циклы: не обнаружены
- Недостижимые шаги: нет
- Тупиковые узлы: EndSuccess, EndRetry, EndEmpty, EndOutOfStock, EndCancelled
- Порядок выполнения: Start -> ValidateCart -> ReserveStock -> ShowEmptyCart -> ChargeCard -> NotifyOutOfStock -> EndEmpty -> FulfillOrder -> RetryPayment -> EndOutOfStock -> ShipOrder -> SendReceipt -> NotifyRetry -> CancelOrder -> EndSuccess -> EndRetry -> EndCancelled
- Предупреждения: нет
