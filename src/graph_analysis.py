"""Анализ графа переходов диаграммы деятельности.

Алгоритмы: поиск сильно связных компонент Тарьяна (итеративная реализация),
обход в ширину для недостижимых узлов, топологическая сортировка Кана.
Сложность всех алгоритмов - O(V + E).
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple


class AnalysisResult:
    """Результат анализа графа деятельности."""

    def __init__(self):
        self.nodes: List[str] = []
        self.edges: List[Tuple[str, str, str]] = []
        self.start_nodes: List[str] = []
        self.cycles: List[List[str]] = []
        self.unreachable: List[str] = []
        self.dead_ends: List[str] = []
        self.topological_order: Optional[List[str]] = None
        self.warnings: List[str] = []

    @property
    def is_acyclic(self) -> bool:
        return not self.cycles

    def summary_lines(self) -> List[str]:
        lines: List[str] = []
        if self.start_nodes:
            lines.append("Начальные узлы: %s" % ", ".join(self.start_nodes))
        else:
            lines.append("Начальные узлы: не найдены (граф состоит из циклов)")
        if self.cycles:
            for cycle in self.cycles:
                lines.append("Цикл: %s" % " -> ".join(cycle + [cycle[0]]))
        else:
            lines.append("Циклы: не обнаружены")
        lines.append(
            "Недостижимые шаги: %s"
            % (", ".join(self.unreachable) if self.unreachable else "нет")
        )
        lines.append(
            "Тупиковые узлы: %s"
            % (", ".join(self.dead_ends) if self.dead_ends else "нет")
        )
        if self.topological_order is not None:
            lines.append("Порядок выполнения: %s" % " -> ".join(self.topological_order))
        else:
            lines.append("Порядок выполнения: не определён (граф содержит циклы)")
        if self.warnings:
            lines.append("Предупреждения:")
            for warning in self.warnings:
                lines.append("  - %s" % warning)
        else:
            lines.append("Предупреждения: нет")
        return lines


def build_graph(
    steps: Sequence[Dict[str, Any]]
) -> Tuple[List[str], Dict[str, List[Tuple[str, str]]]]:
    """Строит список узлов и список смежности с метками переходов."""
    nodes: List[str] = []
    seen: Set[str] = set()
    adjacency: Dict[str, List[Tuple[str, str]]] = {}

    def add_node(name: str) -> None:
        if name not in seen:
            seen.add(name)
            nodes.append(name)
            adjacency[name] = []

    for step in steps:
        name = step["step"]
        add_node(name)
        if "next" in step:
            targets = step["next"] if isinstance(step["next"], list) else [step["next"]]
            for target in targets:
                add_node(str(target))
                adjacency[name].append((str(target), ""))
        else:
            condition_text = step["condition"]
            adjacency[name].append((step["true"], condition_text))
            add_node(step["true"])
            adjacency[name].append((step["false"], "NOT (%s)" % condition_text))
            add_node(step["false"])
    return nodes, adjacency


def tarjan_scc(
    nodes: Sequence[str], adjacency: Dict[str, Iterable[Tuple[str, str]]]
) -> List[List[str]]:
    """Итеративный алгоритм Тарьяна для поиска сильно связных компонент."""
    index_counter = [0]
    indices: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    components: List[List[str]] = []

    for start in nodes:
        if start in indices:
            continue
        indices[start] = lowlink[start] = index_counter[0]
        index_counter[0] += 1
        stack.append(start)
        on_stack.add(start)
        work: List[Tuple[str, Any]] = [
            (start, iter([target for target, _ in adjacency.get(start, ())]))
        ]
        while work:
            node, iterator = work[-1]
            advanced = False
            for neighbour in iterator:
                if neighbour not in indices:
                    indices[neighbour] = lowlink[neighbour] = index_counter[0]
                    index_counter[0] += 1
                    stack.append(neighbour)
                    on_stack.add(neighbour)
                    work.append(
                        (
                            neighbour,
                            iter([target for target, _ in adjacency.get(neighbour, ())]),
                        )
                    )
                    advanced = True
                    break
                if neighbour in on_stack:
                    if indices[neighbour] < lowlink[node]:
                        lowlink[node] = indices[neighbour]
            if advanced:
                continue
            work.pop()
            if lowlink[node] == indices[node]:
                component: List[str] = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(component)
            if work:
                parent = work[-1][0]
                if lowlink[node] < lowlink[parent]:
                    lowlink[parent] = lowlink[node]
    return components


def reachable_from(
    adjacency: Dict[str, Iterable[Tuple[str, str]]], starts: Iterable[str]
) -> Set[str]:
    """Множество узлов, достижимых из заданных начальных узлов."""
    visited: Set[str] = set()
    queue = deque(starts)
    for start in starts:
        visited.add(start)
    while queue:
        node = queue.popleft()
        for target, _ in adjacency.get(node, ()):
            if target not in visited:
                visited.add(target)
                queue.append(target)
    return visited


def topological_sort(
    nodes: Sequence[str], adjacency: Dict[str, Iterable[Tuple[str, str]]]
) -> Optional[List[str]]:
    """Топологическая сортировка Кана; None, если граф содержит цикл."""
    indegree = {node: 0 for node in nodes}
    for node in nodes:
        for target, _ in adjacency.get(node, ()):
            if target in indegree:
                indegree[target] += 1
    queue = deque(node for node in nodes if indegree[node] == 0)
    order: List[str] = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for target, _ in adjacency.get(node, ()):
            if target not in indegree:
                continue
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(nodes):
        return None
    return order


def _self_loop_components(
    nodes: Sequence[str], adjacency: Dict[str, Iterable[Tuple[str, str]]]
) -> List[List[str]]:
    result: List[List[str]] = []
    for node in nodes:
        for target, _ in adjacency.get(node, ()):
            if target == node:
                result.append([node])
                break
    return result


def analyze_steps(steps: Sequence[Dict[str, Any]]) -> AnalysisResult:
    """Полный анализ графа деятельности."""
    nodes, adjacency = build_graph(steps)
    result = AnalysisResult()
    result.nodes = nodes
    result.edges = [
        (node, target, label) for node in nodes for target, label in adjacency[node]
    ]

    indegree = {node: 0 for node in nodes}
    outdegree = {node: 0 for node in nodes}
    for node in nodes:
        for target, _ in adjacency[node]:
            outdegree[node] += 1
            if target in indegree:
                indegree[target] += 1

    result.start_nodes = [node for node in nodes if indegree[node] == 0]
    if len(result.start_nodes) > 1:
        result.warnings.append(
            "Найдено несколько начальных узлов: %s" % ", ".join(result.start_nodes)
        )
    if not result.start_nodes:
        result.warnings.append("Не найдено ни одного начального узла (все узлы в циклах)")

    components = tarjan_scc(nodes, adjacency)
    cycles: List[List[str]] = []
    for component in components:
        if len(component) > 1:
            cycles.append(sorted(component, key=nodes.index))
    cycles.extend(_self_loop_components(nodes, adjacency))
    result.cycles = cycles
    for cycle in cycles:
        result.warnings.append("Обнаружен цикл: %s" % " -> ".join(cycle))

    visited = reachable_from(adjacency, result.start_nodes)
    result.unreachable = [node for node in nodes if node not in visited]
    for node in result.unreachable:
        result.warnings.append("Шаг недостижим из начального узла: %s" % node)

    result.dead_ends = [node for node in nodes if outdegree[node] == 0]
    for node in result.dead_ends:
        if not node.startswith("End"):
            result.warnings.append(
                "Тупиковый узел без исходящих переходов (ожидался финальный шаг): %s" % node
            )

    order = topological_sort(nodes, adjacency)
    result.topological_order = order
    if order is None:
        result.warnings.append(
            "Топологическая сортировка невозможна: граф содержит циклы"
        )
    return result
