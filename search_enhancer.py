"""
PubMed搜索词润色增强模块
提供搜索词润色和优化功能
"""
import os
import re
import sys
import time

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    print("提示: 未发现OpenAI模块，将无法使用搜索词润色功能。您可以通过运行 'pip install openai>=1.0.0' 安装此模块。")

from pubmed_core import safe_print, fix_query_syntax

# 导入日志工具，如果可用
try:
    from log_utils import get_logger, init_logger
except ImportError:
    pass

class SearchEnhancer:
    """PubMed搜索词润色工具"""
    
    def __init__(self, config, verbose=False, log_file=None):
        """初始化搜索词润色工具
        
        Args:
            config: 配置字典
            verbose: 是否输出详细日志
            log_file: 日志文件路径，如果为None则不记录到文件
        """
        self.config = config
        self.verbose = verbose
        self.log_file = log_file
        
        # 如果提供了log_file，初始化日志系统（如果导入了log_utils）
        if log_file and 'init_logger' in globals():
            init_logger(log_file=log_file, verbose=verbose)
        
        self.ai_client = None
        self._init_ai_client()
    
    def _init_ai_client(self):
        """初始化AI客户端，用于搜索词润色"""
        if OpenAI is None:
            safe_print("警告: 未安装OpenAI模块，无法润色搜索词", True)
            safe_print("提示: 可通过运行 'pip install openai>=1.0.0' 安装该模块", True)
            return
        
        api_key = self.config.get('api_key', '')
        api_base_url = self.config.get('api_base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        
        if not api_key:
            safe_print("警告: API密钥未设置，无法润色搜索词", True)
            safe_print("提示: 请在配置文件中设置api_key参数或在环境变量中设置DASHSCOPE_API_KEY", True)
            return
        
        try:
            self.ai_client = OpenAI(
                api_key=api_key,
                base_url=api_base_url,
            )
            safe_print("AI客户端初始化成功，可以润色搜索词", self.verbose)
            
            # 检查API连接是否正常
            try:
                response = self.ai_client.chat.completions.create(
                    model=self.config.get('ai_model', 'qwen-turbo'),
                    messages=[
                        {'role': 'system', 'content': '您好'},
                        {'role': 'user', 'content': '请回复"连接测试成功"'}
                    ],
                    timeout=5,
                    max_tokens=10
                )
                if "连接测试成功" in response.choices[0].message.content:
                    safe_print("API连接测试成功", self.verbose)
                else:
                    safe_print("API连接测试结果不符合预期，但连接成功", self.verbose)
            except Exception as e:
                safe_print(f"API连接测试失败，但客户端初始化成功: {e}", self.verbose)
                
        except Exception as e:
            safe_print(f"AI客户端初始化失败: {e}", True)
            safe_print("提示: 请确保API密钥正确且有效，网络连接正常", True)
            self.ai_client = None
    
    def enhance_query(self, original_query):
        """使用AI润色搜索词，转换为PubMed高级检索格式，进行两轮优化"""
        if not self.ai_client:
            safe_print("AI客户端未初始化，无法润色搜索词", True)
            safe_print("将使用原始搜索词进行检索", True)
            return original_query
        
        try:
            safe_print(f"开始润色搜索词: '{original_query}'", True)
            
            # 对于某些基础关键词，直接使用简单搜索格式而不是过度复杂化
            basic_keywords = ["plant", "genome", "bacteria", "virus", "cancer", "drug", 
                             "disease", "protein", "gene", "cell", "mutation", "therapy"]
            
            if original_query.lower().strip() in basic_keywords:
                # 为基础关键词构建简单而有效的检索式
                simple_query = f'"{original_query}"[MeSH Terms] OR "{original_query}"[All Fields]'
                safe_print(f"检测到基础关键词，使用简单检索式: '{simple_query}'", True)
                return simple_query
            
            # 第一轮：初始转换，生成高级检索格式
            first_round_prompt = f"""请将以下搜索词转换为PubMed高级检索格式，使其更准确、全面地表达用户的需求，并符合PubMed的语法:

原始搜索词: "{original_query}"

请按以下要求润色:
1. 分析最核心的概念，为每个概念找到最合适的MeSH主题词和主要同义词
2. 使用适当的字段限定词，如[All Fields]或[MeSH Terms]，避免过度限制检索范围
3. 合理使用布尔运算符(AND, OR)和括号来构建搜索语句
4. 保持简洁，整个检索式中OR连接的术语总数控制在3-4个以内
5. 确保语法准确，特别是引号、括号的匹配和字段标记的格式
6. 检索式应该非常宽泛，确保能检索到足够多的文献
7. 确保字段标记前没有多余空格，确保布尔运算符大写
8. 不要使用过于特定的限制条件，宁可结果更多也不要遗漏文献

增强后的PubMed检索式:"""

            # 显示处理进度
            safe_print("正在进行第一轮润色...", self.verbose)
            
            # 调用AI API进行第一轮转换
            model = self.config.get('ai_model', 'qwen-turbo')
            timeout = self.config.get('ai_timeout', 30)
            
            first_response = self.ai_client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': '你是一位专业的医学文献检索专家，精通PubMed高级检索语法。'},
                    {'role': 'user', 'content': first_round_prompt}
                ],
                timeout=timeout
            )
            
            first_enhanced_query = first_response.choices[0].message.content.strip()
            
            # 清理第一轮结果
            first_enhanced_query = first_enhanced_query.replace('增强后的PubMed检索式:', '').strip()
            first_enhanced_query = re.sub(r'^["\'`]|["\'`]$', '', first_enhanced_query)  # 移除首尾引号
            
            # 修复第一轮可能的语法错误
            first_enhanced_query = fix_query_syntax(first_enhanced_query, self.verbose)
            
            safe_print(f"第一轮润色完成: '{first_enhanced_query}'", self.verbose)
            
            # 第二轮：校正和优化
            second_round_prompt = f"""请对以下PubMed高级检索式进行校正和简化，使其更加宽泛，确保能检索到足够多的文献:

原始搜索词: "{original_query}"
当前检索式: {first_enhanced_query}

请重点检查并遵循以下规则:
1. 简化检索式，使其更通用
2. 优先使用"[All Fields]"或"[MeSH Terms]"字段限定词，避免过度限制检索范围
3. 确保引号和括号正确配对
4. 确保布尔运算符(AND, OR)大写且用法正确
5. 检索式应该尽可能宽泛，不要设置过多限制
6. 如果是单一概念，可以简化为: "概念"[MeSH Terms] OR "概念"[All Fields]
7. 避免使用[Title/Abstract]等会限制结果的字段限定，除非原始搜索词非常特定

简化后的检索式:"""

            # 显示处理进度
            safe_print("正在进行第二轮优化...", self.verbose)
            
            second_response = self.ai_client.chat.completions.create(
                model=model,
                messages=[
                    {'role': 'system', 'content': '你是一位专业的医学文献检索专家，擅长校正和优化PubMed高级检索式。'},
                    {'role': 'user', 'content': second_round_prompt}
                ],
                timeout=timeout
            )
            
            final_enhanced_query = second_response.choices[0].message.content.strip()
            
            # 清理最终结果
            final_enhanced_query = final_enhanced_query.replace('简化后的检索式:', '').strip()
            final_enhanced_query = final_enhanced_query.replace('优化后的检索式:', '').strip()
            final_enhanced_query = re.sub(r'^["\'`]|["\'`]$', '', final_enhanced_query)  # 移除首尾引号
            
            # 最终语法修复
            final_enhanced_query = fix_query_syntax(final_enhanced_query, self.verbose)
            
            # 检查检索式的有效性
            if "MeSH" not in final_enhanced_query and "All Fields" not in final_enhanced_query:
                # 如果没有包含MeSH或All Fields，转换为更通用的格式
                safe_print("警告: 检索式缺少全局字段，将添加[All Fields]以确保检索有效", self.verbose)
                final_enhanced_query = f'"{original_query}"[MeSH Terms] OR "{original_query}"[All Fields]'
            
            # 检查检索式长度
            if len(final_enhanced_query) > 200:
                safe_print("警告: 检索式过长，可能过于复杂。考虑手动简化检索式以提高效率。", self.verbose)
            
            safe_print(f"润色完成。原始搜索词: '{original_query}'", True)
            safe_print(f"优化后的检索式: '{final_enhanced_query}'", True)
            
            return final_enhanced_query
            
        except Exception as e:
            safe_print(f"润色搜索词失败: {e}", True)
            safe_print("将使用安全的基本检索式", True)
            # 出错时返回一个安全的基本检索式，而不是原始查询
            safe_query = f'"{original_query}"[MeSH Terms] OR "{original_query}"[All Fields]'
            safe_print(f"使用基本检索式: '{safe_query}'", True)
            return safe_query
