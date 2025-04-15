"""
文献翻译核心模块
提供文献内容翻译、理解和处理的核心功能
"""
import os
import time
import json
import concurrent.futures
from tqdm import tqdm
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    print("警告: OpenAI模块未安装，将无法使用AI功能")
    OpenAI = None

try:
    import tiktoken
except ImportError:
    tiktoken = None

# 导入错误处理工具
from error_handler import retry, safe_file_operation, ErrorTracker, safe_print

class TranslationCache:
    """翻译缓存，避免重复翻译"""
    
    def __init__(self, cache_file="cache/translation_cache.json", max_size=1000):
        """初始化缓存
        
        Args:
            cache_file: 缓存文件路径
            max_size: 最大缓存条目数
        """
        self.cache_file = cache_file
        self.max_size = max_size
        self.cache = {}
        self._ensure_cache_dir()
        self.load_cache()
        
    def _ensure_cache_dir(self):
        """确保缓存目录存在"""
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        
    @safe_file_operation(operation_type="read")
    def load_cache(self):
        """从文件加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                safe_print(f"已从 {self.cache_file} 加载 {len(self.cache)} 条翻译缓存", False)
        except Exception as e:
            ErrorTracker().track_error(
                "CacheLoadError", 
                f"加载翻译缓存失败: {str(e)}",
                source="TranslationCache.load_cache"
            )
            self.cache = {}
            
    @safe_file_operation(operation_type="write")
    def save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            ErrorTracker().track_error(
                "CacheSaveError", 
                f"保存翻译缓存失败: {str(e)}",
                source="TranslationCache.save_cache"
            )
            
    def get(self, text, content_type=''):
        """获取缓存内容
        
        Args:
            text: 原文
            content_type: 内容类型，如"标题"、"摘要"、"关键词"
            
        Returns:
            缓存的翻译结果或None
        """
        import hashlib
        # 生成缓存键
        text_with_type = f"{content_type}:{text}"
        key = hashlib.md5(text_with_type.encode('utf-8')).hexdigest()
        return self.cache.get(key)
            
    def set(self, text, translation, content_type=''):
        """设置缓存内容
        
        Args:
            text: 原文
            translation: 翻译结果
            content_type: 内容类型，如"标题"、"摘要"、"关键词"
        """
        import hashlib
        # 生成缓存键
        text_with_type = f"{content_type}:{text}"
        key = hashlib.md5(text_with_type.encode('utf-8')).hexdigest()
        
        # 如果缓存已满，删除最早的项
        if len(self.cache) >= self.max_size:
            # 创建排序后的键列表
            keys = list(self.cache.keys())
            # 删除前10%的缓存项
            for old_key in keys[:max(1, int(self.max_size * 0.1))]:
                self.cache.pop(old_key, None)
                
        self.cache[key] = translation


class LLMTranslator:
    """文献内容翻译工具"""
    
    def __init__(self, config):
        """初始化翻译工具
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.verbose = config.get('verbose', False)
        self.client = self._init_ai_client()
        
        # 统计数据
        self.translation_count = 0
        self.total_tokens = {'input': 0, 'output': 0}
        self.start_time = datetime.now()
        
        # 初始化缓存
        if config.get('use_translation_cache', True):
            cache_file = config.get('cache_file', 'cache/translation_cache.json')
            self.cache = TranslationCache(cache_file=cache_file)
        else:
            self.cache = None
            
        # 初始化token计数器
        if tiktoken:
            try:
                self.encoding = tiktoken.encoding_for_model(config.get('ai_model', 'gpt-3.5-turbo'))
            except:
                try:
                    self.encoding = tiktoken.get_encoding("cl100k_base")
                except:
                    self.encoding = None
        else:
            self.encoding = None
                    
    def _init_ai_client(self):
        """初始化AI客户端"""
        api_key = self.config.get('api_key', '')
        api_base_url = self.config.get('api_base_url', '')
        
        if not api_key:
            api_key = os.getenv("DASHSCOPE_API_KEY", '')
        
        if not api_key:
            safe_print("警告: 未找到API密钥，无法使用翻译功能", True)
            return None
            
        if not OpenAI:
            safe_print("错误: OpenAI模块未安装，无法创建客户端", True)
            return None
            
        try:
            client = OpenAI(
                api_key=api_key,
                base_url=api_base_url
            )
            safe_print("AI客户端初始化成功", self.verbose)
            return client
        except Exception as e:
            ErrorTracker().track_error(
                "ClientInitError", 
                f"初始化AI客户端失败: {str(e)}",
                source="LLMTranslator._init_ai_client"
            )
            return None
    
    def count_tokens(self, text):
        """计算文本的token数量"""
        if not text:
            return 0
            
        try:
            if self.encoding:
                return len(self.encoding.encode(text))
            else:
                # 简单估算
                return len(text) // 4
        except Exception as e:
            return len(text) // 4
            
    @retry(max_attempts=3, delay=1, backoff=2)
    def call_llm_api(self, messages, temperature=0.3):
        """调用LLM API
        
        Args:
            messages: 消息列表，包含角色和内容
            temperature: 温度参数
            
        Returns:
            API响应内容
        """
        if not self.client:
            return "错误: AI客户端未初始化"
            
        model = self.config.get('ai_model', 'qwen-turbo')
        timeout = self.config.get('ai_timeout', 60)
        
        # 计算输入tokens
        input_tokens = sum(self.count_tokens(msg['content']) for msg in messages)
        self.total_tokens['input'] += input_tokens
        
        try:
            start_time = time.time()
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=timeout + (input_tokens / 1000) * 10  # 动态超时
            )
            
            content = response.choices[0].message.content
            
            # 计算输出tokens
            output_tokens = self.count_tokens(content)
            self.total_tokens['output'] += output_tokens
            
            elapsed = time.time() - start_time
            safe_print(f"API调用完成，耗时: {elapsed:.2f}秒，输入: {input_tokens} tokens，输出: {output_tokens} tokens", self.verbose)
            
            return content
        except Exception as e:
            ErrorTracker().track_error(
                "APICallError", 
                f"调用API失败: {str(e)}",
                source="LLMTranslator.call_llm_api"
            )
            raise
            
    def translate_text(self, text, content_type="", system_prompt=None):
        """翻译文本内容
        
        Args:
            text: 要翻译的文本
            content_type: 内容类型，如"标题"、"摘要"、"关键词"
            system_prompt: 系统提示，如果为None则使用默认提示
            
        Returns:
            翻译后的文本
        """
        if not text or not text.strip():
            return ""
            
        # 检查缓存
        if self.cache:
            cached = self.cache.get(text, content_type)
            if cached:
                return cached
                
        # 默认系统提示
        if system_prompt is None:
            system_prompt = "你是一个专业的学术翻译助手，擅长将英文学术文献准确翻译为符合中文学术习惯的表述。"
            
        # 构建用户提示
        user_prompt = f"请将以下{content_type or '文本'}翻译成中文，保持学术专业性:\n\n{text}"
        
        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 调用API
        translation = self.call_llm_api(messages)
        
        # 后处理翻译结果
        translation = self._clean_translation(translation)
        
        # 保存到缓存
        if self.cache:
            self.cache.set(text, translation, content_type)
            
        self.translation_count += 1
        
        return translation
        
    def _clean_translation(self, text):
        """清理翻译结果，删除多余的内容"""
        if not text:
            return ""
            
        # 删除"翻译:"、"翻译结果:"等前缀
        import re
        text = re.sub(r'^.*?[:：]\s*', '', text)
        
        # 删除引号
        text = re.sub(r'^[\s"「\']+|[\s"」\']+$', '', text)
        
        return text.strip()
        
    def translate_batch(self, articles, max_workers=None):
        """批量翻译文章
        
        Args:
            articles: 文章列表
            max_workers: 最大并行工作线程数
            
        Returns:
            翻译后的文章列表
        """
        if not articles:
            return []
            
        # 设置默认并行数
        if max_workers is None:
            max_workers = min(self.config.get('max_parallel_requests', 3), 5)
            
        safe_print(f"开始批量翻译 {len(articles)} 篇文章，最大并行数: {max_workers}", True)
        
        translated_articles = []
        
        # 使用线程池并行翻译
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有翻译任务
            future_to_article = {
                executor.submit(self.translate_article, article): article
                for article in articles
            }
            
            # 使用tqdm显示进度
            with tqdm(total=len(articles), desc="翻译进度") as pbar:
                for future in concurrent.futures.as_completed(future_to_article):
                    try:
                        translated = future.result()
                        translated_articles.append(translated)
                    except Exception as e:
                        # 记录错误但继续处理其他文章
                        article = future_to_article[future]
                        article_id = article.get('id', 'unknown')
                        ErrorTracker().track_error(
                            "TranslationError", 
                            f"翻译文章 {article_id} 失败: {str(e)}",
                            source="LLMTranslator.translate_batch"
                        )
                        # 添加原始文章（未翻译）
                        translated_articles.append(article)
                    finally:
                        pbar.update(1)
        
        # 保存缓存
        if self.cache:
            self.cache.save_cache()
            
        return translated_articles
        
    def translate_article(self, article):
        """翻译单篇文章
        
        Args:
            article: 文章字典
            
        Returns:
            翻译后的文章字典
        """
        # 创建文章的副本
        translated = article.copy()
        
        # 获取原始内容
        title = article.get('title', '')
        abstract = article.get('abstract', '')
        keywords = article.get('keywords', '')
        
        # 翻译标题
        if title:
            translated['translated_title'] = self.translate_text(title, "标题")
            
        # 翻译摘要
        if abstract:
            translated['translated_abstract'] = self.translate_text(abstract, "摘要")
            
        # 翻译或优化关键词
        if keywords:
            if self.config.get('optimize_keywords', False):
                translated['translated_keywords'] = self.optimize_keywords(keywords)
            else:
                translated['translated_keywords'] = self.translate_text(keywords, "关键词")
        else:
            # 如果没有关键词，尝试从标题和摘要中提取关键词
            if title or abstract:
                safe_print(f"文章缺少关键词，尝试从标题和摘要中提取...", self.verbose)
                translated['translated_keywords'] = self.generate_keywords_from_content(title, abstract)
                # 如果生成了关键词，同步回英文关键词字段
                if translated.get('translated_keywords'):
                    translated['keywords'] = "(Auto-generated) " + translated.get('translated_keywords')
                
        return translated
    
    def generate_keywords_from_content(self, title, abstract):
        """从标题和摘要中提取关键词
        
        Args:
            title: 文章标题
            abstract: 文章摘要
            
        Returns:
            生成的关键词
        """
        if not title and not abstract:
            return ""
        
        # 构建用于提取关键词的内容
        content = ""
        if title:
            content += f"标题: {title}\n\n"
        if abstract:
            content += f"摘要: {abstract}\n\n"
            
        # 构建系统提示
        system_prompt = "你是一位擅长文献分析的学术助手，专精于从学术文章中提取关键词和主题。"
        
        # 构建用户提示
        user_prompt = f"""请从以下学术文献内容中提取5-7个关键词:

{content}

要求:
1. 识别文本中最重要和最具代表性的概念和术语
2. 按重要性排序关键词
3. 将关键词翻译为中文
4. 使用分号分隔每个关键词
5. 添加1-2个学科分类词在最后（如"生物信息学"、"分子生物学"等）
6. 只返回关键词列表，不要添加任何解释或前缀

"""
        
        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # 调用API
            result = self.call_llm_api(messages, temperature=0.4)
            
            # 清理结果
            result = self._clean_translation(result)
            
            safe_print(f"已为文章自动生成关键词: {result}", self.verbose)
            return result
        except Exception as e:
            ErrorTracker().track_error(
                "KeywordGenerationError", 
                f"生成关键词失败: {str(e)}",
                source="LLMTranslator.generate_keywords_from_content"
            )
            return "自动生成关键词失败"
    
    def optimize_keywords(self, keywords):
        """优化和翻译关键词
        
        Args:
            keywords: 关键词字符串
            
        Returns:
            优化后的关键词字符串
        """
        if not keywords or not keywords.strip():
            return ""
            
        # 构建用户提示
        system_prompt = "你是一个医学术语专家，擅长标准化和优化医学关键词。"
        user_prompt = f"""请对以下医学文献的关键词进行优化和标准化处理:

原始关键词: {keywords}

要求：
1. 将英文关键词翻译为准确的中文术语
2. 保留专业术语的规范性和学术性
3. 对相近概念进行合并和标准化
4. 按照重要性排序，最重要的关键词放在最前面
5. 以分号分隔各个关键词
6. 如果能判断文献的学科分类，请在末尾添加1-2个学科分类词（如"肿瘤学"、"心血管学"、"神经科学"等）

只需返回处理后的关键词，不需要任何解释或其他内容。
"""
        
        # 构建消息列表
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # 调用API
        result = self.call_llm_api(messages)
        
        # 清理结果
        result = self._clean_translation(result)
        
        return result
        
    def get_statistics(self):
        """获取统计信息"""
        try:
            runtime = (datetime.now() - self.start_time).total_seconds() / 60.0
            
            # 计算成本（按每百万tokens计费）
            api_price_input = self.config.get('api_price_input', 20.0)
            api_price_output = self.config.get('api_price_output', 200.0)
            
            # 转换为每百万token的价格（配置文件通常使用每百万token价格）
            input_cost = self.total_tokens['input'] * api_price_input / 1000000
            output_cost = self.total_tokens['output'] * api_price_output / 1000000
            total_cost = input_cost + output_cost
            
            # 计算每分钟处理的token数量，避免除零错误
            tokens_per_minute = 0
            if runtime > 0:
                tokens_per_minute = sum(self.total_tokens.values()) / max(runtime, 0.1)
            
            return {
                'translation_count': self.translation_count,
                'input_tokens': self.total_tokens['input'],
                'output_tokens': self.total_tokens['output'],
                'total_tokens': sum(self.total_tokens.values()),
                'runtime_minutes': runtime,
                'estimated_cost': total_cost,
                'tokens_per_minute': tokens_per_minute
            }
        except Exception as e:
            # 异常保护，确保统计功能故障不影响主程序
            ErrorTracker().track_error(
                "StatisticsError", 
                f"生成统计信息失败: {str(e)}",
                source="LLMTranslator.get_statistics"
            )
            # 返回默认值
            return {
                'translation_count': self.translation_count,
                'input_tokens': 0,
                'output_tokens': 0,
                'total_tokens': 0,
                'runtime_minutes': 0,
                'estimated_cost': 0,
                'tokens_per_minute': 0
            }
        
    def print_statistics(self):
        """打印统计信息"""
        stats = self.get_statistics()
        
        safe_print("\n" + "="*50, True)
        safe_print("翻译统计信息:", True)
        safe_print(f"总翻译数量: {stats['translation_count']} 条", True)
        safe_print(f"总运行时间: {stats['runtime_minutes']:.2f} 分钟", True)
        safe_print(f"输入tokens: {stats['input_tokens']:,}", True)
        safe_print(f"输出tokens: {stats['output_tokens']:,}", True)
        safe_print(f"总tokens: {stats['total_tokens']:,}", True)
        safe_print(f"平均处理速度: {stats['tokens_per_minute']:.1f} tokens/分钟", True)
        safe_print(f"估计成本: ¥{stats['estimated_cost']:.4f}", True)
        safe_print("="*50, True)
