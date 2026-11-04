"""A generic A* search over any graph given as callbacks."""

import heapq
import itertools
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass
from typing import Any

Node = Hashable


@dataclass
class SearchResult:
    cost: float
    # (node, edge that led to it); the first entry is the start with edge None.
    steps: list[tuple[Node, Any]]
    expanded: int


def astar(
    start: Node,
    goal: Node,
    neighbours: Callable[[Node], Iterable[tuple[Node, float, Any]]],
    heuristic: Callable[[Node], float],
    max_expansions: int = 500_000,
) -> SearchResult | None:
    """Cheapest path from start to goal.

    `neighbours(node)` yields (next node, edge cost >= 0, edge data). `heuristic(node)` must
    never overestimate the remaining cost (admissible), or the result may not be the
    cheapest path.
    """
    best = {start: 0.0}
    came_from: dict[Node, tuple[Node, Any]] = {}
    tie = itertools.count()  # keeps the heap from comparing nodes when f ties
    heap = [(heuristic(start), next(tie), 0.0, start)]
    expanded = 0
    while heap:
        _, _, cost, node = heapq.heappop(heap)
        if node == goal:
            steps = []
            while node in came_from:
                prev, edge = came_from[node]
                steps.append((node, edge))
                node = prev
            steps.append((start, None))
            return SearchResult(cost=cost, steps=steps[::-1], expanded=expanded)
        if cost > best[node]:
            continue
        expanded += 1
        if expanded > max_expansions:
            return None
        for nxt, edge_cost, edge in neighbours(node):
            new_cost = cost + edge_cost
            if new_cost < best.get(nxt, float("inf")):
                best[nxt] = new_cost
                came_from[nxt] = (node, edge)
                heapq.heappush(heap, (new_cost + heuristic(nxt), next(tie), new_cost, nxt))
    return None
