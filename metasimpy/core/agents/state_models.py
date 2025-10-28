from pydantic import BaseModel, Field
from enum import Enum


class MoodState(str, Enum):
    """定义 Agent 可能的情绪状态"""

    HAPPY = "开心"
    NEUTRAL = "中性"
    SAD = "悲伤"
    ANGRY = "愤怒"
    CONTENT = "满足"


class AgentInternalState(BaseModel):
    """定义 Agent 的内部状态"""

    mood: MoodState = Field(default=MoodState.NEUTRAL, description="当前情绪状态")
    energy: int = Field(default=100, ge=0, le=100, description="当前精力值 (0-100)")
    hunger: int = Field(
        default=0, ge=0, le=100, description="当前饥饿度 (0-100, 越高越饿)"
    )
    social_need: int = Field(
        default=50, ge=0, le=100, description="当前社交需求 (0-100, 越高越想社交)"
    )
    stress_level: int = Field(
        default=0, ge=0, le=100, description="当前压力水平 (0-100)"
    )


class RelationshipData(BaseModel):
    """定义 Agent 之间的关系数据"""

    affinity: int = Field(default=0, ge=-100, le=100, description="好感度")
    familiarity: int = Field(default=0, ge=0, le=100, description="熟悉度")
