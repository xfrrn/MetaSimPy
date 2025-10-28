import datetime
from enum import Enum
from loguru import logger
from typing import Optional, Dict, Any

from .state_models import AgentInternalState, RelationshipData


class Agent:
    def __init__(
        self,
        name: str,
        persona: str,
        agent_id: str,
        start_location: str = "home",
    ):

        self.agent_id: str = agent_id
        self.name: str = name
        self.persona: str = persona

        self._internal_state: AgentInternalState = AgentInternalState()
        self._relationships: Dict[str, RelationshipData] = {}
        self._current_location: str = start_location
        self._current_action: Optional[Dict[str, Any]] = None

        logger.info(f"Agent '{self.name}' (ID: {self.agent_id}) 已创建。")

    def update_mood(self, new_mood: str):
        logger.debug(f"Agent '{self.name}' 情绪更新: {self._internal_state.mood} -> {new_mood}")
        from .state_models import MoodState

        try:
            validated_mood = MoodState(new_mood)
            self._internal_state.mood = validated_mood
        except ValueError:
            logger.warning(f"尝试为 Agent '{self.name}' 设置无效的情绪状态: {new_mood}")

    def update_relationship(self, target_agent_id: str, changes: Dict[str, int]):
        """
        更新与另一个 Agent 的关系。
        """
        if target_agent_id == self.agent_id:
            logger.trace(f"Agent '{self.name}' 尝试更新与自己的关系，已跳过。")
            return

        if target_agent_id not in self._relationships:
            self._relationships[target_agent_id] = RelationshipData()
            logger.debug(f"Agent '{self.name}' 首次与 Agent '{target_agent_id}' 建立关系记录。")

        rel = self._relationships[target_agent_id]
        updated_attributes = {}

        for attribute_name, change_value in changes.items():
            if hasattr(rel, attribute_name):
                try:
                    old_value = getattr(rel, attribute_name)
                    new_value = old_value + change_value

                    match attribute_name:
                        case "affinity":
                            new_value = max(-100, min(100, new_value))
                            logger.trace(f"应用 affinity 边界: {old_value}+{change_value} -> {new_value}")
                        case "familiarity":
                            new_value = max(0, min(100, new_value))
                            logger.trace(f"应用 familiarity 边界: {old_value}+{change_value} -> {new_value}")
                        case _:
                            logger.trace(f"属性 '{attribute_name}' 无特定边界检查。")
                            pass

                    if new_value != old_value:
                        setattr(rel, attribute_name, new_value)
                        updated_attributes[attribute_name] = (old_value, new_value)
                    else:
                        logger.trace(f"属性 '{attribute_name}' 的值未改变 ({old_value})，跳过更新。")

                except TypeError:
                    logger.warning(f"Agent '{self.name}': 更新与 Agent '{target_agent_id}' 的关系属性 " f"'{attribute_name}' 时发生类型错误 (值: {change_value})。")
                except Exception as e:
                    logger.error(
                        f"Agent '{self.name}': 更新与 Agent '{target_agent_id}' 的关系属性 " f"'{attribute_name}' 时发生未知错误: {e}",
                        exc_info=True,
                    )
            else:
                logger.warning(f"Agent '{self.name}': 尝试更新与 Agent '{target_agent_id}' " f"不存在的关系属性 '{attribute_name}'。")

        if updated_attributes:
            change_summary = ", ".join(f"{attr} {old}->{new}" for attr, (old, new) in updated_attributes.items())
            logger.debug(f"Agent '{self.name}' 与 Agent '{target_agent_id}' 关系更新: {change_summary}")

    def is_idle(self, current_time: datetime.datetime) -> bool:
        return True

    async def think_and_act(self, current_time: datetime.datetime):
        logger.info(f"[{current_time.strftime('%H:%M')}] Agent '{self.name}' 开始思考...")
        pass

    def _build_prompt(self, current_time: datetime.datetime) -> str:
        prompt = f"""
        你是 {self.name}.
        {self.persona}
        当前时间是 {current_time.strftime('%Y-%m-%d %H:%M')}.
        你现在感觉 {self._internal_state.mood.value if isinstance(self._internal_state.mood, Enum) else self._internal_state.mood}.
        你目前位于 {self._current_location}.

        根据你的情况，决定你接下来要做什么。请只输出一个 JSON 对象，包含 "action_name" 和 "duration_minutes"。
        例如: {{"action_name": "Wait", "duration_minutes": 5}}
        """
        return prompt
