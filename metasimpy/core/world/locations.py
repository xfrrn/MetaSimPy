# metasimpy/core/world/locations.py

from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict
from enum import Enum


class LocationType(str, Enum):
    RESIDENTIAL = "住宅"
    COMMERCIAL = "商业"
    OUTDOOR = "户外"
    TRANSIT = "交通中转"
    INTERNAL_PUBLIC = "公寓内部公共区域"
    EXTERNAL_PUBLIC = "公寓外部公共区域"
    SERVICE = "服务设施"  # 如诊所
    WORKPLACE = "工作场所"  # 明确是工作地点


class Location(BaseModel):
    """定义一个地点的数据结构，包含工作和消费信息"""

    name: str = Field(..., description="地点的唯一名称/ID")
    description: Optional[str] = Field(default=None, description="地点的描述")
    type: LocationType = Field(default=LocationType.OUTDOOR, description="地点类型")
    objects: List[str] = Field(default_factory=list, description="此地点包含的静态物体名称列表")
    coordinates: Optional[Tuple[float, float]] = Field(default=None, description="(可选) 2D 坐标")
    tags: List[str] = Field(default_factory=list, description="(可选) 用于查询的标签")

    # 新增：地点提供的服务及其基础成本 (具体物品价格在 Object 或 BuyAction 中处理)
    services: Optional[Dict[str, int]] = Field(default=None, description="提供的服务及其基础价格 (例如 {'laundry': 5, 'medical_consultation': 100})")

    # 新增：地点提供的工作岗位及其数量上限
    available_jobs: Optional[Dict[str, int]] = Field(default=None, description="提供的工作类型及其最大容纳人数 (例如 {'cashier': 1, 'barista': 1})")

    # (可选) 当前占用工作岗位的信息，可能需要更动态的管理，例如放在 AgentRegistry 或 Map 状态中
    # occupied_jobs: Dict[str, Optional[str]] = Field(default_factory=dict, description="当前占用工作岗位及其 Agent ID")

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Location):
            return self.name == other.name
        return False


# --- 示例数据 (实际应从文件加载) ---
example_locations_data = [
    {"name": "Laundry_Room", "description": "公寓洗衣房", "type": LocationType.INTERNAL_PUBLIC, "objects": ["WashingMachine"], "services": {"laundry": 5}},
    {"name": "Cafe", "description": "社区咖啡馆", "type": LocationType.COMMERCIAL, "objects": ["CoffeeMachine", "CafeCounter", "Table"], "services": {"coffee": 5, "sandwich": 8}, "available_jobs": {"barista": 1}},  # 假设基础消费是买咖啡/三明治的动作处理
    {"name": "Clinic", "description": "社区小诊所", "type": LocationType.SERVICE, "objects": ["ClinicDesk"], "services": {"medical_consultation": 100}},
    {"name": "Supermarket", "description": "社区超市", "type": LocationType.COMMERCIAL, "objects": ["CheckoutCounter", "Shelf_Food", "Shelf_Drink"], "available_jobs": {"cashier": 1}},  # 超市消费在 BuyAction 中处理
    {"name": "Park", "description": "一个宁静的社区公园", "type": LocationType.OUTDOOR, "objects": ["Bench"], "tags": ["relax", "social"]},
    {"name": "Apartment_1A", "description": "1A 公寓", "type": LocationType.RESIDENTIAL, "objects": ["Bed", "Fridge", "Shower"]},
    # ... 其他地点 ...
]
