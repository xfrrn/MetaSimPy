# metasimpy/core/world/world_interactions.py

from typing import TYPE_CHECKING, Dict, Any, Optional
from loguru import logger
import random

# 假设 Agent, WorldMap, AgentRegistry, GameObject, Location 等类型从相应模块导入
if TYPE_CHECKING:
    from ..agents.agent import Agent
    from ..agents.registry import AgentRegistry
    from .map import WorldMap
    from .objects import GameObject
    from .locations import Location

# --- 常量或从配置加载的规则 (示例) ---
# 这些可以从 JSON/YAML 文件加载，而不是硬编码
INTERACTION_RULES = {
    "WashingMachine": {"cost": 5, "duration_minutes": 30, "required_location_type": "INTERNAL_PUBLIC", "state_changes": {"laundry_need": (-70, -30), "energy": (-5, -5)}, "precondition": lambda agent, obj: agent._internal_state.laundry_need > 20},  # 或者直接指定 "Laundry_Room"
    "CoffeeMachine": {"cost": 5, "duration_minutes": 3, "required_location_type": "COMMERCIAL", "produces_item": "coffee", "state_changes": {"energy": (10, 25), "mood": "CONTENT"}},  # 或者指定 "Cafe"  # 将来用于库存  # 可以直接设置状态
    "CafeCounter": {"job_type": "barista", "hourly_wage": 15, "max_workers": 1, "required_location_type": "COMMERCIAL", "state_changes_per_hour": {"energy": (-8, -5), "stress_level": (1, 3)}},  # 作为工作交互点  # 每小时的状态变化
    "ClinicDesk": {"cost": 100, "duration_minutes": 20, "required_location_type": "SERVICE", "service_name": "medical_consultation", "state_changes": {"health_status": "HEALTHY", "stress_level": (-20, -5)}},  # "Clinic"  # 示例：看病后变健康
    "CheckoutCounter": {"job_type": "cashier", "hourly_wage": 12, "max_workers": 1, "required_location_type": "COMMERCIAL", "state_changes_per_hour": {"energy": (-10, -6), "stress_level": (2, 5)}},  # 作为工作交互点
    "Shelf_Food": {"interaction_verb": "buy_from", "duration_minutes": 5, "required_location_type": "COMMERCIAL", "items_for_sale": {"apple": 2, "bread": 3}},  # Supermarket  # 物品:价格
    "Bench": {"duration_minutes": 15, "required_location_type": "OUTDOOR", "state_changes": {"energy": (1, 5), "stress_level": (-10, -1)}},  # Park
    # ... 其他物体交互规则 ...
}

# --- 交互逻辑函数 ---


async def interact_with_object(agent: "Agent", object_name: str, world_map: "WorldMap", agent_registry: Optional["AgentRegistry"] = None) -> Tuple[bool, int]:
    """
    通用的物体交互处理函数。
    根据物体名称查找规则并执行。
    Args:
        agent: 执行交互的 Agent。
        object_name: 交互的物体名称。
        world_map: WorldMap 实例，用于查询地点信息。
        agent_registry: (可选) AgentRegistry 实例，用于工作分配等。
    Returns:
        Tuple[bool, int]: 一个元组 (success: bool, duration: int)，表示交互是否成功以及占用的时间（分钟）。
                          失败时 duration 通常较短。
    """
    location = world_map.get_location(agent._current_location)
    if not location:
        logger.error(f"Agent '{agent.name}' 尝试在无效位置 '{agent._current_location}' 进行交互。")
        return False, 1  # 失败，占用1分钟

    # 检查物体是否存在于当前地点
    if object_name not in location.objects:
        logger.warning(f"Agent '{agent.name}' 尝试在 '{location.name}' 与不存在的物体 '{object_name}' 交互。")
        return False, 1

    # 从规则中查找交互定义
    rules = INTERACTION_RULES.get(object_name)
    if not rules:
        logger.warning(f"物体 '{object_name}' 没有定义交互规则。")
        return False, 1

    # 0. 检查地点类型是否匹配 (如果规则中有定义)
    if "required_location_type" in rules and location.type.value != rules["required_location_type"] and location.name != rules.get("required_location_name"):  # 也允许直接指定地点名称
        logger.warning(f"Agent '{agent.name}' 尝试在错误的地点类型 '{location.type.value}' 与 '{object_name}' 交互 (需要: {rules['required_location_type']})。")
        return False, 1

    # 1. 检查前置条件 (Preconditions)
    precondition = rules.get("precondition")
    if precondition and not precondition(agent, object_name):  # 假设 precondition 是一个函数
        logger.info(f"Agent '{agent.name}' 未满足与 '{object_name}' 交互的前置条件。")
        return False, 1  # 条件不满足，交互失败

    # 2. 计算并检查成本 (Cost)
    cost = rules.get("cost")
    if cost is not None:
        if agent._internal_state.money < cost:
            logger.warning(f"Agent '{agent.name}' 没钱与 '{object_name}' 交互 (需要 {cost}, 只有 {agent._internal_state.money})。")
            return False, 1  # 钱不够，交互失败
        else:
            agent._internal_state.money -= cost
            logger.info(f"Agent '{agent.name}' 为与 '{object_name}' 交互花费了 {cost}。")

    # 3. 计算持续时间 (Duration)
    duration = rules.get("duration_minutes", 1)  # 默认1分钟

    # 4. 应用状态变化 (State Changes)
    state_changes = rules.get("state_changes")
    if state_changes:
        for state_attr, change_range in state_changes.items():
            current_value = getattr(agent._internal_state, state_attr, None)
            if current_value is not None:
                if isinstance(change_range, tuple) and len(change_range) == 2:  # 如果是范围
                    change = random.randint(change_range[0], change_range[1])
                    new_value = current_value + change
                    # 应用边界检查 (这里简化，假设 state_models 中有处理)
                    setattr(agent._internal_state, state_attr, new_value)
                    logger.trace(f"'{agent.name}' 状态 '{state_attr}' 变化: {current_value} -> {new_value} (改变量: {change})")
                elif isinstance(change_range, str):  # 如果是直接设置状态 (如 MoodState, HealthStatus)
                    try:
                        # 假设 state_models 中定义了对应的 Enum
                        from ..agents.state_models import MoodState, HealthStatus  # 移到函数内部避免循环导入

                        enum_map = {"mood": MoodState, "health_status": HealthStatus}
                        if state_attr in enum_map:
                            setattr(agent._internal_state, state_attr, enum_map[state_attr](change_range))
                            logger.trace(f"'{agent.name}' 状态 '{state_attr}' 设置为: {change_range}")
                        else:
                            logger.warning(f"未知的直接状态设置属性: {state_attr}")
                    except ValueError:
                        logger.warning(f"无效的状态值 '{change_range}' 用于属性 '{state_attr}'")
                else:  # 如果是固定值变化
                    change = change_range
                    new_value = current_value + change
                    setattr(agent._internal_state, state_attr, new_value)
                    logger.trace(f"'{agent.name}' 状态 '{state_attr}' 变化: {current_value} -> {new_value} (改变量: {change})")

    # 5. 处理物品产生/消耗 (Inventory - 未来实现)
    produces = rules.get("produces_item")
    requires = rules.get("requires_item")
    if requires:
        # 检查 agent inventory 是否有 requires
        # 如果有则消耗
        pass
    if produces:
        # agent inventory 增加 produces
        pass

    # 6. 处理服务 (Logging/Events)
    service_name = rules.get("service_name")
    if service_name:
        logger.info(f"Agent '{agent.name}' 在 '{location.name}' 完成了服务 '{service_name}'。")
        # 这里可以触发事件，让其他系统响应

    # 交互成功
    logger.info(f"Agent '{agent.name}' 在 '{location.name}' 成功与 '{object_name}' 交互，持续 {duration} 分钟。")
    return True, duration


async def perform_work(agent: "Agent", job_type: str, duration_minutes: int, world_map: "WorldMap", agent_registry: "AgentRegistry") -> Tuple[bool, int]:
    """
    执行工作动作的逻辑。
    Args:
        agent: 执行工作的 Agent。
        job_type: 工作类型 (e.g., 'cashier', 'barista')。
        duration_minutes: 计划工作时长。
        world_map: WorldMap 实例。
        agent_registry: AgentRegistry 实例。
    Returns:
        Tuple[bool, int]: (success, actual_duration)
    """
    location = world_map.get_location(agent._current_location)
    if not location:
        logger.error(f"Agent '{agent.name}' 尝试在无效位置 '{agent._current_location}' 工作。")
        return False, 1

    # 查找工作对应的物体或规则
    job_rule = None
    work_object_name = None
    for obj_name in location.objects:
        rule = INTERACTION_RULES.get(obj_name)
        if rule and rule.get("job_type") == job_type:
            job_rule = rule
            work_object_name = obj_name
            break

    if not job_rule:
        logger.warning(f"Agent '{agent.name}' 无法在 '{location.name}' 找到 '{job_type}' 类型的工作点。")
        return False, 1

    hourly_wage = job_rule.get("hourly_wage")
    if hourly_wage is None:
        logger.error(f"工作 '{job_type}' 在 '{location.name}' 未定义工资。")
        return False, 1

    # 尝试分配工作岗位 (调用 WorldMap 或 AgentRegistry 的方法)
    # 这里假设 WorldMap 负责管理
    if not world_map.assign_job_to_agent(location.name, job_type, agent.agent_id):
        # 分配失败（可能没空位）
        return False, 1

    # --- 工作成功开始 ---
    logger.info(f"Agent '{agent.name}' 在 '{location.name}' 开始 '{job_type}' 工作，计划 {duration_minutes} 分钟...")

    # 计算实际收入
    earnings = round((hourly_wage / 60) * duration_minutes)
    agent._internal_state.money += earnings

    # 计算状态变化
    state_changes_per_hour = job_rule.get("state_changes_per_hour", {})
    hours_worked = duration_minutes / 60.0
    for state_attr, change_range_per_hour in state_changes_per_hour.items():
        current_value = getattr(agent._internal_state, state_attr, None)
        if current_value is not None and isinstance(change_range_per_hour, tuple):
            change_per_hour = random.randint(change_range_per_hour[0], change_range_per_hour[1])
            total_change = round(change_per_hour * hours_worked)
            new_value = current_value + total_change
            setattr(agent._internal_state, state_attr, new_value)  # 假设 state_models 处理边界
            logger.trace(f"'{agent.name}' 工作状态 '{state_attr}' 变化: {current_value} -> {new_value} (总改变量: {total_change})")

    # 工作结束，释放岗位 (这里是动作完成后的逻辑，实际调用应发生在 Agent 状态更新后)
    # 注意：这个移除逻辑需要在 Agent 完成 WorkAction 后由 Agent 或 Registry 调用，而不是在这里直接调用
    # world_map.remove_agent_from_job(agent.agent_id) # 不应在这里移除

    logger.info(f"Agent '{agent.name}' 完成了 {duration_minutes} 分钟的 '{job_type}' 工作，收入 {earnings}。")
    return True, duration_minutes


async def buy_item(agent: "Agent", item_name: str, quantity: int, world_map: "WorldMap") -> Tuple[bool, int]:
    """
    执行购买物品的逻辑。
    Args:
        agent: 购买者。
        item_name: 物品名称。
        quantity: 购买数量。
        world_map: WorldMap 实例。
    Returns:
        Tuple[bool, int]: (success, duration)
    """
    location = world_map.get_location(agent._current_location)
    if not location:
        logger.error(f"Agent '{agent.name}' 尝试在无效位置 '{agent._current_location}' 购物。")
        return False, 1

    item_price: Optional[int] = None
    seller_object_name: Optional[str] = None

    # 查找提供该物品的物体 (例如货架)
    for obj_name in location.objects:
        rules = INTERACTION_RULES.get(obj_name)
        if rules and rules.get("interaction_verb") == "buy_from":
            items_for_sale = rules.get("items_for_sale", {})
            if item_name in items_for_sale:
                item_price = items_for_sale[item_name]
                seller_object_name = obj_name
                break  # 找到第一个提供该物品的物体

    if item_price is None:
        logger.warning(f"在 '{location.name}' 找不到物品 '{item_name}' 出售。")
        return False, 1

    total_cost = item_price * quantity
    duration = INTERACTION_RULES.get(seller_object_name, {}).get("duration_minutes", 3)  # 购物默认时间

    if agent._internal_state.money < total_cost:
        logger.warning(f"Agent '{agent.name}' 想购买 {quantity} 个 '{item_name}' 但钱不够 ({agent._internal_state.money} < {total_cost})。")
        return False, 1

    # 购买成功
    agent._internal_state.money -= total_cost
    # [未来] 更新 Agent 库存
    # agent.add_to_inventory(item_name, quantity)
    logger.info(f"Agent '{agent.name}' 在 '{location.name}' 从 '{seller_object_name}' 购买了 {quantity} 个 '{item_name}'，花费 {total_cost}。")

    # (可选) 购买特定物品可能影响状态，例如食物影响饥饿
    if item_name in ["apple", "bread", "sandwich"]:  # 示例食物
        hunger_reduction = random.randint(5, 15) * quantity  # 每件减少 5-15 饥饿
        agent._internal_state.hunger = max(0, agent._internal_state.hunger - hunger_reduction)
        logger.trace(f"购买食物使 '{agent.name}' 饥饿度减少了 {hunger_reduction}。")

    return True, duration


# --- 你可以继续添加其他交互函数，例如 ---
# async def use_laundry(agent: "Agent", world_map: "WorldMap") -> Tuple[bool, int]: ...
# async def get_coffee(agent: "Agent", world_map: "WorldMap") -> Tuple[bool, int]: ...
# async def consult_doctor(agent: "Agent", world_map: "WorldMap") -> Tuple[bool, int]: ...
# async def sit_on_bench(agent: "Agent", world_map: "WorldMap") -> Tuple[bool, int]: ...
