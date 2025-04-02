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
        
        # 如果提供了log_file，初始化日志系统（如果导入了log_utils）
        if log_file and 'init_logger' in globals():
            init_logger(log_file=log_file, verbose=verbose)
        
        # 然后再读取配置和加载期刊数据
        self.config = self._read_config(config_file)
        self.journal_data = self._load_journal_data()
        
        safe_print(f"期刊信息增强处理工具初始化完成，已加载 {len(self.journal_data)} 本期刊信息", self.verbose)
    
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
                        safe_print(f"已向配置文件 {config_file} 添加期刊和排序设置", self.verbose)
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
                safe_print(f"已创建包含期刊和排序设置的配置文件: {config_file}", self.verbose)
        except Exception as e:
            safe_print(f"更新配置文件出错: {e}", self.verbose)
    
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
                safe_print(f"共加载 {total_journals} 个期刊, 示例期刊: {', '.join(sample_journals)}", self.verbose)
                
                # 检查几个示例期刊的内容格式
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
            else:
                safe_print(f"期刊数据文件不存在: {journal_data_path}", self.verbose)
        except Exception as e:
            safe_print(f"加载期刊数据出错: {e}", self.verbose)
            import traceback
            traceback.print_exc()
        
        return journal_data
    
    def enhance_articles(self, input_file=None):
        """增强文章信息，添加期刊影响因子和分区"""
        input_file = input_file or self.config.get('input_sort')
        
        if not os.path.exists(input_file):
            safe_print(f"输入文件不存在: {input_file}", self.verbose)
            return []
        
        try:
            # 读取文章数据
            with open(input_file, 'r', encoding='utf-8-sig') as f:
                csv_content = f.read(1024)  # 读取文件头部内容进行调试
                safe_print(f"CSV文件开头内容预览:\n{csv_content[:200]}...", self.verbose)
                
                # 重置文件指针并读取CSV
                f.seek(0)
                reader = csv.DictReader(f)
                
                # 检查CSV列名
                if reader.fieldnames:
                    safe_print(f"CSV列名: {', '.join(reader.fieldnames)}", self.verbose)
                    if 'journal' not in reader.fieldnames:
                        safe_print("警告: CSV中不存在'journal'列!", self.verbose)
                else:
                    safe_print("警告: 无法获取CSV列名", self.verbose)
                
                articles = list(reader)
            
            safe_print(f"成功读取 {len(articles)} 篇文章数据", self.verbose)
            
            # 打印前几篇文章的期刊名称
            for i, article in enumerate(articles[:5]):
                safe_print(f"文章 {i+1} 期刊名称: '{article.get('journal', '未知')}'", self.verbose)
            
            # 增强文章信息
            enhanced_count = 0
            match_count = 0
            failed_journals = set()
            
            with tqdm(total=len(articles), desc="增强文章信息", unit="篇", 
                      disable=not self.verbose, # 非详细模式下禁用tqdm
                      leave=False,  # 完成后不留下进度条
                      ncols=80,     # 固定宽度
                      bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}') as pbar:
                for article in articles:
                    try:
                        journal_name = article.get('journal', '')
                        if journal_name:
                            match_count += 1
                            journal_info = self._get_journal_info(journal_name)
                            
                            if journal_info:
                                # 检查journal_info内容
                                if self.verbose:
                                    safe_print(f"获取到期刊信息: {json.dumps(journal_info, ensure_ascii=False)[:200]}...", self.verbose)
                                
                                # 确保impact_factor存在于journal_info中并非未知
                                if 'impact_factor' in journal_info and journal_info['impact_factor'] != "未知":
                                    enhanced_count += 1
                                    # 复制影响因子值到文章字典
                                    safe_print(f"成功添加影响因子: {journal_info['impact_factor']}", self.verbose)
                                else:
                                    safe_print(f"警告: 未获取到期刊 '{journal_name}' 的影响因子", self.verbose)
                                    failed_journals.add(journal_name)
                                
                                # 更新文章字典
                                for key, value in journal_info.items():
                                    article[key] = value
                    except Exception as e:
                        safe_print(f"处理文章期刊 '{journal_name}' 时出错: {e}", self.verbose)
                        if self.verbose:
                            import traceback
                            traceback.print_exc()
                    
                    pbar.update(1)
            
            safe_print(f"文章总数: {len(articles)}, 包含期刊名称: {match_count}, 成功匹配影响因子: {enhanced_count}", self.verbose)
            if failed_journals:
                safe_print(f"未能匹配影响因子的期刊 (前10个): {list(failed_journals)[:10]}", self.verbose)
            
            # 排序文章
            sorted_articles = self._sort_articles(articles)
            
            return sorted_articles
            
        except Exception as e:
            safe_print(f"增强文章信息出错: {e}", self.verbose)
            import traceback
            traceback.print_exc()
            return []
    
    def _get_journal_info(self, journal_name):
        """获取期刊信息，包括影响因子和分区"""
        if not journal_name or not self.journal_data:
            return None
        
        # 规范化期刊名称，移除引号、括号等特殊字符，转为小写
        journal_name_norm = re.sub(r'[^\w\s]', '', journal_name.lower())
        journal_name_norm = re.sub(r'\s+', ' ', journal_name_norm).strip()
        
        # 从期刊名称中移除括号和其中内容
        journal_name_no_paren = re.sub(r'\s*\([^)]*\)', '', journal_name)
        journal_name_no_paren_norm = re.sub(r'[^\w\s]', '', journal_name_no_paren.lower())
        journal_name_no_paren_norm = re.sub(r'\s+', ' ', journal_name_no_paren_norm).strip()
        
        safe_print(f"处理期刊名称: 原始='{journal_name}', 去括号='{journal_name_no_paren}'", self.verbose)
        
        # 直接匹配尝试
        if journal_name in self.journal_data:
            return self._extract_journal_info(journal_name)
        
        # 尝试使用去掉括号的名称匹配
        for journal in self.journal_data.keys():
            # 如果去掉括号后的期刊名称完全匹配数据库中的某个期刊
            if journal_name_no_paren.lower() == journal.lower():
                safe_print(f"通过去除括号匹配到期刊: '{journal_name}' -> '{journal}'", self.verbose)
                return self._extract_journal_info(journal)
        
        # 尝试模糊匹配
        best_match = None
        highest_similarity = 0.6  # 设置一个相似度阈值
        
        for journal in self.journal_data.keys():
            # 规范化数据库中的期刊名称
            journal_norm = re.sub(r'[^\w\s]', '', journal.lower())
            journal_norm = re.sub(r'\s+', ' ', journal_norm).strip()
            
            # 计算两种名称格式的相似度
            similarity1 = self._calculate_similarity(journal_name_norm, journal_norm)
            similarity2 = self._calculate_similarity(journal_name_no_paren_norm, journal_norm)
            
            # 取较高的相似度
            similarity = max(similarity1, similarity2)
            
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = journal
        
        if best_match:
            safe_print(f"期刊名称 '{journal_name}' 匹配到 '{best_match}', 相似度: {highest_similarity:.2f}", self.verbose)
            return self._extract_journal_info(best_match)
        else:
            safe_print(f"未找到期刊 '{journal_name}' 的匹配信息", self.verbose)
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
                if "sciif" in rank_data:
                    impact_factor = rank_data["sciif"]
                elif "if" in rank_data:
                    impact_factor = rank_data["if"]
                
                # 提取分区信息 - 添加常见的分区字段，包括sci和sciBase
                if "sci" in rank_data:
                    # 您的JSON数据使用"sci"字段存储分区信息，如"Q1"
                    quartile = rank_data["sci"]
                    safe_print(f"从sci字段获取到分区信息: {quartile}", self.verbose)
                elif "sciBase" in rank_data:
                    # sciBase可能包含如"生物1区"这样的字符串
                    quartile = rank_data["sciBase"]
                    safe_print(f"从sciBase字段获取到分区信息: {quartile}", self.verbose)
                elif "zone" in rank_data:
                    quartile = rank_data["zone"]
                elif "q" in rank_data:
                    quartile = rank_data["q"]
                elif "quartile" in rank_data:
                    quartile = rank_data["quartile"]
                
                # 添加调试输出
                if quartile != "未知":
                    safe_print(f"成功为期刊 '{journal_name}' 获取分区信息: {quartile}", self.verbose)
                else:
                    safe_print(f"未找到期刊 '{journal_name}' 的分区信息，请检查rank中的字段: {list(rank_data.keys())}", self.verbose)
            
            # 构建返回结果
            return {
                "impact_factor": impact_factor,
                "quartile": quartile,
                "journal_full_name": journal_name
            }
            
        except Exception as e:
            safe_print(f"提取期刊信息出错: {e}", self.verbose)
            return None
    
    def _calculate_similarity(self, s1, s2):
        """计算两个字符串的相似度（简化版Levenshtein距离）"""
        if not s1 or not s2:
            return 0
        
        # 如果其中一个是另一个的子串，给予较高相似度
        if s1 in s2:
            return 0.9 * len(s1) / len(s2)
        if s2 in s1:
            return 0.9 * len(s2) / len(s1)
        
        # 计算公共子序列
        matrix = [[0 for x in range(len(s2) + 1)] for y in range(len(s1) + 1)]
        for i in range(1, len(s1) + 1):
            for j in range(1, len(s2) + 1):
                if s1[i-1] == s2[j-1]:
                    matrix[i][j] = matrix[i-1][j-1] + 1
                else:
                    matrix[i][j] = max(matrix[i-1][j], matrix[i][j-1])
        
        # 计算相似度
        common_length = matrix[len(s1)][len(s2)]
        return (2.0 * common_length) / (len(s1) + len(s2))
    
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
        enhancer = JournalEnhancer(verbose=True, log_file="journal_enhancer.log")
        
        # 增强文章信息
        enhanced_articles = enhancer.enhance_articles()
        
        if enhanced_articles:
            # 导出增强后的文章
            enhancer.export_to_csv(enhanced_articles)
        else:
            safe_print("没有增强后的文章可导出", True)
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}", True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()