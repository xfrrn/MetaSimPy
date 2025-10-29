# metasimpy/core/world/objects.py

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Tuple


class GameObject(BaseModel):
    """定义地图上静态物体的基本数据结构，包含交互和工作属性"""

    name: str = Field(..., description="物体的唯一名称")
    description: Optional[str] = Field(default=None, description="物体的描述")
    interaction_verb: Optional[str] = Field(default=None, description="与物体交互的主要动词 (如 'use', 'sit_on', 'work_at', 'buy_from')")

    # --- 交互属性 ---
    cost: Optional[int] = Field(default=None, description="与此物体交互的基础成本 (如使用洗衣机)")
    produces_item: Optional[str] = Field(default=None, description="交互后产生的物品 (如咖啡机产生'coffee')")
    requires_item: Optional[str] = Field(default=None, description="交互前需要的物品")
    affects_state: Optional[Dict[str, Tuple[int, int]]] = Field(default=None, description="交互对 Agent 状态的影响范围 (例如 {'energy': (10, 25)})")  # (min_change, max_change)

    # --- 工作属性 ---
    job_type: Optional[str] = Field(default=None, description="在此物体工作提供的岗位类型 (如 'cashier', 'barista')")
    hourly_wage: Optional[int] = Field(default=None, description="在此工作的小时工资")
    max_workers: int = Field(default=1, description="此工作岗位同时容纳的最大人数")  # 可以放在 Location，也可以放在具体物体上

    properties: Dict[str, Any] = Field(default_factory=dict, description="物体的其他自定义属性")


# --- 示例数据 (实际应从文件加载) ---
example_objects_data = [
    {"name": "WashingMachine", "description": "公共洗衣机", "interaction_verb": "use", "cost": 5, "affects_state": {"laundry_need": (-70, -30), "energy": (-5, -5)}},
    {"name": "CoffeeMachine", "description": "咖啡机", "interaction_verb": "use", "cost": 5, "produces_item": "coffee", "affects_state": {"energy": (10, 25)}},  # 咖啡馆的服务也可以通过操作物体实现
    {"name": "CafeCounter", "description": "咖啡馆柜台", "interaction_verb": "work_at", "job_type": "barista", "hourly_wage": 15, "max_workers": 1},  # 工作点
    {"name": "ClinicDesk", "description": "诊所前台", "interaction_verb": "consult", "cost": 100},  # 交互点，触发诊疗服务
    {"name": "CheckoutCounter", "description": "超市收银台", "interaction_verb": "work_at", "job_type": "cashier", "hourly_wage": 12, "max_workers": 1},  # 工作点
    {"name": "Shelf_Food", "description": "超市食品货架", "interaction_verb": "buy_from", "properties": {"items": {"apple": 2, "bread": 3}}},  # 购物点，具体价格可放这
    {"name": "Shelf_Drink", "description": "超市饮料货架", "interaction_verb": "buy_from", "properties": {"items": {"water": 1, "soda": 2}}},
    {"name": "Bench", "description": "公园长椅", "interaction_verb": "sit_on", "affects_state": {"energy": (1, 5), "stress_level": (-10, -1)}},
    {"name": "Bed", "description": "床", "interaction_verb": "sleep_in"},  # 具体效果在 SleepAction 中
    {"name": "Fridge", "description": "冰箱", "interaction_verb": "take_food_from"},  # 可能与 EatAction 交互
    {"name": "Shower", "description": "淋浴", "interaction_verb": "use", "affects_state": {"hygiene": (30, 70), "stress_level": (-5, -1)}},
]
