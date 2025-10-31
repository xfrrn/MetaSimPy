from pydantic import BaseModel, Field
from typing import Dict, Tuple, List, Any, TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .map import WorldMap
    from ..agents.agent import Agent


class WorldState(BaseModel):
    """管理和存储模拟世界的所有动态状态，以便于保存和加载"""

    # agent_id,  (地点, 工作类型)
    occupied_jobs: Dict[str, Tuple[str, str]] = Field(default_factory=dict, description="当前被占用的工作岗位")

    # 地点名,  {物体名: agent_id 或 "in_use"}
    object_states: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="动态物体的当前状态 (例如 'WashingMachine': 'adam_01')")

    def is_job_available(self, location_name: str, job_type: str, world_map: "WorldMap") -> bool:
        """[动态] 检查特定地点的工作岗位是否还有空位"""
        location = world_map.get_location(location_name)
        if not location or not location.available_jobs:
            return False

        max_workers = location.available_jobs.get(job_type, 0)
        if max_workers == 0:
            return False

        current_workers = 0
        for loc, job in self.occupied_jobs.values():
            if loc == location_name and job == job_type:
                current_workers += 1

        is_available = current_workers < max_workers
        logger.trace(f"工作检查 '{job_type}' @ '{location_name}': {current_workers}/{max_workers} (空闲: {is_available})")
        return is_available

    def assign_job_to_agent(self, agent: "Agent", location_name: str, job_type: str, world_map: "WorldMap") -> bool:
        """[动态] 尝试将一个工作岗位分配给 Agent。"""
        agent_id = agent.agent_id
        if agent_id in self.occupied_jobs:
            logger.warning(f"Agent '{agent_id}' 尝试分配新工作，但他已在工作。")
            return False

        if self.is_job_available(location_name, job_type, world_map):
            self.occupied_jobs[agent_id] = (location_name, job_type)
            logger.debug(f"工作分配成功: Agent '{agent_id}' 开始在 '{location_name}' 担任 '{job_type}'。")
            return True
        else:
            logger.info(f"工作分配失败: Agent '{agent_id}' 尝试在 '{location_name}' 担任 '{job_type}'，但已满员。")
            return False

    def remove_agent_from_job(self, agent_id: str):
        """[动态] 当 Agent 停止工作时，释放其占用的岗位"""
        if agent_id in self.occupied_jobs:
            loc, job = self.occupied_jobs.pop(agent_id)
            logger.debug(f"释放工作: Agent '{agent_id}' 停止了在 '{loc}' 的 '{job}' 工作。")

    def get_all_available_jobs(self, world_map: "WorldMap") -> Dict[str, List[str]]:
        """[动态] 获取地图上所有当前空闲的工作岗位列表"""
        available_jobs_map: Dict[str, List[str]] = {}
        for loc in world_map.get_all_locations():
            if not loc.available_jobs:
                continue

            loc_jobs = []
            for job_type in loc.available_jobs.keys():
                if self.is_job_available(loc.name, job_type, world_map):
                    loc_jobs.append(job_type)

            if loc_jobs:
                available_jobs_map[loc.name] = loc_jobs

        return available_jobs_map
