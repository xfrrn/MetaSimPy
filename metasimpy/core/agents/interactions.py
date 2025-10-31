from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Optional, Dict
from loguru import logger
import asyncio
import random

from ..world import world_interactions

if TYPE_CHECKING:
    from metasimpy.core.agents.agent import Agent
    from metasimpy.core.agents.registry import AgentRegistry

    from metasimpy.core.world.map import WorldMap
    from metasimpy.core.world.world_state import WorldState
    from metasimpy.core.world.objects import GameObject


class ActionBase(BaseModel):
    """所有 Agent 动作的基类"""

    duration_minutes: int = Field(default=1, description="动作的默认或计算出的持续时间（分钟）", ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        """
        执行动作的基类。
        kwargs 将包含所有运行时依赖：
        - world_map: WorldMap
        - world_state: WorldState
        - object_prototypes: Dict[str, GameObject]
        - agent_registry: AgentRegistry
        - memory_system: MemorySystem
        - current_time: datetime.datetime
        """
        logger.debug(f"Agent '{agent.name}' 正在执行基类动作，这不应该发生。")
        await asyncio.sleep(0)
        self.duration_minutes = 1


class WaitAction(ActionBase):
    """等待指定的分钟数。"""

    duration_minutes: int = Field(default=1, ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        """执行等待动作"""
        logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 等待 {self.duration_minutes} 分钟...")
        await asyncio.sleep(self.duration_minutes * 60)


class MoveToAction(ActionBase):
    """移动到一个新的地点。"""

    target_location: str = Field(..., description="目标位置名称")

    async def execute(self, agent: "Agent", **kwargs):
        world_map: "WorldMap" = kwargs["world_map"]

        if agent._current_location == self.target_location:
            logger.debug(f"Agent '{agent.name}' 已经在 '{self.target_location}'，无需移动。")
            self.duration_minutes = 1
            return

        logger.info(f"Agent '{agent.name}' 正在计算从 '{agent._current_location}' 到 '{self.target_location}' 的路径...")
        path_result = world_map.find_path(agent._current_location, self.target_location)

        if path_result:
            path, total_time = path_result
            self.duration_minutes = total_time

            logger.info(f"Agent '{agent.name}' 开始移动，路径: {' -> '.join(path)} (预计 {self.duration_minutes} 分钟)...")
            agent._internal_state.energy = max(0, agent._internal_state.energy - self.duration_minutes // 2)
        else:
            logger.warning(f"Agent '{agent.name}' 找不到到 '{self.target_location}' 的路径。原地等待。")
            self.duration_minutes = 1


class SpeakAction(ActionBase):
    """对另一个 Agent 说话或自言自语。"""

    duration_minutes: int = Field(default=2, ge=1)
    message: str = Field(..., description="要说的内容")
    target_agent_id: Optional[str] = Field(default=None, description="对话的目标 Agent ID，如果为 None 则是自言自语")

    async def execute(self, agent: "Agent", **kwargs):
        agent_registry: Optional["AgentRegistry"] = kwargs.get("agent_registry")

        if self.target_agent_id and agent_registry:
            target_agent = agent_registry.get_agent_by_id(self.target_agent_id)
            if target_agent:
                if agent._current_location == target_agent._current_location:
                    logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 对 '{target_agent.name}' 说: '{self.message}'")
                    # 更新关系
                    agent.update_relationship(self.target_agent_id, changes={"familiarity": random.randint(1, 3)})
                    target_agent.update_relationship(agent.agent_id, changes={"familiarity": random.randint(1, 3)})
                    # 社交需求减少
                    agent._internal_state.social_need = max(0, agent._internal_state.social_need - random.randint(5, 15))
                    if hasattr(target_agent._internal_state, "social_need"):
                        target_agent._internal_state.social_need = max(0, target_agent._internal_state.social_need - random.randint(5, 15))
                else:
                    logger.warning(f"Agent '{agent.name}' 试图对不在同一地点的 Agent '{target_agent.name}' 说话。")
                    logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 自言自语: '{self.message}'")
            else:
                logger.warning(f"Agent '{agent.name}' 试图对不存在的 Agent (ID: {self.target_agent_id}) 说话。")
                logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 自言自语: '{self.message}'")
        else:
            logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 自言自语: '{self.message}'")


class UseObjectAction(ActionBase):
    """使用一个物体"""

    object_name: str = Field(..., description="交互的物体名称 (例如 'Bed', 'WashingMachine', 'CommunityBoard')")

    async def execute(self, agent: "Agent", **kwargs):
        logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 尝试使用 '{self.object_name}'...")

        # 从 kwargs 获取依赖项
        world_map: "WorldMap" = kwargs["world_map"]
        world_state: "WorldState" = kwargs["world_state"]
        object_prototypes: Dict[str, "GameObject"] = kwargs["object_prototypes"]

        success, duration = await world_interactions.interact_with_object(agent=agent, object_name=self.object_name, world_map=world_map, world_state=world_state, object_prototypes=object_prototypes)

        self.duration_minutes = duration
        if not success:
            logger.warning(f"Agent '{agent.name}' 使用 '{self.object_name}' 失败。")


class WorkAction(ActionBase):
    """执行工作动作"""

    job_type: str = Field(..., description="工作类型 (例如 'cashier', 'barista')")
    duration_minutes: int = Field(default=60, ge=30, description="计划工作时长（分钟）")

    async def execute(self, agent: "Agent", **kwargs):
        logger.info(f"Agent '{agent.name}' 尝试在 '{agent._current_location}' 开始 '{self.job_type}' 工作...")

        world_map: "WorldMap" = kwargs["world_map"]
        world_state: "WorldState" = kwargs["world_state"]
        object_prototypes: Dict[str, "GameObject"] = kwargs["object_prototypes"]
        agent_registry: "AgentRegistry" = kwargs["agent_registry"]
        success, actual_duration = await world_interactions.perform_work(agent=agent, job_type=self.job_type, duration_minutes=self.duration_minutes, world_map=world_map, world_state=world_state, object_prototypes=object_prototypes, agent_registry=agent_registry)

        self.duration_minutes = actual_duration
        if not success:
            logger.warning(f"Agent '{agent.name}' 工作 '{self.job_type}' 失败（可能已满员或位置错误）。")


class BuyItemAction(ActionBase):
    """购买物品"""

    item_name: str = Field(..., description="购买的物品名称")
    quantity: int = Field(default=1, ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        logger.info(f"Agent '{agent.name}' 尝试在 '{agent._current_location}' 购买 {self.quantity} 个 '{self.item_name}'...")

        world_map: "WorldMap" = kwargs["world_map"]
        object_prototypes: Dict[str, "GameObject"] = kwargs["object_prototypes"]

        success, duration = await world_interactions.buy_item(agent=agent, item_name=self.item_name, quantity=self.quantity, world_map=world_map, object_prototypes=object_prototypes)

        self.duration_minutes = duration
        if not success:
            logger.warning(f"Agent '{agent.name}' 购买 '{self.item_name}' 失败（可能钱不够或物品不存在）。")


ACTION_MAPPING = {"Wait": WaitAction, "Speak": SpeakAction, "MoveTo": MoveToAction, "UseObject": UseObjectAction, "Work": WorkAction, "BuyItem": BuyItemAction}
