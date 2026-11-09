# Автоматизированное проектирование UML-диаграмм

Консольное приложение на Python 3.11+ (только стандартная библиотека), которое по
JSON-описанию строит диаграмму последовательности и диаграмму деятельности,
анализирует граф переходов и генерирует Markdown-отчёты. Собственный парсер JSON
написан с нуля - модуль `json` во входных файлах не используется.

Выполнил: Иркитов Тимур, группа ИСП-431.

## Запуск

```bash
# интерактивный режим
python run.py --repl

# отрисовать диаграмму последовательности
python run.py --file samples/sequence_sample.json --render sequence

# отрисовать диаграмму деятельности и сохранить отчёт
python run.py --file samples/activity_sample.json --render activity --report

# анализ графа деятельности
python run.py --file samples/activity_sample.json --analyze

# экспорт через плагин Mermaid
python run.py --file samples/sequence_sample.json --export mermaid
```

Ключи командной строки:

| Ключ | Назначение |
|------|------------|
| `--repl` | интерактивная оболочка |
| `--file <путь>` | входной JSON-файл (можно указывать несколько раз) |
| `--render sequence\|activity` | вывести текстовую диаграмму |
| `--analyze` | анализ графа деятельности |
| `--report` | сохранить `sequence-diagram.md` / `activity-diagram.md` |
| `--export <формат>` | экспорт через плагин (`mermaid`) |
| `--output <каталог>` | каталог для отчётов |
| `--plugins-dir <путь>` | каталог плагинов |
| `--no-plugins` | не загружать плагины |

## Формат JSON: диаграмма последовательности

```json
{
  "sequence": [
    {"actor": "Customer", "action": "PlaceOrder", "target": "OrderSystem", "parameters": ["item: Milk", "quantity: 2"]},
    {"actor": "OrderSystem", "action": "CreateOrder", "target": "Order", "parameters": ["id: 123", "items: [Milk]"]},
    {"actor": "Order", "action": "ProcessPayment", "target": "PaymentGateway", "parameters": ["amount: 50"]}
  ]
}
```

Поля: `actor`, `action`, `target` - обязательные строки, `parameters` - необязательный
массив строк.

Вывод:

```text
Sequence Diagram:
Customer -> OrderSystem: PlaceOrder(item: Milk, quantity: 2)
OrderSystem -> Order: CreateOrder(id: 123, items: [Milk])
Order -> PaymentGateway: ProcessPayment(amount: 50)
```

## Формат JSON: диаграмма деятельности

```json
{
  "activity": [
    {"step": "StartOrderProcessing", "next": "CheckInventory"},
    {"step": "CheckInventory", "condition": "inventoryAvailable AND NOT blacklisted", "true": "ProcessPayment", "false": "NotifyCustomer"},
    {"step": "ProcessPayment", "next": "CompleteOrder"},
    {"step": "NotifyCustomer", "next": "EndOrderProcessing"}
  ]
}
```

Шаг содержит либо `next` (строка или массив строк), либо `condition` + `true` + `false`.
Поле `condition` поддерживает `AND`, `OR`, `NOT`, круглые скобки, имена переменных,
числа, строки и сравнения `==`, `!=`, `<`, `>`, `<=`, `>=`. Приоритеты:
`NOT` > сравнения > `AND` > `OR`.

Вывод:

```text
Activity Diagram:
StartOrderProcessing -> CheckInventory
CheckInventory -> ProcessPayment (if inventoryAvailable AND NOT blacklisted)
CheckInventory -> NotifyCustomer (if NOT (inventoryAvailable AND NOT blacklisted))
ProcessPayment -> CompleteOrder
NotifyCustomer -> EndOrderProcessing
```

## Команды REPL

```
load <файл>...          загрузить и разобрать JSON-файлы
validate                проверить документы по схеме
render sequence         вывести диаграмму последовательности
render activity         вывести диаграмму деятельности
analyze                 анализ графа деятельности
export <формат> [тип]   экспорт через плагин
report                  сохранить Markdown-отчёты
plugins                 список плагинов и экспортёров
clear                   очистить загруженные документы
help                    справка
quit                    выход
```

История команд сохраняется в `history.txt` в рабочем каталоге.

## Плагины

Плагин - `.py`-файл в каталоге `plugins/`. Обязательные атрибуты: `NAME: str` и
функция `register(registry: dict) -> None`. Загрузчик изолирует каждый плагин
(уникальное имя модуля, перехват ошибок), поэтому сбой одного плагина не останавливает
приложение. Реестр содержит секции `exporters` и `validators`.

Пример `plugins/mermaid_export.py` добавляет экспортёр `mermaid`, который строит
разметку `sequenceDiagram` и `flowchart TD`.

## Анализ графа деятельности

* поиск циклов - итеративный алгоритм Тарьяна (SCC размера > 1 и самопетли);
* поиск недостижимых шагов - обход в ширину от узлов без входящих переходов;
* поиск тупиковых узлов - шаги без исходящих переходов (допустимы только имена,
  начинающиеся с `End`);
* топологическая сортировка Кана (только для ациклических графов);
* все предупреждения выводятся в консоль и в блок «Анализ» Markdown-отчёта.

Сложность алгоритмов - `O(V + E)`.

## Тестовые диаграммы и демонстрация

В каталоге `samples/` кроме примеров из задания лежат тестовые наборы:

| Файл | Содержание |
|------|------------|
| `sequence_sample.json`, `activity_sample.json` | примеры из задания |
| `sequence_checkout.json` | 6 сообщений, 4 участника, вызов без параметров |
| `activity_branching.json` | ациклический граф с 5 условиями и слиянием ветвей |
| `activity_cycle.json` | два цикла, недостижимые шаги и тупиковый узел |

Результаты запуска на этих данных находятся в каталоге `demo/`: консольный вывод,
Markdown-отчёты, Mermaid-разметка, сессия REPL и файл `demo/README.md` с пояснениями.

## Тесты и производительность

```bash
python -m unittest discover -s tests -v
python benchmark.py
```

`benchmark.py` формирует диаграмму деятельности из 10 000 шагов и 30 000 переходов,
замеряет разбор JSON, анализ и рендеринг через `time.perf_counter` и проверяет
требование «менее 2 секунд».
