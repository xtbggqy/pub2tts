"""
通用工具函数模块
提供日志记录、安全打印等基础功能
"""
import os
import sys
import time
import random
import hashlib
import threading

# 导入日志工具
try:
    from log_utils import get_logger, init_logger
    
    def safe_print(msg, verbose=True):
        """兼容旧代码，使用日志系统"""
        logger = get_logger()
        if not verbose:
            # 检查是否为重要消息
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告", "初始化", "Token 使用统计"]):
                return
        logger.log(msg, verbose)
except ImportError:
    def safe_print(msg, verbose=True):
        """安全打印，处理编码问题"""
        if not verbose:
            # 检查是否为重要消息
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告", "初始化", "Token 使用统计"]):
                return
                
        try:
            print(msg)
            sys.stdout.flush()
        except:
            print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
            sys.stdout.flush()

def create_directory_if_not_exists(directory_path):
    """确保目录存在，如果不存在则创建
    
    Args:
        directory_path: 目录路径
        
    Returns:
        bool: 是否成功确保目录存在
    """
    if not directory_path:
        return True
        
    if not os.path.exists(directory_path):
        try:
            os.makedirs(directory_path)
            return True
        except Exception as e:
            safe_print(f"创建目录失败: {e}", True)
            return False
    return True

def get_hash(text, prefix=""):
    """计算文本的哈希值
    
    Args:
        text: 要计算哈希的文本
        prefix: 前缀，如"title", "abstract"等
        
    Returns:
        哈希字符串
    """
    text_with_prefix = f"{prefix}:{text}"
    return hashlib.md5(text_with_prefix.encode('utf-8')).hexdigest()

def exponential_backoff(attempt, base=2, max_wait=60):
    """指数退避策略，用于重试
    
    Args:
        attempt: 当前尝试次数(从0开始)
        base: 基础等待时间(秒)
        max_wait: 最大等待时间(秒)
        
    Returns:
        等待时间(秒)
    """
    wait_time = min(base * (2 ** attempt) + (random.random() * 2), max_wait)
    return wait_time
