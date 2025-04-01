"""
PubMed文献检索工具
从PubMed上按照指定关键词获取文献信息，配置从pub.txt读取
"""
import os
import time
import csv
import datetime
import re
from Bio import Entrez
import sys
from tqdm import tqdm
from datetime import datetime, timedelta

def safe_print(msg):
    """安全打印，处理编码问题"""
    try:
        print(msg)
        sys.stdout.flush()
    except:
        print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
        sys.stdout.flush()

def retry_function(func, max_retries=3, delay=1):
    """重试机制，处理网络不稳定问题"""
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = delay * (attempt + 1)
                safe_print(f"尝试失败 ({attempt+1}/{max_retries}): {e}. 将在 {sleep_time}秒后重试...")
                time.sleep(sleep_time)
            else:
                safe_print(f"所有重试均失败: {e}")
                raise

class PubMedFetcher:
    def __init__(self, email, config_file="pub.txt"):
        """初始化PubMed检索工具"""
        self.email = email
        Entrez.email = email
        safe_print(f"PubMed检索初始化完成，使用邮箱: {email}")
        self.config = self.read_config(config_file)
    
    def read_config(self, config_file):
        """从配置文件读取设置"""
        config = {
            'query': 'cancer',
            'time_period': 3.0,  # 默认改为3年
            'start_date': '',    # 新增起始日期
            'end_date': '',      # 新增结束日期
            'max_results': 50,
            'output_file': 'pubmed_results.csv',
            'get_citations': True,
            'pubmed_sort': 'best_match'  # 添加排序方式，默认为最佳匹配
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
                                value = value.strip()
                                
                                if key == 'query':
                                    config['query'] = value
                                elif key == 'time_period':
                                    try:
                                        config['time_period'] = float(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的时间周期值: {value}，使用默认值: 3.0")
                                elif key == 'start_date':  # 处理起始日期
                                    config['start_date'] = value
                                elif key == 'end_date':    # 处理结束日期
                                    config['end_date'] = value
                                elif key == 'max_results':
                                    try:
                                        config['max_results'] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的最大结果数: {value}，使用默认值: 50")
                                elif key == 'output_file':
                                    config['output_file'] = value
                                elif key == 'email':
                                    self.email = value
                                    Entrez.email = value
                                elif key == 'get_citations':
                                    config['get_citations'] = value.lower() in ['true', 'yes', 'y', '1']
                                elif key == 'pubmed_sort':  # 新增，读取排序方式
                                    config['pubmed_sort'] = value.lower()
                
                safe_print(f"已从 {config_file} 加载配置")
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置")
                # 创建默认配置文件
                self.create_default_config(config_file, config)
        except Exception as e:
            safe_print(f"读取配置文件出错: {e}")
            safe_print("使用默认设置")
        
        return config
    
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
    
    def build_date_filter(self, time_period=None, start_date=None, end_date=None):
        """构建日期过滤器
        
        Args:
            time_period: 时间周期（年）
            start_date: 起始日期字符串 (YYYY/MM/DD or YYYY-MM-DD)
            end_date: 结束日期字符串 (YYYY/MM/DD or YYYY-MM-DD)
            
        Returns:
            日期过滤字符串
        """
        try:
            # 优先使用明确的起止日期
            if start_date and end_date:
                # 标准化日期格式 (转换为 YYYY/MM/DD)
                start_date = self._normalize_date_format(start_date)
                end_date = self._normalize_date_format(end_date)
                
                if start_date and end_date:
                    date_filter = f"({start_date}[Date - Publication] : {end_date}[Date - Publication])"
                    safe_print(f"使用指定起止日期过滤: {date_filter}")
                    return date_filter
            
            # 如果没有明确的起止日期，使用时间周期
            if time_period:
                current_date = datetime.now()
                # 将时间周期（年）转换为天数
                days = int(time_period * 365)
                past_date = current_date - timedelta(days=days)
                
                # 格式化为YYYY/MM/DD格式
                start_date = past_date.strftime("%Y/%m/%d")
                end_date = current_date.strftime("%Y/%m/%d")
                
                date_filter = f"({start_date}[Date - Publication] : {end_date}[Date - Publication])"
                safe_print(f"使用时间周期过滤 ({time_period}年): {date_filter}")
                return date_filter
                
            return ""
            
        except Exception as e:
            safe_print(f"构建日期过滤器出错: {e}")
            return ""
    
    def _normalize_date_format(self, date_str):
        """标准化日期格式为YYYY/MM/DD"""
        if not date_str:
            return ""
            
        # 处理不同的日期分隔符
        date_str = date_str.strip().replace('-', '/')
        
        # 验证日期格式
        parts = date_str.split('/')
        if len(parts) == 3:
            # 完整的年月日
            try:
                year, month, day = parts
                # 简单验证
                if 1000 <= int(year) <= 9999 and 1 <= int(month) <= 12 and 1 <= int(day) <= 31:
                    return f"{year}/{month}/{day}"
            except ValueError:
                pass
        elif len(parts) == 2:
            # 只有年月
            try:
                year, month = parts
                if 1000 <= int(year) <= 9999 and 1 <= int(month) <= 12:
                    return f"{year}/{month}/01"
            except ValueError:
                pass
        elif len(parts) == 1:
            # 只有年份
            try:
                year = parts[0]
                if 1000 <= int(year) <= 9999:
                    return f"{year}/01/01"
            except ValueError:
                pass
                
        safe_print(f"警告: 无效的日期格式: '{date_str}'，应为YYYY/MM/DD或YYYY-MM-DD")
        return ""
    
    def fetch_publications(self):
        """获取PubMed文献"""
        query = self.config['query']
        time_period = self.config['time_period']
        start_date = self.config.get('start_date', '')
        end_date = self.config.get('end_date', '')
        max_results = self.config['max_results']
        sort_type = self.config.get('pubmed_sort', 'best_match')
        
        # 添加日期过滤器，检查查询是否已包含日期过滤
        if not any(tag in query.lower() for tag in ['[pdat]', '[date', 'date -']):
            # 如果查询中没有日期过滤器，添加我们的日期过滤
            date_filter = self.build_date_filter(time_period, start_date, end_date)
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
            safe_print("查询已包含日期过滤，将使用原始查询中的日期条件")
            full_query = query
        
        safe_print(f"执行PubMed高级搜索: {full_query}")
        safe_print(f"排序方式: {sort_type}")
        
        # 检查查询语法
        self._validate_search_query(full_query)
        
        # 转换排序方式为Entrez参数
        sort_param = self._get_entrez_sort_param(sort_type)
        
        # 第一步: 使用ESearch获取文献ID列表
        try:
            def _esearch():
                handle = Entrez.esearch(db="pubmed", term=full_query, retmax=max_results, sort=sort_param)
                return Entrez.read(handle)
            
            search_results = retry_function(_esearch)
            id_list = search_results.get("IdList", [])
            
            if not id_list:
                safe_print("未找到符合条件的文献")
                return []
            
            total_count = int(search_results.get("Count", 0))
            safe_print(f"找到 {total_count} 篇文献，将获取前 {len(id_list)} 篇详情")
            
        except Exception as e:
            safe_print(f"搜索过程出错: {e}")
            return []
        
        # 第二步: 获取文献详细信息
        publications = []
        skipped_no_abstract = 0  # 统计因没有摘要而被跳过的文章数
        with tqdm(total=len(id_list), desc="获取文献详情", unit="篇") as pbar:
            # 分批处理，避免一次请求过多
            batch_size = 10
            for i in range(0, len(id_list), batch_size):
                batch_ids = id_list[i:i+batch_size]
                batch_ids_str = ",".join(batch_ids)
                
                try:
                    def _efetch():
                        handle = Entrez.efetch(db="pubmed", id=batch_ids_str, retmode="xml")
                        return Entrez.read(handle)
                    
                    records = retry_function(_efetch)
                    
                    for article in records['PubmedArticle']:
                        try:
                            pub_info = self._extract_article_info(article)
                            # 检查文章是否有摘要，如果没有则跳过
                            if pub_info and pub_info.get('abstract'):
                                publications.append(pub_info)
                            else:
                                skipped_no_abstract += 1
                                safe_print(f"跳过没有摘要的文章 (PMID: {article.get('MedlineCitation', {}).get('PMID', 'Unknown')})")
                        except Exception as e:
                            safe_print(f"提取文章信息出错: {e}")
                            continue
                    
                    pbar.update(len(batch_ids))
                    
                except Exception as e:
                    safe_print(f"获取批次 {i//batch_size + 1} 详情失败: {e}")
                    pbar.update(len(batch_ids))
                    continue
                
                # 添加延迟，避免请求过于频繁
                if i + batch_size < len(id_list):
                    time.sleep(0.5)
        
        if skipped_no_abstract > 0:
            safe_print(f"已跳过 {skipped_no_abstract} 篇没有摘要的文章")
        
        # 第三步: 获取引用次数 (根据配置决定是否获取)
        if self.config.get('get_citations', True):
            self._get_citation_counts(publications)
        else:
            safe_print("已禁用引用次数获取")
        
        safe_print(f"成功获取 {len(publications)} 篇文献信息 (有摘要文章)")
        return publications
    
    def _get_entrez_sort_param(self, sort_type):
        """将排序类型转换为Entrez API参数"""
        sort_map = {
            'best_match': 'relevance',    # 最佳匹配
            'most_recent': 'date_added',  # 最近添加
            'pub_date': 'pub_date',       # 出版日期
            'first_author': 'author',     # 第一作者
            'journal': 'journal'          # 期刊名称
        }
        
        sort_param = sort_map.get(sort_type.lower(), 'relevance')
        safe_print(f"使用PubMed排序参数: {sort_param}")
        return sort_param
    
    def _validate_search_query(self, query):
        """检查搜索查询语法，提供警告和建议"""
        # 检查括号是否匹配
        if query.count('(') != query.count(')'):
            safe_print("警告: 搜索词中括号不匹配，可能导致搜索结果不符合预期")
        
        # 检查引号是否匹配
        if query.count('"') % 2 != 0:
            safe_print("警告: 搜索词中引号不匹配，请确保引号成对使用")
        
        # 检查常见字段标记
        common_fields = ['[Title]', '[Abstract]', '[Author]', '[Journal]', '[MeSH]', 
                        '[Title/Abstract]', '[pdat]', '[Publication Date]', '[Affiliation]']
        for field in common_fields:
            if field.lower() in query.lower() and field not in query:
                safe_print(f"提示: 检测到字段标记 '{field}' 可能大小写不匹配，PubMed字段标记区分大小写")
        
        # 检查布尔运算符大小写
        for op in ['and', 'or', 'not']:
            if f" {op} " in query.lower() and f" {op.upper()} " not in query:
                safe_print(f"警告: 布尔运算符 '{op}' 应使用大写形式 '{op.upper()}'")
        
        # 检查常见语法错误
        if "[mesh]" in query.lower() and not re.search(r'"[^"]+"[^[]*\[mesh\]', query.lower()):
            safe_print("提示: 使用MeSH术语时，通常需要用引号，如: \"Neoplasms\"[MeSH]")
    
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
            title = self._remove_html_tags(str(title))
            
            # 提取摘要并删除HTML标签
            abstract = ""
            abstract_data = article_data.get('Abstract', {})
            if abstract_data:
                abstract_parts = abstract_data.get('AbstractText', [])
                if isinstance(abstract_parts, list):
                    abstract_text_list = []
                    for part in abstract_parts:
                        if isinstance(part, str):
                            abstract_text_list.append(self._remove_html_tags(part))
                        elif hasattr(part, 'attributes') and hasattr(part, '__str__'):
                            label = part.attributes.get('Label', '')
                            text = self._remove_html_tags(str(part))
                            if label:
                                abstract_text_list.append(f"{label.upper()}: {text}")
                            else:
                                abstract_text_list.append(text)
                    abstract = " ".join(abstract_text_list)
                elif abstract_parts:
                    abstract = self._remove_html_tags(str(abstract_parts))
            
            # 检查摘要是否为空
            if not abstract.strip():
                safe_print(f"文章 PMID:{pmid} 没有摘要")
                return None  # 返回None表示这篇文章没有摘要
            
            # 提取作者和单位并删除HTML标签
            authors = []
            affiliations = []
            author_list = article_data.get('AuthorList', [])
            if author_list:
                for author in author_list:
                    if isinstance(author, dict):
                        # 提取作者姓名
                        last_name = self._remove_html_tags(author.get('LastName', ''))
                        fore_name = self._remove_html_tags(author.get('ForeName', author.get('Initials', '')))
                        full_name = ""
                        if last_name and fore_name:
                            full_name = f"{last_name} {fore_name}"
                        elif last_name:
                            full_name = last_name
                        elif author.get('CollectiveName'):
                            full_name = self._remove_html_tags(author.get('CollectiveName'))
                        
                        if full_name:
                            authors.append(full_name)
                        
                        # 提取作者单位
                        affiliation_info = author.get('AffiliationInfo', [])
                        if affiliation_info:
                            for affiliation in affiliation_info:
                                if isinstance(affiliation, dict) and 'Affiliation' in affiliation:
                                    aff_text = self._remove_html_tags(affiliation['Affiliation'])
                                    if aff_text and aff_text not in affiliations:
                                        affiliations.append(aff_text)
            
            # 提取关键词并删除HTML标签
            keywords = []
            # MeSH关键词
            mesh_headings = medline.get('MeshHeadingList', [])
            if mesh_headings:
                for mesh in mesh_headings:
                    if isinstance(mesh, dict) and 'DescriptorName' in mesh:
                        desc = mesh['DescriptorName']
                        if hasattr(desc, '__str__'):
                            keywords.append(self._remove_html_tags(str(desc)))
            
            # 作者关键词
            keyword_list = medline.get('KeywordList', [])
            for keyword_group in keyword_list:
                if isinstance(keyword_group, list):
                    for keyword in keyword_group:
                        if keyword and hasattr(keyword, '__str__'):
                            keywords.append(self._remove_html_tags(str(keyword)))
            
            # 提取发表日期
            pub_date = self._extract_publication_date(article)
            
            # 提取DOI
            doi = ""
            if article.get('PubmedData', {}).get('ArticleIdList'):
                for article_id in article['PubmedData']['ArticleIdList']:
                    if hasattr(article_id, 'attributes'):
                        id_type = article_id.attributes.get('IdType')
                        if id_type == 'doi':
                            doi = str(article_id)
                            break
            
            # 提取期刊信息
            journal = article_data.get('Journal', {})
            journal_name = self._remove_html_tags(
                journal.get('Title', journal.get('ISOAbbreviation', '未知期刊'))
            )
            
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
            safe_print(f"提取文章信息时出错: {e}")
            return None
    
    def _remove_html_tags(self, text):
        """删除文本中的HTML标签"""
        if not text:
            return ""
        
        # 使用正则表达式删除HTML标签
        clean_text = re.sub(r'<[^>]+>', '', str(text))
        # 替换HTML实体
        clean_text = clean_text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        clean_text = clean_text.replace('&quot;', '"').replace('&apos;', "'").replace('&nbsp;', ' ')
        # 删除额外的空白符
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        return clean_text
    
    def _extract_publication_date(self, article):
        """提取并格式化发表日期为YYYY-MM-DD格式"""
        try:
            # 尝试从不同位置提取日期
            article_data = article.get('MedlineCitation', {}).get('Article', {})
            
            # 尝试从ArticleDate获取，这通常是最完整的日期
            article_date = None
            if article_data.get('ArticleDate'):
                article_date = article_data.get('ArticleDate')
                if isinstance(article_date, list):
                    article_date = article_date[0]
                
                if article_date:
                    year = article_date.get('Year', '')
                    month = article_date.get('Month', '')
                    day = article_date.get('Day', '')
                    
                    if year and month and day:
                        try:
                            month = int(month)
                            day = int(day)
                            return f"{year}-{month:02d}-{day:02d}"
                        except (ValueError, TypeError):
                            pass
            
            # 尝试从PubDate获取
            journal = article_data.get('Journal', {})
            pub_date = journal.get('JournalIssue', {}).get('PubDate', {})
            
            year = pub_date.get('Year', '')
            month = pub_date.get('Month', '')
            day = pub_date.get('Day', '')
            
            # 处理月份名称
            month_map = {
                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
                'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
            }
            
            if month in month_map:
                month = month_map[month]
            
            # 构建日期字符串
            if year and month and day:
                try:
                    month_num = int(month)
                    day_num = int(day)
                    return f"{year}-{month_num:02d}-{day_num:02d}"
                except (ValueError, TypeError):
                    pass
            elif year and month:
                try:
                    month_num = int(month)
                    return f"{year}-{month_num:02d}-01"
                except (ValueError, TypeError):
                    pass
            elif year:
                return f"{year}-01-01"
            
            # 如果以上都失败，尝试从MedlineDate解析
            if pub_date.get('MedlineDate'):
                medline_date = pub_date.get('MedlineDate')
                # 尝试匹配YYYY MMM DD格式
                match = re.search(r'(\d{4})\s+([A-Za-z]{3})(?:\s+(\d{1,2}))?', medline_date)
                if match:
                    y, m, d = match.groups()
                    if m in month_map:
                        m = month_map[m]
                    else:
                        m = '01'
                    
                    if d:
                        try:
                            d_num = int(d)
                            return f"{y}-{m}-{d_num:02d}"
                        except (ValueError, TypeError):
                            pass
                    return f"{y}-{m}-01"
                
                # 尝试只匹配年份
                year_match = re.search(r'(\d{4})', medline_date)
                if year_match:
                    return f"{year_match.group(1)}-01-01"
            
            return "未知日期"
            
        except Exception as e:
            safe_print(f"提取发表日期时出错: {e}")
            return "未知日期"
    
    def _get_citation_counts(self, publications):
        """获取文章引用次数"""
        if not publications:
            return
            
        safe_print("获取文章引用次数...")
        
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
                    safe_print(f"获取引用次数出错 (PMID: {pmid}): {e}")
                    pub['citations'] = 0
                
                pbar.update(1)
                
                # 添加延迟，避免请求过于频繁
                time.sleep(0.3)
    
    def export_to_csv(self, publications, output_file=None):
        """导出文献到CSV文件"""
        if not publications:
            safe_print("没有可导出的文献数据")
            return False
        
        # 使用配置文件中的输出路径或提供的路径
        file_path = output_file or self.config.get('output_file', 'pubmed_results.csv')
        
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(file_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                fieldnames = [
                    'pmid', 'title', 'authors', 'affiliations', 
                    'journal', 'pub_date', 'doi', 'citations',
                    'keywords', 'abstract'
                ]
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for pub in publications:
                    # 确保所有字段都是字符串
                    row = {k: str(pub.get(k, '')) for k in fieldnames}
                    writer.writerow(row)
            
            safe_print(f"成功导出 {len(publications)} 篇文献到: {file_path}")
            return True
            
        except Exception as e:
            safe_print(f"导出CSV失败: {e}")
            return False

def main():
    """主程序入口"""
    try:
        # 默认邮箱，如果配置文件中有，将被覆盖
        default_email = "your.email@example.com"
        
        # 初始化PubMed获取器
        fetcher = PubMedFetcher(default_email)
        
        # 获取文献
        publications = fetcher.fetch_publications()
        
        if publications:
            # 导出到CSV
            fetcher.export_to_csv(publications)
        else:
            safe_print("未找到符合条件的文献，未生成输出文件")
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()