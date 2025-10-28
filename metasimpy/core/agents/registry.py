# metasimpy/core/agents/registry.py

import asyncio
import datetime
from loguru import logger
from typing import Dict, Optional, TYPE_CHECKING

# [关键] 使用 TYPE_CHECKING 块来导入 Agent，避免循环导入
if TYPE_CHECKING:
    # 假设 Agent 类定义在 agent.py 中
    from metasimpy.core.agents.agent import Agent


class AgentRegistry:
    """
    AgentRegistry (智能体管理器) 负责创建、存储和管理所有 Agent 实例。
    它同时作为 Timeline 事件的订阅者，驱动 Agent 的思考和行动循环。
    """

    def __init__(self):
        """
        初始化智能体管理器。
        """
        # 使用字典存储 Agent 实例，方便通过 ID 快速查找。
        self._agents: Dict[str, "Agent"] = {}
        logger.info("AgentRegistry 模块已初始化。")

    def register_agent(self, agent: "Agent"):
        """
        将一个新创建的 Agent 实例注册到管理器中。
        """
        if agent.agent_id in self._agents:
            logger.error(
                f"尝试注册已存在的 Agent ID: {agent.agent_id} (名称: {agent.name})"
            )
            raise ValueError(f"Agent ID {agent.agent_id} 已存在。")

        self._agents[agent.agent_id] = agent
        logger.info(
            f"智能体 '{agent.name}' (ID: {agent.agent_id}) 已在 Registry 注册。"
        )

    def get_agent_by_id(self, agent_id: str) -> Optional["Agent"]:
        """
        根据 Agent ID 查找并返回 Agent 实例。
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            logger.warning(f"尝试获取不存在的 Agent ID: {agent_id}")
        return agent

    def get_all_agents(self) -> list["Agent"]:
        """
        返回所有已注册 Agent 的列表。
        """
        return list(self._agents.values())

    async def _trigger_agent_think(
        self, agent: "Agent", current_time: datetime.datetime
    ):
        """
        【内部】安全地异步触发一个 Agent 的思考，并捕获其内部错误。
        """
        try:
            # 调用 Agent 自己的异步思考方法
            await agent.think_and_act(current_time)
        except Exception as e:
            # 捕获 Agent 思考/行动时发生的任何错误
            logger.error(
                f"智能体 '{agent.name}' (ID: {agent.agent_id}) 在 think_and_act 期间遭遇错误: {e}",
                exc_info=True,  # 包含完整的错误堆栈信息
            )

    # --- 核心回调函数 ---

    def on_minute_update(self, current_time: datetime.datetime):
        """
        【公开的回调】由 Timeline 的 "on_minute_passed" 事件触发。
        这是驱动 Agent 行为的核心入口点。
        """
        # 使用 TRACE 级别记录这个非常频繁的事件入口
        logger.trace(f"收到时间刻 {current_time}，检查 {len(self._agents)} 个智能体...")

        # 遍历当前注册的所有 Agent
        # 使用 .values() 获取 Agent 实例列表进行迭代
        for agent in self._agents.values():

            # 1. [过滤] 检查 Agent 是否空闲
            # 调用 Agent 实例自己的 is_idle 方法
            if agent.is_idle(current_time):

                # 2. [驱动] 如果 Agent 空闲，异步触发它的思考和行动
                logger.debug(
                    f"智能体 '{agent.name}' (ID: {agent.agent_id}) 处于空闲状态，触发思考..."
                )
                asyncio.create_task(self._trigger_agent_think(agent, current_time))

            else:
                # Agent 正在忙碌，记录一条 TRACE 级别的日志
                # action_name = getattr(agent._current_action.get("action_obj"), '__class__', {}).__name__ or "未知动作"
                # logger.trace(f"智能体 '{agent.name}' 正在执行 '{action_name}'，跳过。")
                pass  # 通常不需要记录忙碌状态，避免日志过多
