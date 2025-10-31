import datetime
import json
from enum import Enum
from loguru import logger
from typing import Optional, Dict, Any, TYPE_CHECKING, List

from .state_models import AgentInternalState, RelationshipData
from . import interactions as actions

if TYPE_CHECKING:
    from ..cognition.memory import MemorySystem, MemoryRecord
    from ..world.map import WorldMap
    from ..world.world_state import WorldState
    from ..agents.registry import AgentRegistry
    from ..world.objects import GameObject
    from langchain_core.language_models import BaseLanguageModel


class Agent:
    def __init__(
        self,
        name: str,
        persona: str,
        agent_id: str,
        start_location: str = "home",
        llm: Optional["BaseLanguageModel"] = None,
        memory_system: Optional["MemorySystem"] = None,
    ):

        self.agent_id: str = agent_id
        self.name: str = name
        self.persona: str = persona

        self.llm = llm
        self.memory_system = memory_system

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
                        case "familiarity":
                            new_value = max(0, min(100, new_value))
                        case _:
                            pass

                    if new_value != old_value:
                        setattr(rel, attribute_name, new_value)
                        updated_attributes[attribute_name] = (old_value, new_value)

                except TypeError:
                    logger.warning(f"Agent '{self.name}': 更新与 Agent '{target_agent_id}' 的关系属性 " f"'{attribute_name}' 时发生类型错误 (值: {change_value})。")
            else:
                logger.warning(f"Agent '{self.name}': 尝试更新与 Agent '{target_agent_id}' " f"不存在的关系属性 '{attribute_name}'。")

        if updated_attributes:
            change_summary = ", ".join(f"{attr} {old}->{new}" for attr, (old, new) in updated_attributes.items())
            logger.debug(f"Agent '{self.name}' 与 Agent '{target_agent_id}' 关系更新: {change_summary}")

    def is_idle(self, current_time: datetime.datetime, world_state: "WorldState") -> bool:
        """检查 Agent 是否空闲"""
        if self._current_action is None:
            return True

        if current_time >= self._current_action["end_time"]:
            action_name = "未知动作"
            action_obj = self._current_action.get("action_obj")

            if isinstance(action_obj, actions.ActionBase):
                action_name = action_obj.__class__.__name__

            world_state.remove_agent_from_job(self.agent_id)

            logger.trace(f"Agent '{self.name}' 的动作 '{action_name}' 已完成。")
            self._current_action = None
            return True
        else:
            return False

    def _parse_llm_response(self, response_content: str) -> actions.ActionBase:
        """安全地解析 LLM 的 JSON 响应为 Action 对象"""
        try:
            if response_content.startswith("```json"):
                response_content = response_content.strip("```json").strip("```").strip()

            data = json.loads(response_content)
            action_name = data.get("action_name")
            parameters = data.get("parameters", {})

            action_class = actions.ACTION_MAPPING.get(action_name)

            if action_class:
                return action_class(**parameters)
            else:
                logger.warning(f"LLM 返回了未知的 action_name: '{action_name}'。回退到 WaitAction。")
                return actions.WaitAction(duration_minutes=1)

        except json.JSONDecodeError:
            logger.error(f"LLM 返回的 JSON 格式错误: {response_content}")
            return actions.WaitAction(duration_minutes=1)
        except Exception as e:
            logger.error(f"解析 LLM 响应时出错: {e}. 响应: {response_content}")
            return actions.WaitAction(duration_minutes=1)

    async def think_and_act(
        self,
        current_time: datetime.datetime,
        world_map: "WorldMap",
        world_state: "WorldState",
        object_prototypes: Dict[str, "GameObject"],
        agent_registry: "AgentRegistry",
    ):
        logger.info(f"[{current_time.strftime('%H:%M')}] Agent '{self.name}' 开始思考...")

        if not self.llm or not self.memory_system:
            logger.error(f"Agent '{self.name}' 缺少 LLM 或 MemorySystem 实例，无法思考。")
            action_plan = actions.WaitAction(duration_minutes=1)
        else:
            # 感知与记忆检索
            # 1a. 感知当前环境
            agents_here = world_map.get_agents_at_location(self._current_location, agent_registry)
            objects_here = world_map.get_objects_at_location(self._current_location)
            # 1b. 检索相关记忆
            retrieved_memories = await self.memory_system.retrieve_memories(self.agent_id, query_text=f"我现在的状态是 {self._internal_state.mood.value}，我在 {self._current_location}。", current_time=current_time, top_k=10)

            # 2. 构建 Prompt
            prompt = self._build_prompt(current_time=current_time, agents_here=agents_here, objects_here=objects_here, memories=retrieved_memories)

            # 3. 调用 LLM 决策
            logger.debug(f"Agent '{self.name}' 调用 LLM 进行决策...")
            action_plan: actions.ActionBase

            try:
                response = await self.llm.ainvoke(prompt)
                action_plan = self._parse_llm_response(response.content)
                logger.info(f"Agent '{self.name}' 决定执行: {action_plan.__class__.__name__} ({action_plan.duration_minutes} 分钟)")

            except Exception as e:
                logger.error(f"Agent '{self.name}' LLM 决策失败: {e}", exc_info=True)
                action_plan = actions.WaitAction(duration_minutes=1)
        try:
            await action_plan.execute(self, world_map=world_map, world_state=world_state, object_prototypes=object_prototypes, agent_registry=agent_registry, memory_system=self.memory_system, current_time=current_time)

            action_end_time = current_time + datetime.timedelta(minutes=action_plan.duration_minutes)
            self._current_action = {
                "action_obj": action_plan,
                "end_time": action_end_time,
            }
            logger.debug(f"Agent '{self.name}' 当前动作设置为 '{action_plan.__class__.__name__}', 预计结束于 {action_end_time.strftime('%H:%M')}")

            if self.memory_system:
                from ..cognition.memory import MemoryRecord, MemoryType

                memory_content = f"我在 {self._current_location} 执行了动作: {action_plan.__class__.__name__}。"
                if isinstance(action_plan, actions.MoveToAction):
                    memory_content = f"我从 {self._current_location} 移动到了 {action_plan.target_location}。"
                elif isinstance(action_plan, actions.SpeakAction):
                    memory_content = f"我对 {action_plan.target_agent_id or '自己'} 说: '{action_plan.message}'。"

                new_memory = MemoryRecord(
                    agent_id=self.agent_id,
                    timestamp=current_time,
                    type=MemoryType.ACTION,
                    content=memory_content,
                )
                await self.memory_system.add_memory(self.agent_id, new_memory)

            if isinstance(action_plan, actions.MoveToAction):
                self._current_location = action_plan.target_location

        except Exception as e:
            logger.error(
                f"Agent '{self.name}' 执行动作 '{action_plan.__class__.__name__}' 失败: {e}",
                exc_info=True,
            )
            self._current_action = {
                "action_obj": actions.WaitAction(duration_minutes=1),
                "end_time": current_time + datetime.timedelta(minutes=1),
            }

    def _build_prompt(self, current_time: datetime.datetime, agents_here: List["Agent"], objects_here: List[str], memories: List["MemoryRecord"]) -> str:
        prompt = f"""
        你是 {self.name}.
        {self.persona}
        """

        prompt += f"""
        ---
        [当前概况]
        当前时间是 {current_time.strftime('%Y-%m-%d %H:%M')}.
        你目前位于 {self._current_location}.
        你的内部状态: 
        - 情绪: {self._internal_state.mood.value if isinstance(self._internal_state.mood, Enum) else self._internal_state.mood}
        - 精力: {self._internal_state.energy}/100
        - 饥饿度: {self._internal_state.hunger}/100 (越高越饿)
        - 压力: {self._internal_state.stress_level}/100
        - 社交需求: {self._internal_state.social_need}/100
        """

        prompt += "\n[环境感知]"
        if len(agents_here) > 1:
            other_agent_names = [a.name for a in agents_here if a.agent_id != self.agent_id]
            prompt += f"\n你看到这里有 {len(other_agent_names)} 个人: {', '.join(other_agent_names)}."
        else:
            prompt += "\n这里现在只有你一个人。"

        prompt += f"\n你看到这里的物品有: {', '.join(objects_here)}."

        prompt += "\n\n[相关记忆]"
        if memories:
            for mem in memories:
                time_ago = (current_time - mem.timestamp).total_seconds() / 60
                prompt += f"\n- [{mem.type.value}, {time_ago:.0f} 分钟前]: {mem.content}"
        else:
            prompt += "\n你暂时没有相关的记忆。"

        prompt += f"""
        ---
        [决策]
        根据你的身份、当前状态、环境和记忆，决定你接下来要做什么。
        请只输出一个 JSON 对象，描述你的下一个动作。
        
        可选的动作 (action_name) 包括:
        - "Wait": (参数: duration_minutes)
        - "MoveTo": (参数: target_location)
        - "Speak": (参数: message, target_agent_id)
        - "UseObject": (参数: object_name)
        - "Work": (参数: job_type, duration_minutes)
        - "BuyItem": (参数: item_name, quantity)

        示例:
        {{"action_name": "MoveTo", "parameters": {{"target_location": "Cafe"}}}}
        
        你的 JSON 决策:
        """
        return prompt.strip()
