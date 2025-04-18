"""
文献内容理解增强工具
读取CSV文件中的文献数据，调用AI对标题、关键词和摘要进行翻译和优化,
并将结果输出到新的CSV文件中。
"""
import os
import csv
import time
import argparse
import sys
from datetime import datetime

# 导入错误处理工具和翻译核心模块
from error_handler import ErrorTracker, safe_print, safe_file_operation
from llm_translator import LLMTranslator

# 不直接将LLMTranslator作为别名，而是创建一个适配器类
# LiteratureTranslator = LLMTranslator

# 尝试导入日志工具
try:
    from log_utils import init_logger
except ImportError:
    def init_logger(*args, **kwargs):
        pass

class LiteratureTranslator:
    """文献翻译工具（向后兼容适配器）"""
    
    def __init__(self, config_file="pub.txt", verbose=False, log_file=None):
        """初始化翻译工具（兼容旧版本接口）
        
        Args:
            config_file: 配置文件路径
            verbose: 是否输出详细日志
            log_file: 日志文件路径
        """
        # 保存参数以备后用
        self.config_file = config_file
        self.verbose = verbose
        self.log_file = log_file
        self.processor = None
        
    def translate_and_enhance(self):
        """翻译并增强文献（兼容旧版本接口）
        
        Returns:
            是否成功
        """
        try:
            # 延迟初始化处理器，避免重复读取配置文件
            if not self.processor:
                self.processor = LiteratureProcessor(
                    config_file=self.config_file, 
                    verbose=self.verbose, 
                    log_file=self.log_file
                )
            return self.processor.process()
        except Exception as e:
            ErrorTracker().track_error(
                "TranslationError", 
                f"翻译文献失败: {str(e)}",
                source="LiteratureTranslator.translate_and_enhance"
            )
            safe_print(f"翻译文献失败: {str(e)}", True)
            return False

class LiteratureProcessor:
    """文献处理工具，整合读取、翻译和输出功能"""
    
    def __init__(self, config_file="pub.txt", verbose=False, log_file=None):
        """初始化文献处理工具
        
        Args:
            config_file: 配置文件路径
            verbose: 是否输出详细日志
            log_file: 日志文件路径
        """
        # 初始化日志系统
        if log_file:
            init_logger(log_file=log_file, verbose=verbose)
            
        self.verbose = verbose
        self.config = self._read_config(config_file)
        self.config['verbose'] = verbose
        
        # 初始化翻译器
        self.translator = LLMTranslator(self.config)
        safe_print("文献内容理解增强工具初始化完成", True)
        
    def _read_config(self, config_file):
        """从配置文件读取设置
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            配置字典
        """
        # 默认配置
        config = {
            'input_llm': 'pubmed_enhanced.csv',
            'output_llm': 'pubmed_enhanced_llm.csv',
            'max_articles': 5,
            'ai_model': 'qwen-plus',
            'ai_timeout': 60,
            'retry_times': 3,
            'api_key': '',
            'api_base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'api_price_input': 20.0,
            'api_price_output': 200.0,
            'optimize_keywords': False,
            'translation_batch_size': 5,
            'max_parallel_requests': 3,
            'use_translation_cache': True,
            'cache_file': 'cache/translation_cache.json',
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                value = parts[1].strip().split('#', 1)[0].strip()
                                
                                if key in config:
                                    # 根据类型转换值
                                    if key in ['max_articles', 'translation_batch_size', 'max_parallel_requests', 'retry_times']:
                                        try:
                                            config[key] = int(value)
                                        except ValueError:
                                            pass
                                    elif key in ['api_price_input', 'api_price_output', 'ai_timeout']:
                                        try:
                                            config[key] = float(value)
                                        except ValueError:
                                            pass
                                    elif key in ['use_translation_cache', 'optimize_keywords']:
                                        config[key] = value.lower() in ['true', 'yes', 'y', '1']
                                    else:
                                        config[key] = value
                
                self._ensure_config(config_file, config)
                safe_print(f"已从 {config_file} 加载配置", self.verbose)
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置", self.verbose)
                self._create_default_config(config_file, config)
        except Exception as e:
            ErrorTracker().track_error(
                "ConfigLoadError", 
                f"读取配置文件出错: {str(e)}",
                source="LiteratureProcessor._read_config"
            )
            safe_print(f"读取配置文件出错: {e}", True)
            safe_print("使用默认设置", True)
        
        return config
    
    def _ensure_config(self, config_file, config):
        """确保配置文件包含所有必要的配置项"""
        # 实现省略
        pass
    
    def _create_default_config(self, config_file, config):
        """创建默认配置文件"""
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write("# 文献内容理解增强工具配置文件\n\n")
                
                f.write("# 输入输出文件\n")
                f.write(f"input_llm={config['input_llm']}\n")
                f.write(f"output_llm={config['output_llm']}\n\n")
                
                f.write("# AI模型设置\n")
                f.write(f"ai_model={config['ai_model']}\n")
                f.write(f"ai_timeout={config['ai_timeout']}\n")
                f.write(f"retry_times={config['retry_times']}\n")
                f.write(f"api_key={config['api_key']}\n")
                f.write(f"api_base_url={config['api_base_url']}\n\n")
                
                f.write("# 成本计算 (元/百万tokens)\n")
                f.write(f"api_price_input={config['api_price_input']}\n")
                f.write(f"api_price_output={config['api_price_output']}\n\n")
                
                f.write("# 翻译设置\n")
                f.write(f"max_articles={config['max_articles']}\n")
                f.write(f"optimize_keywords={'yes' if config['optimize_keywords'] else 'no'}\n")
                f.write(f"translation_batch_size={config['translation_batch_size']}\n")
                f.write(f"max_parallel_requests={config['max_parallel_requests']}\n")
                f.write(f"use_translation_cache={'yes' if config['use_translation_cache'] else 'no'}\n")
                f.write(f"cache_file={config['cache_file']}\n")
                
            safe_print(f"已创建默认配置文件: {config_file}", True)
        except Exception as e:
            ErrorTracker().track_error(
                "ConfigCreateError", 
                f"创建默认配置文件失败: {str(e)}",
                source="LiteratureProcessor._create_default_config"
            )
    
    @safe_file_operation(operation_type="read")
    def read_articles_from_csv(self, file_path, max_articles=None):
        """从CSV文件读取文章
        
        Args:
            file_path: CSV文件路径
            max_articles: 最大读取文章数，None表示读取全部
            
        Returns:
            文章字典列表
        """
        if not os.path.exists(file_path):
            safe_print(f"错误: 输入文件不存在: {file_path}", True)
            return []
            
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                articles = list(reader)
                
            if max_articles is not None:
                articles = articles[:max_articles]
                
            safe_print(f"已从 {file_path} 读取 {len(articles)} 篇文章", True)
            return articles
        except Exception as e:
            ErrorTracker().track_error(
                "CSVReadError", 
                f"读取CSV文件失败: {str(e)}",
                source="LiteratureProcessor.read_articles_from_csv"
            )
            return []
    
    @safe_file_operation(operation_type="write")
    def save_to_csv(self, articles, file_path):
        """保存文章到CSV文件
        
        Args:
            articles: 文章列表
            file_path: 保存路径
            
        Returns:
            是否成功
        """
        if not articles:
            safe_print("警告: 没有文章可保存", True)
            return False
            
        try:
            # 确保输出目录存在
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # 获取所有字段名
            fieldnames = set()
            for article in articles:
                fieldnames.update(article.keys())
            fieldnames = list(fieldnames)
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(articles)
                
            safe_print(f"已保存 {len(articles)} 篇文章到 {file_path}", True)
            return True
        except Exception as e:
            ErrorTracker().track_error(
                "CSVWriteError", 
                f"保存CSV文件失败: {str(e)}",
                source="LiteratureProcessor.save_to_csv"
            )
            return False
    
    def process(self):
        """处理文献，读取、翻译并保存"""
        start_time = time.time()
        safe_print("开始处理文献...", True)
        
        try:
            # 读取文章
            input_file = self.config['input_llm']
            max_articles = self.config['max_articles']
            articles = self.read_articles_from_csv(input_file, max_articles)
            
            if not articles:
                safe_print("错误: 没有文章可处理", True)
                return False
            
            # 翻译文章
            translated_articles = self.translator.translate_batch(
                articles, 
                max_workers=self.config['max_parallel_requests']
            )
            
            # 保存结果到CSV
            output_csv = self.config['output_llm']
            self.save_to_csv(translated_articles, output_csv)
            
            # 打印统计信息
            self.translator.print_statistics()
            
            elapsed = time.time() - start_time
            safe_print(f"文献处理完成，总耗时: {elapsed:.1f}秒", True)
            
            return True
        except Exception as e:
            ErrorTracker().track_error(
                "ProcessError", 
                f"处理文献时发生错误: {str(e)}",
                source="LiteratureProcessor.process"
            )
            safe_print(f"处理文献时发生错误: {str(e)}", True)
            return False


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="文献内容理解增强工具")
    parser.add_argument("-c", "--config", default="pub.txt", help="配置文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出详细日志")
    parser.add_argument("-l", "--log", help="日志文件路径")
    
    args = parser.parse_args()
    
    # 创建处理器并处理
    try:
        processor = LiteratureProcessor(
            config_file=args.config,
            verbose=args.verbose,
            log_file=args.log
        )
        processor.process()
    except Exception as e:
        safe_print(f"处理错误: {e}", True)
        ErrorTracker().track_error(
            "ProcessError", 
            f"处理文献时发生错误: {str(e)}",
            source="main"
        )
        
        # 生成错误报告
        ErrorTracker().generate_report(save_to_file=True)
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
