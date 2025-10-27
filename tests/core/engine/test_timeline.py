# tests/core/engine/test_timeline.py

import pytest
import asyncio
import datetime
from unittest.mock import MagicMock
from loguru import logger
from metasimpy.core.engine.timeline import Timeline
import logging  # 导入内置 logging


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


@pytest.fixture
def start_time():
    """一个固定的、可重用的起始时间"""
    return datetime.datetime(2023, 1, 1, 12, 0, 0)


@pytest.fixture
def timeline(start_time):
    """
    一个可重用的、干净的 Timeline 实例。
    每个使用它的测试都会得到一个 *新的* 实例。
    默认 time_scale=4.0 (来自 __init__ 的默认值)
    """
    return Timeline(start_time)


# --- Test Class (测试类) ---


class TestTimeline:
    # --- 测试初始化 ---
    def test_init(self):
        """测试自定义初始化"""
        start_time = datetime.datetime(2023, 1, 1, 0, 0, 0)
        timeline_custom = Timeline(start_time, time_scale=2.0)
        assert timeline_custom.get_current_time() == start_time
        assert timeline_custom._is_paused is False
        assert timeline_custom._time_scale == 2.0
        assert timeline_custom._sleep_duration == 0.5  # 1.0 / 2.0

    # --- 测试事件系统 ---
    def test_subscribe_valid_event(self, timeline):
        """测试有效订阅"""
        callback = MagicMock(name="mock_callback")
        timeline.subscribe("on_minute_passed", callback)
        assert callback in timeline._listeners["on_minute_passed"]

    def test_subscribe_invalid_event(self, timeline, caplog):
        """测试无效订阅 (日志)"""
        callback = MagicMock(name="mock_callback_invalid")
        timeline.subscribe("invalid_event", callback)

        assert any(
            "尝试订阅一个不存在的事件" in record.message for record in caplog.records
        )
        # (可选) 检查日志级别是否为 WARNING
        assert any(
            record.levelno == logger.level("WARNING").no for record in caplog.records
        )

        assert callback not in timeline._listeners.get(
            "invalid_event", []
        )  # 确保它没被加到不存在的列表
        assert (
            callback not in timeline._listeners["on_minute_passed"]
        )  # 也确保没加错地方

    def test_publish_event(self, timeline):
        """测试发布者是否正确调用回调"""
        callback = MagicMock(name="mock_callback_publish")
        timeline.subscribe("on_minute_passed", callback)
        timeline._publish("on_minute_passed", "arg1", kwarg1="value")
        # 验证回调被精确地调用
        callback.assert_called_once_with("arg1", kwarg1="value")

    def test_publish_event_with_exception(self, timeline, caplog):
        """测试当回调函数崩溃时，Timeline 是否能捕获异常并继续运行"""
        callback_error = MagicMock(
            name="mock_callback_error", side_effect=Exception("Test error")
        )
        callback_ok = MagicMock(name="mock_callback_ok")

        timeline.subscribe("on_minute_passed", callback_error)
        timeline.subscribe("on_minute_passed", callback_ok)  # 订阅第二个回调

        timeline._publish("on_minute_passed")

        assert any("mock_callback_error" in record.message for record in caplog.records)
        assert any(
            record.levelno == logger.level("ERROR").no for record in caplog.records
        )

        callback_ok.assert_called_once()

    # --- 测试控制功能 ---
    def test_pause_resume(self, timeline):
        """测试暂停和恢复功能"""
        timeline.pause()
        assert timeline._is_paused is True
        timeline.resume()
        assert timeline._is_paused is False

    def test_set_time_scale_valid(self, timeline):
        """测试设置有效的时间流速"""
        timeline.set_time_scale(3.0)
        assert timeline._time_scale == 3.0
        assert timeline._sleep_duration == pytest.approx(
            1.0 / 3.0
        )  # 使用 approx 比较浮点数

    def test_set_time_scale_invalid(self, timeline, caplog):
        """测试设置无效的时间流速 (日志)"""
        # 1. 获取 __init__ 设置的初始流速
        initial_scale = timeline._time_scale
        # 假设 timeline fixture 使用默认值 4.0
        assert initial_scale == 4.0

        # 2. 尝试设置无效值
        timeline.set_time_scale(0)

        # 3. [已修复] 验证日志 (检查 records)
        assert any(
            "time_scale 必须大于 0" in record.message for record in caplog.records
        )
        # (可选) 检查级别
        assert any(
            record.levelno == logger.level("ERROR").no for record in caplog.records
        )

        # 4. 验证 _time_scale 保持为初始值，而不是被错误地修改
        assert timeline._time_scale == initial_scale

    # --- 测试状态查询 (Getters) ---
    def test_get_current_time(self, timeline, start_time):
        """测试时间获取"""
        assert timeline.get_current_time() == start_time

    def test_get_season(self):
        """测试季节计算"""
        # Spring: 3-5, Summer:6-8, Autumn:9-11, Winter:12-2
        test_cases = [
            (datetime.datetime(2023, 3, 1), "Spring"),
            (datetime.datetime(2023, 6, 1), "Summer"),
            (datetime.datetime(2023, 9, 1), "Autumn"),
            (datetime.datetime(2023, 12, 1), "Winter"),
            (datetime.datetime(2023, 2, 28), "Winter"),
        ]
        for dt, expected in test_cases:
            # 此测试不使用 fixture，因为它需要特定时间
            timeline_custom = Timeline(dt)
            assert timeline_custom.get_season() == expected

    def test_is_daytime(self):
        """测试白天/黑夜判断"""
        # Default: day 6-20
        day_time = datetime.datetime(2023, 1, 1, 12, 0, 0)
        night_time = datetime.datetime(2023, 1, 1, 22, 0, 0)
        edge_case_day = datetime.datetime(2023, 1, 1, 6, 0, 0)  # 6:00 是白天
        edge_case_night = datetime.datetime(2023, 1, 1, 20, 0, 0)  # 20:00 是黑夜

        assert Timeline(day_time).is_daytime() is True
        assert Timeline(night_time).is_daytime() is False
        assert Timeline(edge_case_day).is_daytime() is True
        assert Timeline(edge_case_night).is_daytime() is False

    # --- 测试核心逻辑: _tick ---
    def test_tick_minute_passed(self, start_time):
        """测试 _tick 是否推进时间并发布 on_minute_passed"""
        timeline = Timeline(start_time)  # 需要一个特定的时间，不用 fixture
        callback = MagicMock(name="mock_callback_tick_min")
        timeline.subscribe("on_minute_passed", callback)

        timeline._tick()

        expected_time = start_time + datetime.timedelta(minutes=1)
        assert timeline.get_current_time() == expected_time
        callback.assert_called_once_with(expected_time)

    def test_tick_hour_passed(self):
        """测试 _tick 是否在跨小时时发布 on_hour_passed"""
        start_time = datetime.datetime(2023, 1, 1, 0, 59, 0)  # 00:59
        timeline = Timeline(start_time)
        callback = MagicMock(name="mock_callback_tick_hr")
        timeline.subscribe("on_hour_passed", callback)

        timeline._tick()  # 推进到 01:00

        callback.assert_called_once_with(timeline.get_current_time())

    def test_tick_day_passed(self):
        """测试 _tick 是否在跨天时发布 on_day_passed"""
        start_time = datetime.datetime(2023, 1, 1, 23, 59, 0)  # 23:59
        timeline = Timeline(start_time)
        callback = MagicMock(name="mock_callback_tick_day")
        timeline.subscribe("on_day_passed", callback)

        timeline._tick()  # 推进到 00:00 (第二天)

        callback.assert_called_once_with(timeline.get_current_time())

    def test_tick_season_changed(self, caplog):
        """测试 _tick 是否在跨季节时发布 on_season_changed (日志)"""
        # 从 Winter (2月) 到 Spring (3月)
        start_time = datetime.datetime(2023, 2, 28, 23, 59, 0)
        timeline = Timeline(start_time)
        callback = MagicMock(name="mock_callback_tick_season")
        timeline.subscribe("on_season_changed", callback)

        timeline._tick()  # 推进到 2023-03-01 00:00

        callback.assert_called_once_with("Spring")
        # [已修复] 检查 records
        assert any(
            "季节已变更: Winter -> Spring" in record.message
            for record in caplog.records
        )
        # (可选) 检查级别
        assert any(
            record.levelno == logger.level("INFO").no for record in caplog.records
        )

    # --- 测试核心循环: start_loop (异步) ---
    @pytest.mark.asyncio
    async def test_start_loop_paused(self):
        """测试暂停时，主循环不推进时间"""
        start_time = datetime.datetime.now()
        # 创建一个不使用 fixture 的 timeline 实例
        timeline_local = Timeline(start_time)
        timeline_local.pause()  # 立即暂停

        task = asyncio.create_task(timeline_local.start_loop())
        await asyncio.sleep(0.1)  # 给予循环一点运行时间
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # 断言时间 *仍然* 是开始时间
        assert timeline_local.get_current_time() == start_time

    @pytest.mark.asyncio
    async def test_start_loop_running(self):
        """测试主循环是否按 time_scale 推进时间并调用回调"""
        start_time = datetime.datetime(2023, 1, 1, 0, 0, 0)
        timeline_local = Timeline(
            start_time, time_scale=10.0
        )  # 1 真实秒 = 10 模拟分钟 (休眠 0.1 秒/tick)

        # [已修复] 订阅 on_minute_passed，更可靠
        callback = MagicMock(name="mock_callback_loop_min")
        timeline_local.subscribe("on_minute_passed", callback)

        task = asyncio.create_task(timeline_local.start_loop())

        # 休眠 3 真实秒。
        # 预期：模拟时间应该推进了 3 * 10 ≈ 30 模拟分钟。
        # 这意味着 "on_minute_passed" 至少被调用了 30 次。
        await asyncio.sleep(3)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        # 验证回调至少被调用了 25 次以上
        assert callback.call_count >= 25
        # 验证时间确实推进了
        assert timeline_local.get_current_time() > start_time + datetime.timedelta(
            minutes=20
        )
