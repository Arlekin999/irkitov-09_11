# Диаграмма последовательности

## Участники

- Customer
- OrderService
- PaymentGateway
- Warehouse

## Сообщения

| № | Отправитель | Получатель | Действие | Параметры |
|---|-------------|------------|----------|-----------|
| 1 | Customer | OrderService | SubmitOrder | items: 3, total: 149.90 |
| 2 | OrderService | PaymentGateway | Authorize | card: **** 4242, amount: 149.90 |
| 3 | PaymentGateway | OrderService | Approve | transaction: TX-778 |
| 4 | OrderService | Warehouse | ReserveStock |  |
| 5 | Warehouse | OrderService | ConfirmReservation | reservation: R-42 |
| 6 | OrderService | Customer | SendConfirmation | channel: email |

## Текстовое представление

```text
Sequence Diagram:
Customer -> OrderService: SubmitOrder(items: 3, total: 149.90)
OrderService -> PaymentGateway: Authorize(card: **** 4242, amount: 149.90)
PaymentGateway -> OrderService: Approve(transaction: TX-778)
OrderService -> Warehouse: ReserveStock()
Warehouse -> OrderService: ConfirmReservation(reservation: R-42)
OrderService -> Customer: SendConfirmation(channel: email)
```
