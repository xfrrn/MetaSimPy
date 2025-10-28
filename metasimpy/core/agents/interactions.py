import datetime
from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Optional
from loguru import logger
import asyncio

if TYPE_CHECKING:
    from metasimpy.core.agents.agent import Agent


class ActionBase(BaseModel):
    duration_minutes: int = Field(..., description="动作持续模拟分钟")

    async def execute(self, agent: "Agent", **kwargs):
        logger.debug(f"Agent '{agent.name}' 正在执行基类动作，这不应该发生。")
        await asyncio.sleep(0)


class WaitAction(ActionBase):
    duration_minutes: int = Field(default=1, ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        """执行等待动作"""
        logger.info(f"Agent '{agent.name}' 开始等待 {self.duration_minutes} 分钟...")
        pass


class SpeakAction(ActionBase):
    duration_minutes: int = Field(default=2, ge=1)
    message: str = Field(..., description="要说的内容")
    target_agent_id: Optional[str] = Field(default=None, description="对话的目标 Agent ID，如果为 None 则是自言自语")

    async def execute(self, agent: "Agent", **kwargs):
        agent_registry = kwargs.get("agent_registry")

        if self.target_agent_id and agent_registry:
            target_agent = agent_registry.get_agent_by_id(self.target_agent_id)
            if target_agent:
                logger.info(f"Agent '{agent.name}' 对 '{target_agent.name}' 说: '{self.message}'")
                # [未来] 在这里触发对方 Agent 的“感知”
                # await target_agent.perceive_speech(agent.agent_id, self.message)

                # [临时] 示例：更新关系
                agent.update_relationship(self.target_agent_id, changes={"familiarity": 1})
                target_agent.update_relationship(agent.agent_id, changes={"familiarity": 1})
            else:
                logger.warning(f"Agent '{agent.name}' 试图对不存在的 Agent (ID: {self.target_agent_id}) 说话。")
        else:
            logger.info(f"Agent '{agent.name}' 自言自语: '{self.message}'")
