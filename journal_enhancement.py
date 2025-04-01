"""
期刊信息增强处理工具
读取和处理期刊影响因子和分区信息，为文献添加这些信息，并支持多种排序方式
"""
import os
import json
import csv
import re
from datetime import datetime
from tqdm import tqdm

def safe_print(msg):
    """安全打印，处理编码问题"""
    try:
        print(msg)
        import sys
        sys.stdout.flush()
    except:
        print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
        import sys
        sys.stdout.flush()

class JournalEnhancer:
    def __init__(self, config_file="pub.txt"):
        """初始化期刊信息增强处理工具"""
        self.config = self._read_config(config_file)
        self.journal_data = self._load_journal_data()
        safe_print(f"期刊信息增强处理工具初始化完成，已加载 {len(self.journal_data)} 本期刊信息")
    
    def _read_config(self, config_file):
        """从配置文件读取设置"""
        config = {
            'journal_data_path': "D:\\zotero\\zotero_file\\zoterostyle.json",
            'article_sort': 'impact_factor',  # 默认按影响因子排序
            'output_sort': 'pubmed_enhanced.csv',  # 改为output_sort
            'input_sort': 'pubmed_results.csv'     # 改为input_sort
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
                                
                                if key == 'journal_data_path':
                                    config['journal_data_path'] = value
                                elif key == 'article_sort':
                                    config['article_sort'] = value
                                elif key == 'output_sort':  # 变量名修改
                                    config['output_sort'] = value
                                elif key == 'input_sort':   # 变量名修改
                                    config['input_sort'] = value
                
                safe_print(f"已从 {config_file} 加载排序和期刊数据配置")
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置")
                # 在现有配置文件中添加新的排序和期刊数据配置
                self._update_config_file(config_file, config)
        except Exception as e:
            safe_print(f"读取配置文件出错: {e}")
            safe_print("使用默认设置")
        
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
                has_journal_data = False
                has_article_sort = False
                has_input_sort = False
                has_output_sort = False
                
                for line in lines:
                    if line.strip().startswith('journal_data_path='):
                        has_journal_data = True
                    elif line.strip().startswith('article_sort='):
                        has_article_sort = True
                    elif line.strip().startswith('input_sort='):
                        has_input_sort = True
                    elif line.strip().startswith('output_sort='):
                        has_output_sort = True
                
                # 准备新的配置项
                new_config = []
                if not has_journal_data or not has_article_sort or not has_input_sort or not has_output_sort:
                    new_config.append("\n# 期刊信息和排序设置\n")
                    if not has_journal_data:
                        new_config.append(f"# 期刊数据文件路径\njournal_data_path={config['journal_data_path']}\n\n")
                    if not has_article_sort:
                        new_config.append("# 文章排序方式选项:\n")
                        new_config.append("# - impact_factor: 按影响因子排序(从高到低)\n")
                        new_config.append("# - journal: 按期刊名称排序(字母顺序)\n")
                        new_config.append("# - quartile: 按分区排序(Q1>Q2>Q3>Q4),同分区内按影响因子\n")
                        new_config.append("# - date: 按发表日期排序(从新到旧)\n")
                        new_config.append(f"article_sort={config['article_sort']}\n\n")
                    if not has_input_sort:
                        new_config.append("# 输入文件路径(排序前的文献数据)\n")
                        new_config.append(f"input_sort={config['input_sort']}\n\n")
                    if not has_output_sort:
                        new_config.append("# 输出文件路径(排序后的文献数据)\n")
                        new_config.append(f"output_sort={config['output_sort']}\n\n")
                
                # 只有当需要添加新配置时才写入文件
                if new_config:
                    with open(config_file, 'a', encoding='utf-8') as f:
                        f.writelines(new_config)
                        safe_print(f"已向配置文件 {config_file} 添加期刊和排序设置")
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
                    f.write(f"output_sort={config['output_sort']}\n")
                safe_print(f"已创建包含期刊和排序设置的配置文件: {config_file}")
        except Exception as e:
            safe_print(f"更新配置文件出错: {e}")
    
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
                safe_print(f"成功加载期刊数据: {journal_data_path}")
                safe_print(f"共加载 {total_journals} 个期刊, 示例期刊: {', '.join(sample_journals)}")
                
                # 检查几个示例期刊的内容格式
                for journal in sample_journals:
                    if "rank" in journal_data[journal]:
                        rank_data = journal_data[journal]["rank"]
                        safe_print(f"期刊 '{journal}' 的数据结构: {json.dumps(rank_data, ensure_ascii=False)[:200]}")
                        if "sciif" in rank_data:
                            safe_print(f"期刊 '{journal}' 的影响因子: {rank_data['sciif']}")
                        else:
                            safe_print(f"警告: 期刊 '{journal}' 无影响因子字段 'sciif'")
                    else:
                        safe_print(f"警告: 期刊 '{journal}' 无 'rank' 字段")
            else:
                safe_print(f"期刊数据文件不存在: {journal_data_path}")
        except Exception as e:
            safe_print(f"加载期刊数据出错: {e}")
            import traceback
            traceback.print_exc()
        
        return journal_data
    
    def _get_journal_info(self, journal_name):
        """获取期刊的影响因子和分区信息"""
        if not journal_name or not self.journal_data:
            safe_print(f"无法获取期刊信息: journal_name={journal_name}, journal_data_size={len(self.journal_data) if self.journal_data else 0}")
            return {}
        
        # 添加调试信息
        safe_print(f"\n尝试匹配期刊: '{journal_name}'")
        
        # 定义变量，用于存储匹配的期刊名称
        matched_journal_name = journal_name
        
        # 尝试精确匹配
        journal_data = self.journal_data.get(journal_name)
        if journal_data:
            safe_print(f"精确匹配到期刊: '{journal_name}'")
            matched_journal_name = journal_name
        
        # 尝试不区分大小写匹配
        if not journal_data:
            case_insensitive_matches = []
            for key in self.journal_data:
                if key.lower() == journal_name.lower():
                    case_insensitive_matches.append(key)
            
            if case_insensitive_matches:
                matched_journal_name = case_insensitive_matches[0]
                journal_data = self.journal_data[matched_journal_name]
                safe_print(f"不区分大小写匹配到期刊: '{matched_journal_name}'")
                if len(case_insensitive_matches) > 1:
                    safe_print(f"警告: 多个不区分大小写的匹配项: {', '.join(case_insensitive_matches)}")
        
        # 尝试部分匹配 (提高相似度阈值到0.8)
        if not journal_data:
            potential_matches = []
            for key in self.journal_data:
                if journal_name.lower() in key.lower() or key.lower() in journal_name.lower():
                    match_score = self._get_similarity_score(journal_name, key)
                    potential_matches.append((key, match_score))
            
            # 按相似度从高到低排序
            potential_matches.sort(key=lambda x: x[1], reverse=True)
            
            # 输出所有潜在匹配项
            if potential_matches:
                safe_print(f"找到 {len(potential_matches)} 个潜在匹配项:")
                for key, score in potential_matches[:5]:  # 显示前5个
                    safe_print(f"  - '{key}' (相似度: {score:.2f})")
            
            # 选择最佳匹配 (相似度阈值从0.5提高到0.8)
            if potential_matches and potential_matches[0][1] > 0.8:
                matched_journal_name = potential_matches[0][0]
                best_match_score = potential_matches[0][1]
                journal_data = self.journal_data[matched_journal_name]
                safe_print(f"部分匹配到期刊: '{journal_name}' -> '{matched_journal_name}' (相似度: {best_match_score:.2f})")
            elif potential_matches:
                safe_print(f"警告: 最佳匹配项 '{potential_matches[0][0]}' 相似度过低 ({potential_matches[0][1]:.2f} < 0.8)")
        
        # 如果找到匹配的期刊数据
        if journal_data:
            if "rank" not in journal_data:
                safe_print(f"警告: 期刊数据中没有 'rank' 字段: {json.dumps(journal_data, ensure_ascii=False)[:200]}")
                return {}
            
            rank_data = journal_data["rank"]
            
            # 检查rank_data类型并处理类型错误
            if not isinstance(rank_data, dict):
                safe_print(f"警告: 期刊排名数据不是字典类型，实际类型: {type(rank_data).__name__}")
                
                # 如果是字符串，尝试解析为JSON
                if isinstance(rank_data, str):
                    try:
                        safe_print(f"尝试将字符串解析为JSON: {rank_data[:100]}...")
                        rank_data = json.loads(rank_data)
                        safe_print(f"成功解析为JSON，键: {list(rank_data.keys())}")
                    except json.JSONDecodeError:
                        safe_print(f"无法将字符串解析为JSON，使用空字典")
                        return {
                            "impact_factor": "未知",
                            "impact_factor_str": "未知",
                            "impact_factor_5yr": "未知",
                            "jci": "未知",
                            "quartile": "未知",
                            "subject": "未知",
                            "base_category": "未知", 
                            "jcr_category": "未知",
                            "university_ranks": "{}",
                            "matched_journal": matched_journal_name
                        }
            
            # 只在确认rank_data是字典类型后继续处理
            if isinstance(rank_data, dict):
                safe_print(f"期刊排名数据字段: {list(rank_data.keys())}")
                
                # 查找影响因子字段
                impact_factor_field = None
                if "sciif" in rank_data:
                    impact_factor_field = "sciif"
                elif "if" in rank_data:
                    impact_factor_field = "if"
                
                if impact_factor_field:
                    impact_factor = rank_data.get(impact_factor_field, "未知")
                    safe_print(f"提取到的影响因子 ({impact_factor_field}): {impact_factor}, 类型: {type(impact_factor).__name__}")
                else:
                    impact_factor = "未知"
                    safe_print(f"警告: 没有找到影响因子字段, 可用字段: {list(rank_data.keys())}")
                
                # 尝试转换为数字
                try:
                    if impact_factor and impact_factor != "未知":
                        if isinstance(impact_factor, str) and impact_factor.strip():
                            impact_factor_float = float(impact_factor)
                            safe_print(f"影响因子成功转换为数值: {impact_factor_float}")
                            impact_factor = impact_factor_float
                        elif isinstance(impact_factor, (int, float)):
                            safe_print(f"影响因子已经是数值类型: {impact_factor}")
                        else:
                            safe_print(f"影响因子无法转换为数值: '{impact_factor}', 类型: {type(impact_factor).__name__}")
                except (ValueError, TypeError) as e:
                    safe_print(f"影响因子转换为数字失败: {e}, 原始值: '{impact_factor}'")
                
                # 提取五年影响因子
                impact_factor_5yr = rank_data.get("sciif5", "未知")
                
                # 提取JCI指数
                jci = rank_data.get("jci", "未知")
                
                # 提取分区信息
                quartile = rank_data.get("sci", "未知")
                
                # 提取学科分类
                subject = rank_data.get("esi", "未知")
                
                # 提取更多详细分区信息
                base_category = rank_data.get("sciBase", "未知")
                detail_category = rank_data.get("sciUpSmall", "未知")
                
                # 提取中国大学排名信息
                university_ranks = {}
                for key in ["cufe", "swjtu", "nju", "xju", "cug", "scu", "cpu"]:
                    if key in rank_data:
                        university_ranks[key] = rank_data[key]
                
                result = {
                    "impact_factor": impact_factor,
                    "impact_factor_str": str(impact_factor),
                    "impact_factor_5yr": impact_factor_5yr,
                    "jci": jci,
                    "quartile": quartile,
                    "subject": subject,
                    "base_category": base_category,
                    "jcr_category": detail_category,
                    "university_ranks": json.dumps(university_ranks, ensure_ascii=False),
                    "matched_journal": matched_journal_name
                }
                
                # 检查结果中的影响因子值
                safe_print(f"返回期刊信息: impact_factor={result['impact_factor']} ({type(result['impact_factor']).__name__}), " +
                          f"impact_factor_str={result['impact_factor_str']} ({type(result['impact_factor_str']).__name__})")
                
                return result
            else:
                safe_print(f"警告: rank_data仍然不是字典类型: {type(rank_data).__name__}")
        
        safe_print(f"未找到期刊 '{journal_name}' 的匹配数据")
        return {
            "impact_factor": "未知",
            "impact_factor_str": "未知",
            "impact_factor_5yr": "未知",
            "jci": "未知",
            "quartile": "未知",
            "subject": "未知",
            "base_category": "未知", 
            "jcr_category": "未知",
            "university_ranks": "{}",
            "matched_journal": matched_journal_name
        }
    
    def _get_similarity_score(self, name1, name2):
        """计算两个期刊名称的相似度分数"""
        name1 = name1.lower()
        name2 = name2.lower()
        
        # 移除常见的后缀和前缀
        for term in [" journal", " the ", " of ", " and ", " & "]:
            name1 = name1.replace(term, " ")
            name2 = name2.replace(term, " ")
        
        # 标准化空格
        name1 = " ".join(name1.split())
        name2 = " ".join(name2.split())
        
        # 计算相似度 (简单版本)
        if name1 == name2:
            return 1.0
        
        # 检查一个是否是另一个的子字符串
        if name1 in name2:
            return len(name1) / len(name2)
        if name2 in name1:
            return len(name2) / len(name1)
        
        # 计算共同单词
        words1 = set(name1.split())
        words2 = set(name2.split())
        common_words = words1.intersection(words2)
        
        if not common_words:
            return 0.0
        
        # 返回共同单词的比例
        return len(common_words) / max(len(words1), len(words2))
    
    def enhance_articles(self, input_file=None):
        """增强文章信息，添加期刊影响因子和分区"""
        input_file = input_file or self.config.get('input_sort')
        
        if not os.path.exists(input_file):
            safe_print(f"输入文件不存在: {input_file}")
            return []
        
        try:
            # 读取文章数据
            with open(input_file, 'r', encoding='utf-8-sig') as f:
                csv_content = f.read(1024)  # 读取文件头部内容进行调试
                safe_print(f"CSV文件开头内容预览:\n{csv_content[:200]}...")
                
                # 重置文件指针并读取CSV
                f.seek(0)
                reader = csv.DictReader(f)
                
                # 检查CSV列名
                if reader.fieldnames:
                    safe_print(f"CSV列名: {', '.join(reader.fieldnames)}")
                    if 'journal' not in reader.fieldnames:
                        safe_print("警告: CSV中不存在'journal'列!")
                else:
                    safe_print("警告: 无法获取CSV列名")
                
                articles = list(reader)
            
            safe_print(f"成功读取 {len(articles)} 篇文章数据")
            
            # 打印前几篇文章的期刊名称
            for i, article in enumerate(articles[:5]):
                safe_print(f"文章 {i+1} 期刊名称: '{article.get('journal', '未知')}'")
            
            # 增强文章信息
            enhanced_count = 0
            match_count = 0
            failed_journals = set()
            
            with tqdm(total=len(articles), desc="增强文章信息", unit="篇") as pbar:
                for article in articles:
                    try:
                        journal_name = article.get('journal', '')
                        if journal_name:
                            match_count += 1
                            journal_info = self._get_journal_info(journal_name)
                            
                            if journal_info:
                                # 检查journal_info内容
                                safe_print(f"获取到期刊信息: {json.dumps(journal_info, ensure_ascii=False)[:200]}...")
                                
                                # 确保impact_factor存在于journal_info中并非未知
                                if 'impact_factor' in journal_info and journal_info['impact_factor'] != "未知":
                                    enhanced_count += 1
                                    # 复制影响因子值到文章字典
                                    safe_print(f"成功添加影响因子: {journal_info['impact_factor']}")
                                else:
                                    safe_print(f"警告: 未获取到期刊 '{journal_name}' 的影响因子")
                                    failed_journals.add(journal_name)
                                
                                # 更新文章字典
                                for key, value in journal_info.items():
                                    article[key] = value
                    except Exception as e:
                        safe_print(f"处理文章期刊 '{journal_name}' 时出错: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    pbar.update(1)
            
            safe_print(f"文章总数: {len(articles)}, 包含期刊名称: {match_count}, 成功匹配影响因子: {enhanced_count}")
            if failed_journals:
                safe_print(f"未能匹配影响因子的期刊 (前10个): {list(failed_journals)[:10]}")
            
            # 排序文章
            sorted_articles = self._sort_articles(articles)
            
            return sorted_articles
            
        except Exception as e:
            safe_print(f"增强文章信息出错: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _sort_articles(self, articles):
        """根据配置的排序方式对文章进行排序"""
        sort_type = self.config.get('article_sort', 'impact_factor').lower()
        
        safe_print(f"按照 {sort_type} 对文章进行排序")
        
        if sort_type == 'impact_factor':
            # 按影响因子排序 (从高到低)
            return sorted(articles, key=lambda x: self._get_sort_key_impact_factor(x), reverse=True)
        
        elif sort_type == 'journal':
            # 按期刊名称排序 (字母顺序)
            return sorted(articles, key=lambda x: x.get('journal', '').lower())
        
        elif sort_type == 'quartile':
            # 先按分区排序，再按影响因子排序
            return sorted(articles, 
                         key=lambda x: (self._get_sort_key_quartile(x), 
                                      self._get_sort_key_impact_factor(x)), 
                         reverse=True)
        
        elif sort_type == 'date':
            # 按发表日期排序 (从新到旧)
            return sorted(articles, key=lambda x: self._get_sort_key_date(x), reverse=True)
        
        else:
            safe_print(f"未知的排序方式: {sort_type}，默认按影响因子排序")
            return sorted(articles, key=lambda x: self._get_sort_key_impact_factor(x), reverse=True)
    
    def _get_sort_key_impact_factor(self, article):
        """获取文章的影响因子排序键"""
        impact_factor = article.get('impact_factor', 'unknown')
        
        # 如果已经是数字类型，直接返回
        if isinstance(impact_factor, (int, float)):
            return impact_factor
        
        # 尝试转换为数字
        try:
            return float(impact_factor)
        except (ValueError, TypeError):
            return -1  # 未知影响因子排在最后
    
    def _get_sort_key_quartile(self, article):
        """获取文章的分区排序键"""
        quartile = article.get('quartile', 'unknown')
        
        # 分区映射 (Q1 > Q2 > Q3 > Q4 > 未知)
        quartile_map = {
            'Q1': 4,
            'Q2': 3, 
            'Q3': 2,
            'Q4': 1,
            '1区': 4,
            '2区': 3,
            '3区': 2,
            '4区': 1,
            '一区': 4,
            '二区': 3,
            '三区': 2,
            '四区': 1
        }
        
        # 返回分区对应的数值
        return quartile_map.get(quartile, 0)
    
    def _get_sort_key_date(self, article):
        """获取文章的日期排序键"""
        date_str = article.get('pub_date', '')
        
        if not date_str or date_str == '未知日期':
            return datetime.min
        
        try:
            # 尝试解析多种日期格式
            formats = ['%Y-%m-%d', '%Y-%m', '%Y']
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # 如果所有格式都失败了，尝试提取年份
            year_match = re.search(r'(\d{4})', date_str)
            if year_match:
                return datetime(int(year_match.group(1)), 1, 1)
                
            return datetime.min
            
        except Exception:
            return datetime.min
    
    def export_to_csv(self, articles, output_file=None):
        """导出增强后的文章信息到CSV文件"""
        if not articles:
            safe_print("没有文章可导出")
            return False
        
        output_file = output_file or self.config.get('output_sort')
        
        try:
            # 扩展字段列表以包含更多信息
            fieldnames = [
                'title', 'authors', 'journal', 'pub_date', 
                'impact_factor_str', 'impact_factor_5yr', 'jci', 'quartile', 
                'subject', 'base_category', 'jcr_category',
                'doi', 'pmid', 'citations', 'keywords', 'abstract'
            ]
            
            # 添加调试信息: 检查所有文章中的关键字段
            if articles:
                impact_factor_values = []
                for article in articles[:10]:  # 只检查前10篇
                    impact_factor_values.append(
                        (article.get('journal', '未知'), 
                         article.get('impact_factor', '未知'),
                         article.get('impact_factor_str', '未知'))
                    )
                
                safe_print("文章影响因子检查 (前10篇):")
                for i, (journal, if_val, if_str) in enumerate(impact_factor_values):
                    safe_print(f"  {i+1}. 期刊: '{journal}', 影响因子: {if_val}, 影响因子字符串: {if_str}")
            
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for idx, article in enumerate(articles):
                    # 检查要导出的文章数据
                    if idx < 5:  # 只显示前5篇
                        safe_print(f"导出文章 #{idx+1} 数据预览:")
                        for field in ['journal', 'impact_factor', 'impact_factor_str']:
                            safe_print(f"  - {field}: {article.get(field, '未设置')} ({type(article.get(field, '')).__name__})")
                    
                    # 构造行数据
                    row = {}
                    for field in fieldnames:
                        # 确保字段值是字符串
                        value = article.get(field, '')
                        
                        # 特殊处理impact_factor_str字段
                        if field == 'impact_factor_str':
                            # 优先使用原始影响因子值
                            impact_factor = article.get('impact_factor', None)
                            if impact_factor not in [None, '', 'None', 'unknown', '未知']:
                                value = str(impact_factor)
                                safe_print(f"文章 #{idx+1}: 使用影响因子值 {impact_factor} 作为 impact_factor_str")
                        
                        row[field] = str(value)
                    
                    writer.writerow(row)
                    
                    # 输出前几篇文章的行数据
                    if idx < 3:
                        safe_print(f"导出文章 #{idx+1}: impact_factor_str = {row.get('impact_factor_str', '未知')}")
            
            safe_print(f"成功导出 {len(articles)} 篇增强后的文章到: {output_file}")
            return True
            
        except Exception as e:
            safe_print(f"导出CSV失败: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """主程序入口"""
    try:
        # 初始化增强处理器
        enhancer = JournalEnhancer()
        
        # 增强文章信息
        enhanced_articles = enhancer.enhance_articles()
        
        if enhanced_articles:
            # 导出增强后的文章
            enhancer.export_to_csv(enhanced_articles)
        else:
            safe_print("没有增强后的文章可导出")
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()