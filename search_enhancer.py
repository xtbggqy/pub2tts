"""
搜索增强工具
使用AI模型优化PubMed搜索关键词，提高检索质量
"""
import os
import time
import json
import concurrent.futures
from openai import OpenAI

# 导入日志工具，如果可用
try:
    from log_utils import get_logger, init_logger
    
    def safe_print(msg, verbose=True):
        """兼容旧代码，使用日志系统"""
        logger = get_logger()
        if not verbose:
            return
        logger.log(msg, verbose)
except ImportError:
    def safe_print(msg, verbose=True):
        """安全打印，处理编码问题"""
        if not verbose:
            return
                
        try:
            print(msg)
            import sys
            sys.stdout.flush()
        except:
            print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
            import sys
            sys.stdout.flush()

class SearchEnhancer:
    """通过AI优化PubMed搜索关键词"""
    
    def __init__(self, config, verbose=False):
        """初始化搜索增强器
        
        Args:
            config: 配置字典
            verbose: 是否输出详细日志
        """
        self.verbose = verbose
        self.config = config
        self.client = self._init_ai_client()
        
        # 如果无法初始化客户端，也能正常工作，只是不进行优化
        if self.client:
            safe_print("搜索增强器初始化成功", self.verbose)
        else:
            safe_print("搜索增强器初始化失败，将使用原始搜索词", self.verbose)
        
    def _init_ai_client(self):
        """初始化AI客户端"""
        api_key = self.config.get('api_key', '')
        api_base_url = self.config.get('api_base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        
        # 尝试从环境变量获取API密钥
        if not api_key:
            api_key = os.getenv("DASHSCOPE_API_KEY", '')
        
        if not api_key:
            safe_print("警告: 未找到API密钥，无法使用搜索关键词优化功能", self.verbose)
            return None
            
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=api_base_url
            )
            return client
        except Exception as e:
            safe_print(f"初始化AI客户端失败: {e}", self.verbose)
            return None
    
    def enhance_query(self, original_query):
        """增强搜索查询
        
        Args:
            original_query: 原始查询字符串
            
        Returns:
            str: 增强后的查询字符串
        """
        if not self.client:
            return original_query
            
        safe_print(f"原始搜索查询: {original_query}", self.verbose)
        
        # 如果查询为空，返回原始查询
        if not original_query.strip():
            return original_query
            
        try:
            # 构建提示词
            prompt = f"""请帮我优化以下PubMed搜索查询，使其更专业、更精准。请使用PubMed高级搜索语法，包括字段标签和布尔运算符。

原始查询: {original_query}

要求:
1. 根据查询内容添加合适的MeSH术语
2. 使用[Title]、[Abstract]、[MeSH]等字段标签限定搜索范围
3. 使用AND、OR、NOT等布尔运算符组织复杂查询
4. 如有需要，使用括号确定运算优先级
5. 保留原始查询的核心概念，但使其更系统化、结构化
6. 直接输出优化后的查询字符串，不要添加任何解释

优化后的查询:"""

            # 调用AI接口
            response = self.client.chat.completions.create(
                model=self.config.get('ai_model', 'qwen-turbo'),
                messages=[
                    {'role': 'system', 'content': '你是一个专业的PubMed检索专家，擅长医学文献检索和医学领域知识。'},
                    {'role': 'user', 'content': prompt}
                ],
                timeout=self.config.get('ai_timeout', 30)
            )
            
            # 获取增强后的查询
            enhanced_query = response.choices[0].message.content.strip()
            
            # 如果返回的不只是查询本身，而是包含"优化后的查询:"这样的前缀，则提取查询部分
            if "优化后的查询:" in enhanced_query:
                enhanced_query = enhanced_query.split("优化后的查询:", 1)[1].strip()
            
            safe_print(f"增强后的搜索查询: {enhanced_query}", self.verbose)
            
            # 确保查询不为空
            if not enhanced_query.strip():
                safe_print("增强后的查询为空，使用原始查询", self.verbose)
                return original_query
                
            return enhanced_query
            
        except Exception as e:
            safe_print(f"增强搜索查询失败: {e}", self.verbose)
            return original_query
