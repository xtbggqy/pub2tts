"""
文本处理工具模块
提供文本处理、翻译、文件输出等功能
"""
import os
import csv
import re

try:
    from log_utils import get_logger
    
    def safe_print(msg, verbose=True):
        """兼容旧代码，使用日志系统"""
        logger = get_logger()
        if not verbose:
            # 检查是否为重要消息
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告"]):
                return
        logger.log(msg, verbose)
except ImportError:
    def safe_print(msg, verbose=True):
        """安全打印，处理编码问题"""
        if not verbose:
            # 检查是否为重要消息
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告"]):
                return
                
        try:
            print(msg)
            import sys
            sys.stdout.flush()
        except:
            print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
            import sys
            sys.stdout.flush()


class TextProcessor:
    """文本处理工具"""
    
    def __init__(self, cache, api_manager, verbose=False):
        """初始化文本处理器
        
        Args:
            cache: 翻译缓存实例
            api_manager: API管理器实例
            verbose: 是否输出详细日志
        """
        self.cache = cache
        self.api_manager = api_manager
        self.verbose = verbose
    
    def translate_text(self, content_type, text, use_cache=True):
        """翻译单个文本内容
        
        Args:
            content_type: 内容类型，如"标题"、"摘要"、"关键词"
            text: 要翻译的文本
            use_cache: 是否使用缓存
            
        Returns:
            翻译后的文本
        """
        if not text.strip():
            return ""
            
        # 检查缓存
        if use_cache:
            cache_key = self.cache.get_hash(text, content_type)
            cached_result = self.cache.get(cache_key)
            
            if cached_result:
                safe_print(f"从缓存获取{content_type}的翻译", self.verbose)
                return cached_result
        
        # 构建提示词
        prompt = f"请将以下{content_type}翻译成中文，保持学术专业性:\n\n{text}"
        
        # 如果是关键词，添加特殊指令
        if content_type == "关键词":
            prompt += "\n\n请保持关键词的专业性和准确性，并用分号分隔不同的关键词。"
        
        # 调用API
        translation = self.api_manager.call_ai_api(prompt)
        
        # 后处理：删除可能的多余回复
        translation = re.sub(r'^.*?[:：]\s*', '', translation)  # 移除"翻译结果："等前缀
        translation = re.sub(r'^\s*[""「]\s*|\s*[""」]\s*$', '', translation)  # 移除引号
        
        # 保存到缓存
        if use_cache and translation:
            cache_key = self.cache.get_hash(text, content_type)
            self.cache.set(cache_key, translation)
        
        return translation.strip()
    
    def optimize_keywords(self, keywords, use_cache=True):
        """优化和翻译关键词
        
        Args:
            keywords: 原始关键词字符串
            use_cache: 是否使用缓存
            
        Returns:
            优化后的关键词字符串
        """
        if not keywords.strip():
            return ""
            
        # 检查缓存
        if use_cache:
            cache_key = self.cache.get_hash(keywords, "keywords_optimize")
            cached_result = self.cache.get(cache_key)
            
            if cached_result:
                safe_print(f"从缓存获取关键词的优化结果", self.verbose)
                return cached_result
        
        # 构建优化提示词
        prompt = "请对以下医学文献的关键词进行优化和标准化处理:\n\n"
        prompt += "原始关键词: " + keywords + "\n\n"
        prompt += "要求：\n"
        prompt += "1. 将英文关键词翻译为准确的中文术语\n"
        prompt += "2. 保留专业术语的规范性和学术性\n"
        prompt += "3. 对相近概念进行合并和标准化\n"
        prompt += "4. 按照重要性排序，最重要的关键词放在最前面\n"
        prompt += "5. 以分号分隔各个关键词\n"
        prompt += '6. 如果能判断文献的学科分类，请在末尾添加1-2个学科分类词（如"肿瘤学"、"心血管学"、"神经科学"等）\n\n'
        prompt += "只需返回处理后的关键词，不需要任何解释或其他内容。"
        
        # 调用API
        result = self.api_manager.call_ai_api(prompt)
        
        # 清理结果，删除额外说明文字
        result = re.sub(r'^.*?关键词[:：]\s*', '', result)  # 删除"处理后的关键词:"等前缀
        result = re.sub(r'^处理后的关键词[:：]\s*', '', result)
        result = re.sub(r'^优化后的关键词[:：]\s*', '', result)
        
        # 保存到缓存
        if use_cache and result:
            cache_key = self.cache.get_hash(keywords, "keywords_optimize")
            self.cache.set(cache_key, result)
        
        return result.strip()
    
    def prepare_tts_data(self, article):
        """准备文本到语音合成的数据
        
        Args:
            article: 增强后的文章
            
        Returns:
            TTS用的文本字符串
        """
        result = ""
        
        # 添加标题
        translated_title = article.get('translated_title', '')
        if translated_title:
            result += f"标题：{translated_title}\n\n"
        
        # 添加关键词
        translated_keywords = article.get('translated_keywords', '')
        if translated_keywords:
            result += f"关键词：{translated_keywords}\n\n"
        
        # 添加摘要
        translated_abstract = article.get('translated_abstract', '')
        if translated_abstract:
            result += f"摘要：{translated_abstract}\n\n"
        
        # 添加分隔符
        result += "=====================================\n\n"
        
        return result


class FileHandler:
    """文件处理工具"""
    
    def __init__(self, verbose=False):
        """初始化文件处理器
        
        Args:
            verbose: 是否输出详细日志
        """
        self.verbose = verbose
    
    def save_to_csv(self, articles, output_file):
        """将处理后的文章保存到CSV文件
        
        Args:
            articles: 处理后的文章列表
            output_file: 输出文件路径
            
        Returns:
            是否成功保存
        """
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 获取所有列名
            fieldnames = []
            for article in articles:
                for key in article.keys():
                    if key not in fieldnames:
                        fieldnames.append(key)
            
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(articles)
                
            safe_print(f"成功保存 {len(articles)} 篇文章到 {output_file}", True)
            return True
        except Exception as e:
            safe_print(f"保存CSV文件失败: {str(e)}", True)
            return False
    
    def save_to_txt(self, txt_output, output_file):
        """将处理后的TTS文本保存到TXT文件
        
        Args:
            txt_output: 待保存的文本列表
            output_file: 输出文件路径
            
        Returns:
            是否成功保存
        """
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                for text in txt_output:
                    f.write(text)
                    
            safe_print(f"成功保存翻译结果到 {output_file}", True)
            return True
        except Exception as e:
            safe_print(f"保存TXT文件失败: {str(e)}", True)
            return False
