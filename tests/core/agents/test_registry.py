import pytest
import datetime
from unittest.mock import MagicMock, AsyncMock
from loguru import logger
from metasimpy.core.agents.registry import AgentRegistry
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
    agent.name = "MockAgent"
    agent.agent_id = "mock_123"
    agent.is_idle = MagicMock(return_value=True)
    agent.think_and_act = AsyncMock()
    return agent


class TestAgentRegistry:
    def test_init_empty_registry(self):
        """测试 AgentRegistry 的初始化"""
        registry = AgentRegistry()

        assert registry._agents == {}
        # 检查初始化日志
        # 注意：由于 caplog fixture，这个日志应该被捕获

    def test_register_agent_success(self, mock_agent, caplog):
        """测试成功注册 Agent"""
        registry = AgentRegistry()

        registry.register_agent(mock_agent)

        assert mock_agent.agent_id in registry._agents
        assert registry._agents[mock_agent.agent_id] is mock_agent
        # 检查日志
        assert any("已在 Registry 注册" in record.message for record in caplog.records)

    def test_register_agent_duplicate_id_raises_error(self, mock_agent):
        """测试注册重复 ID 的 Agent 抛出错误"""
        registry = AgentRegistry()

        # 先注册一次
        registry.register_agent(mock_agent)

        # 再次注册应该失败
        with pytest.raises(ValueError, match="Agent ID mock_123 已存在"):
            registry.register_agent(mock_agent)

    def test_get_agent_by_id_existing(self, mock_agent):
        """测试获取存在的 Agent"""
        registry = AgentRegistry()
        registry.register_agent(mock_agent)

        result = registry.get_agent_by_id("mock_123")

        assert result is mock_agent

    def test_get_agent_by_id_nonexistent(self, caplog):
        """测试获取不存在的 Agent"""
        registry = AgentRegistry()

        result = registry.get_agent_by_id("nonexistent")

        assert result is None
        # 检查警告日志
        assert any("尝试获取不存在的 Agent ID" in record.message for record in caplog.records)

    def test_get_all_agents_empty(self):
        """测试获取所有 Agent（空注册表）"""
        registry = AgentRegistry()

        result = registry.get_all_agents()

        assert result == []

    def test_get_all_agents_with_agents(self, mock_agent):
        """测试获取所有 Agent"""
        registry = AgentRegistry()
        registry.register_agent(mock_agent)

        result = registry.get_all_agents()

        assert len(result) == 1
        assert result[0] is mock_agent

    @pytest.mark.asyncio
    async def test_trigger_agent_think_idle_agent(self, mock_agent):
        """测试触发空闲 Agent 的思考"""
        registry = AgentRegistry()
        registry.register_agent(mock_agent)

        current_time = datetime.datetime.now()

        await registry._trigger_agent_think(mock_agent, current_time)

        # 检查是否调用了 think_and_act
        mock_agent.think_and_act.assert_called_once_with(current_time)

    @pytest.mark.asyncio
    async def test_trigger_agent_think_non_idle_agent(self, mock_agent):
        """测试触发非空闲 Agent 的思考（仍然会调用，因为这是内部方法）"""
        registry = AgentRegistry()
        registry.register_agent(mock_agent)

        # 注意：_trigger_agent_think 不检查空闲状态，它总是调用 think_and_act
        # 空闲检查在 on_minute_update 中进行
        current_time = datetime.datetime.now()

        await registry._trigger_agent_think(mock_agent, current_time)

        # 检查是否调用了 think_and_act（因为这是内部方法，不检查空闲）
        mock_agent.think_and_act.assert_called_once_with(current_time)

    def test_multiple_agents_registration(self):
        """测试注册多个 Agent"""
        registry = AgentRegistry()

        # 创建多个 mock agents
        agent1 = MagicMock()
        agent1.agent_id = "agent_1"
        agent1.name = "Agent One"

        agent2 = MagicMock()
        agent2.agent_id = "agent_2"
        agent2.name = "Agent Two"

        registry.register_agent(agent1)
        registry.register_agent(agent2)

        assert len(registry._agents) == 2
        assert registry.get_agent_by_id("agent_1") is agent1
        assert registry.get_agent_by_id("agent_2") is agent2

        all_agents = registry.get_all_agents()
        assert len(all_agents) == 2
        assert agent1 in all_agents
        assert agent2 in all_agents
