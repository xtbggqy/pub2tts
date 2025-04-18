"""
期刊信息增强处理工具
读取和处理期刊影响因子和分区信息，为文献添加这些信息，并支持多种排序方式
"""
import os
import json
import csv
import re
import time
import concurrent.futures
from datetime import datetime
from tqdm import tqdm
import threading
import traceback  # 添加导入

# 导入日志工具，如果可用
try:
    from log_utils import get_logger, init_logger
    
    def safe_print(msg, verbose=True):
        """兼容旧代码，使用日志系统"""
        logger = get_logger()
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

# 导入可视化模块（如果可用）
try:
    from journal_viz import JournalVisualizer
    VISUALIZATION_AVAILABLE = True
except ImportError:
    VISUALIZATION_AVAILABLE = False

class JournalEnhancer:
    def __init__(self, config_file="pub.txt", verbose=False, log_file=None):
        """初始化期刊信息增强处理工具
        
        Args:
            config_file: 配置文件路径
            verbose: 是否输出详细日志
            log_file: 日志文件路径，如果为None则不记录到文件
        """
        # 确保先设置verbose属性，因为_read_config和_load_journal_data会使用它
        self.verbose = verbose  # 添加详细日志开关
        self.config_file = config_file  # 存储配置文件路径，供子组件使用
        
        # 如果提供了log_file，初始化日志系统（如果导入了log_utils）
        if log_file and 'init_logger' in globals():
            init_logger(log_file=log_file, verbose=verbose)
        
        # 缓存相关变量
        self.journal_name_cache = {}  # 期刊名称匹配缓存
        self.journal_norm_cache = {}  # 期刊名称标准化缓存
        self.similarity_cache = {}    # 相似度缓存
        self.lock = threading.RLock()  # 多线程操作锁
        
        # 然后再读取配置和加载期刊数据
        self.config = self._read_config(config_file)
        
        # 计时加载期刊数据
        start_time = time.time()
        self.journal_data = self._load_journal_data()
        load_time = time.time() - start_time
        safe_print(f"期刊信息加载完成，用时{load_time:.2f}秒，共加载 {len(self.journal_data)} 本期刊信息", True)
        
        # 预处理配置参数
        self._init_parallel_config()
    
    def _init_parallel_config(self):
        """初始化并行处理配置"""
        # 设置默认的并行参数
        self.max_workers = min(32, os.cpu_count() * 2 if os.cpu_count() else 8)
        self.batch_size = 50  # 每个批次处理的文章数
        
        # 尝试从配置中读取
        try:
            # 从配置文件中读取并行处理参数
            if 'journal_max_workers' in self.config:
                self.max_workers = int(self.config['journal_max_workers'])
            if 'journal_batch_size' in self.config:
                self.batch_size = int(self.config['journal_batch_size'])
        except (ValueError, TypeError):
            pass
            
        safe_print(f"期刊信息增强处理工具并行配置：最大工作线程数={self.max_workers}，批处理大小={self.batch_size}", self.verbose)
    
    def _read_config(self, config_file):
        """从配置文件读取设置"""
        config = {
            'journal_data_path': "D:\\zotero\\zotero_file\\zoterostyle.json",
            'article_sort': 'impact_factor',  # 默认按影响因子排序
            'output_sort': 'pubmed_enhanced.csv',  # 改为output_sort
            'input_sort': 'pubmed_results.csv',     # 改为input_sort
            'viz_enabled': True,  # 默认启用可视化
            'journal_max_workers': 16,  # 默认并行线程数
            'journal_batch_size': 50,   # 默认批处理大小
            'journal_cache_enabled': True,  # 默认启用缓存
            'journal_preload_similarity': True,  # 默认预加载期刊数据
            'journal_match_threshold': 0.7,  # 默认名称匹配阈值
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                key, value = parts
                                key = key.strip()
                                value = value.split('#', 1)[0].strip()  # 移除注释
                                
                                # 标准参数
                                if key in config:
                                    # 处理数值型或布尔型参数
                                    if key in ['journal_max_workers', 'journal_batch_size']:
                                        try:
                                            config[key] = int(value)
                                        except ValueError:
                                            pass
                                    elif key in ['journal_cache_enabled', 'journal_preload_similarity', 'viz_enabled']:
                                        config[key] = value.lower() in ['true', 'yes', 'y', '1']
                                    elif key == 'journal_match_threshold':
                                        try:
                                            config[key] = float(value)
                                        except ValueError:
                                            pass
                                    else:
                                        config[key] = value
                
                # 检查是否缺少配置项
                self._check_and_update_config(config_file, config)
                safe_print(f"已从 {config_file} 加载排序和期刊数据配置", self.verbose)
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置", self.verbose)
                # 在现有配置文件中添加新的排序和期刊数据配置
                self._update_config_file(config_file, config)
        except Exception as e:
            safe_print(f"读取配置文件出错: {e}", self.verbose)
            safe_print("使用默认设置", self.verbose)
        
        return config
    
    def _update_config_file(self, config_file, config):
        """更新现有配置文件，添加排序和期刊数据相关设置"""
        try:
            # 检查文件是否存在
            if os.path.exists(config_file):
                # 读取现有配置内容
                with open(config_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # 检查是否已有这些配置项
                existing_keys = set()
                for line in lines:
                    if '=' in line and not line.strip().startswith('#'):
                        key = line.split('=', 1)[0].strip()
                        existing_keys.add(key)
                
                # 准备新的配置项
                new_config = []
                
                # 检查是否需要添加期刊增强配置区块
                needs_section = any(k for k in [
                    'journal_data_path', 'article_sort', 'output_sort', 'input_sort',
                    'journal_max_workers', 'journal_batch_size', 'journal_cache_enabled',
                    'journal_preload_similarity', 'journal_match_threshold'
                ] if k not in existing_keys)
                
                if needs_section:
                    new_config.append("\n# 期刊信息和排序高级设置\n")
                    
                # 添加缺失的基本配置
                if 'journal_data_path' not in existing_keys:
                    new_config.append(f"# 期刊数据文件路径\njournal_data_path={config['journal_data_path']}\n\n")
                if 'article_sort' not in existing_keys:
                    new_config.append("# 文章排序方式选项:\n")
                    new_config.append("# - impact_factor: 按影响因子排序(从高到低)\n")
                    new_config.append("# - journal: 按期刊名称排序(字母顺序)\n")
                    new_config.append("# - quartile: 按分区排序(Q1>Q2>Q3>Q4),同分区内按影响因子\n")
                    new_config.append("# - date: 按发表日期排序(从新到旧)\n")
                    new_config.append(f"article_sort={config['article_sort']}\n\n")
                if 'input_sort' not in existing_keys:
                    new_config.append("# 输入文件路径(排序前的文献数据)\n")
                    new_config.append(f"input_sort={config['input_sort']}\n\n")
                if 'output_sort' not in existing_keys:
                    new_config.append("# 输出文件路径(排序后的文献数据)\n")
                    new_config.append(f"output_sort={config['output_sort']}\n\n")
                if 'viz_enabled' not in existing_keys:
                    new_config.append("# 是否启用可视化功能(yes/no)\n")
                    new_config.append(f"viz_enabled={'yes' if config['viz_enabled'] else 'no'}\n\n")
                
                # 添加高级性能配置
                if 'journal_max_workers' not in existing_keys:
                    new_config.append("# 期刊信息处理并行线程数 (更高的值可能提高速度，但会增加内存使用)\n")
                    new_config.append(f"journal_max_workers={config['journal_max_workers']}\n\n")
                if 'journal_batch_size' not in existing_keys:
                    new_config.append("# 期刊信息处理批量大小\n")
                    new_config.append(f"journal_batch_size={config['journal_batch_size']}\n\n")
                if 'journal_cache_enabled' not in existing_keys:
                    new_config.append("# 是否启用期刊匹配缓存 (提高速度但使用更多内存)\n")
                    new_config.append(f"journal_cache_enabled={'yes' if config['journal_cache_enabled'] else 'no'}\n\n")
                if 'journal_preload_similarity' not in existing_keys:
                    new_config.append("# 是否预加载期刊名称相似度数据 (提高速度但延长启动时间)\n")
                    new_config.append(f"journal_preload_similarity={'yes' if config['journal_preload_similarity'] else 'no'}\n\n")
                if 'journal_match_threshold' not in existing_keys:
                    new_config.append("# 期刊名称匹配阈值 (0-1之间，越高匹配越精确但可能漏掉部分期刊)\n")
                    new_config.append(f"journal_match_threshold={config['journal_match_threshold']}\n\n")
                
                # 只有当需要添加新配置时才写入文件
                if new_config:
                    with open(config_file, 'a', encoding='utf-8') as f:
                        f.writelines(new_config)
                        safe_print(f"已向配置文件 {config_file} 添加期刊和排序高级设置", self.verbose)
            else:
                # 如果文件不存在，创建一个包含完整配置的新文件
                with open(config_file, 'w', encoding='utf-8') as f:
                    f.write("# PubMed文献增强处理配置\n")
                    f.write("# 使用格式: 参数=值\n\n")
                    f.write("# 期刊数据文件路径\n")
                    f.write(f"journal_data_path={config['journal_data_path']}\n\n")
                    f.write("# 文章排序方式选项:\n")
                    f.write("# - impact_factor: 按影响因子排序(从高到低)\n")
                    f.write("# - journal: 按期刊名称排序(字母顺序)\n")
                    f.write("# - quartile: 按分区排序(Q1>Q2>Q3>Q4),同分区内按影响因子\n")
                    f.write("# - date: 按发表日期排序(从新到旧)\n")
                    f.write(f"article_sort={config['article_sort']}\n\n")
                    f.write("# 输入文件路径(排序前的文献数据)\n")
                    f.write(f"input_sort={config['input_sort']}\n\n")
                    f.write("# 输出文件路径(排序后的文献数据)\n")
                    f.write(f"output_sort={config['output_sort']}\n\n")
                    f.write("# 是否启用可视化功能(yes/no)\n")
                    f.write(f"viz_enabled={'yes' if config['viz_enabled'] else 'no'}\n\n")
                    f.write("# 期刊信息处理高级设置\n")
                    f.write(f"journal_max_workers={config['journal_max_workers']}\n")
                    f.write(f"journal_batch_size={config['journal_batch_size']}\n")
                    f.write(f"journal_cache_enabled={'yes' if config['journal_cache_enabled'] else 'no'}\n")
                    f.write(f"journal_preload_similarity={'yes' if config['journal_preload_similarity'] else 'no'}\n")
                    f.write(f"journal_match_threshold={config['journal_match_threshold']}\n")
                safe_print(f"已创建包含期刊和排序设置的配置文件: {config_file}", self.verbose)
        except Exception as e:
            safe_print(f"更新配置文件出错: {e}", self.verbose)
    
    def _check_and_update_config(self, config_file, config):
        """检查并更新配置文件，检查是否缺少新的高级配置项"""
        self._update_config_file(config_file, config)  # 直接使用更新函数
    
    def _load_journal_data(self):
        """加载期刊影响因子和分区数据"""
        journal_data = {}
        journal_data_path = self.config.get('journal_data_path')
        
        try:
            if os.path.exists(journal_data_path):
                with open(journal_data_path, 'r', encoding='utf-8') as f:
                    journal_data = json.load(f)
                
                # 添加文件内容的调试信息
                total_journals = len(journal_data)
                sample_journals = list(journal_data.keys())[:3]
                safe_print(f"成功加载期刊数据: {journal_data_path}", self.verbose)
                safe_print(f"共加载 {total_journals} 个期刊", self.verbose)
                
                # 检查几个示例期刊的内容格式
                if self.verbose:
                    for journal in sample_journals:
                        if "rank" in journal_data[journal]:
                            rank_data = journal_data[journal]["rank"]
                            safe_print(f"期刊 '{journal}' 的数据结构: {json.dumps(rank_data, ensure_ascii=False)[:200]}", self.verbose)
                            if "sciif" in rank_data:
                                safe_print(f"期刊 '{journal}' 的影响因子: {rank_data['sciif']}", self.verbose)
                            else:
                                safe_print(f"警告: 期刊 '{journal}' 无影响因子字段 'sciif'", self.verbose)
                        else:
                            safe_print(f"警告: 期刊 '{journal}' 无 'rank' 字段", self.verbose)
                
                # 如果配置了预加载相似度数据，则初始化常用期刊的标准化名称
                if self.config.get('journal_preload_similarity', True):
                    safe_print("开始预处理期刊名称数据...", self.verbose)
                    self._preload_journal_names(journal_data)
                    safe_print("期刊名称预处理完成", self.verbose)
            else:
                safe_print(f"期刊数据文件不存在: {journal_data_path}", True)
        except Exception as e:
            safe_print(f"加载期刊数据出错: {e}", True)
            traceback.print_exc()
        
        return journal_data
    
    def _preload_journal_names(self, journal_data):
        """预处理期刊名称，加速后续匹配"""
        try:
            # 为所有期刊名称创建标准化版本
            journal_count = len(journal_data)
            safe_print(f"预处理 {journal_count} 个期刊名称...", self.verbose)
            
            # 使用多线程加速预处理
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, os.cpu_count() * 2 if os.cpu_count() else 8)) as executor:
                # 分批提交任务以减少内存占用
                batch_size = 1000
                for i in range(0, journal_count, batch_size):
                    batch_journals = list(journal_data.keys())[i:i+batch_size]
                    executor.map(self._normalize_journal_name, batch_journals)
            
            safe_print(f"期刊名称预处理完成，共处理 {len(self.journal_norm_cache)} 条规范化名称", self.verbose)
        except Exception as e:
            safe_print(f"期刊名称预处理失败: {e}", self.verbose)
    
    def _normalize_journal_name(self, journal_name):
        """规范化期刊名称，结果存入缓存"""
        if not journal_name:
            return ""
            
        # 检查缓存
        if journal_name in self.journal_norm_cache:
            return self.journal_norm_cache[journal_name]
            
        # 规范化处理：移除特殊字符，统一大小写
        journal_norm = re.sub(r'[^\w\s]', '', journal_name.lower())
        journal_norm = re.sub(r'\s+', ' ', journal_norm).strip()
        
        # 存入缓存
        with self.lock:
            self.journal_norm_cache[journal_name] = journal_norm
            
        return journal_norm
    
    def enhance_articles(self, input_file=None):
        """增强文章信息，添加期刊影响因子和分区"""
        input_file = input_file or self.config.get('input_sort')
        
        if not os.path.exists(input_file):
            safe_print(f"输入文件不存在: {input_file}", True)
            return []
        
        try:
            start_time = time.time()  # 开始计时
            
            # 读取文章数据
            with open(input_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                articles = list(reader)
            
            safe_print(f"成功读取 {len(articles)} 篇文章数据，用时{time.time()-start_time:.2f}秒", True)
            
            # 统计信息初始化
            enhanced_count = 0
            failed_journals = set()
            
            # 使用并行处理增强文章信息
            enhanced_time_start = time.time()
            safe_print(f"开始并行处理文章增强，使用{self.max_workers}个线程，批大小{self.batch_size}...", True)
            
            # 创建进度条
            with tqdm(total=len(articles), desc="增强文章信息", unit="篇", 
                      disable=not self.verbose, # 非详细模式下禁用tqdm
                      leave=False,  # 完成后不留下进度条
                      ncols=80,     # 固定宽度
                      bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]',
                      gui=False) as pbar: # 明确禁用 GUI 模式
                
                # 并行处理文章
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # 分批提交文章，以减少内存占用
                    for i in range(0, len(articles), self.batch_size):
                        batch_articles = articles[i:i+self.batch_size]
                        batch_results = list(executor.map(self._enhance_article, batch_articles))
                        
                        # 更新统计信息
                        for success, journal_name in batch_results:
                            if success:
                                enhanced_count += 1
                            elif journal_name:
                                failed_journals.add(journal_name)
                            
                            # 更新进度条
                            pbar.update(1)
            
            # 统计处理结果
            enhanced_time = time.time() - enhanced_time_start
            match_rate = enhanced_count / len(articles) * 100 if articles else 0
            safe_print(f"并行增强处理完成，用时{enhanced_time:.2f}秒", True)
            safe_print(f"文章总数: {len(articles)}, 成功匹配影响因子: {enhanced_count} ({match_rate:.1f}%)", True)
            if failed_journals:
                safe_print(f"未能匹配影响因子的期刊数量: {len(failed_journals)}", self.verbose)
                if self.verbose:
                    safe_print(f"未匹配期刊示例 (前10个): {list(failed_journals)[:10]}", self.verbose)
            
            # 排序文章
            sort_time_start = time.time()
            sorted_articles = self._sort_articles(articles)
            sort_time = time.time() - sort_time_start
            safe_print(f"文章排序完成，用时{sort_time:.2f}秒", self.verbose)
            
            # 新增：生成期刊数据可视化
            self._generate_visualizations(sorted_articles, input_file)
            
            # 总结性能
            total_time = time.time() - start_time
            safe_print(f"期刊信息增强全部完成，总用时{total_time:.2f}秒", True)
            
            return sorted_articles
            
        except Exception as e:
            safe_print(f"增强文章信息出错: {e}", True)
            traceback.print_exc()
            return []
    
    def _enhance_article(self, article):
        """增强单篇文章的信息，添加期刊影响因子和分区"""
        try:
            journal_name = article.get('journal', '')
            if not journal_name:
                return (False, None)  # 无期刊名称
                
            # 获取期刊信息
            journal_info = self._get_journal_info(journal_name)
            
            if journal_info:
                # 更新文章字典
                for key, value in journal_info.items():
                    article[key] = value
                
                # 验证是否成功匹配影响因子
                if ('impact_factor' in journal_info and 
                    journal_info['impact_factor'] != "未知" and 
                    journal_info['impact_factor']):
                    return (True, journal_name)  # 成功匹配
            
            return (False, journal_name)  # 匹配失败
            
        except Exception as e:
            safe_print(f"处理文章期刊 '{journal_name if 'journal_name' in locals() else "未知"}' 时出错: {e}", self.verbose)
            return (False, journal_name if 'journal_name' in locals() else None)
    
    def _generate_visualizations(self, articles, input_file):
        """生成期刊数据可视化图表（作为独立的图像文件）"""
        # 检查是否启用可视化和是否可用
        if not self.config.get('viz_enabled', True) or not VISUALIZATION_AVAILABLE:
            if not VISUALIZATION_AVAILABLE:
                safe_print("警告: 可视化功能不可用，请安装matplotlib和wordcloud", self.verbose)
            else:
                safe_print("可视化功能已在配置中禁用", self.verbose)
            return

        try:
            # 初始化可视化工具
            visualizer = JournalVisualizer(
                config_file=self.config_file,
                verbose=self.verbose
            )

            # 使用增强后的数据生成可视化图表文件
            safe_print("正在生成期刊数据可视化图表文件...", True)
            output_file = self.config.get('output_sort')  # 使用增强后的文件作为可视化输入

            viz_start_time = time.time()
            # 调用可视化函数，它会读取 output_file 并生成图像
            chart_files = visualizer.visualize_journal_data(output_file)
            viz_time = time.time() - viz_start_time

            if chart_files:
                safe_print(f"成功生成 {len(chart_files)} 个期刊数据图表文件，用时{viz_time:.2f}秒", True)
                for chart in chart_files:
                    safe_print(f"  - {chart}", self.verbose)
            else:
                safe_print("未能生成任何图表文件", self.verbose)
        except Exception as e:
            safe_print(f"期刊可视化生成失败: {e}", self.verbose)
            traceback.print_exc()

    def _get_journal_info(self, journal_name):
        """获取期刊信息，包括影响因子和分区"""
        if not journal_name or not self.journal_data:
            return None
        
        # 检查缓存
        cache_enabled = self.config.get('journal_cache_enabled', True)
        if cache_enabled:
            with self.lock:
                if journal_name in self.journal_name_cache:
                    return self.journal_name_cache[journal_name]
        
        # 规范化期刊名称，移除引号、括号等特殊字符，转为小写
        journal_name_norm = self._normalize_journal_name(journal_name)
        
        # 从期刊名称中移除括号和其中内容
        journal_name_no_paren = re.sub(r'\s*\([^)]*\)', '', journal_name)
        journal_name_no_paren_norm = self._normalize_journal_name(journal_name_no_paren)
        
        # 直接匹配尝试
        if journal_name in self.journal_data:
            result = self._extract_journal_info(journal_name)
            if cache_enabled and result:
                with self.lock:
                    self.journal_name_cache[journal_name] = result
            return result
        
        # 尝试使用去掉括号的名称匹配
        for journal in self.journal_data.keys():
            # 如果去掉括号后的期刊名称完全匹配数据库中的某个期刊
            if journal_name_no_paren.lower() == journal.lower():
                result = self._extract_journal_info(journal)
                if cache_enabled and result:
                    with self.lock:
                        self.journal_name_cache[journal_name] = result
                return result
        
        # 尝试模糊匹配
        match_threshold = self.config.get('journal_match_threshold', 0.7)
        best_match = None
        highest_similarity = match_threshold  # 设置一个相似度阈值
        
        # 遍历所有期刊名称
        for journal in self.journal_data.keys():
            # 规范化数据库中的期刊名称
            journal_norm = self._normalize_journal_name(journal)
            
            # 计算两种名称格式的相似度
            similarity1 = self._calculate_similarity(journal_name_norm, journal_norm)
            similarity2 = self._calculate_similarity(journal_name_no_paren_norm, journal_norm)
            
            # 取较高的相似度
            similarity = max(similarity1, similarity2)
            
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = journal
        
        if best_match:
            result = self._extract_journal_info(best_match)
            if cache_enabled and result:
                with self.lock:
                    self.journal_name_cache[journal_name] = result
            return result
        else:
            # 未找到匹配，也缓存结果避免重复计算
            if cache_enabled:
                with self.lock:
                    self.journal_name_cache[journal_name] = None
            return None
    
    def _extract_journal_info(self, journal_name):
        """从加载的数据中提取期刊信息"""
        if journal_name not in self.journal_data:
            return None
        
        try:
            journal_data = self.journal_data[journal_name]
            
            # 提取影响因子和分区信息
            impact_factor = "未知"
            quartile = "未知"
            
            if "rank" in journal_data:
                rank_data = journal_data["rank"]
                
                # 提取影响因子
                if "sciif" in rank_data and rank_data["sciif"]:
                    impact_factor = rank_data["sciif"]
                elif "if" in rank_data and rank_data["if"]:
                    impact_factor = rank_data["if"]
                
                # 提取分区信息
                for field in ["sci", "sciBase", "zone", "q", "quartile"]:
                    if field in rank_data and rank_data[field]:
                        quartile = rank_data[field]
                        break
            
            # 构建返回结果
            return {
                "impact_factor": impact_factor,
                "quartile": quartile,
                "journal_full_name": journal_name
            }
            
        except Exception as e:
            safe_print(f"提取期刊 '{journal_name}' 信息出错: {e}", self.verbose)
            return None
    
    def _calculate_similarity(self, s1, s2):
        """计算两个字符串的相似度"""
        if not s1 or not s2:
            return 0
        
        # 检查缓存
        cache_key = f"{s1}||{s2}"
        cache_enabled = self.config.get('journal_cache_enabled', True)
        if cache_enabled:
            with self.lock:
                if cache_key in self.similarity_cache:
                    return self.similarity_cache[cache_key]
        
        # 如果其中一个是另一个的子串，给予较高相似度
        if s1 in s2:
            similarity = 0.9 * len(s1) / len(s2)
            if cache_enabled:
                with self.lock:
                    self.similarity_cache[cache_key] = similarity
            return similarity
            
        if s2 in s1:
            similarity = 0.9 * len(s2) / len(s1)
            if cache_enabled:
                with self.lock:
                    self.similarity_cache[cache_key] = similarity
            return similarity
        
        # 使用改进的相似度算法
        try:
            # 分词比较
            words1 = set(s1.split())
            words2 = set(s2.split())
            
            # 如果两个集合有很多共同单词，则相似度高
            common_words = words1.intersection(words2)
            if common_words:
                word_similarity = len(common_words) * 2.0 / (len(words1) + len(words2))
                
                # 如果单词相似度高，进一步计算编辑距离
                if word_similarity > 0.5:
                    # 使用前缀相似度以加速计算
                    prefix_len = min(5, min(len(s1), len(s2)))
                    if s1[:prefix_len] == s2[:prefix_len]:
                        word_similarity = (word_similarity + 0.2)
                    
                    # 保存结果到缓存
                    if cache_enabled:
                        with self.lock:
                            self.similarity_cache[cache_key] = min(1.0, word_similarity)
                    return min(1.0, word_similarity)
            
            # 一般长字符串相似度计算，允许跳过长字符串以节省时间
            if len(s1) > 100 and len(s2) > 100:
                # 对于长字符串，使用子串采样计算相似度
                similarity = self._calculate_substring_similarity(s1, s2)
                if cache_enabled:
                    with self.lock:
                        self.similarity_cache[cache_key] = similarity
                return similarity
                
            # 对于短字符串，计算字符级别相似度
            similarity = self._calculate_char_similarity(s1, s2)
            
            # 保存结果到缓存
            if cache_enabled:
                with self.lock:
                    self.similarity_cache[cache_key] = similarity
            return similarity
            
        except Exception as e:
            safe_print(f"计算相似度时出错: {e}", self.verbose)
            return 0
    
    def _calculate_substring_similarity(self, s1, s2):
        """使用子串采样方法计算大字符串的相似度"""
        # 从每个字符串中提取几个子串进行比较
        samples = 5
        sample_len = min(10, min(len(s1), len(s2)) // 2)
        
        if sample_len < 3:  # 太短的字符串不采样
            return self._calculate_char_similarity(s1, s2)
        
        total_similarity = 0
        count = 0
        
        # 从开头、中间和结尾采样
        positions = [0]  # 开头
        if len(s1) > sample_len:
            positions.append(len(s1) // 2 - sample_len // 2)  # 中间
        if len(s1) > sample_len * 2:
            positions.append(len(s1) - sample_len)  # 结尾
            
        for pos in positions:
            if pos + sample_len <= len(s1):
                sub1 = s1[pos:pos+sample_len]
                
                # 在s2中寻找最相似的子串
                max_sub_sim = 0
                for i in range(0, len(s2) - sample_len + 1, max(1, len(s2) // 10)):
                    sub2 = s2[i:i+sample_len]
                    sim = self._calculate_char_similarity(sub1, sub2)
                    max_sub_sim = max(max_sub_sim, sim)
                
                total_similarity += max_sub_sim
                count += 1
        
        return total_similarity / max(1, count)
    
    def _calculate_char_similarity(self, s1, s2):
        """计算两个字符串的字符级别相似度"""
        # 简化的编辑距离计算
        if s1 == s2:
            return 1.0
            
        len1, len2 = len(s1), len(s2)
        
        # 如果长度相差太多，直接返回较低相似度
        if abs(len1 - len2) / max(len1, len2) > 0.5:
            return 0.1
        
        # 计算最长公共子序列（而不是完整的编辑距离）
        matrix = [[0 for x in range(len2 + 1)] for y in range(len1 + 1)]
        for i in range(1, len1 + 1):
            for j in range(1, len2 + 1):
                if s1[i-1] == s2[j-1]:
                    matrix[i][j] = matrix[i-1][j-1] + 1
                else:
                    matrix[i][j] = max(matrix[i-1][j], matrix[i][j-1])
        
        # 计算相似度
        common_length = matrix[len1][len2]
        return (2.0 * common_length) / (len1 + len2)
    
    def _sort_articles(self, articles):
        """根据指定方式排序文章"""
        sort_method = self.config.get('article_sort', 'impact_factor')
        safe_print(f"按 {sort_method} 排序文章", self.verbose)
        
        if sort_method == 'impact_factor':
            # 按影响因子从高到低排序
            return sorted(articles, key=lambda x: self._extract_float(x.get('impact_factor', '0')), reverse=True)
        elif sort_method == 'journal':
            # 按期刊名称字母顺序排序
            return sorted(articles, key=lambda x: x.get('journal', '').lower())
        elif sort_method == 'quartile':
            # 按分区排序，同分区按影响因子
            return sorted(articles, 
                          key=lambda x: (self._quartile_value(x.get('quartile', 'Q4')), 
                                        -self._extract_float(x.get('impact_factor', '0'))))
        elif sort_method == 'date':
            # 按发表日期从新到旧排序
            return sorted(articles, 
                         key=lambda x: self._parse_date(x.get('pub_date', '1900-01-01')), 
                         reverse=True)
        else:
            safe_print(f"未知的排序方式: {sort_method}，使用默认排序", self.verbose)
            return articles
    
    def _extract_float(self, value):
        """从字符串中提取浮点数"""
        try:
            if isinstance(value, (int, float)):
                return float(value)
            
            # 使用正则表达式提取第一个浮点数
            match = re.search(r"[-+]?\d*\.\d+|\d+", str(value))
            if match:
                return float(match.group())
            return 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _quartile_value(self, quartile):
        """将分区转换为数值，用于排序"""
        quartile = str(quartile).upper()
        if 'Q1' in quartile:
            return 1
        elif 'Q2' in quartile:
            return 2
        elif 'Q3' in quartile:
            return 3
        elif 'Q4' in quartile:
            return 4
        else:
            return 5  # 未知分区放在最后
    
    def _parse_date(self, date_str):
        """解析日期字符串为日期对象"""
        try:
            # 尝试不同的日期格式
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m', '%Y/%m', '%Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # 如果以上格式都不匹配，尝试提取年份
            year_match = re.search(r'(\d{4})', date_str)
            if year_match:
                return datetime.strptime(year_match.group(), '%Y')
            
            # 默认返回很早的日期
            return datetime(1900, 1, 1)
        except Exception:
            return datetime(1900, 1, 1)
    
    def export_to_csv(self, articles, output_file=None):
        """导出增强后的文章到CSV文件"""
        if not articles:
            safe_print("没有可导出的文章数据", self.verbose)
            return False
        
        # 使用配置文件中的输出路径或提供的路径
        file_path = output_file or self.config.get('output_sort', 'pubmed_enhanced.csv')
        
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 获取所有列名
            fieldnames = []
            for article in articles:
                fieldnames.extend([k for k in article.keys() if k not in fieldnames])
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(articles)
            
            safe_print(f"成功导出 {len(articles)} 篇文章到: {file_path}", True)
            return True
            
        except Exception as e:
            safe_print(f"导出CSV失败: {e}", True)
            return False

def main():
    """主程序入口"""
    try:
        # 初始化增强处理器
        start_time = time.time()
        enhancer = JournalEnhancer(verbose=True, log_file="journal_enhancer.log")
        init_time = time.time() - start_time
        safe_print(f"初始化完成，用时: {init_time:.2f}秒", True)
        
        # 增强文章信息
        enhanced_articles = enhancer.enhance_articles()
        
        if enhanced_articles:
            # 导出增强后的文章
            enhancer.export_to_csv(enhanced_articles)
        else:
            safe_print("没有增强后的文章可导出", True)
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}", True)
        traceback.print_exc()

if __name__ == "__main__":
    main()