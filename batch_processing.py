"""
批量处理模块
提供并行处理和批量翻译的功能
"""
import re
import concurrent.futures
from tqdm import tqdm

try:
    from log_utils import get_logger
    
    def safe_print(msg, verbose=True):
        """兼容旧代码，使用日志系统"""
        logger = get_logger()
        if not verbose:
            # 检查是否为重要消息
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告", "初始化"]):
                return
        logger.log(msg, verbose)
except ImportError:
    def safe_print(msg, verbose=True):
        """安全打印，处理编码问题"""
        if not verbose:
            # 检查是否为重要消息
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告", "初始化"]):
                return
                
        try:
            print(msg)
            import sys
            sys.stdout.flush()
        except:
            print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
            import sys
            sys.stdout.flush()


class BatchProcessor:
    """批量处理工具"""
    
    def __init__(self, api_manager, verbose=False):
        """初始化批量处理器
        
        Args:
            api_manager: API管理器实例
            verbose: 是否输出详细日志
        """
        self.api_manager = api_manager
        self.verbose = verbose
    
    def process_batches_parallel(self, articles, batch_size, max_workers, process_func):
        """并行处理多个批次
        
        Args:
            articles: 要处理的文章列表
            batch_size: 每个批次的文章数量
            max_workers: 最大并行工作线程数
            process_func: 处理单个批次的函数
            
        Returns:
            处理后的文章列表
        """
        processed_articles = []
        
        # 将文章分成批次
        batches = []
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            batches.append(batch)
        
        safe_print(f"将 {len(articles)} 篇文章分成 {len(batches)} 个批次处理", True)
        
        # 使用线程池并行处理批次
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for batch in batches:
                future = executor.submit(process_func, batch)
                futures.append(future)
            
            # 使用tqdm显示进度条
            with tqdm(total=len(batches), desc="批量处理", unit="批", gui=False) as pbar: # 明确禁用 GUI 模式
                for future in concurrent.futures.as_completed(futures):
                    try:
                        batch_result = future.result()
                        processed_articles.extend(batch_result)
                        pbar.update(1)
                    except Exception as e:
                        safe_print(f"处理批次时出错: {str(e)}", True)
        
        safe_print(f"批量处理完成 {len(processed_articles)} 篇文章", True)
        return processed_articles
    
    def process_articles_parallel(self, articles, max_workers, process_func):
        """并行处理多篇单独的文章
        
        Args:
            articles: 要处理的文章列表
            max_workers: 最大并行工作线程数
            process_func: 处理单篇文章的函数
            
        Returns:
            处理后的文章列表
        """
        processed_articles = []
        
        # 使用线程池并行处理文章
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for article in articles:
                future = executor.submit(process_func, article)
                futures.append(future)
            
            # 使用tqdm显示进度条
            with tqdm(total=len(articles), desc="翻译文献", unit="篇", gui=False) as pbar: # 明确禁用 GUI 模式
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        processed_articles.append(result)
                        pbar.update(1)
                    except Exception as e:
                        safe_print(f"处理文章时出错: {str(e)}", True)
        
        return processed_articles
    
    def build_batch_translation_prompt(self, batch, api_manager):
        """构建批量翻译的提示词
        
        Args:
            batch: 一批文章
            api_manager: API管理器实例，用于token计数
            
        Returns:
            批量翻译的提示词
        """
        prompt = "请将以下多篇学术文章的标题、摘要和关键词翻译成中文，保持学术专业性。\n\n"
        prompt += "格式要求:\n"
        prompt += "1. 每篇文章的翻译结果放在【文章ID】和【/文章ID】标记之间\n"
        prompt += "2. 每篇文章的翻译包含三部分：标题翻译、摘要翻译和关键词翻译\n"
        prompt += "3. 对于标题和摘要，直接翻译即可\n"
        prompt += "4. 对于关键词，请保持专业性，用分号分隔\n\n"
        
        # 检查批次大小是否过大
        total_tokens = 0
        for article in batch:
            title = article.get('title', '')
            abstract = article.get('abstract', '')
            keywords = article.get('keywords', '')
            
            # 估计token数
            article_tokens = api_manager.count_tokens(title + abstract + keywords)
            total_tokens += article_tokens
        
        # 如果总tokens超过一定阈值，发出警告并分割批次
        if total_tokens > 4000:
            safe_print(f"警告: 输入过长 ({total_tokens} tokens)，尝试分割为多个批次", True)
            
            if len(batch) > 1:
                # 将批次分为两半递归处理
                mid = len(batch) // 2
                first_half = self.build_batch_translation_prompt(batch[:mid], api_manager)
                second_half = self.build_batch_translation_prompt(batch[mid:], api_manager)
                return first_half + "\n\n" + second_half
        
        # 添加文章到提示词
        for i, article in enumerate(batch):
            title = article.get('title', '')
            abstract = article.get('abstract', '')
            keywords = article.get('keywords', '')
            
            prompt += f"文章 【{i+1}】:\n"
            if title:
                prompt += f"标题: {title}\n"
            else:
                prompt += "标题: [无标题]\n"
                
            if abstract:
                # 如果摘要很长，只取前1000个字符
                if len(abstract) > 1000:
                    prompt += f"摘要(节选): {abstract[:1000]}...\n"
                else:
                    prompt += f"摘要: {abstract}\n"
            else:
                prompt += "摘要: [无摘要]\n"
                
            if keywords:
                prompt += f"关键词: {keywords}\n"
            else:
                prompt += "关键词: [无关键词]\n"
                
            prompt += "\n"
        
        return prompt
    
    def extract_batch_translations(self, batch, response):
        """从批量翻译响应中提取翻译结果
        
        Args:
            batch: 原始文章批次
            response: AI响应的翻译结果
            
        Returns:
            翻译后的文章列表
        """
        results = []
        
        # 为每篇文章提取翻译结果
        for i, article in enumerate(batch):
            article_copy = article.copy()
            
            # 提取当前文章的翻译
            pattern = rf"【{i+1}】(.*?)【/{i+1}】"
            matches = re.findall(pattern, response, re.DOTALL)
            
            if matches:
                translation = matches[0].strip()
                
                # 提取标题翻译
                title_match = re.search(r"标题翻译[:：]?\s*(.*?)(?:\n|$)", translation, re.DOTALL)
                if title_match:
                    article_copy['translated_title'] = title_match.group(1).strip()
                else:
                    article_copy['translated_title'] = ""
                
                # 提取摘要翻译
                abstract_match = re.search(r"摘要翻译[:：]?\s*(.*?)(?:\n关键词|$)", translation, re.DOTALL)
                if abstract_match:
                    article_copy['translated_abstract'] = abstract_match.group(1).strip()
                else:
                    article_copy['translated_abstract'] = ""
                
                # 提取关键词翻译
                keywords_match = re.search(r"关键词翻译[:：]?\s*(.*?)(?:\n|$)", translation, re.DOTALL)
                if keywords_match:
                    article_copy['translated_keywords'] = keywords_match.group(1).strip()
                else:
                    article_copy['translated_keywords'] = ""
            else:
                # 如果未找到匹配，保持原始字段
                article_copy['translated_title'] = ""
                article_copy['translated_abstract'] = ""
                article_copy['translated_keywords'] = ""
                
            results.append(article_copy)
        
        return results
    
    def generate_keywords_for_batch(self, articles_batch, api_manager):
        """为一批文章生成关键词
        
        Args:
            articles_batch: 一批需要生成关键词的文章
            api_manager: API管理器实例
            
        Returns:
            已添加关键词的文章列表
        """
        if not articles_batch:
            return []
            
        # 准备提示词
        prompt = "请为以下学术文章批量生成专业关键词，每篇文章生成5-8个关键词。\n\n"
        prompt += "格式要求:\n"
        prompt += "1. 同时提供英文关键词和中文翻译，格式为 '英文关键词 (中文翻译)'\n"
        prompt += "2. 每篇文章的关键词之间用分号隔开\n"
        prompt += "3. 每篇文章的关键词集合放在【文章ID】关键词集合【/文章ID】之间\n\n"
        
        for i, article in enumerate(articles_batch):
            prompt += f"文章 【{i+1}】:\n"
            prompt += f"标题: {article.get('title', '无标题')}\n"
            
            # 如果摘要太长，截取前500个字符
            abstract = article.get('abstract', '')
            if abstract:
                if len(abstract) > 500:
                    prompt += f"摘要(节选): {abstract[:500]}...\n\n"
                else:
                    prompt += f"摘要: {abstract}\n\n"
            else:
                prompt += "摘要: 无\n\n"
                
        # 调用API
        response = api_manager.call_ai_api(prompt)
        
        # 处理返回的关键词
        return self.extract_batch_keywords(articles_batch, response)
    
    def extract_batch_keywords(self, articles_batch, response):
        """从API响应中提取关键词并添加到文章中
        
        Args:
            articles_batch: 原始文章批次
            response: AI生成的关键词响应
            
        Returns:
            添加了关键词的文章批次
        """
        result_articles = []
        
        for i, article in enumerate(articles_batch):
            article_copy = article.copy()
            
            # 提取当前文章的关键词
            pattern = rf"【{i+1}】(.*?)【/{i+1}】"
            matches = re.findall(pattern, response, re.DOTALL)
            
            if matches:
                # 清理提取的关键词文本
                keywords_text = matches[0].strip()
                # 删除可能的"关键词："前缀
                keywords_text = re.sub(r'^.*?关键词[:：]\s*', '', keywords_text)
                # 标记为AI生成
                ai_keywords = f"[AI生成] {keywords_text}"
                article_copy['keywords'] = ai_keywords
                
                safe_print(f"为文章生成关键词: {ai_keywords}", self.verbose)
            else:
                # 如果匹配失败，添加一个通用标记
                article_copy['keywords'] = "[AI生成] English keywords not available (无法生成关键词)"
                safe_print(f"无法为文章提取关键词", self.verbose)
            
            result_articles.append(article_copy)
            
        return result_articles
