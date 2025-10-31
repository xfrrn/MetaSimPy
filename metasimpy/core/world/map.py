import json
from pathlib import Path
from typing import Dict, List, Optional, Callable, Tuple, TYPE_CHECKING
from loguru import logger
import random
import heapq

from .locations import Location, LocationType

if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..agents.registry import AgentRegistry
    from .objects import GameObject

ConnectionData = Dict[str, Dict[str, int]]


class WorldMap:
    """
    管理模拟世界的空间布局、地点及其连接关系。
    """

    def __init__(self):
        self._locations: Dict[str, Location] = {}
        self._connections: ConnectionData = {}

        logger.info("WorldMap 模块已初始化")

    def load_map_from_files(self, locations_file: Path, connections_file: Path):
        """
        从 JSON 文件加载地点和连接数据。
        """
        try:
            # 1. 加载地点
            logger.debug(f"尝试加载地点数据从: {locations_file}")
            with open(locations_file, "r", encoding="utf-8") as f:
                locations_data = json.load(f)
                count = 0
                loaded_object_names = set()
                for loc_data in locations_data:
                    try:
                        location = Location(**loc_data)
                        if location.name in self._locations:
                            logger.warning(f"重复的地点名称: '{location.name}'，后加载的将覆盖前者。")
                        self._locations[location.name] = location
                        loaded_object_names.update(location.objects)
                        count += 1
                    except Exception as e:
                        logger.error(f"解析地点数据时出错: {loc_data} - {e}")
            logger.success(f"成功加载 {count} 个地点从 {locations_file}")
            logger.info(f"地图共引用了 {len(loaded_object_names)} 种不同的物体名称。")

            # 2. 加载连接
            logger.debug(f"尝试加载连接数据从: {connections_file}")
            with open(connections_file, "r", encoding="utf-8") as f:
                raw_connections = json.load(f)
                valid_connections_count = 0
                processed_connections: ConnectionData = {}
                for start_node, destinations in raw_connections.items():
                    if start_node not in self._locations:
                        logger.warning(f"连接数据中发现无效的起始地点: '{start_node}'，已跳过。")
                        continue
                    valid_destinations = {}
                    for end_node, time in destinations.items():
                        if end_node not in self._locations:
                            logger.warning(f"连接数据中发现无效的目标地点: '{start_node}' -> '{end_node}'，已跳过。")
                            continue
                        if not isinstance(time, int) or time <= 0:
                            logger.warning(f"连接数据中发现无效的旅行时间: '{start_node}' -> '{end_node}' (时间: {time})，必须为正整数，已跳过。")
                            continue
                        valid_destinations[end_node] = time
                        valid_connections_count += 1
                    if valid_destinations:
                        processed_connections[start_node] = valid_destinations
                self._connections = processed_connections
            logger.success(f"成功加载并校验 {len(self._connections)} 个地点的 {valid_connections_count} 条单向连接数据从 {connections_file}")
            self._ensure_bidirectional_connections()
        except FileNotFoundError as e:
            logger.critical(f"加载地图文件失败，文件未找到: {e}")
            raise
        except json.JSONDecodeError as e:
            logger.critical(f"解析地图 JSON 文件失败: {e}")
            raise
        except Exception as e:
            logger.critical(f"加载地图数据时发生未知错误: {e}", exc_info=True)
            raise

    def _ensure_bidirectional_connections(self):
        """确保连接是双向的。如果 A->B (time) 存在，但 B->A 不存在，则添加 B->A (time)。"""
        missing_connections = 0
        connections_to_add: ConnectionData = {}
        current_connections = self._connections.copy()

        for start_node, destinations in current_connections.items():
            for end_node, time in destinations.items():
                reverse_exists = end_node in self._connections and start_node in self._connections[end_node]
                planned_to_add = end_node in connections_to_add and start_node in connections_to_add[end_node]

                if not reverse_exists and not planned_to_add:
                    if end_node not in connections_to_add:
                        connections_to_add[end_node] = {}
                    if end_node not in self._connections:
                        self._connections[end_node] = {}
                    connections_to_add[end_node][start_node] = time
                    missing_connections += 1
                    logger.trace(f"准备添加缺失的反向连接: {end_node} -> {start_node} (时间: {time})")

        for start_node, destinations in connections_to_add.items():
            self._connections[start_node].update(destinations)

        if missing_connections > 0:
            logger.info(f"自动补充了 {missing_connections} 条反向连接以确保地图双向连通。")

    def get_location(self, name: str) -> Optional[Location]:
        """根据名称获取地点对象，如果不存在则返回 None。"""
        return self._locations.get(name)

    def is_valid_location(self, name: str) -> bool:
        """检查地点名称是否存在于地图中"""
        return name in self._locations

    def get_all_location_names(self) -> List[str]:
        """获取所有有效地点名称的列表"""
        return list(self._locations.keys())

    def get_all_locations(self) -> List[Location]:
        """获取所有 Location 对象的列表"""
        return list(self._locations.values())

    def get_neighbors(self, name: str) -> List[str]:
        """获取一个地点的所有直接相邻地点名称列表"""
        if name in self._connections:
            return list(self._connections[name].keys())
        return []

    def get_travel_time(self, start_name: str, end_name: str) -> Optional[int]:
        """
        获取两个直接相连地点之间的移动时间（分钟）。
        如果地点无效或不直接相连，返回 None。
        """
        if not self.is_valid_location(start_name) or not self.is_valid_location(end_name):
            return None

        if start_name == end_name:
            return 0

        if start_name in self._connections and end_name in self._connections[start_name]:
            return self._connections[start_name][end_name]
        else:
            return None

    def get_objects_at_location(self, location_name: str) -> List[str]:
        """获取指定地点包含的物体名称列表"""
        location = self.get_location(location_name)
        if location:
            return location.objects
        else:
            logger.warning(f"尝试获取地点 '{location_name}' 的物体列表失败：地点不存在。")
            return []

    def get_location_type(self, location_name: str) -> Optional[LocationType]:
        """获取指定地点的类型"""
        location = self.get_location(location_name)
        return location.type if location else None

    def get_location_services(self, location_name: str) -> Optional[Dict[str, int]]:
        """获取指定地点提供的服务及其基础价格"""
        location = self.get_location(location_name)
        return location.services if location else None

    def get_location_jobs(self, location_name: str) -> Optional[Dict[str, int]]:
        """获取指定地点提供的工作类型及其最大容纳人数"""
        location = self.get_location(location_name)
        return location.available_jobs if location else None

    # --- 其他查询 ---
    def get_locations_by_type(self, loc_type: LocationType) -> List[Location]:
        """根据类型查找地点"""
        return [loc for loc in self._locations.values() if loc.type == loc_type]

    def get_locations_with_tag(self, tag: str) -> List[Location]:
        """根据标签查找地点"""
        return [loc for loc in self._locations.values() if tag in loc.tags]

    def get_random_location(self, filter_func: Optional[Callable[[Location], bool]] = None) -> Optional[Location]:
        """获取一个随机地点，可选择性地应用过滤函数"""
        candidate_locations = list(self._locations.values())
        if filter_func:
            candidate_locations = [loc for loc in candidate_locations if filter_func(loc)]

        if not candidate_locations:
            logger.warning("无法获取随机地点：没有符合条件的地点。")
            return None
        return random.choice(candidate_locations)

    def find_path(self, start_name: str, end_name: str) -> Optional[Tuple[List[str], int]]:
        """使用 Dijkstra 算法计算两个地点之间的最短路径和总时间"""
        if not self.is_valid_location(start_name) or not self.is_valid_location(end_name):
            logger.warning(f"路径规划失败：无效的地点 '{start_name}' 或 '{end_name}'")
            return None

        if start_name == end_name:
            return ([start_name], 0)
        distances: Dict[str, float] = {loc: float("inf") for loc in self._locations}
        previous_nodes: Dict[str, Optional[str]] = {loc: None for loc in self._locations}
        distances[start_name] = 0

        pq: List[Tuple[float, str]] = [(0, start_name)]

        while pq:
            current_distance, current_node = heapq.heappop(pq)

            if current_distance > distances[current_node]:
                continue
            if current_node == end_name:
                path: List[str] = []
                temp_node = end_name
                while temp_node is not None:
                    path.append(temp_node)
                    temp_node = previous_nodes[temp_node]

                if distances[end_name] == float("inf"):
                    break

                return (list(reversed(path)), int(distances[end_name]))
            if current_node in self._connections:
                for neighbor, time in self._connections[current_node].items():
                    new_distance = current_distance + time

                    if new_distance < distances[neighbor]:
                        distances[neighbor] = new_distance
                        previous_nodes[neighbor] = current_node
                        heapq.heappush(pq, (new_distance, neighbor))

        logger.warning(f"无法找到从 '{start_name}' 到 '{end_name}' 的路径。")
        return None

    def get_agents_at_location(self, location_name: str, agent_registry: "AgentRegistry") -> List["Agent"]:
        """[空间查询] 获取当前在指定地点的所有 Agent 实例"""
        if not self.is_valid_location(location_name):
            logger.warning(f"尝试查询一个无效地点的 Agent: {location_name}")
            return []

        all_agents = agent_registry.get_all_agents()
        agents_at_location = [agent for agent in all_agents if agent._current_location == location_name]
        return agents_at_location

    def get_objects_with_verb(
        self,
        location_name: str,
        verb: str,
        object_prototypes: Dict[str, "GameObject"],
    ) -> List["GameObject"]:
        """[空间查询] 获取指定地点中所有允许特定交互动词的物体原型"""
        location = self.get_location(location_name)
        if not location:
            logger.warning(f"尝试查询无效地点的物体: {location_name}")
            return []

        matching_objects = []
        for obj_name in location.objects:
            prototype = object_prototypes.get(obj_name)
            if prototype and prototype.interaction_verb == verb:
                matching_objects.append(prototype)

        return matching_objects
