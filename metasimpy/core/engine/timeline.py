# metasimpy/core/engine/timeline.py

import asyncio
import datetime
from loguru import logger
from typing import Callable, Dict, List, Any

# --- 类型定义 ---
EventCallback = Callable[..., Any]  # 定义新类型
ListenerDict = Dict[str, List[EventCallback]]  # 事件名称到回调函数列表的映射


class Timeline:
    """
    管理模拟世界的时间流逝、日夜更替、季节变化
    """

    def __init__(self, start_time: datetime.datetime, time_scale: float = 4.0):
        """
        初始化时间线
        """
        self._current_time: datetime.datetime = start_time
        self._is_paused: bool = False

        self._time_scale: float = 1.0
        self._sleep_duration: float = 1.0
        self.set_time_scale(time_scale)

        # 事件订阅系统
        self._listeners: ListenerDict = {
            "on_minute_passed": [],
            "on_hour_passed": [],
            "on_day_passed": [],
            "on_season_changed": [],
        }
        logger.info(f"时间线模块已初始化，起始时间: {start_time}")

    # --- 1. 事件系统 (发布-订阅) ---

    def subscribe(self, event_name: str, callback: EventCallback):
        """
        【公开】允许其他模块订阅一个时间事件。
        """
        if event_name in self._listeners:
            self._listeners[event_name].append(callback)
            # [已修复] 使用 getattr 安全获取名称
            callback_name = getattr(callback, "name", repr(callback))
            logger.debug(f"订阅成功: 回调 '{callback_name}' 订阅了 '{event_name}'")
        else:
            logger.warning(f"尝试订阅一个不存在的事件: '{event_name}'")

    def _publish(self, event_name: str, *args, **kwargs):
        """
        【内部】广播一个事件，触发所有订阅者（回调函数）。
        """
        if event_name in self._listeners:
            for callback in self._listeners[event_name]:
                try:
                    callback(*args, **kwargs)  # 执行时会跳转到对应的函数执行
                except Exception as e:
                    callback_name = getattr(callback, "name", repr(callback))
                    logger.error(
                        f"在执行 '{event_name}' 的回调 '{callback_name}' 时出错: {e}",  # 使用 callback_name
                        exc_info=True,
                    )

    # --- 2. 时间控制 (管理员功能) ---

    def pause(self):
        """【公开】暂停时间流逝。"""
        self._is_paused = True
        logger.info(f"时间已暂停于: {self._current_time}")

    def resume(self):
        """【公开】恢复时间流逝。"""
        self._is_paused = False
        logger.info("时间已恢复。")

    def set_time_scale(self, scale: float):
        """
        【公开】动态调整时间流速。
        """
        if scale <= 0:
            logger.error(f"time_scale 必须大于 0，但收到了: {scale}")
            return

        self._time_scale = scale
        self._sleep_duration = 1.0 / self._time_scale

        logger.info(
            f"时间流速调整为: 1 真实秒 = {scale:.1f} 模拟分钟 (休眠 {self._sleep_duration:.4f} 秒/tick)"
        )

    # --- 3. 状态查询 (Getters) ---

    def get_current_time(self) -> datetime.datetime:
        """【公开】获取当前的模拟时间。"""
        return self._current_time

    def _get_season_for_date(self, date_obj: datetime.datetime) -> str:
        """【内部】根据日期对象获取季节（北半球）。"""
        month = date_obj.month
        if month in (3, 4, 5):
            return "Spring"
        elif month in (6, 7, 8):
            return "Summer"
        elif month in (9, 10, 11):
            return "Autumn"
        else:
            return "Winter"

    def get_season(self) -> str:
        """【公开】获取当前的模拟季节。"""
        return self._get_season_for_date(self._current_time)

    def is_daytime(self, day_start_hour: int = 6, night_start_hour: int = 20) -> bool:
        """【公开】判断当前是白天还是黑夜。"""
        hour = self._current_time.hour
        return day_start_hour <= hour < night_start_hour

    # --- 4. 核心循环 ---

    def _tick(self):
        """
        【内部】推进一个最小时间单位（1分钟），并广播所有相关事件。
        """
        old_time = self._current_time
        self._current_time += datetime.timedelta(minutes=1)

        # --- 广播事件 ---
        self._publish("on_minute_passed", self._current_time)

        if old_time.hour != self._current_time.hour:
            self._publish("on_hour_passed", self._current_time)

        if old_time.day != self._current_time.day:
            self._publish("on_day_passed", self._current_time)

            old_season = self._get_season_for_date(old_time)
            new_season = self.get_season()
            if old_season != new_season:
                self._publish("on_season_changed", new_season)
                logger.info(
                    f"季节已变更: {old_season} -> {new_season}"
                )  # 季节变更是个大事件，适合用 INFO

    async def start_loop(self):
        """
        【公开】启动时间线的异步主循环。
        """
        logger.info(f"时间线已启动，流速: {self._time_scale:.1f}x")
        while True:
            if self._is_paused:
                await asyncio.sleep(0.5)
                continue

            await asyncio.sleep(self._sleep_duration)

            self._tick()
