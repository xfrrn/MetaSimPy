from typing import TYPE_CHECKING, Dict, Optional, Tuple
from loguru import logger
import random

if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..agents.registry import AgentRegistry
    from .map import WorldMap
    from .objects import GameObject


async def interact_with_object(
    agent: "Agent",
    object_name: str,
    world_map: "WorldMap",
    object_prototypes: Dict[str, "GameObject"],
) -> Tuple[bool, int]:
    """
    通用的物体交互处理函数。
    根据物体名称从 object_prototypes 查找规则并执行。
    Args:
        agent: 执行交互的 Agent。
        object_name: 交互的物体名称。
        world_map: WorldMap 实例，用于查询地点信息。
        object_prototypes: 包含所有 GameObject 原型定义的字典 (从 objects.json 加载)。
    Returns:
        Tuple[bool, int]: (success, duration)
    """
    location = world_map.get_location(agent._current_location)
    if not location:
        logger.error(f"Agent '{agent.name}' 尝试在无效位置 '{agent._current_location}' 进行交互。")
        return False, 1

    # 检查物体是否存在于当前地点
    if object_name not in location.objects:
        logger.warning(f"Agent '{agent.name}' 尝试在 '{location.name}' 与不存在的物体 '{object_name}' 交互。")
        return False, 1

    # 从原型中查找交互定义
    rules = object_prototypes.get(object_name)
    if not rules:
        logger.warning(f"物体 '{object_name}' 没有在 object_prototypes 中定义。")
        return False, 1

    # 1. 检查前置条件 (Preconditions)
    if object_name == "WashingMachine":
        if not agent._internal_state.laundry_need > 20:
            logger.info(f"Agent '{agent.name}' 未满足与 '{object_name}' 交互的前置条件 (laundry_need <= 20)。")
            return False, 1

    # 2. 计算并检查成本 (Cost)
    cost = rules.cost
    if cost is not None:
        if agent._internal_state.money < cost:
            logger.warning(f"Agent '{agent.name}' 没钱与 '{object_name}' 交互 (需要 {cost}, 只有 {agent._internal_state.money})。")
            return False, 1
        else:
            agent._internal_state.money -= cost
            logger.info(f"Agent '{agent.name}' 为与 '{object_name}' 交互花费了 {cost}。")

    # 3. 计算持续时间 (Duration)
    duration = rules.base_duration_minutes

    # 4. 应用状态变化 (State Changes)
    state_changes = rules.affects_state
    if state_changes:
        for state_attr, change_range in state_changes.items():
            current_value = getattr(agent._internal_state, state_attr, None)
            if current_value is not None:
                # 随机列表范围，直接值，或字符串枚举
                if isinstance(change_range, list) and len(change_range) == 2:
                    change_tuple = tuple(change_range)
                    change = random.randint(change_tuple[0], change_tuple[1])
                    new_value = current_value + change
                    setattr(agent._internal_state, state_attr, new_value)
                    logger.trace(f"'{agent.name}' 状态 '{state_attr}' 变化: {current_value} -> {new_value} (改变量: {change})")
                elif isinstance(change_range, str):
                    try:
                        from ..agents.state_models import MoodState, HealthStatus

                        enum_map = {"mood": MoodState, "health_status": HealthStatus}
                        if state_attr in enum_map:
                            setattr(
                                agent._internal_state,
                                state_attr,
                                enum_map[state_attr](change_range),
                            )
                            logger.trace(f"'{agent.name}' 状态 '{state_attr}' 设置为: {change_range}")
                        else:
                            logger.warning(f"未知的直接状态设置属性: {state_attr}")
                    except ValueError:
                        logger.warning(f"无效的状态值 '{change_range}' 用于属性 '{state_attr}'")
                else:
                    change = change_range
                    new_value = current_value + change
                    setattr(agent._internal_state, state_attr, new_value)
                    logger.trace(f"'{agent.name}' 状态 '{state_attr}' 变化: {current_value} -> {new_value} (改变量: {change})")

    # 5. 处理物品产生/消耗 (Inventory)
    produces = rules.produces_item
    requires = rules.requires_item
    if requires:
        # [未来] 检查 agent inventory 是否有 requires
        pass
    if produces:
        # [未来] agent inventory 增加 produces
        pass

    # 6. 处理服务
    if rules.interaction_verb == "consult":
        service_name = "medical_consultation"
        logger.info(f"Agent '{agent.name}' 在 '{location.name}' 完成了服务 '{service_name}'。")

    # 交互成功
    logger.info(f"Agent '{agent.name}' 在 '{location.name}' 成功与 '{object_name}' 交互，持续 {duration} 分钟。")
    return True, duration


async def perform_work(
    agent: "Agent",
    job_type: str,
    duration_minutes: int,
    world_map: "WorldMap",
    object_prototypes: Dict[str, "GameObject"],
) -> Tuple[bool, int]:
    """
    执行工作动作的逻辑。
    Args:
        agent: 执行工作的 Agent。
        job_type: 工作类型 (e.g., 'cashier', 'barista')。
        duration_minutes: 计划工作时长。
        world_map: WorldMap 实例。
        object_prototypes: 包含所有 GameObject 原型定义的字典。
        agent_registry: AgentRegistry 实例。
    Returns:
        Tuple[bool, int]: (success, actual_duration)
    """
    location = world_map.get_location(agent._current_location)
    if not location:
        logger.error(f"Agent '{agent.name}' 尝试在无效位置 '{agent._current_location}' 工作。")
        return False, 1

    job_rule: Optional["GameObject"] = None
    for obj_name in location.objects:
        rule = object_prototypes.get(obj_name)
        if rule and rule.job_type == job_type:
            job_rule = rule
            break

    if not job_rule:
        logger.warning(f"Agent '{agent.name}' 无法在 '{location.name}' 找到 '{job_type}' 类型的工作点。")
        return False, 1

    hourly_wage = job_rule.hourly_wage
    if hourly_wage is None:
        logger.error(f"工作 '{job_type}' 在 '{location.name}' 未定义工资。")
        return False, 1
    logger.info(f"Agent '{agent.name}' 在 '{location.name}' 开始 '{job_type}' 工作，计划 {duration_minutes} 分钟...")

    # 计算实际收入
    earnings = round((hourly_wage / 60) * duration_minutes)
    agent._internal_state.money += earnings

    # 状态改变
    state_changes_per_hour = job_rule.state_changes_per_hour or {}
    hours_worked = duration_minutes / 60.0

    for state_attr, change_range_per_hour in state_changes_per_hour.items():
        current_value = getattr(agent._internal_state, state_attr, None)
        if current_value is not None and isinstance(change_range_per_hour, list) and len(change_range_per_hour) == 2:
            change_per_hour = random.randint(change_range_per_hour[0], change_range_per_hour[1])
            total_change = round(change_per_hour * hours_worked)
            new_value = current_value + total_change
            setattr(agent._internal_state, state_attr, new_value)
            logger.trace(f"'{agent.name}' 工作状态 '{state_attr}' 变化: {current_value} -> {new_value} (总改变量: {total_change})")

    logger.info(f"Agent '{agent.name}' 完成了 {duration_minutes} 分钟的 '{job_type}' 工作，收入 {earnings}。")
    return True, duration_minutes


async def buy_item(
    agent: "Agent",
    item_name: str,
    quantity: int,
    world_map: "WorldMap",
    object_prototypes: Dict[str, "GameObject"],
) -> Tuple[bool, int]:
    """
    执行购买物品的逻辑。
    Args:
        agent: 购买者。
        item_name: 物品名称。
        quantity: 购买数量。
        world_map: WorldMap 实例。
        object_prototypes: 包含所有 GameObject 原型定义的字典。
    Returns:
        Tuple[bool, int]: (success, duration)
    """
    location = world_map.get_location(agent._current_location)
    if not location:
        logger.error(f"Agent '{agent.name}' 尝试在无效位置 '{agent._current_location}' 购物。")
        return False, 1

    item_price: Optional[int] = None
    seller_object_name: Optional[str] = None
    seller_rule: Optional["GameObject"] = None

    # 物品检查
    for obj_name in location.objects:
        rules = object_prototypes.get(obj_name)
        if rules and rules.interaction_verb == "buy_from":
            items_for_sale = rules.items_for_sale
            if items_for_sale and item_name in items_for_sale:
                item_price = items_for_sale[item_name]
                seller_object_name = obj_name
                seller_rule = rules
                break

            properties = rules.properties
            if properties and "items" in properties and item_name in properties["items"]:
                item_price = properties["items"][item_name]
                seller_object_name = obj_name
                seller_rule = rules
                break

    if item_price is None or seller_rule is None:
        logger.warning(f"在 '{location.name}' 找不到物品 '{item_name}' 出售。")
        return False, 1

    total_cost = item_price * quantity
    duration = seller_rule.base_duration_minutes

    if agent._internal_state.money < total_cost:
        logger.warning(f"Agent '{agent.name}' 想购买 {quantity} 个 '{item_name}' 但钱不够 ({agent._internal_state.money} < {total_cost})。")
        return False, 1
    agent._internal_state.money -= total_cost
    logger.info(f"Agent '{agent.name}' 在 '{location.name}' 从 '{seller_object_name}' 购买了 {quantity} 个 '{item_name}'，花费 {total_cost}。")

    return True, duration
