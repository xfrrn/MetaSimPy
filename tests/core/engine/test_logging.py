import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from loguru import logger


class TestSetupLogging:

    # 模拟 Path，这是一个好做法，保持不变
    @pytest.fixture
    def mock_path(self):
        """模拟 Path 对象以避免文件系统操作"""
        with patch("metasimpy.core.engine.logging.Path") as mock_path_class:
            # 配置 mock_path_class 的实例（即 __file__）
            mock_instance = mock_path_class.return_value

            # 模拟路径回溯: ...parent.parent.parent.parent
            mock_root_path = MagicMock(spec=Path)
            mock_instance.parent.parent.parent.parent = mock_root_path

            # 模拟 / "logs"
            mock_logs_dir = MagicMock(spec=Path)
            mock_root_path.__truediv__.return_value = mock_logs_dir

            # 模拟 / "world.log"
            mock_log_file = MagicMock(spec=Path)
            mock_logs_dir.__truediv__.return_value = mock_log_file

            # 确保 mkdir 和 __truediv__ 在链式调用中返回正确的 mock
            mock_logs_dir.mkdir = MagicMock()

            # 返回最重要的 mock，即日志目录和日志文件
            yield mock_logs_dir, mock_log_file

    # --- 模拟 logger.add 和 logger.remove ---
    @pytest.fixture
    def mock_logger_config(self):
        """模拟 logger.add 和 logger.remove 方法"""
        with (
            patch.object(logger, "remove") as mock_remove,
            patch.object(logger, "add") as mock_add,
        ):
            yield mock_remove, mock_add

    def test_setup_logging_calls(self, mock_path, mock_logger_config):
        """
        测试 setup_logging 是否正确调用了 remove 和 add
        """
        from metasimpy.core.engine.logging import setup_logging

        mock_logs_dir, mock_log_file = mock_path
        mock_remove, mock_add = mock_logger_config

        # --- 执行被测函数 ---
        setup_logging()

        # --- 断言配置行为 ---

        # 1. 是否清空了默认处理器？
        mock_remove.assert_called_once_with()  # 验证 logger.remove() 被无参数调用

        # 2. 是否添加了两个处理器？
        assert mock_add.call_count == 2

        # 3. 检查控制台处理器 (第一个 add 调用)
        call_1_args, call_1_kwargs = mock_add.call_args_list[0]
        assert call_1_args[0] == sys.stdout  # 检查是否输出到 stdout
        assert call_1_kwargs["level"] == "DEBUG"
        assert call_1_kwargs["colorize"] is True
        assert call_1_kwargs["enqueue"] is True

        # 4. 检查文件处理器 (第二个 add 调用)
        call_2_args, call_2_kwargs = mock_add.call_args_list[1]
        assert call_2_args[0] == mock_log_file  # 检查是否输出到模拟的 log file
        assert call_2_kwargs["level"] == "DEBUG"
        assert call_2_kwargs["rotation"] == "10 MB"
        assert call_2_kwargs["retention"] == "7 days"
        assert call_2_kwargs["compression"] == "zip"
        assert call_2_kwargs["enqueue"] is True

        # 5. 检查 log 目录是否被创建
        mock_logs_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)


@pytest.fixture
def capsys_stdout(capsys):
    """一个简单的 fixture，用于清除之前的 stdout 捕获"""
    # 在测试前清除任何可能存在的捕获
    capsys.readouterr()
    yield capsys
    # 测试后也可以清除
    capsys.readouterr()
