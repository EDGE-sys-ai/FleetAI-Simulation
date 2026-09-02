from typing import List, Tuple, Set, Optional, Dict
import heapq
from models.warehouse import Warehouse
from models.robot import Robot


class PathFinder:
    def __init__(self):
        self.directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    def find_path(
        self,
        warehouse: Warehouse,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        ignore_robot_id: str = None,
    ) -> List[Tuple[int, int]]:
        if start == goal:
            return [start]

        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from: Dict[Tuple[int, int], Tuple[int, int]] = {}
        g_score: Dict[Tuple[int, int], float] = {start: 0}
        f_score: Dict[Tuple[int, int], float] = {start: self._heuristic(start, goal)}

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                return self._reconstruct_path(came_from, current)

            for dx, dy in self.directions:
                neighbor = (current[0] + dx, current[1] + dy)

                if not self._is_valid(warehouse, neighbor, ignore_robot_id, goal):
                    continue

                tentative_g = g_score[current] + 1

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f_score[neighbor] = tentative_g + self._heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return []

    def _is_valid(self, warehouse: Warehouse, pos: Tuple[int, int], ignore_robot_id: str = None, goal: Tuple[int, int] = None) -> bool:
        x, y = pos
        if not (0 <= x < warehouse.width and 0 <= y < warehouse.height):
            return False

        # Allow goal position even if occupied
        if goal and pos == goal:
            return True

        rack = warehouse.get_rack_at(x, y)
        if rack:
            return False

        robot = warehouse.get_robot_at(x, y)
        if robot and robot.id != ignore_robot_id:
            return False

        return True

    def _heuristic(self, a: Tuple[int, int], b: Tuple[int, int]) -> float:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def _reconstruct_path(self, came_from: Dict, current: Tuple[int, int]) -> List[Tuple[int, int]]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def find_path_to_rack(
        self,
        warehouse: Warehouse,
        robot: Robot,
        rack_id: str,
    ) -> List[Tuple[int, int]]:
        rack = warehouse.racks.get(rack_id)
        if not rack:
            return []

        target_positions = [
            (rack.x - 1, rack.y),
            (rack.x + 1, rack.y),
            (rack.x, rack.y - 1),
            (rack.x, rack.y + 1),
        ]

        valid_targets = [
            pos for pos in target_positions
            if self._is_valid(warehouse, pos, robot.id)
        ]

        if not valid_targets:
            return []

        best_path = None
        best_length = float('inf')

        for target in valid_targets:
            path = self.find_path(warehouse, (robot.x, robot.y), target, robot.id)
            if path and len(path) < best_length:
                best_length = len(path)
                best_path = path

        return best_path or []

    def find_path_to_zone(
        self,
        warehouse: Warehouse,
        robot: Robot,
        zone_bounds: Tuple[int, int, int, int],
    ) -> List[Tuple[int, int]]:
        x1, y1, x2, y2 = zone_bounds
        targets = []

        for x in range(x1, x2):
            for y in [y1 - 1, y2]:
                if 0 <= x < warehouse.width and 0 <= y < warehouse.height:
                    if self._is_valid(warehouse, (x, y), robot.id):
                        targets.append((x, y))

        for y in range(y1, y2):
            for x in [x1 - 1, x2]:
                if 0 <= x < warehouse.width and 0 <= y < warehouse.height:
                    if self._is_valid(warehouse, (x, y), robot.id):
                        targets.append((x, y))

        if not targets:
            return []

        best_path = None
        best_length = float('inf')

        for target in targets:
            path = self.find_path(warehouse, (robot.x, robot.y), target, robot.id)
            if path and len(path) < best_length:
                best_length = len(path)
                best_path = path

        return best_path or []