from pydantic import BaseModel, Field
from enum import Enum


class MoodState(str, Enum):
    """定义 Agent 可能的情绪状态"""

    HAPPY = "开心"
    NEUTRAL = "中性"
    SAD = "悲伤"
    ANGRY = "愤怒"
    CONTENT = "满足"


class HealthStatus(str, Enum):
    """定义 Agent 的健康状况"""

    HEALTHY = "健康"
    UNWELL = "不适"
    SICK = "生病"


class AgentInternalState(BaseModel):
    """
    定义 Agent 的内部状态 (已扩展)
    """

    # --- 核心心理/生理状态 ---
    mood: MoodState = Field(default=MoodState.NEUTRAL, description="当前情绪状态")
    energy: int = Field(default=100, ge=0, le=100, description="当前精力值 (0-100)")
    hunger: int = Field(default=0, ge=0, le=100, description="当前饥饿度 (0-100, 越高越饿)")
    stress_level: int = Field(default=0, ge=0, le=100, description="当前压力水平 (0-100)")

    health_status: HealthStatus = Field(default=HealthStatus.HEALTHY, description="当前健康状况")
    social_need: int = Field(default=50, ge=0, le=100, description="当前社交需求 (0-100, 越高越想社交)")
    hygiene: int = Field(default=100, ge=0, le=100, description="当前清洁度 (0-100, 越低越脏)")
    laundry_need: int = Field(default=0, ge=0, le=100, description="洗衣需求 (0-100, 越高越需要洗衣)")
    money: int = Field(default=100, ge=0, description="持有的金钱 (ge=0 意味着钱不能是负数)")


class RelationshipData(BaseModel):
    """定义 Agent 之间的关系数据"""

    affinity: int = Field(default=0, ge=-100, le=100, description="好感度")
    familiarity: int = Field(default=0, ge=0, le=100, description="熟悉度")
