import asyncio
import datetime
from loguru import logger
from typing import Dict, Optional, TYPE_CHECKING

# metasimpy/core/agents/registry.py

if TYPE_CHECKING:
    from metasimpy.core.agents.agent import Agent

    # [新增] 导入依赖
    from metasimpy.core.world.map import WorldMap
    from metasimpy.core.world.world_state import WorldState
    from metasimpy.core.world.objects import GameObject


class AgentRegistry:
    def __init__(self, world_map: "WorldMap", world_state: "WorldState"):  # <-- [修改]
        self._agents: Dict[str, "Agent"] = {}
        self.world_map = world_map  # <-- [新增]
        self.world_state = world_state  # <-- [新增]
        logger.info("AgentRegistry 模块已初始化。")

    def register_agent(self, agent: "Agent"):
        if agent.agent_id in self._agents:
            logger.error(f"尝试注册已存在的 Agent ID: {agent.agent_id} (名称: {agent.name})")
            raise ValueError(f"Agent ID {agent.agent_id} 已存在。")

        self._agents[agent.agent_id] = agent
        logger.info(f"智能体 '{agent.name}' (ID: {agent.agent_id}) 已在 Registry 注册。")

    def get_agent_by_id(self, agent_id: str) -> Optional["Agent"]:
        agent = self._agents.get(agent_id)
        if agent is None:
            logger.warning(f"尝试获取不存在的 Agent ID: {agent_id}")
        return agent

    def get_all_agents(self) -> list["Agent"]:
        return list(self._agents.values())

    # metasimpy/core/agents/registry.py

    async def _trigger_agent_think(self, agent: "Agent", current_time: datetime.datetime, object_prototypes: Dict[str, "GameObject"]):  # <-- [修改]
        try:
            # [修改] 传入所有依赖项
            await agent.think_and_act(current_time=current_time, world_map=self.world_map, world_state=self.world_state, object_prototypes=object_prototypes, agent_registry=self)
        except Exception as e:
            logger.error(...)  # ... (错误处理不变) ...

    def on_minute_update(self, current_time: datetime.datetime, object_prototypes: Dict[str, "GameObject"]):  # <-- [修改]
        logger.trace(f"收到时间刻 {current_time}，检查 {len(self._agents)} 个智能体...")
        for agent in self._agents.values():
            # [修改] 调用 is_idle 时必须传入 world_state
            if agent.is_idle(current_time, self.world_state):
                logger.debug(f"智能体 '{agent.name}' (ID: {agent.agent_id}) 处于空闲状态，触发思考...")
                # [修改] 传递 object_prototypes
                asyncio.create_task(self._trigger_agent_think(agent, current_time, object_prototypes))
            else:
                pass
