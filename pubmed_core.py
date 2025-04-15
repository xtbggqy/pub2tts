"""
PubMed核心功能模块
提供PubMed检索和数据处理的通用功能
"""
import re
import time
import datetime
import random
import os

def safe_print(msg, verbose=True):
    """安全打印，处理编码问题"""
    if not verbose:
        return
        
    try:
        print(msg)
        import sys
        sys.stdout.flush()
    except:
        print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
        import sys
        sys.stdout.flush()

def retry_function(func, max_retries=3, delay=1):
    """重试执行函数
    
    Args:
        func: 要执行的函数
        max_retries: 最大重试次数
        delay: 重试间隔时间(秒)
    
    Returns:
        函数执行结果
    
    Raises:
        最后一次尝试的异常
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt < max_retries - 1:
                # 对于网络错误，使用指数退避策略
                wait_time = delay * (2 ** attempt)
                safe_print(f"尝试执行失败 ({attempt+1}/{max_retries}): {e}. 将在{wait_time}秒后重试...", True)
                time.sleep(wait_time)
            else:
                safe_print(f"达到最大重试次数 ({max_retries})，操作失败: {e}", True)
                raise  # 重新抛出最后一次尝试的异常

def fix_query_syntax(query):
    """修复查询语法问题，确保查询能被PubMed正确处理
    
    Args:
        query: 原始查询字符串
        
    Returns:
        str: 修复后的查询字符串
    """
    if not query:
        return query
    
    # 去除首尾空白
    fixed_query = query.strip()
    
    # 修复常见语法问题
    
    # 1. 检查AND/OR/NOT后面是否有空格，没有则添加
    fixed_query = re.sub(r'\b(AND|OR|NOT)([^\s)])', r'\1 \2', fixed_query)
    
    # 2. 检查字段标签前是否有空格，没有则添加 (如 gene[title] -> gene [title])
    fixed_query = re.sub(r'(\w+)(\[[^\]]+\])', r'\1 \2', fixed_query)
    
    # 3. 检查括号匹配
    open_count = fixed_query.count('(')
    close_count = fixed_query.count(')')
    
    if open_count > close_count:
        # 添加缺失的右括号
        fixed_query += ')' * (open_count - close_count)
    elif close_count > open_count:
        # 添加缺失的左括号
        fixed_query = '(' * (close_count - open_count) + fixed_query
    
    # 4. 处理空括号，避免语法错误
    fixed_query = re.sub(r'\(\s*\)', '', fixed_query)
    
    # 5. 处理连续的运算符 (如 AND AND -> AND)
    fixed_query = re.sub(r'\b(AND|OR|NOT)\s+\1\b', r'\1', fixed_query)
    
    # 6. 处理首尾的运算符
    fixed_query = re.sub(r'^(AND|OR|NOT)\s+', '', fixed_query)
    fixed_query = re.sub(r'\s+(AND|OR|NOT)$', '', fixed_query)
    
    return fixed_query

def validate_search_query(query, verbose=False):
    """检查PubMed搜索查询语法是否正确
    
    Args:
        query: 查询字符串
        verbose: 是否输出详细日志
        
    Returns:
        bool: 检查通过返回True，否则返回False
    """
    # 检查括号是否配对
    open_count = query.count('(')
    close_count = query.count(')')
    if open_count != close_count:
        safe_print(f"警告: 查询中的括号不匹配 (开括号: {open_count}, 闭括号: {close_count})", verbose)
        return False
    
    # 检查引号是否配对
    double_quote_count = query.count('"')
    if double_quote_count % 2 != 0:
        safe_print(f"警告: 查询中的双引号不匹配 (共 {double_quote_count} 个)", verbose)
        return False
    
    # 检查是否有错误的字段标签格式
    field_tags = re.findall(r'\[\w+\]', query)
    invalid_tags = [tag for tag in field_tags if tag not in [
        '[Title]', '[Abstract]', '[Author]', '[Journal]', '[MeSH]', 
        '[Affiliation]', '[Text Word]', '[Title/Abstract]', '[TIAB]',
        '[Date - Publication]', '[DP]', '[DOI]', '[Volume]', '[Issue]',
        '[Page]', '[First Author]', '[PMID]', '[PDAT]'
    ]]
    
    if invalid_tags:
        safe_print(f"警告: 查询中可能有无效的字段标签: {', '.join(invalid_tags)}", verbose)
    
    return True

def build_date_filter(time_period=None, start_date=None, end_date=None, verbose=False):
    """构建日期过滤条件
    
    按照以下优先级:
    1. 如果提供了start_date和end_date，使用它们
    2. 如果提供了time_period，计算相对于当前的日期范围
    3. 如果都未提供，返回空字符串（不添加日期过滤）
    
    Args:
        time_period: 时间周期(年)，例如0.5表示半年，1表示1年
        start_date: 起始日期，格式为YYYY-MM-DD或YYYY/MM/DD
        end_date: 结束日期，格式为YYYY-MM-DD或YYYY/MM/DD
        verbose: 是否输出详细日志
        
    Returns:
        str: 日期过滤条件字符串，例如" AND (2020/01/01:2021/01/01[Date - Publication])"
    """
    date_filter = ""
    
    # 规范化日期格式
    def normalize_date(date_str):
        if not date_str:
            return ""
        # 替换连字符为斜杠
        return date_str.replace('-', '/')
    
    # 检查并格式化日期
    def validate_date(date_str, default=""):
        if not date_str:
            return default
        
        # 尝试解析日期
        date_patterns = ["%Y/%m/%d", "%Y-%m-%d", "%Y/%m", "%Y-%m", "%Y", "%Y/%m/%d %H:%M:%S"]
        for pattern in date_patterns:
            try:
                datetime.datetime.strptime(date_str, pattern)
                return date_str
            except ValueError:
                continue
                
        safe_print(f"无效的日期格式: {date_str}，应为YYYY-MM-DD或YYYY/MM/DD", verbose)
        return default
    
    if start_date or end_date:
        # 优先使用明确指定的日期范围
        start = validate_date(normalize_date(start_date))
        end = validate_date(normalize_date(end_date), datetime.datetime.now().strftime("%Y/%m/%d"))
        
        if start and end:
            date_filter = f" AND ({start}:{end}[Date - Publication])"
        elif start:
            date_filter = f" AND ({start}:{datetime.datetime.now().strftime('%Y/%m/%d')}[Date - Publication])"
        elif end:
            date_filter = f" AND (1000/01/01:{end}[Date - Publication])"
    
    elif time_period:
        # 计算相对时间范围
        try:
            end_date = datetime.datetime.now()
            days = int(time_period * 365.25)  # 转换为天数（考虑闰年）
            start_date = end_date - datetime.timedelta(days=days)
            
            date_filter = f" AND ({start_date.strftime('%Y/%m/%d')}:{end_date.strftime('%Y/%m/%d')}[Date - Publication])"
        except ValueError as e:
            safe_print(f"计算日期范围出错: {e}，将不应用日期过滤", verbose)
    
    return date_filter

def get_entrez_sort_param(sort_type="best_match", verbose=False):
    """获取Entrez排序参数
    
    Args:
        sort_type: 排序类型，支持"best_match", "most_recent", "pub_date", "first_author", "journal"
        verbose: 是否输出详细日志
        
    Returns:
        str: Entrez排序参数
    """
    sort_map = {
        "best_match": "relevance",
        "most_recent": "date_added",
        "pub_date": "pub_date",
        "first_author": "first_author",
        "journal": "journal",
    }
    
    if sort_type not in sort_map:
        safe_print(f"未知的排序类型: {sort_type}，使用默认排序: best_match", verbose)
        return "relevance"
    
    return sort_map[sort_type]

def remove_html_tags(text):
    """移除HTML标签
    
    Args:
        text: 文本字符串
        
    Returns:
        str: 清理后的文本
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 替换HTML实体
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&quot;", "\"", text)
    text = re.sub(r"&apos;", "'", text)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    
    # 移除HTML标签
    text = re.sub(r"<[^>]*>", "", text)
    
    # 移除多余的空白字符
    text = re.sub(r"\s+", " ", text).strip()
    
    return text

def extract_publication_date(article, verbose=False):
    """从文章数据中提取出版日期
    
    Args:
        article: PubMed文章数据对象
        verbose: 是否输出详细日志
        
    Returns:
        str: 格式化的出版日期 (YYYY-MM-DD)
    """
    pub_date = ""
    
    try:
        # 尝试从多个可能的位置获取日期
        # 1. 首先尝试 PubmedData → History → PubMed → PubStatus="pubmed"
        if article.get('PubmedData', {}).get('History') and isinstance(article.get('PubmedData').get('History'), list):
            for event in article['PubmedData']['History']:
                if hasattr(event, 'attributes') and event.attributes.get('PubStatus') == 'pubmed':
                    year = event.get('Year', '')
                    month = event.get('Month', '01')
                    day = event.get('Day', '01')
                    if year:
                        pub_date = f"{year}-{month:0>2s}-{day:0>2s}"
                        break
        
        # 2. 然后尝试 MedlineCitation → Article → Journal → JournalIssue → PubDate
        if not pub_date:
            journal_issue = article.get('MedlineCitation', {}).get('Article', {}).get('Journal', {}).get('JournalIssue', {})
            if journal_issue and 'PubDate' in journal_issue:
                pub_date_obj = journal_issue['PubDate']
                year = pub_date_obj.get('Year', '')
                month = pub_date_obj.get('Month', '01')
                day = pub_date_obj.get('Day', '01')
                
                if year:
                    try:
                        # 处理月份可能是英文缩写的情况
                        if month.isalpha():
                            import calendar
                            month_map = {m[:3].lower(): str(i) for i, m in enumerate(calendar.month_name) if i > 0}
                            month = month_map.get(month[:3].lower(), '01')
                        
                        # 格式化日期
                        pub_date = f"{year}-{month:0>2s}-{day:0>2s}"
                    except:
                        pub_date = f"{year}-01-01"  # 默认为当年1月1日

    except Exception as e:
        safe_print(f"提取出版日期失败: {e}", verbose)
    
    return pub_date

def safe_create_dir(directory):
    """安全创建目录，处理权限和路径问题
    
    Args:
        directory: 要创建的目录路径
        
    Returns:
        bool: 是否成功创建或目录已存在
    """
    try:
        if not directory:
            return True
        
        if os.path.exists(directory):
            if os.path.isdir(directory):
                return True
            else:
                safe_print(f"错误: {directory} 已存在但不是一个目录", True)
                return False
        
        os.makedirs(directory, exist_ok=True)
        return True
    except Exception as e:
        safe_print(f"创建目录 {directory} 失败: {e}", True)
        return False
