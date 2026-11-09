# Диаграмма деятельности

## Переходы

| Из | В | Условие |
|----|---|---------|
| AcceptRequest | CheckLimit | - |
| CheckLimit | Approve | amount <= limit |
| CheckLimit | Review | NOT amount <= limit |
| Approve | SendResponse | - |
| Review | CheckLimit | - |
| ClosedLoopA | ClosedLoopB | - |
| ClosedLoopB | ClosedLoopA | - |

## Текстовое представление

```text
Activity Diagram:
AcceptRequest -> CheckLimit
CheckLimit -> Approve (if amount <= limit)
CheckLimit -> Review (if NOT amount <= limit)
Approve -> SendResponse
Review -> CheckLimit
ClosedLoopA -> ClosedLoopB
ClosedLoopB -> ClosedLoopA
```

## Анализ

- Начальные узлы: AcceptRequest
- Цикл: CheckLimit -> Review -> CheckLimit
- Цикл: ClosedLoopA -> ClosedLoopB -> ClosedLoopA
- Недостижимые шаги: ClosedLoopA, ClosedLoopB
- Тупиковые узлы: SendResponse
- Порядок выполнения: не определён (граф содержит циклы)

### Предупреждения

- Обнаружен цикл: CheckLimit -> Review
- Обнаружен цикл: ClosedLoopA -> ClosedLoopB
- Шаг недостижим из начального узла: ClosedLoopA
- Шаг недостижим из начального узла: ClosedLoopB
- Тупиковый узел без исходящих переходов (ожидался финальный шаг): SendResponse
- Топологическая сортировка невозможна: граф содержит циклы
