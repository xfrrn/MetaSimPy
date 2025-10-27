import sys
from loguru import logger
from pathlib import Path


def setup_logging():
    """
    配置 Loguru 的全局记录器。
    """
    logger.remove()

    # [配置] 设置项目根目录，用于定位日志文件
    log_path = Path(__file__).parent.parent.parent.parent / "logs"
    log_path.mkdir(parents=True, exist_ok=True)
    log_file = log_path / "world.log"

    # [添加] 配置“控制台”处理器 (Console Handler)
    logger.add(
        sys.stdout,  # 输出到标准输出
        level="DEBUG",
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
        enqueue=True,
    )

    # [添加] 配置“日志文件”处理器 (File Handler)
    logger.add(
        log_file,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        enqueue=True,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )

    logger.info("Logger 配置已加载。日志将输出到控制台和文件。")
