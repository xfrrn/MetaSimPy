import pytest
import datetime
from unittest.mock import MagicMock
from loguru import logger
from metasimpy.core.agents.agent import Agent
from metasimpy.core.agents.state_models import MoodState
import logging


# --- [ 新增 Fixture 开始 ] ---
@pytest.fixture(autouse=True)
def caplog_for_loguru(caplog):
    """
    这个 fixture 会自动为每个测试配置 loguru，
    使其日志能够被 pytest 的 caplog 捕获。
    """
    # 设置为最低级别以捕获所有日志
    caplog.set_level(1)

    # Loguru 配置: 添加一个 handler，将日志传播给内置 logging
    def loguru_to_logging(msg):
        level = msg.record["level"].no
        message = msg.record["message"]
        logging.log(level, message)

    # 添加 handler 前先移除可能存在的旧 handler，避免重复
    try:
        logger.remove(handler_id=None)  # 移除所有 loguru 默认 handler
    except ValueError:
        pass  # 如果没有 handler 可移除，会抛 ValueError

    # 添加传播 handler，包含 TRACE 级别
    logger.add(loguru_to_logging, level="TRACE")

    yield  # 测试在这里运行

    # 测试结束后，可以考虑移除 handler 或恢复默认配置，如果需要的话
    # logger.remove() # 清理，虽然 pytest 通常会隔离环境


class TestAgent:
    def test_init_basic_attributes(self):
        """测试 Agent 的基本属性初始化"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        assert agent.name == "Test Agent"
        assert agent.persona == "A test persona"
        assert agent.agent_id == "test_123"
        assert agent._current_location == "home"
        assert agent._current_action is None

    def test_init_internal_state(self):
        """测试 Agent 的内部状态初始化"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        # 检查内部状态的默认值
        assert agent._internal_state.mood == MoodState.NEUTRAL
        assert agent._internal_state.energy == 100
        assert agent._internal_state.hunger == 0
        assert agent._internal_state.social_need == 50
        assert agent._internal_state.stress_level == 0

    def test_init_relationships_empty(self):
        """测试 Agent 的关系字典初始化为空"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        assert agent._relationships == {}

    def test_init_custom_location(self):
        """测试 Agent 的自定义位置初始化"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123", start_location="office")

        assert agent._current_location == "office"

    def test_update_mood_valid(self, caplog):
        """测试更新有效的情绪状态"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        agent.update_mood("开心")

        assert agent._internal_state.mood == MoodState.HAPPY
        # 检查日志
        assert any("情绪更新" in record.message for record in caplog.records)

    def test_update_mood_invalid(self, caplog):
        """测试更新无效的情绪状态"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        original_mood = agent._internal_state.mood
        agent.update_mood("invalid_mood")

        # 情绪应该保持不变
        assert agent._internal_state.mood == original_mood
        # 检查警告日志
        assert any("无效的情绪状态" in record.message for record in caplog.records)

    def test_update_relationship_new_target(self, caplog):
        """测试与新目标建立关系"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        agent.update_relationship("target_456", {"familiarity": 5})

        assert "target_456" in agent._relationships
        assert agent._relationships["target_456"].familiarity == 5
        # 检查日志
        assert any("首次与 Agent" in record.message for record in caplog.records)

    def test_update_relationship_existing_target(self, caplog):
        """测试更新现有关系"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        # 先建立关系
        agent.update_relationship("target_456", {"familiarity": 5})
        # 再更新
        agent.update_relationship("target_456", {"affinity": 10, "familiarity": 3})

        rel = agent._relationships["target_456"]
        assert rel.affinity == 10
        assert rel.familiarity == 8  # 5 + 3
        # 检查日志
        assert any("关系更新" in record.message for record in caplog.records)

    def test_update_relationship_boundary_affinity(self):
        """测试关系更新的边界检查（affinity）"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        # 测试上限
        agent.update_relationship("target_456", {"affinity": 200})  # 超过 100
        assert agent._relationships["target_456"].affinity == 100

        # 测试下限
        agent.update_relationship("target_456", {"affinity": -200})  # 低于 -100
        assert agent._relationships["target_456"].affinity == -100

    def test_update_relationship_boundary_familiarity(self):
        """测试关系更新的边界检查（familiarity）"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        # 测试下限
        agent.update_relationship("target_456", {"familiarity": -50})  # 低于 0
        assert agent._relationships["target_456"].familiarity == 0

    def test_update_relationship_self_skip(self, caplog):
        """测试更新与自己的关系时跳过"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        agent.update_relationship("test_123", {"familiarity": 5})

        # 关系字典应该仍然为空
        assert agent._relationships == {}
        # 检查日志
        assert any("尝试更新与自己的关系" in record.message for record in caplog.records)

    def test_update_relationship_invalid_attribute(self, caplog):
        """测试更新不存在的关系属性"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        agent.update_relationship("target_456", {"invalid_attr": 5})

        # 检查警告日志
        assert any("不存在的关系属性" in record.message for record in caplog.records)

    def test_is_idle_always_true(self):
        """测试 is_idle 方法（当前实现总是返回 True）"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        current_time = datetime.datetime.now()
        assert agent.is_idle(current_time) is True

    @pytest.mark.asyncio
    async def test_think_and_act_logs(self, caplog):
        """测试 think_and_act 方法的日志输出"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123")

        current_time = datetime.datetime(2023, 1, 1, 12, 0, 0)
        await agent.think_and_act(current_time)

        # 检查日志
        assert any("开始思考" in record.message for record in caplog.records)

    def test_build_prompt_content(self):
        """测试 _build_prompt 方法的内容"""
        agent = Agent(name="Test Agent", persona="A test persona", agent_id="test_123", start_location="park")

        current_time = datetime.datetime(2023, 1, 1, 14, 30, 0)
        prompt = agent._build_prompt(current_time)

        # 检查提示内容包含必要信息
        assert "Test Agent" in prompt
        assert "A test persona" in prompt
        assert "2023-01-01 14:30" in prompt
        assert "中性" in prompt  # 默认情绪
        assert "park" in prompt
        assert "JSON" in prompt
