"""
PubMed文献检索工具
从PubMed上按照指定关键词获取文献信息，配置从pub.txt读取
"""
import os
import csv
import sys
import time
import threading
import concurrent.futures
from Bio import Entrez
from tqdm import tqdm
import random

# 导入自定义模块
from pubmed_core import (
    safe_print, retry_function, validate_search_query, 
    build_date_filter, get_entrez_sort_param, remove_html_tags, 
    extract_publication_date, safe_create_dir
)
from search_enhancer import SearchEnhancer

# 导入日志工具，如果可用
try:
    from log_utils import get_logger, init_logger
except ImportError:
    pass

class PubMedFetcher:
    def __init__(self, email=None, config_file="pub.txt", verbose=False, log_file=None):
        """初始化PubMed检索工具
        
        Args:
            email: PubMed API Email
            config_file: 配置文件路径
            verbose: 是否输出详细日志
            log_file: 日志文件路径，如果为None则不记录到文件
        """
        self.verbose = verbose
        self.config = self.read_config(config_file)
        
        # 如果提供了log_file，初始化日志系统（如果导入了log_utils）
        if log_file and 'init_logger' in globals():
            init_logger(log_file=log_file, verbose=verbose)
        
        # 设置email和初始化搜索增强器
        self.email = email or self.config.get('email', 'default@example.com')
        Entrez.email = self.email
        
        self.search_enhancer = None
        if self.config.get('enhance_query', False):
            self.search_enhancer = SearchEnhancer(self.config, verbose=self.verbose)
        
        safe_print(f"PubMed检索初始化完成，使用邮箱: {self.email}", self.verbose)
    
    def read_config(self, config_file):
        """从配置文件读取设置"""
        # 定义默认配置
        config = {
            'query': 'cancer',
            'multi_query': '',         # 多关键词搜索
            'time_period': 3.0,        # 默认3年
            'start_date': '',          # 起始日期
            'end_date': '',            # 结束日期
            'max_results': 50,
            'output_file': 'pubmed_results.csv',
            'get_citations': True,
            'pubmed_sort': 'best_match',
            'enhance_query': False,    # 是否润色搜索词
            'ai_model': 'qwen-turbo',  # 用于润色的AI模型
            'api_key': '',             # API密钥
            'api_base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
            'ai_timeout': 30,
        }
        
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                key, value = parts[0].strip(), parts[1].strip()
                                
                                # 处理数值型配置
                                if key == 'time_period':
                                    try:
                                        config['time_period'] = float(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的时间周期值: {value}，使用默认值: 3.0")
                                elif key == 'max_results':
                                    try:
                                        config['max_results'] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的最大结果数: {value}，使用默认值: 50")
                                elif key == 'get_citations':
                                    config['get_citations'] = value.lower() in ['true', 'yes', 'y', '1']
                                elif key == 'enhance_query':
                                    config['enhance_query'] = value.lower() in ['true', 'yes', 'y', '1']
                                elif key == 'ai_timeout':
                                    try:
                                        config['ai_timeout'] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的AI超时设置: {value}，使用默认值: 30秒")
                                # 处理字符串型配置
                                elif key in config:
                                    config[key] = value
                
                # 检查是否缺少配置项
                self._check_and_update_config(config_file, config)
                safe_print(f"已从 {config_file} 加载配置")
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置")
                self.create_default_config(config_file, config)
        except Exception as e:
            safe_print(f"读取配置文件出错: {e}")
            safe_print("使用默认设置")
        
        return config
    
    def _check_and_update_config(self, config_file, config):
        """检查并更新配置文件，添加缺失的配置项"""
        needed_params = {
            'enhance_query': '# 是否润色搜索词(yes/no)\nenhance_query=no\n\n',
            'ai_model': '# 用于润色搜索词的AI模型\nai_model=qwen-turbo\n\n',
            'ai_timeout': '# AI调用超时时间(秒)\nai_timeout=30\n\n',
            'multi_query': '# 多关键词查询(用逗号分隔)\nmulti_query=\n\n',
        }
        
        try:
            # 读取当前配置文件内容
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 检查并添加缺失的配置项
            additions = []
            for param, template in needed_params.items():
                if f"{param}=" not in content:
                    additions.append(template)
            
            # 如果有需要添加的内容，向文件末尾追加
            if additions:
                with open(config_file, 'a', encoding='utf-8') as f:
                    f.write("\n# 搜索词润色设置\n")
                    for addition in additions:
                        f.write(addition)
                safe_print(f"已向 {config_file} 添加搜索词润色设置", self.verbose)
        except Exception as e:
            safe_print(f"更新配置文件出错: {e}", self.verbose)
    
    def create_default_config(self, config_file, config):
        """创建默认配置文件"""
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write("# PubMed查询配置文件\n")
                f.write("# 使用格式: 参数=值\n\n")
                f.write("# 搜索关键词\n")
                f.write("# 支持PubMed高级搜索语法，例如:\n")
                f.write("# 基本搜索: cancer therapy\n")
                f.write("# 字段限定: cancer[Title] AND therapy[Title/Abstract]\n")
                f.write("# 布尔运算: (cancer OR tumor) AND (therapy OR treatment) NOT lung\n")
                f.write("# MeSH术语: \"Neoplasms\"[MeSH] AND \"Drug Therapy\"[MeSH]\n")
                f.write(f"query={config['query']}\n\n")
                f.write("# 多关键词查询(用逗号分隔，比如: cancer,diabetes,alzheimer)\n")
                f.write("# 如果此项不为空，将优先于单一查询(query)执行\n")
                f.write(f"multi_query={config.get('multi_query', '')}\n\n")
                f.write("# 是否润色搜索词(yes/no)\n")
                f.write(f"enhance_query={'yes' if config['enhance_query'] else 'no'}\n\n")
                f.write("# 用于润色搜索词的AI模型\n")
                f.write(f"ai_model={config['ai_model']}\n\n")
                f.write("# AI调用超时时间(秒)\n")
                f.write(f"ai_timeout={config['ai_timeout']}\n\n")
                f.write("# 时间设置 (三种方式，优先级: 起止日期 > 时间周期 > 查询中的日期过滤)\n")
                f.write(f"# 方式1: 时间周期（单位：年），如0.5表示最近6个月，1表示最近一年\ntime_period={config['time_period']}\n\n")
                f.write("# 方式2: 明确的起止日期 (格式: YYYY/MM/DD 或 YYYY-MM-DD)\n")
                f.write("# 如果设置了起止日期，将忽略时间周期设置\n")
                f.write(f"start_date={config['start_date']}\n")
                f.write(f"end_date={config['end_date']}\n\n")
                f.write(f"# 最大获取结果数量\nmax_results={config['max_results']}\n\n")
                f.write(f"# 输出CSV文件路径\noutput_file={config['output_file']}\n\n")
                f.write(f"# 是否获取引用次数 (yes/no)\nget_citations={'yes' if config['get_citations'] else 'no'}\n\n")
                f.write(f"# PubMed API邮箱\nemail={self.email}\n")
                f.write(f"# PubMed文献排序方式\n")
                f.write(f"# - best_match: 最佳匹配(默认)\n")
                f.write(f"# - most_recent: 最近添加\n")
                f.write(f"# - pub_date: 出版日期\n")
                f.write(f"# - first_author: 第一作者\n")
                f.write(f"# - journal: 期刊名称\n")
                f.write(f"pubmed_sort={config['pubmed_sort']}\n\n")
            safe_print(f"已创建默认配置文件: {config_file}")
        except Exception as e:
            safe_print(f"创建默认配置文件失败: {e}")
    
    def fetch_publications(self):
        """获取PubMed文献"""
        # 检查是否有多查询
        multi_query = self.config.get('multi_query', '')
        if multi_query:
            queries = [q.strip() for q in multi_query.split(',') if q.strip()]
            if queries:
                safe_print(f"检测到{len(queries)}个查询关键词: {', '.join(queries)}", True)
                
                all_publications = []
                max_per_query = max(1, int(self.config['max_results'] / len(queries)))
                
                # 用于追踪已处理的PMID，防止重复
                processed_pmids = set()
                duplicates_count = 0
                
                # 为每个查询执行搜索
                for i, query in enumerate(queries):
                    safe_print(f"\n[{i+1}/{len(queries)}] 正在查询: '{query}'", True)
                    
                    # 更新进度条状态（如果在main模块中导入了ProgressDisplay）
                    try:
                        from main import ProgressDisplay
                        ProgressDisplay.set_status(f"查询 {i+1}/{len(queries)}: {query}")
                    except:
                        pass
                    
                    # 临时修改配置
                    original_query = self.config['query']
                    original_max = self.config['max_results']
                    self.config['query'] = query
                    self.config['max_results'] = max_per_query
                    
                    try:
                        publications = self._fetch_single_query()
                        if publications:
                            # 添加查询关键词标记并去重
                            for pub in publications:
                                pub['search_query'] = query
                                
                                # 检查是否重复
                                pmid = pub.get('pmid', '')
                                if pmid and pmid in processed_pmids:
                                    duplicates_count += 1
                                    continue
                                
                                # 不重复，添加到结果并记录PMID
                                if pmid:
                                    processed_pmids.add(pmid)
                                    all_publications.append(pub)
                            
                            safe_print(f"查询 '{query}' 获取到 {len(publications)} 篇文献", True)
                        else:
                            safe_print(f"查询 '{query}' 未找到符合条件的文献", True)
                    except Exception as e:
                        safe_print(f"处理查询 '{query}' 时出错: {e}", True)
                        if self.verbose:
                            import traceback
                            traceback.print_exc()
                    finally:
                        # 恢复原始配置
                        self.config['query'] = original_query
                        self.config['max_results'] = original_max
                
                # 返回结果
                if all_publications:
                    safe_print(f"多关键词查询完成，共获取 {len(all_publications)} 篇不重复文献", True)
                    if duplicates_count > 0:
                        safe_print(f"已过滤 {duplicates_count} 篇重复文献", True)
                    
                    # 清除进度条状态
                    try:
                        from main import ProgressDisplay
                        ProgressDisplay.set_status("")
                    except:
                        pass
                    
                    return all_publications
                else:
                    safe_print("所有查询均未找到符合条件的文献", True)
                    return []
        
        # 如果没有多查询或多查询为空，执行单一查询
        return self._fetch_single_query()
    
    def _fetch_single_query(self):
        """运行单个查询的PubMed文献"""
        original_query = self.config['query']
        time_period = self.config['time_period']
        start_date = self.config.get('start_date', '')
        end_date = self.config.get('end_date', '')
        max_results = self.config['max_results']
        sort_type = self.config.get('pubmed_sort', 'best_match')
        
        # 为了应对过滤后数量不足的情况，获取更多的初始文献
        # 增加批处理大小，确保有足够的文献供过滤和重复检查
        initial_fetch_multiplier = 2.0  # 增加倍数，为大批量处理做准备
        initial_fetch_amount = min(int(max_results * initial_fetch_multiplier), max_results + 200)
        
        # 确保 initial_fetch_amount 是正整数
        initial_fetch_amount = max(1, initial_fetch_amount)
        
        # 对大批量检索特殊处理
        if max_results >= 300:
            safe_print(f"检测到大批量检索需求: {max_results}篇文献，采用超高效检索策略", True)
            # 确保初始获取量始终是有效的正整数
            initial_fetch_amount = min(600, max(1, int(max_results * 1.5)))  # 增加初始获取数量
            safe_print(f"初始获取量设置为: {initial_fetch_amount}篇", self.verbose)
        
        # 如果启用了搜索词润色，先润色搜索词
        query = original_query
        if self.config.get('enhance_query', False) and self.search_enhancer:
            query = self.search_enhancer.enhance_query(original_query)
        
        # 添加日期过滤器
        if not any(tag in query.lower() for tag in ['[pdat]', '[date', 'date -']):
            date_filter = build_date_filter(time_period, start_date, end_date, self.verbose)
            if date_filter:
                # 检查查询是否已经用括号包围
                if not (query.startswith('(') and query.endswith(')')):
                    full_query = f"({query}){date_filter}"
                else:
                    full_query = f"{query}{date_filter}"
            else:
                full_query = query
        else:
            # 查询已包含日期过滤
            safe_print("查询已包含日期过滤，将使用原始查询中的日期条件", self.verbose)
            full_query = query
        
        safe_print(f"执行PubMed高级搜索: {full_query}", True)  # 改为始终显示
        safe_print(f"排序方式: {sort_type}", self.verbose)
        safe_print(f"请求文献数量: {max_results}，初始获取: {initial_fetch_amount} (考虑过滤后可能减少)", self.verbose)
        
        # 检查查询语法和设置排序
        validate_search_query(full_query, self.verbose)
        sort_param = get_entrez_sort_param(sort_type, self.verbose)
        
        # 更新进度显示
        try:
            from main import ProgressDisplay
            ProgressDisplay.set_status(f"正在执行检索: {original_query}")
        except:
            pass
        
        # 第一步: 使用ESearch获取文献ID列表
        try:
            safe_print("正在查询PubMed索引数据库...", True)
            
            def _esearch():
                # 确保retmax参数为正整数
                retmax = max(1, int(initial_fetch_amount))
                safe_print(f"发送请求，retmax={retmax}", self.verbose)
                handle = Entrez.esearch(db="pubmed", term=full_query, retmax=retmax, sort=sort_param)
                return Entrez.read(handle)
            
            search_results = retry_function(_esearch, max_retries=5, delay=2)  # 增加重试次数和延迟
            id_list = search_results.get("IdList", [])
            
            if not id_list:
                safe_print("未找到符合条件的文献", True)
                return []
            
            total_count = int(search_results.get("Count", 0))
            safe_print(f"✓ 检索完成! 共找到 {total_count} 篇相关文献，初始获取 {len(id_list)} 篇详情", True)
            
            # 更新进度显示
            try:
                from main import ProgressDisplay
                ProgressDisplay.set_status(f"找到 {total_count} 篇文献，准备获取详情")
            except:
                pass
            
        except Exception as e:
            safe_print(f"搜索过程出错: {e}", True)
            return []
        
        publications = []
        skipped_no_abstract = 0
        processed_ids = set()
        duplicate_pmids = set()  # 跟踪重复的PMID
        
        # 创建一个进度条
        with tqdm(total=min(len(id_list), max_results), desc="获取文献详情", unit="篇", 
                  disable=False,  # 始终显示进度条
                  ncols=80,  # 固定宽度
                  bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]') as progress_bar:
            
            # 分批处理ID，提取文献信息
            batch_size = 300  # 大幅增加每批处理ID数量至300
            safe_print(f"设置超大批量处理: 每批{batch_size}篇文献", self.verbose)
            
            while len(publications) < max_results:
                # 获取未处理的ID
                remaining_ids = [id for id in id_list if id not in processed_ids]
                if not remaining_ids:
                    # 尝试获取更多ID
                    if len(publications) < max_results:
                        try:
                            # 调整获取更多ID的量，基于当前已获取的有效文献比例
                            valid_ratio = len(publications) / max(1, len(processed_ids))
                            # 一次性获取更多ID，大幅减少API调用次数
                            additional_needed = min(1000, int((max_results - len(publications)) / valid_ratio * 2.5))
                            
                            safe_print(f"当前有效文献比例: {valid_ratio:.2f}, 将获取额外 {additional_needed} 篇", self.verbose)
                            
                            # 更新进度显示
                            try:
                                from main import ProgressDisplay
                                ProgressDisplay.set_status(f"已获取 {len(publications)} 篇有效文献，获取更多...")
                            except:
                                pass
                                
                            more_ids = self._get_more_ids(full_query, len(id_list), additional_needed, sort_param)
                            if more_ids:
                                # 去除已处理过的ID
                                new_ids = [id for id in more_ids if id not in processed_ids]
                                id_list.extend(new_ids)
                                
                                # 更新进度条总数
                                new_total = min(len(id_list), max_results)
                                if new_total > progress_bar.total:
                                    progress_bar.total = new_total
                                    progress_bar.refresh()
                                
                                safe_print(f"成功获取 {len(new_ids)} 个新的文献ID", self.verbose)
                            else:
                                safe_print("无法获取更多文献ID，已达到检索结果上限", self.verbose)
                                break
                        except Exception as e:
                            safe_print(f"获取额外ID时出错: {e}", self.verbose)
                            break
                    else:
                        break
                
                # 处理一批ID (使用更大的批处理大小300)
                current_batch = remaining_ids[:min(batch_size, len(remaining_ids))]
                if not current_batch:
                    break
                
                # 更新进度显示
                batch_start = len(publications)
                batch_end = min(batch_start + len(current_batch), max_results)
                try:
                    from main import ProgressDisplay
                    ProgressDisplay.set_status(f"批量获取 {batch_start+1}-{batch_end}/{max_results} 详情 (批量:{len(current_batch)}篇)")
                except:
                    pass
                
                safe_print(f"开始超大批量处理 {len(current_batch)} 篇文献", self.verbose)
                processed_ids.update(current_batch)
                
                # 无论批量大小如何，都使用并行处理来提高效率
                batch_pubs = self._process_article_batch_parallel(current_batch, max_workers=8)  # 增加工作线程数
                
                # 过滤无摘要文章并检查重复
                for pub in batch_pubs:
                    if not pub:  # 跳过处理失败的文献
                        continue
                        
                    pmid = pub.get('pmid', '')
                    
                    # 检查是否已存在这个PMID (重复检查)
                    if pmid in duplicate_pmids:
                        continue
                    
                    # 修改: 放宽摘要检查条件，允许短摘要通过
                    abstract = pub.get('abstract', '')
                    if not isinstance(abstract, str) or len(abstract.strip()) < 5:  # 允许至少5个字符的摘要通过
                        skipped_no_abstract += 1
                        safe_print(f"PMID {pmid} 被过滤: 摘要缺失或过短 ('{abstract}')", self.verbose)
                        continue
                    
                    # 标记为已处理并添加到结果
                    duplicate_pmids.add(pmid)
                    publications.append(pub)
                    progress_bar.update(1)
                    
                    # 达到所需数量后停止
                    if len(publications) >= max_results:
                        break
                
                # 添加极小延迟，避免请求过于频繁
                if len(publications) < max_results and remaining_ids[len(current_batch):]:
                    time.sleep(0.1)  # 减少延迟时间以提高吞吐量
        
        # 报告过滤结果
        total_processed = len(processed_ids)
        final_count = len(publications)
        safe_print(f"\n获取文献详情结果:", True)
        safe_print(f"- 请求文献数量: {max_results} 篇", True)
        safe_print(f"- 处理文献总数: {total_processed} 篇", True)
        safe_print(f"- 无摘要被过滤: {skipped_no_abstract} 篇", True)
        safe_print(f"- 获取有效文献: {final_count} 篇", True)
        
        if final_count < max_results:
            shortage = max_results - final_count
            safe_print(f"注意: 最终获取的有效文献比请求少 {shortage} 篇，这是正常的过滤结果", True)
        
        # 第三步: 获取引用次数 (根据配置决定是否获取)
        if self.config.get('get_citations', True):
            # 更新进度显示
            try:
                from main import ProgressDisplay
                ProgressDisplay.set_status(f"获取 {len(publications)} 篇文献的引用次数...")
            except:
                pass
                
            # 对于大量文献的情况，使用并行处理获取引用
            if max_results >= 300:
                self._get_citation_counts_parallel(publications)
            else:
                self._get_citation_counts(publications)
        else:
            safe_print("已禁用引用次数获取", self.verbose)
        
        # 更新进度显示
        try:
            from main import ProgressDisplay
            ProgressDisplay.set_status(f"已完成获取 {len(publications)} 篇文献")
        except:
            pass
            
        safe_print(f"✓ 查询完成! 成功获取 {len(publications)} 篇有效文献 (含摘要，无重复)", True)
        return publications
    
    def _get_more_ids(self, query, start_position, retmax, sort_param):
        """获取更多文献ID，用于分批获取大量文献
        
        Args:
            query: 搜索查询语句
            start_position: 起始位置(已获取的ID数量)
            retmax: 要获取的最大ID数量
            sort_param: 排序参数
            
        Returns:
            list: 文献ID列表
        """
        try:
            def _esearch_more():
                handle = Entrez.esearch(
                    db="pubmed",
                    term=query,
                    retstart=start_position,  # 从这个位置开始获取
                    retmax=retmax, 
                    sort=sort_param
                )
                return Entrez.read(handle)
                
            # 使用更长的重试机制，因为这是额外获取
            search_results = retry_function(_esearch_more, max_retries=5, delay=3)
            
            # 从结果中提取ID列表
            more_ids = search_results.get("IdList", [])
            return more_ids
            
        except Exception as e:
            # 更详细的错误日志，帮助调试
            safe_print(f"获取更多文献ID时出错 (位置 {start_position}, 数量 {retmax}): {e}", self.verbose)
            import traceback
            if self.verbose:
                traceback.print_exc()
            return []
    
    def export_to_csv(self, publications, output_file=None):
        """导出文献到CSV文件"""
        if not publications:
            safe_print("没有可导出的文献数据", self.verbose)
            return False
        
        # 使用配置文件中的输出路径或提供的路径
        file_path = output_file or self.config.get('output_file', 'pubmed_results.csv')
        
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(file_path)
            if output_dir:
                if not safe_create_dir(output_dir):
                    # 如果创建目录失败，尝试使用默认位置
                    safe_print(f"无法创建输出目录: {output_dir}，将使用当前目录", True)
                    file_path = os.path.basename(file_path)
            
            # 收集字段并写入CSV
            base_fields = [
                'pmid', 'title', 'authors', 'affiliations', 
                'journal', 'pub_date', 'doi', 'citations',
                'keywords', 'abstract'
            ]
            
            # 添加可能存在的附加字段(例如search_query)
            all_fields = set()
            for pub in publications:
                all_fields.update(pub.keys())
            
            fieldnames = base_fields + [f for f in sorted(all_fields) if f not in base_fields]
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for pub in publications:
                    # 确保所有字段都是字符串
                    row = {k: str(pub.get(k, '')) for k in fieldnames}
                    writer.writerow(row)
            
            safe_print(f"成功导出 {len(publications)} 篇文献到: {file_path}", self.verbose)
            return True
            
        except Exception as e:
            safe_print(f"导出CSV失败: {e}", self.verbose)
            return False

    def _process_article_batch_parallel(self, id_batch, max_workers=8):
        """使用并行处理批量获取文章详情，提高处理效率
        
        Args:
            id_batch: 要处理的文章ID批次
            max_workers: 最大工作线程数
            
        Returns:
            list: 处理后的文章信息列表
        """
        if not id_batch:
            return []
        
        # 使用最佳分割策略处理大批量
        # 如果ID数量大于300，分割成多个子批次，每个最多含300个ID
        if len(id_batch) > 300:
            safe_print(f"超大批量处理 {len(id_batch)} 篇文献，分成多个子批次", self.verbose)
            sub_batches = [id_batch[i:i+300] for i in range(0, len(id_batch), 300)]
        else:
            # 优化处理大批次的效率
            sub_batches = [id_batch]
        
        all_results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有批次的处理任务
            future_to_batch = {executor.submit(self._process_article_batch, batch): batch for batch in sub_batches}
            
            # 收集结果
            for future in concurrent.futures.as_completed(future_to_batch):
                batch = future_to_batch[future]
                try:
                    batch_results = future.result()
                    all_results.extend(batch_results)
                except Exception as e:
                    safe_print(f"并行处理批次出错: {e}", self.verbose)
        
        safe_print(f"并行处理完成，获取到 {len(all_results)} 篇文献信息", self.verbose)
        return all_results

    def _process_article_batch(self, id_batch):
        """处理一批文章ID，获取详细信息
        
        Args:
            id_batch: 要处理的ID批次
            
        Returns:
            list: 处理后的文章信息列表
        """
        if not id_batch:
            return []
            
        # 改进：如果ID批次过大，自动分割以提高稳定性
        if len(id_batch) > 300:
            safe_print(f"ID批次过大({len(id_batch)}篇)，自动分割处理", self.verbose)
            results = []
            for i in range(0, len(id_batch), 300):
                sub_batch = id_batch[i:i+300]
                sub_results = self._process_article_batch(sub_batch)
                results.extend(sub_results)
            return results
            
        batch_ids_str = ",".join(id_batch)
        safe_print(f"批量处理 {len(id_batch)} 篇文献: PMID {id_batch[0]}...{id_batch[-1]}", self.verbose)
        
        try:
            def _efetch():
                # 增加Entrez参数以提高大批量处理的稳定性
                handle = Entrez.efetch(db="pubmed", id=batch_ids_str, retmode="xml", retmax=len(id_batch))
                return Entrez.read(handle)
            
            records = retry_function(_efetch, max_retries=5, delay=2)  # 增加重试次数
            
            # 显示成功获取的记录数
            pub_article_count = len(records.get('PubmedArticle', []))
            safe_print(f"成功获取 {pub_article_count} 篇文献详情", self.verbose)
            
            # 优化大批量文章的处理速度
            result = []
            for article in records.get('PubmedArticle', []):
                try:
                    pub_info = self._extract_article_info(article)
                    result.append(pub_info)
                except Exception as e:
                    safe_print(f"提取文章信息出错: {e}", self.verbose)
                    result.append(None)
                    
            return result
                
        except Exception as e:
            safe_print(f"获取批次详情失败: {e}", self.verbose)
            return [None] * len(id_batch)
    
    def _extract_article_info(self, article):
        """从PubMed文章中提取信息"""
        try:
            medline = article.get('MedlineCitation', {})
            article_data = medline.get('Article', {})
            
            if not article_data:
                return None
            
            # 提取PMID
            pmid = str(medline.get('PMID', ''))
            
            # 提取标题并删除HTML标签
            title = article_data.get('ArticleTitle', '无标题')
            if isinstance(title, list):
                title = ' '.join([str(t) for t in title])
            title = remove_html_tags(title)
            
            # 提取摘要并删除HTML标签
            abstract = ""
            abstract_data = article_data.get('Abstract', {})
            if abstract_data:
                abstract_parts = abstract_data.get('AbstractText', [])
                if isinstance(abstract_parts, list):
                    abstract_text_list = []
                    for part in abstract_parts:
                        if isinstance(part, str):
                            abstract_text_list.append(remove_html_tags(part))
                        elif hasattr(part, 'attributes') and hasattr(part, '__str__'):
                            label = part.attributes.get('Label', '')
                            text = remove_html_tags(str(part))
                            if label:
                                abstract_text_list.append(f"{label.upper()}: {text}")
                            else:
                                abstract_text_list.append(text)
                    abstract = " ".join(abstract_text_list)
                elif abstract_parts:
                    abstract = remove_html_tags(str(abstract_parts))
            
            # 提取作者和单位
            authors = []
            affiliations = []
            author_list = article_data.get('AuthorList', [])
            if author_list:
                for author in author_list:
                    if isinstance(author, dict):
                        # 提取作者姓名
                        last_name = remove_html_tags(author.get('LastName', ''))
                        fore_name = remove_html_tags(author.get('ForeName', author.get('Initials', '')))
                        full_name = ""
                        if last_name and fore_name:
                            full_name = f"{last_name} {fore_name}"
                        elif last_name:
                            full_name = last_name
                        elif author.get('CollectiveName'):
                            full_name = remove_html_tags(author.get('CollectiveName'))
                        
                        if full_name:
                            authors.append(full_name)
                        
                        # 提取作者单位
                        affiliation_info = author.get('AffiliationInfo', [])
                        if affiliation_info:
                            for affiliation in affiliation_info:
                                if isinstance(affiliation, dict) and 'Affiliation' in affiliation:
                                    aff_text = remove_html_tags(affiliation['Affiliation'])
                                    if aff_text and aff_text not in affiliations:
                                        affiliations.append(aff_text)
            
            # 提取关键词
            keywords = []
            self._extract_keywords(medline, keywords)
            
            # 提取出版日期
            pub_date = extract_publication_date(article, self.verbose)
            
            # 提取DOI
            doi = self._extract_doi(article)
            
            # 提取期刊名称
            journal_name = self._extract_journal_name(article_data)
            
            return {
                'pmid': pmid,
                'title': title,
                'abstract': abstract,
                'authors': "; ".join(authors),
                'affiliations': "; ".join(affiliations),
                'keywords': "; ".join(set(keywords)),
                'pub_date': pub_date,
                'doi': doi,
                'journal': journal_name,
                'citations': 0
            }
            
        except Exception as e:
            safe_print(f"提取文章信息出错: {e}", self.verbose)
            return None
            
    def _extract_keywords(self, medline, keywords):
        """提取关键词"""
        keyword_list = medline.get('KeywordList', [])
        for keyword_group in keyword_list:
            for keyword in keyword_group:
                keywords.append(keyword)
    
    def _extract_doi(self, article):
        """提取DOI"""
        if article.get('PubmedData', {}).get('ArticleIdList'):
            for article_id in article['PubmedData']['ArticleIdList']:
                if hasattr(article_id, 'attributes'):
                    id_type = article_id.attributes.get('IdType')
                    if id_type == 'doi':
                        return str(article_id)
        return ""
    
    def _extract_journal_name(self, article_data):
        """提取期刊名称"""
        journal = article_data.get('Journal', {})
        return remove_html_tags(
            journal.get('Title', journal.get('ISOAbbreviation', '未知期刊'))
        )

def main():
    """主程序入口"""
    try:
        # 初始化PubMed获取器
        fetcher = PubMedFetcher(verbose=True)
        
        # 获取文献
        publications = fetcher.fetch_publications()
        
        if publications:
            # 导出到CSV
            fetcher.export_to_csv(publications)
        else:
            safe_print("未找到符合条件的文献，未生成输出文件", True)
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}", True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()