"""
PubMed文献检索核心功能模块
提供PubMed文献检索的基础功能和工具函数
"""
import os
import time
import re
import sys
from Bio import Entrez
from datetime import datetime, timedelta
from tqdm import tqdm

# 导入日志工具，如果没有找到则使用备用的safe_print
try:
    from log_utils import get_logger, init_logger
    
    def safe_print(msg, verbose=True, log_file=None):
        """兼容旧代码，使用日志系统"""
        # 如果提供了log_file并且当前没有初始化logger，则初始化
        if log_file and get_logger() is None:
            init_logger(log_file=log_file, verbose=verbose)
            
        logger = get_logger()
        if not verbose:
            # 检查是否为重要消息
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告:", "找到"]):
                return
        logger.log(msg, verbose)
        
except ImportError:
    def safe_print(msg, verbose=True, log_file=None):
        """安全打印，处理编码问题"""
        if not verbose:
            # 检查是否为重要消息
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告:", "找到"]):
                return
                
        try:
            print(msg)
            sys.stdout.flush()
        except:
            print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
            sys.stdout.flush()
            
        # 如果指定了日志文件，也保存到文件
        if log_file:
            try:
                # 确保目录存在
                log_dir = os.path.dirname(log_file)
                if log_dir and not os.path.exists(log_dir):
                    os.makedirs(log_dir)
                
                # 格式化消息
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                formatted_msg = f"{timestamp} {msg}"
                
                # 追加到日志文件
                with open(log_file, 'a', encoding='utf-8') as f:
                    f.write(formatted_msg + '\n')
            except Exception as e:
                print(f"写入日志文件失败: {e}")

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

def validate_search_query(query, verbose=True):
    """检查搜索查询语法，提供警告和建议"""
    syntax_issues = []
    
    # 检查括号是否匹配
    if query.count('(') != query.count(')'):
        msg = "警告: 搜索词中括号不匹配，可能导致搜索结果不符合预期"
        safe_print(msg, verbose)
        syntax_issues.append(msg)
    
    # 检查引号是否匹配
    if query.count('"') % 2 != 0:
        msg = "警告: 搜索词中引号不匹配，请确保引号成对使用"
        safe_print(msg, verbose)
        syntax_issues.append(msg)
    
    # 检查常见字段标记
    common_fields = ['[Title]', '[Abstract]', '[Author]', '[Journal]', '[MeSH]', 
                    '[Title/Abstract]', '[pdat]', '[Publication Date]', '[Affiliation]']
    for field in common_fields:
        if field.lower() in query.lower() and field not in query:
            safe_print(f"提示: 检测到字段标记 '{field}' 可能大小写不匹配，PubMed字段标记区分大小写", verbose)
    
    # 检查布尔运算符大小写
    for op in ['and', 'or', 'not']:
        if f" {op} " in query.lower() and f" {op.upper()} " not in query:
            safe_print(f"警告: 布尔运算符 '{op}' 应使用大写形式 '{op.upper()}'", verbose)
    
    # 检查常见语法错误
    if "[mesh]" in query.lower() and not re.search(r'"[^"]+"[^[]*\[mesh\]', query.lower()):
        safe_print("提示: 使用MeSH术语时，通常需要用引号，如: \"Neoplasms\"[MeSH]", verbose)
    
    return syntax_issues

def fix_query_syntax(query, verbose=True):
    """修复搜索查询中的常见语法错误"""
    # 1. 修复引号不匹配问题
    if query.count('"') % 2 != 0:
        safe_print("修复查询中的不匹配引号", verbose)
        # 移除所有引号，重新添加必要的引号
        query = query.replace('"', '')
        # 识别并重新为MeSH术语添加引号
        query = re.sub(r'(\w+)(\[MeSH\])', r'"\1"\2', query)
    
    # 2. 移除字段标记中的空格
    query = re.sub(r'\s+\[', '[', query)
    
    # 3. 确保布尔运算符大写
    for op in ['and', 'or', 'not']:
        query = re.sub(r'(?<!\w)' + op + r'(?!\w)', op.upper(), query, flags=re.IGNORECASE)
    
    # 4. 修复字段语法，标准化字段名称
    query = re.sub(r'\[mesh\]', '[MeSH]', query, flags=re.IGNORECASE)
    query = re.sub(r'\[title/abstract\]', '[Title/Abstract]', query, flags=re.IGNORECASE)
    query = re.sub(r'\[title\]', '[Title]', query, flags=re.IGNORECASE)
    query = re.sub(r'\[author\]', '[Author]', query, flags=re.IGNORECASE)
    query = re.sub(r'\[journal\]', '[Journal]', query, flags=re.IGNORECASE)
    
    return query

def build_date_filter(time_period=None, start_date=None, end_date=None, verbose=True):
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
            start_date = normalize_date_format(start_date)
            end_date = normalize_date_format(end_date)
            
            if start_date and end_date:
                date_filter = f"({start_date}[Date - Publication] : {end_date}[Date - Publication])"
                safe_print(f"使用指定起止日期过滤: {date_filter}", verbose)
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
            safe_print(f"使用时间周期过滤 ({time_period}年): {date_filter}", verbose)
            return date_filter
            
        return ""
        
    except Exception as e:
        safe_print(f"构建日期过滤器出错: {e}", verbose)
        return ""

def normalize_date_format(date_str):
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
            
    return ""

def get_entrez_sort_param(sort_type, verbose=True):
    """将排序类型转换为Entrez API参数"""
    sort_map = {
        'best_match': 'relevance',    # 最佳匹配
        'most_recent': 'date_added',  # 最近添加
        'pub_date': 'pub_date',       # 出版日期
        'first_author': 'author',     # 第一作者
        'journal': 'journal'          # 期刊名称
    }
    
    sort_param = sort_map.get(sort_type.lower(), 'relevance')
    safe_print(f"使用PubMed排序参数: {sort_param}", verbose)
    return sort_param

def remove_html_tags(text):
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

def extract_publication_date(article, verbose=True):
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
        safe_print(f"提取发表日期时出错: {e}", verbose)
        return "未知日期"
