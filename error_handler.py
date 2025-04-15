"""
错误处理工具模块
提供统一的错误处理和恢复机制，增强应用程序稳健性
"""
import os
import sys
import time
import random
import json
import traceback
import threading
from datetime import datetime
from functools import wraps

# 尝试导入日志工具
try:
    from log_utils import get_logger, init_logger
    
    def safe_print(msg, verbose=True):
        """使用日志系统输出信息"""
        logger = get_logger()
        logger.log(msg, verbose)
except ImportError:
    def safe_print(msg, verbose=True):
        """备用输出方法"""
        if not verbose:
            return
            
        try:
            print(msg)
            sys.stdout.flush()
        except:
            print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
            sys.stdout.flush()

class ErrorTracker:
    """错误跟踪器，记录和分析错误模式"""
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ErrorTracker, cls).__new__(cls)
                cls._instance._errors = []
                cls._instance._error_counts = {}
                cls._instance._start_time = datetime.now()
                cls._instance._last_report_time = datetime.now()
                cls._instance._report_interval = 300  # 默认每5分钟报告一次
            return cls._instance
            
    def track_error(self, error_type, message, source=None, severity="ERROR"):
        """记录一个错误
        
        Args:
            error_type: 错误类型
            message: 错误信息
            source: 错误来源（模块/函数）
            severity: 严重程度（INFO, WARNING, ERROR, CRITICAL）
        """
        with self._lock:
            timestamp = datetime.now()
            
            # 创建错误记录
            error_record = {
                "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "type": error_type,
                "message": message,
                "source": source or "unknown",
                "severity": severity,
                "traceback": traceback.format_exc() if sys.exc_info()[0] else None
            }
            
            # 添加到错误列表
            self._errors.append(error_record)
            
            # 更新错误计数
            error_key = f"{error_type}:{source}"
            if error_key in self._error_counts:
                self._error_counts[error_key] += 1
            else:
                self._error_counts[error_key] = 1
            
            # 如果是严重错误，立即记录日志
            if severity in ["ERROR", "CRITICAL"]:
                safe_print(f"{severity}: {error_type} in {source}: {message}", True)
                
            # 检查是否需要生成报告
            self._check_report_time()
    
    def _check_report_time(self):
        """检查是否需要生成错误报告"""
        now = datetime.now()
        if (now - self._last_report_time).total_seconds() > self._report_interval:
            self.generate_report()
            self._last_report_time = now
    
    def generate_report(self, save_to_file=False):
        """生成错误报告
        
        Args:
            save_to_file: 是否保存到文件
        """
        with self._lock:
            if not self._errors:
                return
                
            # 错误摘要
            total_errors = len(self._errors)
            runtime = (datetime.now() - self._start_time).total_seconds() / 60.0
            
            report = [
                "=" * 60,
                f"错误报告 - 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"总运行时间: {runtime:.1f} 分钟",
                f"总错误数: {total_errors}",
                "=" * 60
            ]
            
            # 按错误类型分组
            error_types = {}
            for error in self._errors:
                error_type = error["type"]
                if error_type in error_types:
                    error_types[error_type].append(error)
                else:
                    error_types[error_type] = [error]
            
            # 添加错误类型摘要
            report.append("\n错误类型摘要:")
            for error_type, errors in error_types.items():
                report.append(f"- {error_type}: {len(errors)} 次错误")
            
            # 添加最近的5个错误的详细信息
            report.append("\n最近错误详情 (最多5个):")
            for i, error in enumerate(self._errors[-5:]):
                report.append(f"\n{i+1}. [{error['severity']}] {error['type']} - {error['timestamp']}")
                report.append(f"   来源: {error['source']}")
                report.append(f"   消息: {error['message']}")
                
                if error.get("traceback"):
                    tb_lines = error["traceback"].split("\n")
                    if len(tb_lines) > 5:
                        tb_summary = "\n      ".join(tb_lines[:5]) + "\n      ..."
                    else:
                        tb_summary = "\n      ".join(tb_lines)
                    report.append(f"   堆栈: {tb_summary}")
            
            report_text = "\n".join(report)
            safe_print(report_text, True)
            
            # 如果需要，保存到文件
            if save_to_file:
                try:
                    # 创建错误报告目录
                    report_dir = "error_reports"
                    if not os.path.exists(report_dir):
                        os.makedirs(report_dir)
                        
                    # 生成文件名
                    filename = f"{report_dir}/error_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    
                    # 写入文件
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(report_text)
                    
                    safe_print(f"错误报告已保存到: {filename}", True)
                except Exception as e:
                    safe_print(f"保存错误报告失败: {e}", True)
            
            # 清除旧错误记录，只保留最近100个
            if len(self._errors) > 100:
                self._errors = self._errors[-100:]

def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """重试装饰器
    
    Args:
        max_attempts: 最大尝试次数
        delay: 初始延迟时间(秒)
        backoff: 退避因子
        exceptions: 要捕获和重试的异常类型
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = ErrorTracker()
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts == max_attempts:
                        tracker.track_error(
                            type(e).__name__, 
                            str(e),
                            source=func.__name__,
                            severity="ERROR"
                        )
                        raise
                    
                    # 计算延迟时间（指数退避 + 抖动）
                    wait_time = delay * (backoff ** (attempts - 1)) + (random.random())
                    
                    # 记录重试情况
                    tracker.track_error(
                        type(e).__name__, 
                        f"尝试 {attempts}/{max_attempts} 失败: {str(e)}. 将在 {wait_time:.1f}秒后重试",
                        source=func.__name__,
                        severity="WARNING"
                    )
                    
                    time.sleep(wait_time)
        return wrapper
    return decorator

def safe_file_operation(operation_type="write"):
    """安全文件操作装饰器
    
    Args:
        operation_type: 操作类型 ("read", "write", "append")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = ErrorTracker()
            try:
                return func(*args, **kwargs)
            except (IOError, OSError, PermissionError) as e:
                # 获取文件路径参数（假设它是第一个参数或名为file_path的参数）
                file_path = args[0] if args else kwargs.get('file_path', 'unknown_file')
                
                tracker.track_error(
                    type(e).__name__,
                    f"文件{operation_type}操作失败: {str(e)}",
                    source=f"{func.__name__}({file_path})",
                    severity="ERROR"
                )
                
                # 尝试提供替代路径
                if operation_type in ("write", "append"):
                    try:
                        backup_path = f"{os.path.basename(file_path)}.backup"
                        safe_print(f"尝试写入备份文件: {backup_path}", True)
                        
                        # 修改参数后重新调用函数
                        if args:
                            new_args = list(args)
                            new_args[0] = backup_path
                            return func(*new_args, **kwargs)
                        else:
                            kwargs['file_path'] = backup_path
                            return func(*args, **kwargs)
                    except Exception as backup_error:
                        tracker.track_error(
                            type(backup_error).__name__,
                            f"备份文件操作也失败: {str(backup_error)}",
                            source=func.__name__,
                            severity="CRITICAL"
                        )
                        raise backup_error
                raise
        return wrapper
    return decorator

# 示例: 如何使用这个模块
if __name__ == "__main__":
    # 示例1: 使用重试装饰器
    @retry(max_attempts=3)
    def sample_api_call():
        """一个示例函数，演示重试装饰器的使用"""
        # 模拟随机失败的API调用
        if random.random() < 0.7:
            raise ConnectionError("连接失败")
        return "API调用成功"
    
    # 示例2: 使用安全文件操作装饰器
    @safe_file_operation(operation_type="write")
    def save_data(file_path, data):
        """安全地保存数据到文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 测试错误跟踪器
    tracker = ErrorTracker()
    
    # 运行演示
    print("开始演示错误处理模块...")
    
    # 尝试调用可能失败的API
    try:
        result = sample_api_call()
        print(f"API结果: {result}")
    except Exception as e:
        print(f"API最终失败: {e}")
    
    # 尝试写入文件
    try:
        # 故意使用无效路径
        save_data("/invalid/path/data.json", {"test": "data"})
    except Exception as e:
        print(f"文件操作最终失败: {e}")
    
    # 生成错误报告
    tracker.generate_report(save_to_file=True)
    
    print("演示完成")
