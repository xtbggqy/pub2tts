"""
期刊数据可视化模块
提供将期刊影响因子和分区信息可视化的功能
"""
import os
import csv
import json
import re
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from collections import Counter, defaultdict
import random

# 导入词云图所需库
try:
    from wordcloud import WordCloud, STOPWORDS
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False

# 设置matplotlib支持中文和英文字体
try:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'STHeiti', 'sans-serif']
    plt.rcParams['font.monospace'] = ['Consolas', 'Courier New', 'DejaVu Sans Mono']  # 设置等宽英文字体
    plt.rcParams['font.family'] = 'sans-serif'  # 默认使用sans-serif族
    # 设置全局默认英文字体为Consolas
    matplotlib.rcParams['mathtext.fontset'] = 'custom'
    matplotlib.rcParams['mathtext.rm'] = 'Consolas'
    matplotlib.rcParams['mathtext.it'] = 'Consolas:italic'
    matplotlib.rcParams['mathtext.bf'] = 'Consolas:bold'
    plt.rcParams['axes.unicode_minus'] = False  # 解决保存图像是负号'-'显示为方块的问题
except:
    pass  # 如果设置失败，继续使用默认字体

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
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告", "生成图表", "可视化"]):
                return
                
        try:
            print(msg)
            import sys
            sys.stdout.flush()
        except:
            print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
            import sys
            sys.stdout.flush()

class JournalVisualizer:
    """期刊数据可视化工具"""
    
    # 定义颜色主题和调色板
    COLOR_THEMES = {
        'default': {
            'impact_factor': ['#4285F4', '#EA4335', '#FBBC05', '#34A853', '#5F6368', '#7B42F6', '#137333', '#FA903E'],
            'quartile': ['#4CAF50', '#8BC34A', '#FFC107', '#FF9800', '#9E9E9E', '#E0E0E0'],
            'journal': ['#5C6BC0', '#EC407A', '#26A69A', '#7E57C2', '#9CCC65', '#78909C', '#FF7043', '#FFCA28'],
            'year': ['#039BE5', '#536DFE', '#1DE9B6', '#F06292', '#9FA8DA', '#29B6F6'],
            'background': '#f8f9fa',
            'text': '#202124',
            'grid': '#dadce0',
        },
        'modern': {
            'impact_factor': ['#3366CC', '#DC3912', '#FF9900', '#109618', '#990099', '#0099C6', '#DD4477', '#66AA00'],
            'quartile': ['#2E7D32', '#689F38', '#F9A825', '#EF6C00', '#757575', '#BDBDBD'],
            'journal': ['#3949AB', '#D81B60', '#00897B', '#7B1FA2', '#7CB342', '#546E7A', '#D84315', '#FFB300'],
            'year': ['#0288D1', '#304FFE', '#00BFA5', '#C2185B', '#7986CB', '#039BE5'],
            'background': '#FFFFFF',
            'text': '#212121',
            'grid': '#EEEEEE',
        },
        'pastel': {
            'impact_factor': ['#B3DAF2', '#F2C9C5', '#FADCAE', '#C8E6C9', '#D1C4E9', '#FFE0B2', '#FFCCBC', '#D7CCC8'],
            'quartile': ['#A5D6A7', '#C5E1A5', '#FFF59D', '#FFCC80', '#EEEEEE', '#F5F5F5'],
            'journal': ['#C5CAE9', '#F8BBD0', '#B2DFDB', '#D1C4E9', '#DCEDC8', '#CFD8DC', '#FFCCBC', '#FFE0B2'],
            'year': ['#B3E5FC', '#C5CAE9', '#B2DFDB', '#F8BBD0', '#C5CAE9', '#B3E5FC'],
            'background': '#FAFAFA',
            'text': '#37474F',
            'grid': '#E0E0E0',
        },
        'dark': {
            'impact_factor': ['#5C6BC0', '#EF5350', '#FFCA28', '#66BB6A', '#78909C', '#AB47BC', '#26A69A', '#FF7043'],
            'quartile': ['#2E7D32', '#558B2F', '#F9A825', '#FF6F00', '#616161', '#9E9E9E'],
            'journal': ['#3949AB', '#E91E63', '#00897B', '#8E24AA', '#7CB342', '#546E7A', '#F4511E', '#FFB300'],
            'year': ['#0277BD', '#3949AB', '#00897B', '#E91E63', '#5C6BC0', '#0288D1'],
            'background': '#263238',
            'text': '#ECEFF1',
            'grid': '#37474F',
        },
        'scientific': {
            'impact_factor': ['#0277BD', '#00695C', '#F57F17', '#1B5E20', '#283593', '#880E4F', '#4E342E', '#004D40'],
            'quartile': ['#00695C', '#2E7D32', '#F57F17', '#E65100', '#424242', '#757575'],
            'journal': ['#1A237E', '#880E4F', '#004D40', '#4A148C', '#33691E', '#37474F', '#BF360C', '#E65100'],
            'year': ['#01579B', '#1A237E', '#004D40', '#880E4F', '#303F9F', '#0277BD'],
            'background': '#FAFAFA',
            'text': '#212121',
            'grid': '#DDDDDD',
        }
    }
    
    def __init__(self, config_file="pub.txt", verbose=False, log_file=None):
        """初始化可视化工具
        
        Args:
            config_file: 配置文件路径
            verbose: 是否输出详细日志
            log_file: 日志文件路径，如果为None则不记录到文件
        """
        # 先设置verbose属性
        self.verbose = verbose
        self.config_file = config_file
        
        # 如果提供了log_file，初始化日志系统
        if log_file and 'init_logger' in globals():
            init_logger(log_file=log_file, verbose=verbose)
        
        # 读取配置
        self.config = self._read_config(config_file)
        
        # 创建输出目录
        self.viz_output_dir = self.config.get('viz_output_dir', 'out/viz')
        if not os.path.exists(self.viz_output_dir):
            os.makedirs(self.viz_output_dir, exist_ok=True)
            
        # 设置图表主题
        self.theme = self.config.get('viz_color_theme', 'default')
        if self.theme not in self.COLOR_THEMES:
            safe_print(f"警告: 未知的颜色主题 '{self.theme}'，使用默认主题", self.verbose)
            self.theme = 'default'
            
        safe_print(f"期刊可视化工具初始化完成，使用 '{self.theme}' 主题", self.verbose)
    
    def _read_config(self, config_file):
        """从配置文件读取设置"""
        config = {
            'viz_enabled': True,                       # 是否启用可视化
            'viz_output_dir': 'out/viz',               # 可视化输出目录
            'viz_format': 'png',                       # 图表格式(png, jpg, pdf, svg)
            'viz_style': 'ggplot',                     # 图表样式
            'viz_dpi': 300,                            # 图表DPI
            'viz_figsize': '10,6',                     # 图表大小(宽,高)
            'viz_show_if': False,                      # 改为默认不显示影响因子趋势
            'viz_show_quartile': True,                 # 是否显示分区分布
            'viz_show_journals': False,                # 改为默认不显示期刊分布
            'viz_show_years': True,                    # 是否显示发表年份分布
            'viz_show_wordcloud': True,                # 新增: 是否显示关键词词云图
            'viz_wordcloud_max': 100,                  # 新增: 词云图最大显示词数
            'viz_color_theme': 'default',              # 颜色主题
            'viz_font_size': 11,                       # 字体大小
            'viz_title_size': 14,                      # 标题字体大小
            'viz_label_size': 12,                      # 标签字体大小
            'viz_grid_alpha': 0.3,                     # 网格透明度
            'input_sort': 'out/pubmed_enhanced.csv',   # 期刊增强后的输入文件
            'viz_interactive': False,                  # 是否启用交互式图表
            'time_period': 3.0,                        # 默认时间周期(年)
            'start_date': '',                          # 开始日期
            'end_date': '',                            # 结束日期
            'expected_year_range': 3,                  # 默认预期年份范围
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
                                # 移除值部分的注释
                                value = value.split('#', 1)[0].strip()
                                
                                # 处理布尔值
                                if key in ['viz_enabled', 'viz_show_if', 'viz_show_quartile', 
                                           'viz_show_journals', 'viz_show_years', 'viz_show_wordcloud', 'viz_interactive']:
                                    config[key] = value.lower() in ['true', 'yes', 'y', '1']
                                # 处理数值
                                elif key in ['viz_dpi', 'viz_font_size', 'viz_title_size', 'viz_label_size', 'viz_wordcloud_max']:
                                    try:
                                        config[key] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的{key}值: {value}，使用默认值", self.verbose)
                                elif key in ['viz_grid_alpha', 'time_period']:
                                    try:
                                        config[key] = float(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的{key}值: {value}，使用默认值", self.verbose)
                                # 处理其他字符串值
                                elif key in config:
                                    config[key] = value
                                # 输入文件特殊处理
                                elif key == 'output_sort':
                                    config['input_sort'] = value

                # 确定预期年份范围
                # 使用明确的日期范围（如果设置了）
                if config['start_date'] and config['end_date']:
                    try:
                        # 尝试解析日期
                        start_date = self._parse_config_date(config['start_date'])
                        end_date = self._parse_config_date(config['end_date'])
                        if start_date and end_date:
                            # 计算年份差异
                            year_diff = end_date.year - start_date.year
                            # 考虑月份来精确计算
                            if end_date.month < start_date.month or (end_date.month == start_date.month and end_date.day < start_date.day):
                                year_diff -= 1
                            config['expected_year_range'] = max(1, year_diff)
                            safe_print(f"根据明确日期范围设置预期年份范围: {config['expected_year_range']}年", self.verbose)
                    except Exception as e:
                        safe_print(f"解析日期范围出错: {e}", self.verbose)
                # 使用时间周期（如果没有设置明确日期）
                elif config['time_period'] > 0:
                    config['expected_year_range'] = max(1, int(config['time_period'] + 0.5))  # 四舍五入到整数年
                    safe_print(f"根据时间周期设置预期年份范围: {config['expected_year_range']}年", self.verbose)
                
                # 检查是否缺少配置项，如果是，则添加到配置文件
                self._check_and_update_config(config_file, config)
                
                safe_print("已从配置文件加载可视化设置", self.verbose)
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置", self.verbose)
        except Exception as e:
            safe_print(f"读取配置文件出错: {e}", self.verbose)
            safe_print("使用默认可视化设置", self.verbose)
        
        return config
    
    def _parse_config_date(self, date_str):
        """解析配置文件中的日期字符串"""
        try:
            # 尝试不同的日期格式
            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m', '%Y/%m', '%Y']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    def _check_and_update_config(self, config_file, config):
        """检查并更新配置文件，添加缺失的配置项"""
        needed_params = {
            'viz_enabled': '# 是否启用可视化功能(yes/no)\nviz_enabled=yes\n\n',
            'viz_output_dir': '# 可视化输出目录\nviz_output_dir=out/viz\n\n',
            'viz_format': '# 图表格式(png, jpg, pdf, svg)\nviz_format=png\n\n',
            'viz_style': '# 图表样式(ggplot, seaborn, classic, dark_background等)\nviz_style=ggplot\n\n',
            'viz_dpi': '# 图表DPI(分辨率)\nviz_dpi=300\n\n',
            'viz_figsize': '# 图表大小(宽,高，单位为英寸)\nviz_figsize=10,6\n\n',
            'viz_show_if': '# 是否显示影响因子趋势(yes/no)\nviz_show_if=no\n\n',
            'viz_show_quartile': '# 是否显示分区分布(yes/no)\nviz_show_quartile=yes\n\n',
            'viz_show_journals': '# 是否显示期刊分布(yes/no)\nviz_show_journals=no\n\n',
            'viz_show_years': '# 是否显示发表年份分布(yes/no)\nviz_show_years=yes\n\n',
            'viz_show_wordcloud': '# 是否显示关键词词云图(yes/no)\nviz_show_wordcloud=yes\n\n',
            'viz_wordcloud_max': '# 词云图最大显示词数\nviz_wordcloud_max=100\n\n',
            'viz_color_theme': '# 颜色主题(default, modern, pastel, dark, scientific)\nviz_color_theme=default\n\n',
            'viz_font_size': '# 图表字体大小\nviz_font_size=11\n\n',
            'viz_title_size': '# 图表标题字体大小\nviz_title_size=14\n\n',
            'viz_label_size': '# 图表标签字体大小\nviz_label_size=12\n\n',
            'viz_grid_alpha': '# 网格透明度(0-1)\nviz_grid_alpha=0.3\n\n',
            'viz_interactive': '# 是否启用交互式图表(yes/no)\nviz_interactive=no\n\n',
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
                    f.write("\n# 期刊可视化高级设置\n")
                    for addition in additions:
                        f.write(addition)
                safe_print(f"已向 {config_file} 添加可视化高级设置", self.verbose)
        except Exception as e:
            safe_print(f"更新配置文件出错: {e}", self.verbose)
    
    def _parse_figsize(self, figsize_str):
        """解析图表大小配置"""
        try:
            width, height = figsize_str.split(',')
            return (float(width), float(height))
        except:
            safe_print(f"无效的图表大小格式: {figsize_str}，使用默认值(10,6)", self.verbose)
            return (10, 6)
    
    def _setup_figure_style(self, ax=None):
        """设置图表样式"""
        # 获取当前主题的配色
        colors = self.COLOR_THEMES[self.theme]
        
        # 设置字体大小
        plt.rcParams['font.size'] = self.config.get('viz_font_size', 11)
        
        # 如果提供了ax对象，设置其样式
        if ax:
            # 设置背景颜色
            ax.set_facecolor(colors['background'])
            if ax.figure:
                ax.figure.set_facecolor(colors['background'])
            
            # 设置文本颜色
            ax.title.set_color(colors['text'])
            ax.xaxis.label.set_color(colors['text'])
            ax.yaxis.label.set_color(colors['text'])
            
            # 设置刻度标签颜色
            for label in ax.get_xticklabels():
                label.set_color(colors['text'])
            for label in ax.get_yticklabels():
                label.set_color(colors['text'])
            
            # 设置网格样式
            grid_alpha = self.config.get('viz_grid_alpha', 0.3)
            ax.grid(True, linestyle='--', alpha=grid_alpha, color=colors['grid'])
            
            # 设置脊线颜色
            for spine in ax.spines.values():
                spine.set_color(colors['grid'])
    
    def visualize_journal_data(self, input_file=None):
        """可视化期刊数据
        
        Args:
            input_file: CSV文件路径，包含期刊数据
            
        Returns:
            生成的图表文件路径列表
        """
        if not self.config.get('viz_enabled', True):
            safe_print("期刊可视化功能已禁用", self.verbose)
            return []
            
        input_file = input_file or self.config.get('input_sort')
        if not os.path.exists(input_file):
            safe_print(f"输入文件不存在: {input_file}", self.verbose)
            return []
        
        try:
            # 读取期刊数据
            data = self._read_journal_data(input_file)
            if not data:
                safe_print("未找到有效的期刊数据", self.verbose)
                return []
            
            # 设置matplotlib样式
            plt.style.use(self.config.get('viz_style', 'ggplot'))
            
            # 生成图表
            chart_files = []
            
            # 影响因子趋势图 - 可选择显示
            if self.config.get('viz_show_if', False):
                if_chart = self._create_impact_factor_chart(data)
                if if_chart:
                    chart_files.append(if_chart)
            
            # 分区分布图 - 保留
            if self.config.get('viz_show_quartile', True):
                quartile_chart = self._create_quartile_chart(data)
                if quartile_chart:
                    chart_files.append(quartile_chart)
            
            # 期刊分布图 - 可选择显示
            if self.config.get('viz_show_journals', False):
                journal_chart = self._create_journal_chart(data)
                if journal_chart:
                    chart_files.append(journal_chart)
            
            # 发表年份分布图 - 保留
            if self.config.get('viz_show_years', True):
                year_chart = self._create_year_chart(data)
                if year_chart:
                    chart_files.append(year_chart)
            
            # 新增: 关键词词云图
            if self.config.get('viz_show_wordcloud', True):
                if WORDCLOUD_AVAILABLE:
                    wordcloud_chart = self._create_wordcloud_chart(data)
                    if wordcloud_chart:
                        chart_files.append(wordcloud_chart)
                else:
                    safe_print("警告: 无法生成词云图，请安装wordcloud库：pip install wordcloud", True)
            
            return chart_files
            
        except Exception as e:
            safe_print(f"可视化期刊数据出错: {e}", self.verbose)
            import traceback
            traceback.print_exc()
            return []
    
    def _read_journal_data(self, file_path):
        """读取期刊数据"""
        data = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 确保必要的字段存在
                    if 'journal' not in row:
                        continue
                    
                    # 收集数据
                    journal_data = {
                        'journal': row.get('journal', '').strip(),
                        'impact_factor': self._extract_float(row.get('impact_factor', '0')),
                        'quartile': row.get('quartile', '').strip(),
                        'pub_date': row.get('pub_date', '').strip(),
                        'keywords': row.get('keywords', '').strip(),
                        'translated_keywords': row.get('translated_keywords', '').strip()
                    }
                    data.append(journal_data)
            
            safe_print(f"读取了 {len(data)} 篇文章的期刊数据", self.verbose)
            return data
        except Exception as e:
            safe_print(f"读取期刊数据出错: {e}", self.verbose)
            return []
    
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
    
    def _create_wordcloud_chart(self, data):
        """创建关键词词云图
        
        Args:
            data: 文章数据列表
            
        Returns:
            词云图文件路径或None
        """
        try:
            if not WORDCLOUD_AVAILABLE:
                safe_print("无法创建词云图: 缺少wordcloud库", True)
                return None
                
            # 收集所有关键词
            all_keywords = []
            for article in data:
                # 优先使用翻译后的关键词
                keywords = article.get('translated_keywords', '') or article.get('keywords', '')
                if not keywords:
                    continue
                
                # 分割关键词
                keyword_list = re.split(r'[;,，；]', keywords)
                for keyword in keyword_list:
                    # 清理关键词
                    keyword = keyword.strip()
                    # 去除一些常见的AI生成标记和括号内容
                    keyword = re.sub(r'\[AI生成\]|\(.*?\)', '', keyword).strip()
                    
                    if len(keyword) > 1:  # 过滤单字符关键词
                        all_keywords.append(keyword)
            
            if not all_keywords or len(all_keywords) < 5:
                safe_print("警告: 没有足够的关键词可供生成词云图", self.verbose)
                return None
            
            # 统计关键词频率
            keyword_freq = Counter(all_keywords)
            
            safe_print(f"收集到 {len(keyword_freq)} 个不同的关键词用于词云图", self.verbose)
            if self.verbose:
                safe_print(f"前10个高频关键词: {keyword_freq.most_common(10)}", self.verbose)
            
            # 准备词云图
            max_words = self.config.get('viz_wordcloud_max', 100)
            
            # 获取配色和设置
            colors = self.COLOR_THEMES[self.theme]
            background_color = colors['background']
            text_color = colors['text']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            # 获取合适的中文字体
            font_path = self._get_font_path()
            
            # 创建词云图对象
            wordcloud = WordCloud(
                width=1600, 
                height=900,
                background_color=background_color,
                max_words=max_words,
                min_font_size=10,
                max_font_size=160,
                prefer_horizontal=0.9,
                scale=2,
                relative_scaling=0.6,  # 词频和大小的关联度
                colormap='viridis',    # 默认颜色映射
                collocations=False,    # 避免显示二元词组
                regexp=r'\w[\w\s()+-]+',  # 匹配模式
                normalize_plurals=False,  # 不要规范复数
                include_numbers=False,    # 不包含数字
                font_path=font_path,      # 设置字体
                random_state=42           # 固定随机状态以保持一致性
            ).generate_from_frequencies(dict(keyword_freq))
            
            # 创建图表
            fig, ax = plt.subplots(figsize=figsize, facecolor=background_color)
            ax.set_facecolor(background_color)
            
            # 显示词云图
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis('off')  # 关闭坐标轴
            
            # 设置标题
            ax.set_title('文献关键词云图', fontsize=title_size, fontweight='bold', color=text_color, pad=20)
            
            # 添加注释
            plt.figtext(
                0.5, 0.02,
                f"基于{len(data)}篇文献，共{len(keyword_freq)}个独立关键词，显示频率最高的{max_words}个",
                ha='center',
                fontsize=label_size-2,
                color=text_color,
                alpha=0.8
            )
            
            # 保存图表
            output_file = os.path.join(self.viz_output_dir, 
                                      f"keywords_wordcloud.{self.config.get('viz_format', 'png')}")
            plt.savefig(output_file, dpi=self.config.get('viz_dpi', 300), bbox_inches='tight')
            plt.close()
            
            safe_print(f"成功生成关键词词云图: {output_file}", self.verbose)
            return output_file
            
        except Exception as e:
            safe_print(f"生成关键词词云图失败: {e}", self.verbose)
            import traceback
            traceback.print_exc()
            return None
    
    def _get_font_path(self):
        """获取合适的中文字体路径"""
        # 尝试常见的中文字体路径
        font_paths = [
            # Windows路径
            "C:/Windows/Fonts/simhei.ttf",  # 黑体
            "C:/Windows/Fonts/simsun.ttc",   # 宋体
            "C:/Windows/Fonts/msyh.ttc",     # 微软雅黑
            
            # Mac路径
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            
            # Linux路径
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            
            # 项目内部路径 (如果有自带字体)
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts/simhei.ttf")
        ]
        
        # 检查字体文件是否存在
        for path in font_paths:
            if os.path.exists(path):
                safe_print(f"使用字体: {path}", self.verbose)
                return path
        
        # 如果找不到合适的中文字体，显示警告
        safe_print("警告: 找不到合适的中文字体，词云图可能无法正确显示中文字符", self.verbose)
        return None

    def _create_impact_factor_chart(self, data):
        """创建影响因子趋势图"""
        try:
            # 筛选有影响因子的数据并排序
            impact_data = [(item['journal'], item['impact_factor']) for item in data if item['impact_factor'] > 0]
            if not impact_data:
                safe_print("警告: 没有有效的影响因子数据可供可视化", self.verbose)
                return None
            
            # 按影响因子排序
            impact_data.sort(key=lambda x: x[1], reverse=True)
            
            # 如果数据过多，限制为前15个
            if len(impact_data) > 15:
                impact_data = impact_data[:15]
            
            # 准备绘图数据
            journals = [item[0] for item in impact_data]
            impact_factors = [item[1] for item in impact_data]
            
            # 获取配色和设置
            colors = self.COLOR_THEMES[self.theme]['impact_factor']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            # 为长期刊名调整图表高度
            max_journal_len = max([len(j) for j in journals])
            if max_journal_len > 30:
                height_factor = 1 + (max_journal_len - 30) / 100
                figsize = (figsize[0], figsize[1] * height_factor)
            
            # 创建图表
            fig, ax = plt.subplots(figsize=figsize)
            
            # 应用颜色主题和样式
            self._setup_figure_style(ax)
            
            # 横向条形图
            bars = ax.barh(journals, impact_factors, color=colors[:len(impact_data)], alpha=0.8)
            
            # 设置渐变色条形图
            for i, bar in enumerate(bars):
                # 根据影响因子值应用不同深浅的颜色
                color_index = i % len(colors)
                # 添加渐变填充，左侧深色，右侧浅色
                grad = matplotlib.colors.LinearSegmentedColormap.from_list(
                    f"grad{i}", 
                    [matplotlib.colors.to_rgba(colors[color_index], 0.7), 
                     matplotlib.colors.to_rgba(colors[color_index], 1.0)]
                )
                
                # 获取条形的位置和大小
                x, y = bar.get_xy()
                w, h = bar.get_width(), bar.get_height()
                
                # 在每个条形图中添加数值文本
                ax.text(
                    w + w*0.02,             # 略微偏离条形图右侧
                    y + h/2,                # 垂直居中
                    f'{w:.2f}',             # 显示两位小数
                    va='center',
                    ha='left',
                    fontsize=label_size-1,  # 稍微小一点的字体
                    color=self.COLOR_THEMES[self.theme]['text'],
                    fontweight='bold',      # 加粗显示
                    bbox=dict(
                        boxstyle="round,pad=0.3",  # 圆角方框
                        fc=self.COLOR_THEMES[self.theme]['background'],  # 背景色
                        ec=self.COLOR_THEMES[self.theme]['grid'],  # 边框色
                        alpha=0.7  # 半透明
                    )
                )
                
                # 使用渐变色填充条形图
                ax.imshow(
                    np.array([[0, 1]]), 
                    cmap=grad, 
                    aspect='auto',
                    extent=[x, x+w, y, y+h],
                    alpha=0.8
                )
            
            # 美化x轴
            ax.set_xlabel('影响因子 (Impact Factor)', fontsize=label_size, fontweight='bold')
            
            # 美化y轴
            ax.set_ylabel('期刊 (Journal)', fontsize=label_size, fontweight='bold')
            
            # 设置y轴标签旋转，使其更清晰
            plt.yticks(fontsize=label_size-1)
            
            # 设置标题
            ax.set_title('期刊影响因子分布', fontsize=title_size, fontweight='bold', pad=20)
            
            # 添加网格线，仅对x轴
            ax.xaxis.grid(True)
            ax.yaxis.grid(False)
            
            # 移除上边框和右边框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # 在图表底部添加注释
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献，显示影响因子前{len(impact_data)}的期刊",
                ha='center', 
                fontsize=label_size-2,
                alpha=0.7
            )
            
            # 调整布局
            plt.tight_layout(pad=1.5)
            
            # 保存图表
            output_file = os.path.join(self.viz_output_dir, 
                                      f"impact_factor_chart.{self.config.get('viz_format', 'png')}")
            plt.savefig(output_file, dpi=self.config.get('viz_dpi', 300))
            plt.close()
            
            safe_print(f"成功生成影响因子趋势图: {output_file}", self.verbose)
            return output_file
        except Exception as e:
            safe_print(f"生成影响因子趋势图出错: {e}", self.verbose)
            return None

    def _create_quartile_chart(self, data):
        """创建分区分布图"""
        try:
            # 统计分区分布
            quartile_counts = Counter()
            for item in data:
                quartile = item.get('quartile', '').upper()
                if quartile:
                    # 标准化分区值
                    if 'Q1' in quartile:
                        quartile_counts['Q1'] += 1
                    elif 'Q2' in quartile:
                        quartile_counts['Q2'] += 1
                    elif 'Q3' in quartile:
                        quartile_counts['Q3'] += 1
                    elif 'Q4' in quartile:
                        quartile_counts['Q4'] += 1
                    else:
                        quartile_counts['其他'] += 1
                else:
                    quartile_counts['未知'] += 1
            
            # 如果没有分区数据，返回None
            if not quartile_counts or (len(quartile_counts) == 1 and '未知' in quartile_counts):
                safe_print("警告: 没有有效的分区数据可供可视化", self.verbose)
                return None
            
            # 定义分区顺序和颜色
            quartile_order = ['Q1', 'Q2', 'Q3', 'Q4', '其他', '未知']
            quartile_colors = self.COLOR_THEMES[self.theme]['quartile']
            
            # 准备绘图数据
            labels = []
            values = []
            colors = []
            
            # 按预定义顺序整理数据
            for q in quartile_order:
                if q in quartile_counts and quartile_counts[q] > 0:
                    labels.append(q)
                    values.append(quartile_counts[q])
                    colors.append(quartile_colors[quartile_order.index(q)])
            
            # 获取配置
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            # 创建图表
            fig, ax = plt.subplots(figsize=figsize, facecolor=self.COLOR_THEMES[self.theme]['background'])
            ax.set_facecolor(self.COLOR_THEMES[self.theme]['background'])
            
            # 应用颜色主题和样式
            self._setup_figure_style(ax)
            
            # 增加空隙，使饼图更美观
            explode = [0.02] * len(values)
            
            # 绘制饼图
            wedges, texts, autotexts = ax.pie(
                values, 
                labels=None,  # 不使用自动标签
                autopct='%1.1f%%', 
                startangle=90, 
                colors=colors,
                explode=explode,
                shadow=False,
                wedgeprops=dict(
                    edgecolor=self.COLOR_THEMES[self.theme]['background'],
                    linewidth=2,
                    antialiased=True
                ),
                textprops=dict(
                    color=self.COLOR_THEMES[self.theme]['text'],
                    fontsize=label_size,
                    fontweight='bold'
                ),
                pctdistance=0.8
            )
            
            # 自定义百分比文本格式
            for i, autotext in enumerate(autotexts):
                autotext.set_text(f"{values[i]} ({autotext.get_text()})")
                autotext.set_fontweight('bold')
                # 如果比例太小，调整文本位置避免重叠
                if values[i] / sum(values) < 0.05:
                    autotext.set_visible(False)
            
            # 创建自定义图例
            legend_labels = [f"{q} - {v} ({v/sum(values)*100:.1f}%)" for q, v in zip(labels, values)]
            ax.legend(
                wedges, 
                legend_labels, 
                loc="center left", 
                bbox_to_anchor=(1.05, 0.5),
                fontsize=label_size-1,
                frameon=True,
                facecolor=self.COLOR_THEMES[self.theme]['background'],
                edgecolor=self.COLOR_THEMES[self.theme]['grid']
            )
            
            # 设置标题
            ax.set_title('期刊分区分布', fontsize=title_size, fontweight='bold', pad=20, color=self.COLOR_THEMES[self.theme]['text'])
            
            # 确保饼图为圆形
            plt.axis('equal')
            
            # 在图表底部添加注释
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献，共{sum(values)}个具有分区信息的期刊",
                ha='center', 
                fontsize=label_size-2,
                color=self.COLOR_THEMES[self.theme]['text'],
                alpha=0.7
            )
            
            # 调整布局
            plt.tight_layout(pad=1.5)
            
            # 保存图表
            output_file = os.path.join(self.viz_output_dir, 
                                      f"quartile_chart.{self.config.get('viz_format', 'png')}")
            plt.savefig(output_file, dpi=self.config.get('viz_dpi', 300))
            plt.close()
            
            safe_print(f"成功生成分区分布图: {output_file}", self.verbose)
            return output_file
        except Exception as e:
            safe_print(f"生成分区分布图出错: {e}", self.verbose)
            return None
            
    def _create_journal_chart(self, data):
        """创建期刊分布图"""
        try:
            # 统计各期刊的文章数量
            journal_counts = Counter()
            for item in data:
                journal = item.get('journal', '')
                if journal:
                    journal_counts[journal] += 1
            
            # 如果没有期刊数据，返回None
            if not journal_counts:
                safe_print("警告: 没有有效的期刊数据可供可视化", self.verbose)
                return None
            
            # 获取前10个期刊
            top_journals = journal_counts.most_common(10)
            
            # 如果少于3个期刊，可能不值得绘图
            if len(top_journals) < 3:
                safe_print("警告: 期刊数量过少，不创建期刊分布图", self.verbose)
                return None
            
            # 准备绘图数据
            journals = [item[0] for item in top_journals]
            counts = [item[1] for item in top_journals]
            
            # 如果期刊名称过长，做一些缩略处理
            shortened_journals = []
            for j in journals:
                if len(j) > 40:
                    shortened_journals.append(j[:37] + "...")
                else:
                    shortened_journals.append(j)
            
            # 获取配色和设置
            colors = self.COLOR_THEMES[self.theme]['journal']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            # 创建图表
            fig, ax = plt.subplots(figsize=figsize)
            
            # 应用颜色主题和样式
            self._setup_figure_style(ax)
            
            # 绘制条形图
            bars = ax.barh(shortened_journals, counts, color=colors[:len(top_journals)], alpha=0.8)
            
            # 在每个条形图上添加数值
            for i, bar in enumerate(bars):
                width = bar.get_width()
                ax.text(
                    width + 0.5, 
                    bar.get_y() + bar.get_height()/2,
                    str(width),
                    ha='left', 
                    va='center',
                    fontsize=label_size-1,
                    color=self.COLOR_THEMES[self.theme]['text'],
                    fontweight='bold',
                    bbox=dict(
                        boxstyle="round,pad=0.3",
                        fc=self.COLOR_THEMES[self.theme]['background'],
                        ec=self.COLOR_THEMES[self.theme]['grid'],
                        alpha=0.7
                    )
                )
            
            # 设置标题和标签
            ax.set_title('发文期刊分布 (前10名)', fontsize=title_size, fontweight='bold', pad=20)
            ax.set_xlabel('文章数量', fontsize=label_size, fontweight='bold')
            ax.set_ylabel('期刊名称', fontsize=label_size, fontweight='bold')
            
            # 设置y轴标签格式
            plt.yticks(fontsize=max(8, label_size-2))  # 调整期刊名称的字体大小
            
            # 设置x轴从0开始
            ax.set_xlim(left=0)
            
            # 移除上边框和右边框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # 添加网格线
            ax.grid(True, linestyle='--', alpha=self.config.get('viz_grid_alpha', 0.3), axis='x')
            
            # 在图表底部添加注释
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献，显示发文量前{len(top_journals)}的期刊",
                ha='center', 
                fontsize=label_size-2,
                color=self.COLOR_THEMES[self.theme]['text'],
                alpha=0.7
            )
            
            # 调整布局，考虑期刊名称长度
            plt.tight_layout(rect=[0, 0.03, 1, 0.97], pad=1.5)
            
            # 保存图表
            output_file = os.path.join(self.viz_output_dir, 
                                      f"journal_chart.{self.config.get('viz_format', 'png')}")
            plt.savefig(output_file, dpi=self.config.get('viz_dpi', 300))
            plt.close()
            
            safe_print(f"成功生成期刊分布图: {output_file}", self.verbose)
            return output_file
        except Exception as e:
            safe_print(f"生成期刊分布图出错: {e}", self.verbose)
            return None

    def _create_year_chart(self, data):
        """创建发表年份分布图"""
        try:
            # 从发表日期中提取年份和月份
            date_data = []
            for item in data:
                pub_date = item.get('pub_date', '')
                if pub_date:
                    # 尝试提取年份和月份
                    year_match = re.search(r'(\d{4})', pub_date)
                    month_match = re.search(r'(\d{4})[-/\s](\d{1,2})', pub_date)
                    
                    if year_match:
                        year = int(year_match.group(1))
                        # 如果找到月份，则包含月份信息；否则默认为1月
                        month = int(month_match.group(2)) if month_match else 1
                        
                        # 存储年份-月份组合
                        date_data.append((year, month))
            
            # 如果没有日期数据，返回None
            if not date_data:
                safe_print("警告: 没有有效的发表日期数据可供可视化", self.verbose)
                return None
            
            # 计算跨度起始和结束日期
            min_date = min(date_data)
            max_date = max(date_data)
            
            # 按年月对数据进行聚合和排序
            date_counts = Counter(date_data)
            sorted_dates = sorted(date_counts.keys())
            
            # 调试输出提取的年份-月份数据
            date_strs = [f"{y}-{m:02d}" for y, m in sorted_dates]
            safe_print(f"提取到的发表日期: {date_strs}", self.verbose)
            
            # 检查日期范围是否符合预期
            if len(sorted_dates) > 0:
                # 计算月份跨度
                start_year, start_month = min_date
                end_year, end_month = max_date
                total_months = (end_year - start_year) * 12 + (end_month - start_month) + 1
                
                # 将预期年份范围转换为月份
                expected_range = self.config.get('expected_year_range', 3)
                expected_months = expected_range * 12
                
                # 显示预期范围信息
                safe_print(f"预期的时间跨度: {expected_range}年 ({expected_months}个月)，实际检索到的跨度: {total_months}个月", self.verbose)
                
                # 获取当前日期
                current_date = datetime.now()
                current_year = current_date.year
                current_month = current_date.month
                
                # 如果日期范围超过预期，需要过滤
                if total_months > expected_months:
                    safe_print(f"提取到的时间跨度({total_months}个月)超过了预期的{expected_months}个月，将进行过滤", self.verbose)
                    
                    # 找出需要保留的日期（最近的expected_months个月）
                    cutoff_year = current_year
                    cutoff_month = current_month - expected_months
                    
                    # 调整可能为负的月份
                    while cutoff_month <= 0:
                        cutoff_year -= 1
                        cutoff_month += 12
                    
                    # 过滤日期
                    dates_to_keep = [(year, month) for year, month in sorted_dates 
                                    if year > cutoff_year or (year == cutoff_year and month >= cutoff_month)]
                    
                    # 如果找不到足够的日期，则保留最近的几个月
                    if len(dates_to_keep) < expected_months:
                        # 按从新到旧排序
                        all_dates_desc = sorted(sorted_dates, reverse=True)
                        # 保留最近的expected_months个月
                        dates_to_keep = all_dates_desc[:expected_months]
                    
                    # 找出需要过滤的日期
                    dates_to_filter = [date for date in sorted_dates if date not in dates_to_keep]
                    
                    if dates_to_filter:
                        date_filter_strs = [f"{y}-{m:02d}" for y, m in dates_to_filter]
                        safe_print(f"过滤超出预期范围的日期: {date_filter_strs}", self.verbose)
                        
                        # 过滤日期
                        for date in dates_to_filter:
                            if date in date_counts:
                                date_counts.pop(date)
                        
                        # 重新计算排序后的日期
                        sorted_dates = sorted(date_counts.keys())
                
                # 检测日期序列中的间隙
                if len(sorted_dates) >= 2:
                    # 生成预期的完整年月序列
                    expected_dates = []
                    start_year, start_month = sorted_dates[0]
                    end_year, end_month = sorted_dates[-1]
                    
                    current_year, current_month = start_year, start_month
                    while (current_year, current_month) <= (end_year, end_month):
                        expected_dates.append((current_year, current_month))
                        
                        # 递增月份
                        current_month += 1
                        if current_month > 12:
                            current_month = 1
                            current_year += 1
                    
                    # 找出缺失的年月
                    missing_dates = [date for date in expected_dates if date not in sorted_dates]
                    
                    # 如果有间隙，添加对应的年月并设置其文章数量为0
                    if missing_dates:
                        missing_date_strs = [f"{y}-{m:02d}" for y, m in missing_dates]
                        safe_print(f"发现日期间隙: {missing_date_strs}，将在图表中显示为零值", self.verbose)
                        
                        for date in missing_dates:
                            date_counts[date] = 0
                        
                        # 重新计算排序后的日期
                        sorted_dates = sorted(date_counts.keys())
            
            # 准备绘图数据，确保按日期排序
            article_counts = [date_counts[date] for date in sorted_dates]
            
            # 创建X轴标签
            date_labels = []
            for year, month in sorted_dates:
                # 如果是每年的1月或间隔太大，则显示年月，否则只显示月
                if month == 1 or len(sorted_dates) < 12:
                    date_labels.append(f"{year}-{month:02d}")
                else:
                    date_labels.append(f"{month:02d}")
            
            # 获取设置
            colors = self.COLOR_THEMES[self.theme]['year']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            # 创建图表
            fig, ax = plt.subplots(figsize=figsize)
            
            # 应用颜色主题和样式
            self._setup_figure_style(ax)
            
            # 如果只有一个数据点，简单显示
            if len(sorted_dates) == 1:
                year, month = sorted_dates[0]
                date_label = f"{year}-{month:02d}"
                
                # 绘制单点
                ax.bar([date_label], article_counts, color=colors[0], alpha=0.8)
                ax.text(date_label, article_counts[0] + 0.2, str(article_counts[0]), 
                        ha='center', va='bottom', fontweight='bold')
            else:
                # 使用色彩渐变区域图
                ax.fill_between(
                    range(len(sorted_dates)), 
                    article_counts,
                    color=colors[1],
                    alpha=0.2
                )
                
                # 绘制折线图，使用渐变色
                for i in range(len(sorted_dates)-1):
                    seg_color = colors[i % len(colors)]
                    plt.plot(
                        [i, i+1],
                        [article_counts[i], article_counts[i+1]],
                        '-', 
                        color=seg_color, 
                        linewidth=2.5
                    )
                
                # 添加数据点
                for i in range(len(sorted_dates)):
                    marker_color = colors[i % len(colors)]
                    ax.plot(
                        i, 
                        article_counts[i], 
                        'o', 
                        color=marker_color,
                        markersize=8,
                        markeredgecolor='white',
                        markeredgewidth=1.5
                    )
                
                # 在每个点上方添加数值
                for i, count in enumerate(article_counts):
                    if count > 0:  # 只为数量大于0的点添加标签
                        ax.annotate(
                            str(count),
                            xy=(i, count),
                            xytext=(0, 10),
                            textcoords="offset points",
                            ha='center',
                            va='bottom',
                            fontsize=label_size,
                            fontweight='bold',
                            bbox=dict(
                                boxstyle="round,pad=0.3",
                                fc=self.COLOR_THEMES[self.theme]['background'],
                                ec=self.COLOR_THEMES[self.theme]['grid'],
                                alpha=0.7
                            )
                        )
            
            # 设置标题和标签
            time_period = self.config.get('time_period', 0)
            title_suffix = f"(检索范围: {self.config.get('expected_year_range')}年)" if time_period > 0 else ""
            ax.set_title(f'文章发表时间分布{title_suffix}', fontsize=title_size, fontweight='bold', pad=20)
            ax.set_xlabel('发表日期', fontsize=label_size, fontweight='bold')
            ax.set_ylabel('文章数量', fontsize=label_size, fontweight='bold')
            
            # 设置x轴刻度
            ax.set_xticks(range(len(date_labels)))
            ax.set_xticklabels(date_labels, rotation=45)
            
            # 确保y轴从0开始
            ax.set_ylim(bottom=0)
            
            # 让y轴有一点额外空间，避免注释被截断
            y_max = max(article_counts) if article_counts else 0
            ax.set_ylim(top=y_max * 1.2)
            
            # 添加网格线
            ax.grid(True, linestyle='--', alpha=self.config.get('viz_grid_alpha', 0.3))
            
            # 删除上边框和右边框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # 在图表底部添加注释
            start_year, start_month = min(sorted_dates)
            end_year, end_month = max(sorted_dates)
            start_date_str = f"{start_year}-{start_month:02d}"
            end_date_str = f"{end_year}-{end_month:02d}"
            
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献，时间跨度: {start_date_str} 至 {end_date_str}",
                ha='center', 
                fontsize=label_size-2,
                color=self.COLOR_THEMES[self.theme]['text'],
                alpha=0.7
            )
            
            # 调整布局
            plt.tight_layout(pad=1.5)
            
            # 保存图表
            output_file = os.path.join(self.viz_output_dir, 
                                      f"year_chart.{self.config.get('viz_format', 'png')}")
            plt.savefig(output_file, dpi=self.config.get('viz_dpi', 300))
            plt.close()
            
            safe_print(f"成功生成发表年份分布图: {output_file}", self.verbose)
            return output_file
        except Exception as e:
            safe_print(f"生成发表年份分布图出错: {e}", self.verbose)
            import traceback
            traceback.print_exc()
            return None

def main():
    """主程序入口"""
    try:
        # 初始化可视化工具
        visualizer = JournalVisualizer(verbose=True)
        
        # 可视化期刊数据
        chart_files = visualizer.visualize_journal_data()
        
        if chart_files:
            safe_print(f"成功生成 {len(chart_files)} 个图表:", True)
            for chart in chart_files:
                safe_print(f"  - {chart}", True)
        else:
            safe_print("未能生成任何图表", True)
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}", True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
