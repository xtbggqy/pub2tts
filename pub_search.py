"""
PubMed文献检索工具
从PubMed上按照指定关键词获取文献信息，配置从pub.txt读取
"""
import os
import csv
import sys
import time
from Bio import Entrez
from tqdm import tqdm

# 导入自定义模块
from pubmed_core import (
    safe_print, retry_function, validate_search_query, 
    build_date_filter, get_entrez_sort_param, remove_html_tags, extract_publication_date
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
                
                # 为每个查询执行搜索
                for i, query in enumerate(queries):
                    safe_print(f"\n[{i+1}/{len(queries)}] 正在查询: '{query}'", True)
                    
                    # 临时修改配置
                    original_query = self.config['query']
                    original_max = self.config['max_results']
                    self.config['query'] = query
                    self.config['max_results'] = max_per_query
                    
                    try:
                        publications = self._fetch_single_query()
                        if publications:
                            # 添加查询关键词标记
                            for pub in publications:
                                pub['search_query'] = query
                            
                            all_publications.extend(publications)
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
                    safe_print(f"多关键词查询完成，共获取 {len(all_publications)} 篇文献", True)
                    return all_publications
                else:
                    safe_print("所有查询均未找到符合条件的文献", True)
                    return []
        
        # 如果没有多查询或多查询为空，执行单一查询
        return self._fetch_single_query()
    
    def _fetch_single_query(self):
        """获取单个查询的PubMed文献"""
        original_query = self.config['query']
        time_period = self.config['time_period']
        start_date = self.config.get('start_date', '')
        end_date = self.config.get('end_date', '')
        max_results = self.config['max_results']
        sort_type = self.config.get('pubmed_sort', 'best_match')
        
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
        
        safe_print(f"执行PubMed高级搜索: {full_query}", self.verbose)
        safe_print(f"排序方式: {sort_type}", self.verbose)
        
        # 检查查询语法和设置排序
        validate_search_query(full_query, self.verbose)
        sort_param = get_entrez_sort_param(sort_type, self.verbose)
        
        # 第一步: 使用ESearch获取文献ID列表
        try:
            def _esearch():
                handle = Entrez.esearch(db="pubmed", term=full_query, retmax=max_results, sort=sort_param)
                return Entrez.read(handle)
            
            search_results = retry_function(_esearch)
            id_list = search_results.get("IdList", [])
            
            if not id_list:
                safe_print("未找到符合条件的文献", self.verbose)
                return []
            
            total_count = int(search_results.get("Count", 0))
            safe_print(f"找到 {total_count} 篇文献，将获取前 {len(id_list)} 篇详情", self.verbose)
        except Exception as e:
            safe_print(f"搜索过程出错: {e}", self.verbose)
            return []
        
        # 第二步: 获取文献详细信息
        publications = []
        skipped_no_abstract = 0
        processed_ids = set()
        
        # 分批处理ID，提取文献信息
        while len(publications) < max_results:
            # 获取未处理的ID
            remaining_ids = [id for id in id_list if id not in processed_ids]
            if not remaining_ids:
                # 尝试获取更多ID
                if len(publications) < max_results:
                    try:
                        additional_needed = (max_results - len(publications)) * 2
                        more_ids = self._get_more_ids(full_query, len(id_list), additional_needed, sort_param)
                        if more_ids:
                            id_list.extend(more_ids)
                            remaining_ids = [id for id in more_ids if id not in processed_ids]
                        else:
                            break
                    except Exception as e:
                        safe_print(f"获取额外ID时出错: {e}", self.verbose)
                        break
                else:
                    break
            
            # 处理一批ID
            current_batch = remaining_ids[:min(10, len(remaining_ids))]
            if not current_batch:
                break
                
            processed_ids.update(current_batch)
            batch_pubs = self._process_article_batch(current_batch)
            
            # 过滤无摘要文章并添加到结果
            for pub in batch_pubs:
                if pub and pub.get('abstract'):
                    publications.append(pub)
                else:
                    skipped_no_abstract += 1
                
                if len(publications) >= max_results:
                    break
            
            # 添加延迟，避免请求过于频繁
            if len(publications) < max_results and remaining_ids[len(current_batch):]:
                time.sleep(0.5)
        
        # 报告结果
        if len(publications) < max_results:
            safe_print(f"警告: 请求了{max_results}篇文献，但只找到{len(publications)}篇有效文献（含摘要）", True)
            safe_print(f"有{skipped_no_abstract}篇文献因没有摘要被跳过", True)
        else:
            if skipped_no_abstract > 0:
                safe_print(f"已跳过 {skipped_no_abstract} 篇没有摘要的文章", True)
        
        # 第三步: 获取引用次数 (根据配置决定是否获取)
        if self.config.get('get_citations', True):
            self._get_citation_counts(publications)
        else:
            safe_print("已禁用引用次数获取", self.verbose)
        
        safe_print(f"成功获取 {len(publications)} 篇文献信息 (有摘要文章)", True)
        return publications
    
    def _get_more_ids(self, query, start, count, sort_param):
        """获取更多文献ID"""
        safe_print(f"尝试获取额外 {count} 个文献ID (从位置 {start} 开始)", self.verbose)
        def _esearch_more():
            handle = Entrez.esearch(db="pubmed", term=query, retmax=count, 
                                   retstart=start, sort=sort_param)
            return Entrez.read(handle)
        
        more_results = retry_function(_esearch_more)
        more_ids = more_results.get("IdList", [])
        
        if more_ids:
            safe_print(f"获取到额外 {len(more_ids)} 个文献ID", self.verbose)
        else:
            safe_print(f"无法获取更多文献ID", True)
            
        return more_ids
    
    def _process_article_batch(self, id_batch):
        """处理一批文章ID，获取详细信息"""
        if not id_batch:
            return []
            
        batch_ids_str = ",".join(id_batch)
        try:
            def _efetch():
                handle = Entrez.efetch(db="pubmed", id=batch_ids_str, retmode="xml")
                return Entrez.read(handle)
            
            records = retry_function(_efetch)
            
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
            
            # 检查摘要是否为空
            if not abstract.strip():
                safe_print(f"文章 PMID:{pmid} 没有摘要", self.verbose)
                return None  # 返回None表示这篇文章没有摘要
            
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
            
            # 提取其他信息
            pub_date = extract_publication_date(article, self.verbose)
            doi = self._extract_doi(article)
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
        # MeSH关键词
        mesh_headings = medline.get('MeshHeadingList', [])
        if mesh_headings:
            for mesh in mesh_headings:
                if isinstance(mesh, dict) and 'DescriptorName' in mesh:
                    desc = mesh['DescriptorName']
                    if hasattr(desc, '__str__'):
                        keywords.append(remove_html_tags(str(desc)))
        
        # 作者关键词
        keyword_list = medline.get('KeywordList', [])
        for keyword_group in keyword_list:
            if isinstance(keyword_group, list):
                for keyword in keyword_group:
                    if keyword and hasattr(keyword, '__str__'):
                        keywords.append(remove_html_tags(str(keyword)))
    
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
    
    def _get_citation_counts(self, publications):
        """获取文章引用次数"""
        if not publications:
            return
            
        safe_print("获取文章引用次数...", self.verbose)
        
        with tqdm(total=len(publications), desc="获取引用", unit="篇") as pbar:
            for pub in publications:
                pmid = pub.get('pmid')
                if not pmid:
                    pbar.update(1)
                    continue
                
                try:
                    def _elink():
                        handle = Entrez.elink(dbfrom="pubmed", db="pubmed", 
                                            linkname="pubmed_pubmed_citedin", id=pmid)
                        return Entrez.read(handle)
                    
                    link_results = retry_function(_elink, max_retries=2)
                    
                    citation_count = 0
                    if link_results and len(link_results) > 0:
                        linkset = link_results[0]
                        if 'LinkSetDb' in linkset and linkset['LinkSetDb']:
                            linkdb = linkset['LinkSetDb'][0]
                            if 'Link' in linkdb:
                                citation_count = len(linkdb['Link'])
                    
                    pub['citations'] = citation_count
                    
                except Exception as e:
                    safe_print(f"获取引用次数出错 (PMID: {pmid}): {e}", self.verbose)
                    pub['citations'] = 0
                
                pbar.update(1)
                
                # 添加延迟，避免请求过于频繁
                time.sleep(0.3)
    
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
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
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