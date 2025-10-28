import asyncio
import datetime
from loguru import logger
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from metasimpy.core.agents.agent import Agent


class AgentRegistry:
    def __init__(self):

        self._agents: Dict[str, "Agent"] = {}
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

    async def _trigger_agent_think(self, agent: "Agent", current_time: datetime.datetime):
        try:
            await agent.think_and_act(current_time)
        except Exception as e:
            logger.error(
                f"智能体 '{agent.name}' (ID: {agent.agent_id}) 在 think_and_act 期间遭遇错误: {e}",
                exc_info=True,
            )

    def on_minute_update(self, current_time: datetime.datetime):
        logger.trace(f"收到时间刻 {current_time}，检查 {len(self._agents)} 个智能体...")
        for agent in self._agents.values():
            if agent.is_idle(current_time):
                logger.debug(f"智能体 '{agent.name}' (ID: {agent.agent_id}) 处于空闲状态，触发思考...")
                asyncio.create_task(self._trigger_agent_think(agent, current_time))
            else:
                pass
