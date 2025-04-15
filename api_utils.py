"""
API调用工具模块
提供与AI API交互的功能，包括调用管理、token计数等
"""
import time
import random
import re
import threading
import tiktoken

try:
    from log_utils import get_logger
    
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
            import sys
            sys.stdout.flush()
        except:
            print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
            import sys
            sys.stdout.flush()


class ApiManager:
    """API调用管理器"""
    
    def __init__(self, client, config, verbose=False):
        """初始化API管理器
        
        Args:
            client: OpenAI客户端实例
            config: 配置字典
            verbose: 是否输出详细日志
        """
        self.client = client
        self.config = config
        self.verbose = verbose
        self.request_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.lock = threading.RLock()
        
        # 初始化token计数器
        try:
            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except:
            try:
                self.encoding = tiktoken.get_encoding("cl100k_base")
            except:
                self.encoding = None
                safe_print("警告：无法初始化token计数器，将使用估算方法", self.verbose)
    
    def call_ai_api(self, prompt, retries=None):
        """调用AI API
        
        Args:
            prompt: 提示词文本
            retries: 重试次数，如果为None则使用配置中的默认值
            
        Returns:
            API响应的文本内容
        """
        if retries is None:
            retries = self.config.get('retry_times', 3)
        
        model = self.config.get('ai_model', 'qwen-plus')
        timeout = self.config.get('ai_timeout', 60)
        
        input_tokens = self.count_tokens(prompt)
        system_tokens = self.count_tokens('你是一个专业的学术翻译助手，擅长将英文学术文献准确翻译为符合中文学术习惯的表述。')
        total_input = input_tokens + system_tokens
        
        # 检查是否为空请求
        if not prompt.strip() or input_tokens == 0:
            safe_print(f"警告: 尝试发送空请求，已跳过", self.verbose)
            return ""
        
        with self.lock:
            self.total_input_tokens += total_input
            self.request_count += 1
            request_id = self.request_count
            
        safe_print(f"API请求 #{request_id}: 发送 {total_input} tokens", self.verbose)
        
        for attempt in range(retries):
            try:
                start_time = time.time()
                
                # 设置动态超时：基础超时 + 每1000 token增加10秒
                dynamic_timeout = timeout + (total_input / 1000) * 10
                safe_print(f"API请求 #{request_id} 设置动态超时: {dynamic_timeout:.1f}秒", self.verbose)
                
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {'role': 'system', 'content': '你是一个专业的学术翻译助手，擅长将英文学术文献准确翻译为符合中文学术习惯的表述。'},
                        {'role': 'user', 'content': prompt}
                    ],
                    timeout=dynamic_timeout  # 使用动态超时
                )
                
                result = response.choices[0].message.content
                
                # 验证结果有效性
                if not self.validate_translation_result(result, prompt):
                    raise ValueError("翻译结果验证失败，可能缺少关键内容")
                
                output_tokens = self.count_tokens(result)
                with self.lock:
                    self.total_output_tokens += output_tokens
                
                elapsed_time = time.time() - start_time
                safe_print(f"API请求 #{request_id} 完成，耗时: {elapsed_time:.2f}秒", self.verbose)
                safe_print(f"请求 #{request_id}: 输入{total_input}个token, 输出{output_tokens}个token", self.verbose)
                
                return result
                
            except Exception as e:
                safe_print(f"API请求 #{request_id} 调用失败 (尝试 {attempt+1}/{retries}): {str(e)}", True)
                if attempt < retries - 1:
                    # 使用指数退避策略和抖动
                    sleep_time = (2 ** attempt) + (random.random() * 2)
                    safe_print(f"请求 #{request_id} 将在 {sleep_time:.1f} 秒后重试...", True)
                    time.sleep(sleep_time)
        
        safe_print(f"API请求 #{request_id} 所有尝试都失败", True)
        return ""
    
    def validate_translation_result(self, result, prompt):
        """验证翻译结果是否有效
        
        Args:
            result: API返回的翻译结果
            prompt: 原始请求
            
        Returns:
            bool: 结果是否有效
        """
        if not result or len(result) < 10:
            safe_print("警告: 翻译结果过短或为空", self.verbose)
            return False
            
        # 检查是否包含标记格式
        if "【" in prompt and "】" in prompt:
            if "【" not in result or "】" not in result:
                safe_print("警告: 翻译结果缺少标记格式", self.verbose)
                # 轻微的格式问题不一定导致失败
                # return False
        
        # 计算预期的内容项数量 (通过计算输入中的标记对)
        expected_items = len(re.findall(r'【\d+】.*?【/\d+】', prompt, re.DOTALL))
        
        # 如果原始请求包含标记但结果没有相应的标记对，验证失败
        if expected_items > 0:
            actual_items = len(re.findall(r'【\d+】.*?【/\d+】', result, re.DOTALL))
            
            # 允许有一定的容错性，只要返回了大部分内容
            if actual_items < expected_items * 0.8:  # 80%容错阈值
                safe_print(f"警告: 翻译结果不完整，预期{expected_items}项，实际只有{actual_items}项", self.verbose)
                return False
                
        return True
    
    def count_tokens(self, text):
        """计算文本的token数量
        
        Args:
            text: 要计算token数的文本
            
        Returns:
            int: token数量
        """
        try:
            if hasattr(self, 'encoding') and self.encoding:
                return len(self.encoding.encode(text))
            else:
                try:
                    self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
                    return len(self.encoding.encode(text))
                except:
                    try:
                        self.encoding = tiktoken.get_encoding("cl100k_base")
                        return len(self.encoding.encode(text))
                    except:
                        safe_print("警告：无法使用tiktoken，使用简单字符数量估算", self.verbose)
                        return len(text) // 4
        except Exception as e:
            safe_print(f"计算token数量时出错: {e}", self.verbose)
            return len(text) // 4
    
    def print_token_statistics(self):
        """打印Token使用统计"""
        try:
            # 如果没有调用API，则跳过统计
            if self.total_input_tokens == 0 and self.total_output_tokens == 0:
                return
                
            safe_print("\n" + "="*50, True)
            safe_print("Token 使用统计:", True)
            safe_print(f"总输入 tokens: {self.total_input_tokens:,}", True)
            safe_print(f"总输出 tokens: {self.total_output_tokens:,}", True)
            safe_print(f"总计 tokens: {self.total_input_tokens + self.total_output_tokens:,}", True)
            
            # 计算费用
            input_price = self.config.get('api_price_input', 20.0) / 1000000  # 元/token
            output_price = self.config.get('api_price_output', 200.0) / 1000000  # 元/token
            
            input_cost = self.total_input_tokens * input_price
            output_cost = self.total_output_tokens * output_price
            total_cost = input_cost + output_cost
            
            safe_print(f"估算费用: ¥{total_cost:.4f} (输入: ¥{input_cost:.4f}, 输出: ¥{output_cost:.4f})", True)
            safe_print(f"价格设置: 输入 ¥{input_price*1000000:.1f}/百万tokens, 输出 ¥{output_price*1000000:.1f}/百万tokens", True)
            safe_print("="*50, True)
        except Exception as e:
            safe_print(f"计算Token统计时出错: {e}", True)
