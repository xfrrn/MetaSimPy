import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from loguru import logger
from metasimpy.core.agents.interactions import ActionBase, WaitAction, SpeakAction
import logging


# --- [ 新增 Fixture 开始 ] ---
@pytest.fixture(autouse=True)
def caplog_for_loguru(caplog):
    """
    这个 fixture 会自动为每个测试配置 loguru，
    使其日志能够被 pytest 的 caplog 捕获。
    """
    caplog.set_level(logging.DEBUG)

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

    # 添加传播 handler
    logger.add(loguru_to_logging, level="DEBUG")

    yield  # 测试在这里运行

    # 测试结束后，可以考虑移除 handler 或恢复默认配置，如果需要的话
    # logger.remove() # 清理，虽然 pytest 通常会隔离环境


@pytest.fixture
def mock_agent():
    """提供一个模拟的 Agent 实例"""
    agent = MagicMock()
    agent.name = "TestAgent"
    agent.agent_id = "test_agent_1"
    agent.update_relationship = MagicMock()
    return agent


@pytest.fixture
def mock_agent_registry():
    """提供一个模拟的 AgentRegistry 实例"""
    registry = MagicMock()
    return registry


class TestActionBase:
    def test_init_with_duration(self):
        """测试 ActionBase 的初始化"""
        action = ActionBase(duration_minutes=5)
        assert action.duration_minutes == 5

    def test_init_without_duration_raises_error(self):
        """测试 ActionBase 没有 duration_minutes 时抛出错误"""
        with pytest.raises(TypeError):
            ActionBase()

    @pytest.mark.asyncio
    async def test_execute_base_action(self, mock_agent, caplog):
        """测试基类 execute 方法"""
        action = ActionBase(duration_minutes=1)

        await action.execute(mock_agent)

        # 检查日志输出
        assert any("正在执行基类动作" in record.message for record in caplog.records)


class TestWaitAction:
    def test_init_default_duration(self):
        """测试 WaitAction 的默认初始化"""
        action = WaitAction()
        assert action.duration_minutes == 1

    def test_init_custom_duration(self):
        """测试 WaitAction 的自定义初始化"""
        action = WaitAction(duration_minutes=10)
        assert action.duration_minutes == 10

    def test_init_invalid_duration(self):
        """测试 WaitAction 的无效 duration"""
        with pytest.raises(ValueError):
            WaitAction(duration_minutes=0)  # ge=1 应该失败

    @pytest.mark.asyncio
    async def test_execute_wait_action(self, mock_agent, caplog):
        """测试 WaitAction 的 execute 方法"""
        action = WaitAction(duration_minutes=5)

        await action.execute(mock_agent)

        # 检查日志输出
        assert any("开始等待 5 分钟" in record.message for record in caplog.records)
        assert any("TestAgent" in record.message for record in caplog.records)


class TestSpeakAction:
    def test_init_required_fields(self):
        """测试 SpeakAction 的必需字段初始化"""
        action = SpeakAction(message="Hello world")
        assert action.message == "Hello world"
        assert action.duration_minutes == 2  # 默认值
        assert action.target_agent_id is None

    def test_init_all_fields(self):
        """测试 SpeakAction 的完整初始化"""
        action = SpeakAction(message="Hi there", duration_minutes=3, target_agent_id="target_1")
        assert action.message == "Hi there"
        assert action.duration_minutes == 3
        assert action.target_agent_id == "target_1"

    def test_init_missing_message_raises_error(self):
        """测试 SpeakAction 缺少 message 时抛出错误"""
        with pytest.raises(ValueError):
            SpeakAction()

    @pytest.mark.asyncio
    async def test_execute_speak_to_self(self, mock_agent, caplog):
        """测试 SpeakAction 自言自语"""
        action = SpeakAction(message="I'm talking to myself")

        await action.execute(mock_agent)

        # 检查日志输出
        assert any("自言自语" in record.message for record in caplog.records)
        assert any("I'm talking to myself" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_execute_speak_to_target_success(self, mock_agent, mock_agent_registry, caplog):
        """测试 SpeakAction 成功对目标说话"""
        action = SpeakAction(message="Hello friend", target_agent_id="target_1")

        # 设置 mock registry 返回目标 agent
        target_agent = MagicMock()
        target_agent.name = "TargetAgent"
        mock_agent_registry.get_agent_by_id.return_value = target_agent

        await action.execute(mock_agent, agent_registry=mock_agent_registry)

        # 检查日志输出
        assert any("对 'TargetAgent' 说" in record.message for record in caplog.records)
        assert any("Hello friend" in record.message for record in caplog.records)

        # 检查关系更新
        mock_agent.update_relationship.assert_called_once_with("target_1", changes={"familiarity": 1})
        target_agent.update_relationship.assert_called_once_with(mock_agent.agent_id, changes={"familiarity": 1})

    @pytest.mark.asyncio
    async def test_execute_speak_to_target_not_found(self, mock_agent, mock_agent_registry, caplog):
        """测试 SpeakAction 对不存在的目标说话"""
        action = SpeakAction(message="Hello?", target_agent_id="nonexistent")

        # 设置 mock registry 返回 None
        mock_agent_registry.get_agent_by_id.return_value = None

        await action.execute(mock_agent, agent_registry=mock_agent_registry)

        # 检查警告日志
        assert any("不存在的 Agent" in record.message for record in caplog.records)
        assert any("nonexistent" in record.message for record in caplog.records)

        # 确保没有调用关系更新
        mock_agent.update_relationship.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_speak_without_registry(self, mock_agent, caplog):
        """测试 SpeakAction 在没有 registry 的情况下说话"""
        action = SpeakAction(message="Hello world", target_agent_id="target_1")

        await action.execute(mock_agent)

        # 应该回退到自言自语
        assert any("自言自语" in record.message for record in caplog.records)
        assert any("Hello world" in record.message for record in caplog.records)
