# encoding=utf-8
"""
日志配置模块
提供统一的日志配置，支持控制台输出和文件记录
"""
import logging
import os
from pathlib import Path
from datetime import datetime


def setup_logger(
    name: str = "RTC",
    log_level: str = "INFO",
    log_to_file: bool = True,
    log_dir: str = "logs",
    log_file_prefix: str = "rtc"
) -> logging.Logger:
    """
    配置并返回 logger 实例

    参数:
        name: logger 名称
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_to_file: 是否写入文件
        log_dir: 日志文件目录
        log_file_prefix: 日志文件前缀

    返回:
        logging.Logger: 配置好的 logger 实例
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 日志格式
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 控制台输出 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出 handler（可选）
    if log_to_file:
        # 创建日志目录
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        # 日志文件名：rtc_2026-02-01.log
        log_filename = f"{log_file_prefix}_{datetime.now().strftime('%Y-%m-%d')}.log"
        log_file_path = log_path / log_filename

        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # 文件记录更详细的日志
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# 创建默认 logger 实例
default_logger = setup_logger()
