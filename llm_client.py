"""
AI客户端模块
提供AI客户端初始化、API调用和Token计数
"""
import os
import re
import time
import tiktoken
import threading
from openai import OpenAI
from utils import safe_print, exponential_backoff

class LLMClient:
    """AI大模型客户端封装类"""
    
    def __init__(self, config):
        """初始化AI客户端
        
        Args:
            config: 配置字典，包含API密钥、模型名称等
        """
        self.config = config
        self.client = self._init_ai_client()
        self.lock = threading.RLock()
        self.request_count = 0
        
        # 添加token计数器
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        
        # 初始化token计数器
        try:
            self.encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        except:
            try:
                self.encoding = tiktoken.get_encoding("cl100k_base")
            except:
                self.encoding = None
                safe_print("警告: tiktoken初始化失败，将使用字符数估算token", False)
        
    def _init_ai_client(self):
        """初始化AI客户端"""
        api_key = self.config.get('api_key', '')
        api_base_url = self.config.get('api_base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        
        if not api_key:
            api_key = os.getenv("DASHSCOPE_API_KEY", '')
            if api_key:
                safe_print("从环境变量加载 API 密钥")
        
        if not api_key:
            safe_print("警告: 未找到API密钥，请在配置文件或环境变量中设置")
            return None
        
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=api_base_url,
            )
            
            safe_print("AI客户端初始化成功")
            if api_key:
                try:
                    test_response = client.chat.completions.create(
                        model=self.config['ai_model'],
                        messages=[{'role': 'system', 'content': '你是一个助手'}, {'role': 'user', 'content': '请回复"API连接测试成功"'}],
                        timeout=5
                    )
                    safe_print(f"API连接测试结果: {test_response.choices[0].message.content}")
                except Exception as e:
                    safe_print(f"API连接测试失败: {e}")
                    
            return client
        except Exception as e:
            safe_print(f"AI客户端初始化失败: {e}")
            return None
    
    def count_tokens(self, text):
        """计算文本的token数量"""
        try:
            if self.encoding:
                return len(self.encoding.encode(text))
            else:
                # 简单估算：平均每个英文单词1.3个token
                return len(text.split()) * 1.3
        except Exception as e:
            safe_print(f"计算token数量时出错: {e}", False)
            return len(text) // 4
    
    def call_api(self, prompt, system_content=None, retries=None, verbose=True):
        """调用AI API处理提示词
        
        Args:
            prompt: 用户提示词
            system_content: 系统消息内容
            retries: 重试次数，None则使用配置
            verbose: 是否输出详细日志
            
        Returns:
            API返回的内容
        """
        if retries is None:
            retries = self.config.get('retry_times', 3)
        
        if not self.client:
            safe_print("AI客户端未初始化，无法调用API", True)
            return ""
        
        model = self.config.get('ai_model', 'qwen-plus')
        timeout = self.config.get('ai_timeout', 60)
        
        if not system_content:
            system_content = '你是一个专业的学术翻译助手，擅长将英文学术文献准确翻译为符合中文学术习惯的表述。'
        
        input_tokens = self.count_tokens(prompt)
        system_tokens = self.count_tokens(system_content)
        total_input = input_tokens + system_tokens
        
        # 检查是否为空请求
        if not prompt.strip() or input_tokens == 0:
            safe_print(f"警告: 尝试发送空请求，已跳过", verbose)
            return ""
        
        with self.lock:
            self.total_input_tokens += total_input
            self.request_count += 1
            request_id = self.request_count
            
        safe_print(f"API请求 #{request_id}: 发送 {total_input} tokens", verbose)
        
        for attempt in range(retries):
            try:
                start_time = time.time()
                
                # 设置动态超时：基础超时 + 每1000 token增加10秒
                dynamic_timeout = timeout + (total_input / 1000) * 10
                safe_print(f"API请求 #{request_id} 设置动态超时: {dynamic_timeout:.1f}秒", verbose)
                
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {'role': 'system', 'content': system_content},
                        {'role': 'user', 'content': prompt}
                    ],
                    timeout=dynamic_timeout
                )
                
                result = response.choices[0].message.content
                
                # 验证结果有效性
                if not self._validate_result(result, prompt):
                    raise ValueError("结果验证失败，可能缺少关键内容")
                
                output_tokens = self.count_tokens(result)
                with self.lock:
                    self.total_output_tokens += output_tokens
                
                elapsed_time = time.time() - start_time
                safe_print(f"API请求 #{request_id} 完成，耗时: {elapsed_time:.2f}秒", verbose)
                safe_print(f"请求 #{request_id}: 输入{total_input}个token, 输出{output_tokens}个token", verbose)
                
                return result
                
            except Exception as e:
                safe_print(f"API请求 #{request_id} 调用失败 (尝试 {attempt+1}/{retries}): {str(e)}", True)
                if attempt < retries - 1:
                    # 使用指数退避策略
                    sleep_time = exponential_backoff(attempt)
                    safe_print(f"请求 #{request_id} 将在 {sleep_time:.1f} 秒后重试...", True)
                    time.sleep(sleep_time)
        
        safe_print(f"API请求 #{request_id} 所有尝试都失败", True)
        return ""
    
    def _validate_result(self, result, prompt):
        """验证API返回结果是否有效
        
        Args:
            result: API返回的结果
            prompt: 原始请求
            
        Returns:
            bool: 结果是否有效
        """
        if not result or len(result) < 10:
            safe_print("警告: API结果过短或为空", False)
            return False
            
        # 检查是否包含标记格式
        if "【" in prompt and "】" in prompt:
            if "【" not in result or "】" not in result:
                safe_print("警告: API结果缺少标记格式", False)
                
        # 计算预期的内容项数量 (通过计算输入中的标记对)
        expected_items = len(re.findall(r'【\d+】.*?【/\d+】', prompt, re.DOTALL))
        
        # 如果原始请求包含标记但结果没有相应的标记对，验证失败
        if expected_items > 0:
            actual_items = len(re.findall(r'【\d+】.*?【/\d+】', result, re.DOTALL))
            
            # 允许有一定的容错性，只要返回了大部分内容
            if actual_items < expected_items * 0.8:  # 80%容错阈值
                safe_print(f"警告: API结果不完整，预期{expected_items}项，实际只有{actual_items}项", False)
                return False
                
        return True
        
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
