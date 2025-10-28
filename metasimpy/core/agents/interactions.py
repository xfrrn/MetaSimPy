# metasimpy/core/agents/interactions.py

import datetime
from pydantic import BaseModel, Field, field_validator
from typing import TYPE_CHECKING, Optional, List
from loguru import logger
import asyncio
import random

# 引入Agent内部状态模型，用于修改状态
from .state_models import MoodState, HealthStatus

if TYPE_CHECKING:
    from metasimpy.core.agents.agent import Agent
    from metasimpy.core.agents.registry import AgentRegistry

LOCATIONS = [
    # 公寓内部
    "Rooftop",
    "Lobby",
    "Laundry_Room",
    # 假设公寓名称格式为 "Apartment_1A", "Apartment_1B", ... "Apartment_7B"
    *[f"Apartment_{i}{L}" for i in range(1, 8) for L in ["A", "B"]],
    # 公寓外部
    "Building_Entrance",
    "Walking_Path",
    "Park",
    # 社区/商业区
    "Supermarket",
    "Cafe",
    "Clinic",
    "Community_Center",
    # 外部世界
    "Bus_Stop",
    "Highway",
]


class ActionBase(BaseModel):
    duration_minutes: int = Field(..., description="动作持续模拟分钟", ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        logger.debug(f"Agent '{agent.name}' 正在执行基类动作，这不应该发生。")
        await asyncio.sleep(0)


class WaitAction(ActionBase):
    duration_minutes: int = Field(default=1, ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        """执行等待动作"""
        logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 等待 {self.duration_minutes} 分钟...")
        # 等待动作通常不直接改变状态，但可以根据游戏逻辑添加，比如轻微减少压力
        # agent._internal_state.stress_level = max(0, agent._internal_state.stress_level - 1)
        pass


class SpeakAction(ActionBase):
    duration_minutes: int = Field(default=2, ge=1)
    message: str = Field(..., description="要说的内容")
    target_agent_id: Optional[str] = Field(default=None, description="对话的目标 Agent ID，如果为 None 则是自言自语")

    async def execute(self, agent: "Agent", **kwargs):
        agent_registry: Optional["AgentRegistry"] = kwargs.get("agent_registry")  # 类型提示

        if self.target_agent_id and agent_registry:
            target_agent = agent_registry.get_agent_by_id(self.target_agent_id)
            if target_agent:
                # 确保目标在同一地点 (简单规则，可根据需要调整)
                if agent._current_location == target_agent._current_location:
                    logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 对 '{target_agent.name}' 说: '{self.message}'")
                    # [未来] 在这里触发对方 Agent 的“感知”
                    # await target_agent.perceive_speech(agent.agent_id, self.message, agent._current_location)

                    # 更新关系
                    # 说话通常增加熟悉度，好感度取决于内容（这里简化处理）
                    agent.update_relationship(self.target_agent_id, changes={"familiarity": random.randint(1, 3)})
                    target_agent.update_relationship(agent.agent_id, changes={"familiarity": random.randint(1, 3)})
                    # 社交需求减少
                    agent._internal_state.social_need = max(0, agent._internal_state.social_need - random.randint(5, 15))
                    target_agent._internal_state.social_need = max(0, target_agent._internal_state.social_need - random.randint(5, 15))
                else:
                    logger.warning(f"Agent '{agent.name}' 试图对不在同一地点的 Agent '{target_agent.name}' 说话 " f"('{agent._current_location}' vs '{target_agent._current_location}')。")
                    # 可以视为自言自语或失败
                    logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 自言自语 (因为目标不在): '{self.message}'")

            else:
                logger.warning(f"Agent '{agent.name}' 试图对不存在的 Agent (ID: {self.target_agent_id}) 说话。")
                logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 自言自语: '{self.message}'")
        else:
            logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 自言自语: '{self.message}'")


class MoveToAction(ActionBase):
    target_location: str = Field(..., description="目标位置名称")
    duration_minutes: int = Field(default=5, ge=1, description="移动所需时间（分钟）")  # 提供默认值

    @field_validator("target_location")
    @classmethod
    def check_location_exists(cls, v):
        if v not in LOCATIONS:
            # 实际上不应该在这里 raise ValueError, LLM 可能生成地图外的地点
            # 应该在 execute 中处理无效地点
            logger.warning(f"目标位置 '{v}' 不在预定义的地图位置列表中。")
        return v

    async def execute(self, agent: "Agent", **kwargs):
        if agent._current_location == self.target_location:
            logger.debug(f"Agent '{agent.name}' 已经在 '{self.target_location}'，无需移动。")
            # 可以选择将持续时间设为0或1，避免卡住
            self.duration_minutes = 1
            return

        if self.target_location not in LOCATIONS:
            logger.error(f"Agent '{agent.name}' 尝试移动到无效位置 '{self.target_location}'。原地等待1分钟。")
            # 直接修改持续时间为1分钟，避免复杂的状态修改
            self.duration_minutes = 1
            return

        logger.info(f"Agent '{agent.name}' 开始从 '{agent._current_location}' 移动到 '{self.target_location}' (预计 {self.duration_minutes} 分钟)...")
        # 模拟效果
        agent._internal_state.energy = max(0, agent._internal_state.energy - self.duration_minutes // 2)  # 每2分钟消耗1点能量
        # 实际位置变更应在动作结束后由 Agent 或 Timeline 更新，这里只记录意图
        # agent._current_location = self.target_location # 不在这里改，在 Agent.is_idle 检查结束后改

        # **重要**: 真正的移动逻辑（更新 agent._current_location）应该在 Agent 类
        # 的 is_idle 方法检测到动作完成 *之后* 执行，或者由 Timeline 在 tick 结束时处理。
        # 这里只记录日志和状态变化。
        pass


# --- 2. 与环境/物品交互 ---
class UseObjectAction(ActionBase):
    object_name: str = Field(..., description="交互的物体名称")
    # target_location: str = Field(..., description="物体所在位置") # 可以省略，假设Agent已在物体位置
    duration_minutes: int = Field(default=5, ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        location = agent._current_location
        logger.info(f"Agent '{agent.name}' 在 '{location}' 尝试使用 '{self.object_name}'...")

        if location == "Laundry_Room" and self.object_name == "WashingMachine":
            if agent._internal_state.laundry_need > 20:  # 只有需要洗衣时才有效
                reduction = random.randint(30, 70)
                agent._internal_state.laundry_need = max(0, agent._internal_state.laundry_need - reduction)
                logger.info(f"Agent '{agent.name}' 使用洗衣机，洗衣需求减少 {reduction}，剩余 {agent._internal_state.laundry_need}。")
                agent._internal_state.energy = max(0, agent._internal_state.energy - 5)  # 消耗少量能量
            else:
                logger.info(f"Agent '{agent.name}' 不需要洗衣，使用洗衣机无效。")
                self.duration_minutes = 1  # 减少无效动作时间
        elif location == "Cafe" and self.object_name == "CoffeeMachine":
            cost = 5
            if agent._internal_state.money >= cost:
                agent._internal_state.money -= cost
                agent._internal_state.energy = min(100, agent._internal_state.energy + random.randint(10, 25))
                agent._internal_state.mood = MoodState.CONTENT  # 喝咖啡可能满足
                logger.info(f"Agent '{agent.name}' 在咖啡馆买了咖啡，花费 {cost}，精力增加，心情满足。")
            else:
                logger.warning(f"Agent '{agent.name}' 想买咖啡但钱不够。")
                self.duration_minutes = 1
        elif location == "Park" and self.object_name == "Bench":
            energy_gain = random.randint(1, 5)
            agent._internal_state.energy = min(100, agent._internal_state.energy + energy_gain)
            stress_reduction = random.randint(1, 10)
            agent._internal_state.stress_level = max(0, agent._internal_state.stress_level - stress_reduction)
            logger.info(f"Agent '{agent.name}' 在公园长椅休息，精力恢复 {energy_gain}，压力减少 {stress_reduction}。")
        # 可以添加更多物体交互逻辑...
        else:
            logger.warning(f"Agent '{agent.name}' 尝试在 '{location}' 使用 '{self.object_name}'，但未定义交互逻辑或物体不存在于此。")
            # 视为短时间等待
            self.duration_minutes = 1
            await WaitAction(duration_minutes=1).execute(agent, **kwargs)


class GardeningAction(ActionBase):
    duration_minutes: int = Field(default=30, ge=10)

    async def execute(self, agent: "Agent", **kwargs):
        if agent._current_location == "Rooftop":
            logger.info(f"Agent '{agent.name}' 在楼顶花园园艺 {self.duration_minutes} 分钟...")
            agent._internal_state.energy = max(0, agent._internal_state.energy - self.duration_minutes // 3)
            # 如果人设匹配，增加满足感
            if "园艺" in agent.persona or "gardening" in agent.persona.lower():
                agent._internal_state.mood = MoodState.CONTENT
                agent._internal_state.stress_level = max(0, agent._internal_state.stress_level - random.randint(5, 15))
                logger.debug(f"Agent '{agent.name}' 通过园艺感到满足，压力减轻。")
        else:
            logger.warning(f"Agent '{agent.name}' 尝试在非楼顶位置 '{agent._current_location}' 进行园艺。")
            self.duration_minutes = 1
            await WaitAction(duration_minutes=1).execute(agent, **kwargs)


class WalkAction(ActionBase):
    path_name: str = Field(default="Walking_Path", description="散步路径名称")
    duration_minutes: int = Field(default=20, ge=5)

    async def execute(self, agent: "Agent", **kwargs):
        if agent._current_location == self.path_name or agent._current_location == "Park":  # 假设可以在公园散步或在路径上散步
            logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 散步 {self.duration_minutes} 分钟...")
            energy_cost = self.duration_minutes // 4
            stress_reduction = self.duration_minutes // 3
            agent._internal_state.energy = max(0, agent._internal_state.energy - energy_cost)
            agent._internal_state.stress_level = max(0, agent._internal_state.stress_level - stress_reduction)
            logger.debug(f"Agent '{agent.name}' 散步消耗 {energy_cost} 精力，压力减少 {stress_reduction}。")
        else:
            logger.warning(f"Agent '{agent.name}' 尝试在 '{agent._current_location}' 散步，但需要先移动到 'Walking_Path' 或 'Park'。")
            self.duration_minutes = 1
            await WaitAction(duration_minutes=1).execute(agent, **kwargs)


# --- 3. 社交相关 ---
class ListenAction(ActionBase):
    target_agent_id: str = Field(..., description="倾听的目标 Agent ID")
    duration_minutes: int = Field(default=3, ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        agent_registry: Optional["AgentRegistry"] = kwargs.get("agent_registry")
        if agent_registry:
            target_agent = agent_registry.get_agent_by_id(self.target_agent_id)
            if target_agent and agent._current_location == target_agent._current_location:
                logger.info(f"Agent '{agent.name}' 在 '{agent._current_location}' 倾听 '{target_agent.name}'...")
                agent.update_relationship(self.target_agent_id, changes={"familiarity": random.randint(0, 2)})  # 倾听可能增加熟悉度
                # 社交需求轻微减少
                agent._internal_state.social_need = max(0, agent._internal_state.social_need - random.randint(1, 5))
            elif target_agent:
                logger.warning(f"Agent '{agent.name}' 试图倾听不在同一地点的 Agent '{target_agent.name}'。")
                self.duration_minutes = 1
            else:
                logger.warning(f"Agent '{agent.name}' 试图倾听不存在的 Agent (ID: {self.target_agent_id})。")
                self.duration_minutes = 1
        else:
            logger.warning(f"Agent '{agent.name}' 无法倾听，缺少 Agent Registry。")
            self.duration_minutes = 1


class HangOutAction(ActionBase):
    target_agent_ids: List[str] = Field(..., description="一起闲逛的 Agent ID列表")
    # location: str = Field(..., description="闲逛地点") # 可以省略，使用当前位置
    duration_minutes: int = Field(default=30, ge=10)

    async def execute(self, agent: "Agent", **kwargs):
        agent_registry: Optional["AgentRegistry"] = kwargs.get("agent_registry")
        location = agent._current_location

        valid_targets = []
        if agent_registry:
            for target_id in self.target_agent_ids:
                if target_id == agent.agent_id:
                    continue  # 不能和自己闲逛
                target = agent_registry.get_agent_by_id(target_id)
                if target and target._current_location == location:
                    valid_targets.append(target)
                elif target:
                    logger.warning(f"HangOutAction: Agent '{target.name}' 不在 '{location}'，无法加入。")
                else:
                    logger.warning(f"HangOutAction: Agent ID '{target_id}' 不存在。")

        if not valid_targets:
            logger.info(f"Agent '{agent.name}' 在 '{location}' 找不到人一起闲逛，独自等待。")
            self.duration_minutes = 5  # 减少等待时间
            await WaitAction(duration_minutes=self.duration_minutes).execute(agent, **kwargs)
            return

        target_names = ", ".join([t.name for t in valid_targets])
        logger.info(f"Agent '{agent.name}' 在 '{location}' 与 '{target_names}' 一起闲逛 {self.duration_minutes} 分钟...")

        # 更新关系和状态
        social_need_reduction = random.randint(15, 40)
        agent._internal_state.social_need = max(0, agent._internal_state.social_need - social_need_reduction)
        agent._internal_state.stress_level = max(0, agent._internal_state.stress_level - random.randint(5, 15))

        for target in valid_targets:
            familiarity_increase = random.randint(3, 8)
            affinity_increase = random.randint(1, 5)
            agent.update_relationship(target.agent_id, changes={"familiarity": familiarity_increase, "affinity": affinity_increase})
            target.update_relationship(agent.agent_id, changes={"familiarity": familiarity_increase, "affinity": affinity_increase})
            target._internal_state.social_need = max(0, target._internal_state.social_need - social_need_reduction)
            target._internal_state.stress_level = max(0, target._internal_state.stress_level - random.randint(5, 15))


# --- 4. 个人需求 ---
class EatAction(ActionBase):
    duration_minutes: int = Field(default=15, ge=5)
    # location: str = Field(..., description="吃饭地点") # 使用 agent._current_location

    async def execute(self, agent: "Agent", **kwargs):
        location = agent._current_location
        hunger_reduction = 0
        cost = 0

        logger.info(f"Agent '{agent.name}' 尝试在 '{location}' 吃饭...")

        if "Apartment" in location:  # 假设在家吃
            hunger_reduction = random.randint(40, 80)
            # 可以在这里添加检查是否有食物库存的逻辑
            logger.info(f"Agent '{agent.name}' 在家吃饭，饥饿度减少 {hunger_reduction}。")
        elif location == "Cafe":
            hunger_reduction = random.randint(30, 60)
            cost = random.randint(10, 25)
            if agent._internal_state.money >= cost:
                agent._internal_state.money -= cost
                logger.info(f"Agent '{agent.name}' 在咖啡馆吃饭，花费 {cost}，饥饿度减少 {hunger_reduction}。")
            else:
                logger.warning(f"Agent '{agent.name}' 想在咖啡馆吃饭但钱不够。")
                self.duration_minutes = 1  # 动作失败，只等待1分钟
                hunger_reduction = 0
        else:
            logger.warning(f"Agent '{agent.name}' 无法在 '{location}' 吃饭。")
            self.duration_minutes = 1
            await WaitAction(duration_minutes=1).execute(agent, **kwargs)
            return

        agent._internal_state.hunger = max(0, agent._internal_state.hunger - hunger_reduction)
        agent._internal_state.energy = min(100, agent._internal_state.energy + random.randint(0, 10))  # 吃饭可能恢复少量能量


class SleepAction(ActionBase):
    duration_minutes: int = Field(default=480, ge=60)  # 默认睡8小时

    async def execute(self, agent: "Agent", **kwargs):
        if "Apartment" in agent._current_location:  # 只能在家睡觉
            logger.info(f"Agent '{agent.name}' 在家开始睡觉 {self.duration_minutes} 分钟...")
            energy_gain = min(100 - agent._internal_state.energy, (self.duration_minutes // 60) * random.randint(10, 15))  # 每小时恢复10-15点
            agent._internal_state.energy = min(100, agent._internal_state.energy + energy_gain)
            # 睡觉可以减少压力
            agent._internal_state.stress_level = max(0, agent._internal_state.stress_level - self.duration_minutes // 10)
            logger.debug(f"Agent '{agent.name}' 睡觉后精力恢复至 {agent._internal_state.energy}，压力降至 {agent._internal_state.stress_level}。")
        else:
            logger.warning(f"Agent '{agent.name}' 尝试在 '{agent._current_location}' 睡觉，但只能在家进行。")
            self.duration_minutes = 1
            await WaitAction(duration_minutes=1).execute(agent, **kwargs)


class ShowerAction(ActionBase):
    duration_minutes: int = Field(default=10, ge=5)

    async def execute(self, agent: "Agent", **kwargs):
        if "Apartment" in agent._current_location:
            logger.info(f"Agent '{agent.name}' 在家洗澡 {self.duration_minutes} 分钟...")
            hygiene_gain = min(100 - agent._internal_state.hygiene, random.randint(30, 70))
            agent._internal_state.hygiene = min(100, agent._internal_state.hygiene + hygiene_gain)
            # 洗澡可能放松，减少压力
            agent._internal_state.stress_level = max(0, agent._internal_state.stress_level - random.randint(1, 5))
            logger.debug(f"Agent '{agent.name}' 洗澡后清洁度提升至 {agent._internal_state.hygiene}。")
        else:
            logger.warning(f"Agent '{agent.name}' 尝试在 '{agent._current_location}' 洗澡，但只能在家进行。")
            self.duration_minutes = 1
            await WaitAction(duration_minutes=1).execute(agent, **kwargs)


# --- 5. 购物/交易 ---
class BuyAction(ActionBase):
    item_name: str = Field(..., description="购买的物品名称")
    quantity: int = Field(default=1, ge=1)
    # location: str = Field(..., description="购物地点") # 使用 agent._current_location
    duration_minutes: int = Field(default=10, ge=3)

    async def execute(self, agent: "Agent", **kwargs):
        location = agent._current_location
        cost_per_item = 0
        can_buy = False

        if location == "Supermarket":
            # 假设超市有各种物品
            item_costs = {"food": 10, "drink": 3, "cleaning_supply": 8}  # 示例价格
            if self.item_name in item_costs:
                cost_per_item = item_costs[self.item_name]
                can_buy = True
            else:
                logger.warning(f"超市没有 '{self.item_name}' 出售。")
        elif location == "Cafe":
            item_costs = {"coffee": 5, "sandwich": 8}
            if self.item_name in item_costs:
                cost_per_item = item_costs[self.item_name]
                can_buy = True
            else:
                logger.warning(f"咖啡馆没有 '{self.item_name}' 出售。")
        else:
            logger.warning(f"Agent '{agent.name}' 无法在 '{location}' 购物。")

        if can_buy:
            total_cost = cost_per_item * self.quantity
            if agent._internal_state.money >= total_cost:
                agent._internal_state.money -= total_cost
                # [未来] 更新 Agent 库存
                # agent.add_to_inventory(self.item_name, self.quantity)
                logger.info(f"Agent '{agent.name}' 在 '{location}' 购买了 {self.quantity} 个 '{self.item_name}'，花费 {total_cost}。")
                # 购物可能略微增加压力，也可能带来满足感
                if self.item_name == "food":
                    agent._internal_state.hunger = max(0, agent._internal_state.hunger - 5)  # 买了食物略微不饿？
            else:
                logger.warning(f"Agent '{agent.name}' 想购买 '{self.item_name}' 但钱不够 ({agent._internal_state.money} < {total_cost})。")
                self.duration_minutes = 1
        else:
            self.duration_minutes = 1  # 动作失败


# --- 6. 离开/进入社区 ---
class TakeBusAction(ActionBase):
    destination: str = Field(..., description="目标地点 (例如 'Work', 'Downtown', 'Leave_Community')")
    duration_minutes: int = Field(default=20, ge=10)

    async def execute(self, agent: "Agent", **kwargs):
        if agent._current_location == "Bus_Stop":
            logger.info(f"Agent '{agent.name}' 在公交车站等车去 '{self.destination}'...")
            # 模拟等车和乘车时间
            # 实际效果：改变 Agent 的位置到一个地图外的区域，或者标记为“在途”
            agent._current_location = f"In_Transit_to_{self.destination}"  # 标记为在途
            # [未来] 可能需要 AgentRegistry 处理离开社区的 Agent
            if self.destination == "Leave_Community":
                logger.info(f"Agent '{agent.name}' 乘坐公交车离开了社区。")
                # agent_registry.mark_agent_as_departed(agent.agent_id) # 示例
        else:
            logger.warning(f"Agent '{agent.name}' 必须先移动到 'Bus_Stop' 才能乘坐公交车。")
            self.duration_minutes = 1
            await WaitAction(duration_minutes=1).execute(agent, **kwargs)


class LeaveCommunityAction(ActionBase):
    method: str = Field(default="Drive", description="离开方式 (Drive, Bus)")
    duration_minutes: int = Field(default=5, ge=1)

    async def execute(self, agent: "Agent", **kwargs):
        can_leave = False
        if self.method == "Drive" and agent._current_location == "Highway":
            can_leave = True
            logger.info(f"Agent '{agent.name}' 驾车从公路离开社区...")
        elif self.method == "Bus" and agent._current_location == "Bus_Stop":
            logger.info(f"Agent '{agent.name}' 在公交车站准备乘车离开社区...")
            # 调用 TakeBusAction 更合适
            await TakeBusAction(destination="Leave_Community").execute(agent, **kwargs)
            return  # TakeBusAction 会处理后续逻辑
        else:
            logger.warning(f"Agent '{agent.name}' 无法通过 '{self.method}' 从 '{agent._current_location}' 离开社区。")

        if can_leave:
            agent._current_location = "Left_Community"  # 标记为离开
            # [未来] AgentRegistry 可能需要处理
            # agent_registry.mark_agent_as_departed(agent.agent_id)
        else:
            self.duration_minutes = 1
            await WaitAction(duration_minutes=1).execute(agent, **kwargs)


# --- (可选) 社交聆听 ---
# ListenAction 之前已实现，这里不再重复


# --- 动作字典 (可选，用于 LLM 输出解析) ---
# 这可以帮助你将 LLM 输出的字符串映射到实际的动作类
# 在 Agent 的 think_and_act 中使用
ACTION_MAPPING = {
    "Wait": WaitAction,
    "Speak": SpeakAction,
    "MoveTo": MoveToAction,
    "UseObject": UseObjectAction,
    "Gardening": GardeningAction,
    "Walk": WalkAction,
    "Listen": ListenAction,
    "HangOut": HangOutAction,
    "Eat": EatAction,
    "Sleep": SleepAction,
    "Shower": ShowerAction,
    "Buy": BuyAction,
    "TakeBus": TakeBusAction,
    "LeaveCommunity": LeaveCommunityAction,
}
