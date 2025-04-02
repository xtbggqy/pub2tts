"""
日志工具模块
提供统一的日志记录功能，支持同时输出到终端和文件
"""
import os
import sys
import time
import threading
from datetime import datetime

class Logger:
    """日志记录器，支持同时输出到终端和文件"""
    
    def __init__(self, log_file=None, verbose=True):
        """初始化日志记录器
        
        Args:
            log_file: 日志文件路径，如果为None则不记录到文件
            verbose: 是否输出详细日志
        """
        self.verbose = verbose
        self.log_file = log_file
        self.lock = threading.Lock()
        
        # 如果指定了日志文件，则确保目录存在
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
                
            # 添加日志文件头部
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'=' * 80}\n")
                f.write(f"PubMed文献处理系统日志 - 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'=' * 80}\n\n")
    
    def log(self, msg, always_print=False, level=None):
        """记录日志消息
        
        Args:
            msg: 日志消息
            always_print: 是否始终打印到终端，无视verbose设置
            level: 日志级别(INFO, WARNING, ERROR, SUCCESS, DEBUG)
        """
        with self.lock:
            # 格式化日志消息
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            level_str = f"[{level}]" if level else ""
            formatted_msg = f"{timestamp} {level_str} {msg}"
            
            # 输出到终端
            if self.verbose or always_print:
                try:
                    print(msg)
                    sys.stdout.flush()
                except:
                    # 处理编码问题
                    print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
                    sys.stdout.flush()
            
            # 输出到文件
            if self.log_file:
                try:
                    with open(self.log_file, 'a', encoding='utf-8') as f:
                        f.write(formatted_msg + '\n')
                except Exception as e:
                    print(f"写入日志文件失败: {e}")
    
    def info(self, msg, always_print=False):
        """记录信息级别日志"""
        self.log(msg, always_print, "INFO")
    
    def warning(self, msg, always_print=True):
        """记录警告级别日志"""
        self.log(f"警告: {msg}", always_print, "WARNING")
    
    def error(self, msg, always_print=True):
        """记录错误级别日志"""
        self.log(f"错误: {msg}", always_print, "ERROR")
    
    def success(self, msg, always_print=True):
        """记录成功级别日志"""
        self.log(f"成功: {msg}", always_print, "SUCCESS")
    
    def debug(self, msg):
        """记录调试级别日志，只在详细模式下显示"""
        if self.verbose:
            self.log(msg, False, "DEBUG")

# 全局日志记录器实例
_logger = None

def init_logger(log_file=None, verbose=True):
    """初始化全局日志记录器"""
    global _logger
    _logger = Logger(log_file, verbose)
    return _logger

def get_logger():
    """获取全局日志记录器"""
    global _logger
    if _logger is None:
        # 默认初始化
        _logger = init_logger()
    return _logger

# 便捷函数
def log(msg, always_print=False, level=None):
    """记录日志"""
    get_logger().log(msg, always_print, level)

def info(msg, always_print=False):
    """记录信息"""
    get_logger().info(msg, always_print)

def warning(msg, always_print=True):
    """记录警告"""
    get_logger().warning(msg, always_print)

def error(msg, always_print=True):
    """记录错误"""
    get_logger().error(msg, always_print)

def success(msg, always_print=True):
    """记录成功"""
    get_logger().success(msg, always_print)

def debug(msg):
    """记录调试信息"""
    get_logger().debug(msg)
