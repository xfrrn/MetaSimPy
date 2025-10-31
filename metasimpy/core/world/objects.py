# metasimpy/core/world/objects.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class GameObject(BaseModel):
    name: str = Field(..., description="物体的唯一名称")
    description: Optional[str] = Field(default=None, description="物体的描述")
    interaction_verb: Optional[str] = Field(default=None, description="与物体交互的主要动词 (如 'use', 'sit_on', 'work_at', 'buy_from')")

    cost: Optional[int] = Field(default=None, description="与此物体交互的基础成本")
    produces_item: Optional[str] = Field(default=None, description="交互后产生的物品名称")
    requires_item: Optional[str] = Field(default=None, description="交互前需要的物品名称")
    affects_state: Optional[Dict[str, Any]] = Field(default=None, description="交互对 Agent 状态的影响")
    base_duration_minutes: int = Field(default=1, description="执行与此物体交互的基础持续时间（分钟）")

    # 工作属性
    job_type: Optional[str] = Field(default=None, description="提供的岗位类型")
    hourly_wage: Optional[int] = Field(default=None, description="小时工资")

    # 售卖属性
    items_for_sale: Optional[Dict[str, int]] = Field(default=None, description="可售卖物品及其价格 (e.g., {'apple': 2, 'water': 1})")
    properties: Dict[str, Any] = Field(default_factory=dict, description="物体的其他自定义属性 (例如初始状态 'status': 'idle')")

    state_changes_per_hour: Optional[Dict[str, List[int]]] = Field(default=None, description="工作时每小时的状态变化 (e.g., {'energy': [-10, -5]})")
