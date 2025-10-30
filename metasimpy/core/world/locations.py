from pydantic import BaseModel, Field
from typing import List, Optional, Tuple, Dict
from enum import Enum


class LocationType(str, Enum):
    RESIDENTIAL = "住宅"
    COMMERCIAL = "商业"
    OUTDOOR = "户外"
    TRANSIT = "交通中转"
    INTERNAL_PUBLIC = "公寓内部公共区域"  # 例如大厅、洗衣房
    EXTERNAL_PUBLIC = "公寓外部公共区域"  # 例如入口、步道
    SERVICE = "服务设施"  # 如诊所
    WORKPLACE = "工作场所"  # 明确是工作地点


class Location(BaseModel):
    name: str = Field(..., description="地点的唯一名称/ID")
    description: Optional[str] = Field(default=None, description="地点的描述")
    type: LocationType = Field(default=LocationType.OUTDOOR, description="地点类型")
    objects: List[str] = Field(default_factory=list, description="此地点包含的静态物体名称列表")
    coordinates: Optional[Tuple[float, float]] = Field(default=None, description="(可选) 2D 坐标")
    tags: List[str] = Field(default_factory=list, description="(可选) 用于查询的标签")
    services: Optional[Dict[str, int]] = Field(default=None, description="提供的服务及其基础价格 (例如 {'laundry': 5, 'medical_consultation': 100})")
    available_jobs: Optional[Dict[str, int]] = Field(default=None, description="提供的工作类型及其最大容纳人数 (例如 {'cashier': 1, 'barista': 1})")

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, Location):
            return self.name == other.name
        return False
