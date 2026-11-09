# Демонстрация работы

Каталог содержит результаты запуска приложения на тестовых данных.

## Входные тестовые диаграммы

| Файл | Что демонстрирует |
|------|-------------------|
| `samples/sequence_checkout.json` | диаграмма последовательности из 6 сообщений и 4 участников, в том числе вызов без параметров |
| `samples/activity_branching.json` | ациклический граф деятельности с 5 условиями, ветвлением и слиянием |
| `samples/activity_cycle.json` | граф с двумя циклами, недостижимыми шагами и тупиковым узлом |

## Команды запуска

```bash
python run.py --file samples/sequence_checkout.json --render sequence --output demo/sequence-checkout
python run.py --file samples/activity_branching.json --render activity --analyze --report --output demo/activity-branching
python run.py --file samples/activity_cycle.json --render activity --analyze --report --output demo/activity-cycle
python run.py --file samples/sequence_checkout.json --export mermaid --output demo/exports
python run.py --file samples/activity_branching.json --export mermaid --output demo/exports
python run.py --file samples/activity_cycle.json --export mermaid --output demo/exports
```

## Результаты

* `demo/sequence-checkout/` - консольный вывод и Markdown-отчёт по диаграмме последовательности;
* `demo/activity-branching/` - вывод, анализ графа и Markdown-отчёт по ациклической диаграмме;
* `demo/activity-cycle/` - вывод, анализ графа и отчёт по диаграмме с циклами;
* `demo/exports/` - Mermaid-разметка для всех трёх диаграмм;
* `demo/repl-session.txt` - полная сессия REPL с загрузкой, проверкой, рендерингом,
  анализом, экспортом и отчётами;
* `demo/repl/` - файлы, созданные в сессии REPL, и `history.txt`.

## Ключевые фрагменты вывода

Диаграмма последовательности (ветвление отсутствует, вызов без параметров
печатается как `ReserveStock()`):

```text
Sequence Diagram:
Customer -> OrderService: SubmitOrder(items: 3, total: 149.90)
OrderService -> PaymentGateway: Authorize(card: **** 4242, amount: 149.90)
PaymentGateway -> OrderService: Approve(transaction: TX-778)
OrderService -> Warehouse: ReserveStock()
Warehouse -> OrderService: ConfirmReservation(reservation: R-42)
OrderService -> Customer: SendConfirmation(channel: email)
```

Отрицание условия в ветви false и нормализация скобок:

```text
ValidateCart -> ReserveStock (if cart.items > 0 AND NOT customer.blocked)
ValidateCart -> ShowEmptyCart (if NOT (cart.items > 0 AND NOT customer.blocked))
ReserveStock -> ChargeCard (if stock.available == true OR stock.backorder == true)
ReserveStock -> NotifyOutOfStock (if NOT (stock.available == true OR stock.backorder == true))
```

Анализ графа с циклами:

```text
Начальные узлы: AcceptRequest
Цикл: CheckLimit -> Review -> CheckLimit
Цикл: ClosedLoopA -> ClosedLoopB -> ClosedLoopA
Недостижимые шаги: ClosedLoopA, ClosedLoopB
Тупиковые узлы: SendResponse
Порядок выполнения: не определён (граф содержит циклы)
Предупреждения:
  - Обнаружен цикл: CheckLimit -> Review
  - Обнаружен цикл: ClosedLoopA -> ClosedLoopB
  - Шаг недостижим из начального узла: ClosedLoopA
  - Шаг недостижим из начального узла: ClosedLoopB
  - Тупиковый узел без исходящих переходов (ожидался финальный шаг): SendResponse
  - Топологическая сортировка невозможна: граф содержит циклы
```

Ациклическая диаграмма деятельности анализируется без предупреждений и получает
линейный порядок выполнения:

```text
Начальные узлы: Start
Циклы: не обнаружены
Недостижимые шаги: нет
Тупиковые узлы: EndSuccess, EndRetry, EndEmpty, EndOutOfStock, EndCancelled
Предупреждения: нет
```
