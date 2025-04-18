"""
期刊数据可视化模块
提供将期刊影响因子和分区信息可视化的功能
"""
import os
import sys
import csv
import re
import traceback
from datetime import datetime
from collections import Counter, defaultdict
import matplotlib
# 在导入 pyplot 之前设置后端为 Agg，避免 tkinter 错误
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors
import numpy as np

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
except Exception as e:
    print(f"警告: 设置matplotlib字体失败: {e}")

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
            if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告", "生成图表", "可视化", "初始化"]):
                return

        try:
            print(msg)
            sys.stdout.flush()
        except:
            try:
                print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
                sys.stdout.flush()
            except Exception as e_print:
                print(f"Fallback print failed: {e_print}")

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
                                value = value.split('#', 1)[0].strip()
                                
                                if key in ['viz_enabled', 'viz_show_if', 'viz_show_quartile', 
                                           'viz_show_journals', 'viz_show_years', 'viz_show_wordcloud', 'viz_interactive']:
                                    config[key] = value.lower() in ['true', 'yes', 'y', '1']
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
                                elif key in config:
                                    config[key] = value
                                elif key == 'output_sort':
                                    config['input_sort'] = value

                if config['start_date'] and config['end_date']:
                    try:
                        start_date = self._parse_config_date(config['start_date'])
                        end_date = self._parse_config_date(config['end_date'])
                        if start_date and end_date:
                            year_diff = end_date.year - start_date.year
                            if end_date.month < start_date.month or (end_date.month == start_date.month and end_date.day < start_date.day):
                                year_diff -= 1
                            config['expected_year_range'] = max(1, year_diff)
                            safe_print(f"根据明确日期范围设置预期年份范围: {config['expected_year_range']}年", self.verbose)
                    except Exception as e:
                        safe_print(f"解析日期范围出错: {e}", self.verbose)
                elif config['time_period'] > 0:
                    config['expected_year_range'] = max(1, int(config['time_period'] + 0.5))
                    safe_print(f"根据时间周期设置预期年份范围: {config['expected_year_range']}年", self.verbose)
                
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
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            additions = []
            for param, template in needed_params.items():
                if f"{param}=" not in content:
                    additions.append(template)
            
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
        colors = self.COLOR_THEMES[self.theme]
        
        plt.rcParams['font.size'] = self.config.get('viz_font_size', 11)
        
        if ax:
            ax.set_facecolor(colors['background'])
            if ax.figure:
                ax.figure.set_facecolor(colors['background'])
            
            ax.title.set_color(colors['text'])
            ax.xaxis.label.set_color(colors['text'])
            ax.yaxis.label.set_color(colors['text'])
            
            for label in ax.get_xticklabels():
                label.set_color(colors['text'])
            for label in ax.get_yticklabels():
                label.set_color(colors['text'])
            
            grid_alpha = self.config.get('viz_grid_alpha', 0.3)
            ax.grid(True, linestyle='--', alpha=grid_alpha, color=colors['grid'])
            
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
            data = self._read_journal_data(input_file)
            if not data:
                safe_print("未找到有效的期刊数据", self.verbose)
                return []
            
            plt.style.use(self.config.get('viz_style', 'ggplot'))
            
            chart_files = []
            
            if self.config.get('viz_show_if', False):
                if_chart = self._create_impact_factor_chart(data)
                if if_chart:
                    chart_files.append(if_chart)
            
            if self.config.get('viz_show_quartile', True):
                quartile_chart = self._create_quartile_chart(data)
                if quartile_chart:
                    chart_files.append(quartile_chart)
            
            if self.config.get('viz_show_journals', False):
                journal_chart = self._create_journal_chart(data)
                if journal_chart:
                    chart_files.append(journal_chart)
            
            if self.config.get('viz_show_years', True):
                year_chart = self._create_year_chart(data)
                if year_chart:
                    chart_files.append(year_chart)
            
            if self.config.get('viz_show_wordcloud', True):
                if WORDCLOUD_AVAILABLE:
                    wordcloud_chart = self._create_wordcloud_chart(data)
                    if wordcloud_chart:
                        chart_files.append(wordcloud_chart)
                else:
                    safe_print("警告: 未安装wordcloud库，无法生成关键词词云图", self.verbose)
            
            return chart_files
            
        except Exception as e:
            safe_print(f"可视化期刊数据出错: {e}", self.verbose)
            traceback.print_exc()
            return []
    
    def _read_journal_data(self, file_path):
        """读取期刊数据"""
        data = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row['impact_factor'] = self._extract_float(row.get('impact_factor', 0))
                    row['year'] = row.get('year', '')
                    data.append(row)

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
                
            all_keywords = []
            for article in data:
                keywords = article.get('translated_keywords', '') or article.get('keywords', '')
                if not keywords:
                    continue
                
                keyword_list = re.split(r'[;,，；]', keywords)
                for keyword in keyword_list:
                    kw = keyword.strip()
                    if kw:
                        all_keywords.append(kw)
            
            if not all_keywords or len(all_keywords) < 5:
                safe_print("警告: 没有足够的关键词可供生成词云图", self.verbose)
                return None
            
            keyword_freq = Counter(all_keywords)
            
            safe_print(f"收集到 {len(keyword_freq)} 个不同的关键词用于词云图", self.verbose)
            if self.verbose:
                safe_print(f"前10个高频关键词: {keyword_freq.most_common(10)}", self.verbose)
            
            max_words = self.config.get('viz_wordcloud_max', 100)
            
            colors = self.COLOR_THEMES[self.theme]
            background_color = colors['background']
            text_color = colors['text']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            font_path = self._get_font_path()
            
            wordcloud = WordCloud(
                width=1600, 
                height=900,
                background_color=background_color,
                max_words=max_words,
                min_font_size=10,
                max_font_size=160,
                prefer_horizontal=0.9,
                scale=2,
                relative_scaling=0.6,
                colormap='viridis',
                collocations=False,
                regexp=r'\w[\w\s()+-]+',
                normalize_plurals=False,
                include_numbers=False,
                font_path=font_path,
                random_state=42
            ).generate_from_frequencies(dict(keyword_freq))
            
            fig, ax = plt.subplots(figsize=figsize, facecolor=background_color)
            ax.set_facecolor(background_color)
            
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis('off')
            
            ax.set_title('文献关键词云图', fontsize=title_size, fontweight='bold', color=text_color, pad=20)
            
            plt.figtext(
                0.5, 0.02,
                f"基于{len(data)}篇文献，共{len(keyword_freq)}个独立关键词，显示频率最高的{max_words}个",
                ha='center',
                fontsize=label_size-2,
                color=text_color,
                alpha=0.8
            )
            
            output_file = os.path.join(self.viz_output_dir, 
                                      f"keywords_wordcloud.{self.config.get('viz_format', 'png')}")
            plt.savefig(output_file, dpi=self.config.get('viz_dpi', 300), bbox_inches='tight')
            plt.close()
            
            safe_print(f"成功生成关键词词云图: {output_file}", self.verbose)
            return output_file
            
        except Exception as e:
            safe_print(f"生成关键词词云图失败: {e}", self.verbose)
            traceback.print_exc()
            return None
    
    def _get_font_path(self):
        """获取合适的中文字体路径"""
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",
            "C:/Windows/Fonts/simsun.ttc",
            "C:/Windows/Fonts/msyh.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts/simhei.ttf")
        ]
        
        for path in font_paths:
            try:
                if os.path.exists(path):
                    safe_print(f"使用字体: {path}", self.verbose)
                    return path
            except Exception as e:
                safe_print(f"检查字体路径 {path} 时出错: {e}", self.verbose)
        
        safe_print("警告: 找不到合适的中文字体，词云图可能无法正确显示中文字符", True)
        return None

    def _create_impact_factor_chart(self, data):
        """创建影响因子趋势图"""
        try:
            impact_data = [(item['journal'], item['impact_factor']) for item in data if item['impact_factor'] > 0]
            if not impact_data:
                safe_print("警告: 没有有效的影响因子数据可供可视化", self.verbose)
                return None
            
            impact_data.sort(key=lambda x: x[1], reverse=True)
            
            if len(impact_data) > 15:
                impact_data = impact_data[:15]
            
            journals = [item[0] for item in impact_data]
            impact_factors = [item[1] for item in impact_data]
            
            colors = self.COLOR_THEMES[self.theme]['impact_factor']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            max_journal_len = max([len(j) for j in journals])
            if max_journal_len > 30:
                height_factor = 1 + (max_journal_len - 30) / 100
                figsize = (figsize[0], figsize[1] * height_factor)
            
            fig, ax = plt.subplots(figsize=figsize)
            
            self._setup_figure_style(ax)
            
            bars = ax.barh(journals, impact_factors, color=colors[:len(impact_data)], alpha=0.8)
            
            for i, bar in enumerate(bars):
                color_index = i % len(colors)
                grad = matplotlib.colors.LinearSegmentedColormap.from_list(
                    f"grad{i}", 
                    [matplotlib.colors.to_rgba(colors[color_index], 0.7), 
                     matplotlib.colors.to_rgba(colors[color_index], 1.0)]
                )
                
                x, y = bar.get_xy()
                w, h = bar.get_width(), bar.get_height()
                
                ax.text(
                    w + w*0.02,
                    y + h/2,
                    f'{w:.2f}',
                    va='center',
                    ha='left',
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
                
                ax.imshow(
                    np.array([[0, 1]]), 
                    cmap=grad, 
                    aspect='auto',
                    extent=[x, x+w, y, y+h],
                    alpha=0.8
                )
            
            ax.set_xlabel('影响因子 (Impact Factor)', fontsize=label_size, fontweight='bold')
            ax.set_ylabel('期刊 (Journal)', fontsize=label_size, fontweight='bold')
            
            plt.yticks(fontsize=label_size-1)
            
            ax.set_title('期刊影响因子分布', fontsize=title_size, fontweight='bold', pad=20)
            
            ax.xaxis.grid(True)
            ax.yaxis.grid(False)
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献，显示影响因子前{len(impact_data)}的期刊",
                ha='center', 
                fontsize=label_size-2,
                alpha=0.7
            )
            
            plt.tight_layout(pad=1.5)
            
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
            quartile_counts = Counter()
            for item in data:
                quartile = item.get('quartile', '').upper().strip()
                if quartile and quartile.startswith('Q') and len(quartile) == 2 and quartile[1].isdigit():
                    quartile_counts[quartile] += 1
                elif quartile:
                    quartile_counts['其他'] += 1
                else:
                    quartile_counts['未知'] += 1
            
            if not quartile_counts or (len(quartile_counts) == 1 and '未知' in quartile_counts):
                safe_print("警告: 没有有效的分区数据可供可视化", self.verbose)
                return None
            
            quartile_order = ['Q1', 'Q2', 'Q3', 'Q4', '其他', '未知']
            quartile_colors = self.COLOR_THEMES[self.theme]['quartile']
            
            labels = []
            values = []
            colors = []
            
            for q in quartile_order:
                if q in quartile_counts and quartile_counts[q] > 0:
                    labels.append(q)
                    values.append(quartile_counts[q])
                    colors.append(quartile_colors[len(labels) % len(quartile_colors)])
            
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            fig, ax = plt.subplots(figsize=figsize, facecolor=self.COLOR_THEMES[self.theme]['background'])
            ax.set_facecolor(self.COLOR_THEMES[self.theme]['background'])
            
            self._setup_figure_style(ax)
            
            explode = [0.02] * len(values)
            
            wedges, texts, autotexts = ax.pie(
                values, 
                labels=None,
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
            
            for i, autotext in enumerate(autotexts):
                autotext.set_text(f"{values[i]} ({autotext.get_text()})")
                autotext.set_fontweight('bold')
                if values[i] / sum(values) < 0.05:
                    autotext.set_fontsize(label_size - 2)
            
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
            
            ax.set_title('期刊分区分布', fontsize=title_size, fontweight='bold', pad=20, color=self.COLOR_THEMES[self.theme]['text'])
            
            plt.axis('equal')
            
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献，共{sum(values)}个具有分区信息的期刊",
                ha='center', 
                fontsize=label_size-2,
                color=self.COLOR_THEMES[self.theme]['text'],
                alpha=0.7
            )
            
            plt.tight_layout(pad=1.5)
            
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
            journal_counts = Counter()
            for item in data:
                journal = item.get('journal', '').strip()
                if journal:
                    journal_counts[journal] += 1
            
            if not journal_counts:
                safe_print("警告: 没有有效的期刊数据可供可视化", self.verbose)
                return None
            
            top_journals = journal_counts.most_common(10)
            
            if len(top_journals) < 3:
                safe_print("警告: 期刊数量过少，不创建期刊分布图", self.verbose)
                return None
            
            journals = [item[0] for item in top_journals]
            counts = [item[1] for item in top_journals]
            
            shortened_journals = []
            for j in journals:
                if len(j) > 40:
                    shortened_journals.append(j[:37] + '...')
                else:
                    shortened_journals.append(j)
            
            colors = self.COLOR_THEMES[self.theme]['journal']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            fig, ax = plt.subplots(figsize=figsize)
            
            self._setup_figure_style(ax)
            
            bars = ax.barh(shortened_journals, counts, color=colors[:len(top_journals)], alpha=0.8)
            
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
            
            ax.set_title('发文期刊分布 (前10名)', fontsize=title_size, fontweight='bold', pad=20)
            ax.set_xlabel('文章数量', fontsize=label_size, fontweight='bold')
            ax.set_ylabel('期刊名称', fontsize=label_size, fontweight='bold')
            
            plt.yticks(fontsize=max(8, label_size-2))
            
            ax.set_xlim(left=0)
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            ax.grid(True, linestyle='--', alpha=self.config.get('viz_grid_alpha', 0.3), axis='x')
            
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献，显示发文量前{len(top_journals)}的期刊",
                ha='center', 
                fontsize=label_size-2,
                color=self.COLOR_THEMES[self.theme]['text'],
                alpha=0.7
            )
            
            plt.tight_layout(rect=[0, 0.03, 1, 0.97], pad=1.5)
            
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
            date_data = []
            for item in data:
                pub_date = item.get('pub_date', '')
                if pub_date:
                    try:
                        parsed_date = None
                        for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y-%m', '%Y/%m', '%Y']:
                            try:
                                parsed_date = datetime.strptime(pub_date.split(' ')[0], fmt)
                                break
                            except ValueError:
                                continue
                        if parsed_date:
                            date_data.append((parsed_date.year, parsed_date.month))
                        else:
                            year_match = re.search(r'(\d{4})', pub_date)
                            if year_match:
                                date_data.append((int(year_match.group(1)), 1))
                    except Exception as e_date:
                        safe_print(f"解析日期 '{pub_date}' 失败: {e_date}", self.verbose)
            
            if not date_data:
                safe_print("警告: 没有有效的发表日期数据可供可视化", self.verbose)
                return None
            
            min_date = min(date_data)
            max_date = max(date_data)
            
            date_counts = Counter(date_data)
            sorted_dates = sorted(date_counts.keys())
            
            date_strs = [f"{y}-{m:02d}" for y, m in sorted_dates]
            safe_print(f"提取到的发表日期: {date_strs}", self.verbose)
            
            if len(sorted_dates) > 0:
                start_year, start_month = min_date
                end_year, end_month = max_date
                total_months = (end_year - start_year) * 12 + (end_month - start_month) + 1
                
                expected_range = self.config.get('expected_year_range', 3)
                expected_months = expected_range * 12
                
                safe_print(f"预期的时间跨度: {expected_range}年 ({expected_months}个月)，实际检索到的跨度: {total_months}个月", self.verbose)
                
                current_date = datetime.now()
                current_year = current_date.year
                current_month = current_date.month
                
                if total_months > expected_months:
                    safe_print(f"提取到的时间跨度({total_months}个月)超过了预期的{expected_months}个月，将进行过滤", self.verbose)
                    
                    cutoff_year = current_year
                    cutoff_month = current_month - expected_months
                    
                    while cutoff_month <= 0:
                        cutoff_year -= 1
                        cutoff_month += 12
                    
                    dates_to_keep = [(year, month) for year, month in sorted_dates 
                                    if year > cutoff_year or (year == cutoff_year and month >= cutoff_month)]
                    
                    if len(dates_to_keep) < expected_months:
                        all_dates_desc = sorted(sorted_dates, reverse=True)
                        dates_to_keep = all_dates_desc[:expected_months]
                    
                    dates_to_filter = [date for date in sorted_dates if date not in dates_to_keep]
                    
                    if dates_to_filter:
                        date_filter_strs = [f"{y}-{m:02d}" for y, m in dates_to_filter]
                        safe_print(f"过滤超出预期范围的日期: {date_filter_strs}", self.verbose)
                        
                        for date in dates_to_filter:
                            if date in date_counts:
                                date_counts.pop(date)
                        
                        sorted_dates = sorted(date_counts.keys())
                
                if len(sorted_dates) >= 2:
                    expected_dates = []
                    start_year, start_month = sorted_dates[0]
                    end_year, end_month = sorted_dates[-1]
                    
                    current_year, current_month = start_year, start_month
                    while (current_year, current_month) <= (end_year, end_month):
                        expected_dates.append((current_year, current_month))
                        
                        current_month += 1
                        if current_month > 12:
                            current_month = 1
                            current_year += 1
                    
                    missing_dates = [date for date in expected_dates if date not in sorted_dates]
                    
                    if missing_dates:
                        missing_date_strs = [f"{y}-{m:02d}" for y, m in missing_dates]
                        safe_print(f"发现日期间隙: {missing_date_strs}，将在图表中显示为零值", self.verbose)
                        
                        for date in missing_dates:
                            date_counts[date] = 0
                        
                        sorted_dates = sorted(date_counts.keys())
            
            article_counts = [date_counts[date] for date in sorted_dates]
            
            date_labels = []
            for year, month in sorted_dates:
                if month == 1 or len(sorted_dates) < 12:
                    date_labels.append(f"{year}-{month:02d}")
                else:
                    date_labels.append(f"{month:02d}")
            
            colors = self.COLOR_THEMES[self.theme]['year']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            fig, ax = plt.subplots(figsize=figsize)
            
            self._setup_figure_style(ax)
            
            if len(sorted_dates) == 1:
                year, month = sorted_dates[0]
                date_label = f"{year}-{month:02d}"
                
                ax.bar([date_label], article_counts, color=colors[0], alpha=0.8)
                ax.text(date_label, article_counts[0] + 0.2, str(article_counts[0]), 
                        ha='center', va='bottom', fontweight='bold')
            else:
                ax.fill_between(
                    range(len(sorted_dates)), 
                    article_counts,
                    color=colors[1],
                    alpha=0.2
                )
                
                for i in range(len(sorted_dates)-1):
                    color_start = colors[i % len(colors)]
                    color_end = colors[(i+1) % len(colors)]
                    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
                        f"line_grad_{i}", [color_start, color_end]
                    )
                    x_coords = np.linspace(i, i+1, 10)
                    y_coords = np.linspace(article_counts[i], article_counts[i+1], 10)
                    points = np.array([x_coords, y_coords]).T.reshape(-1, 1, 2)
                    segments = np.concatenate([points[:-1], points[1:]], axis=1)
                    lc = matplotlib.collections.LineCollection(segments, cmap=cmap, norm=plt.Normalize(0, 1))
                    lc.set_array(np.linspace(0, 1, len(x_coords)))
                    lc.set_linewidth(2)
                    ax.add_collection(lc)
                
                for i in range(len(sorted_dates)):
                    ax.plot(i, article_counts[i], 'o', color=colors[i % len(colors)], markersize=5)
                
                for i, count in enumerate(article_counts):
                    ax.text(i, count + max(article_counts) * 0.02, str(count), ha='center', va='bottom',
                            fontsize=label_size-2, fontweight='bold', color=self.COLOR_THEMES[self.theme]['text'])
            
            time_period = self.config.get('time_period', 0)
            title_suffix = f"(检索范围: {self.config.get('expected_year_range')}年)" if time_period > 0 else ""
            ax.set_title(f'文章发表时间分布{title_suffix}', fontsize=title_size, fontweight='bold', pad=20)
            ax.set_xlabel('发表日期', fontsize=label_size, fontweight='bold')
            ax.set_ylabel('文章数量', fontsize=label_size, fontweight='bold')
            
            ax.set_xticks(range(len(date_labels)))
            ax.set_xticklabels(date_labels, rotation=45)
            
            ax.set_ylim(bottom=0)
            
            y_max = max(article_counts) if article_counts else 0
            ax.set_ylim(top=y_max * 1.2)
            
            ax.grid(True, linestyle='--', alpha=self.config.get('viz_grid_alpha', 0.3))
            
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            if sorted_dates:
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
            else:
                 plt.figtext(0.5, 0.01, f"基于{len(data)}篇文献，无有效日期数据", ha='center', fontsize=label_size-2, color=self.COLOR_THEMES[self.theme]['text'], alpha=0.7)

            plt.tight_layout(pad=1.5, rect=[0, 0.03, 1, 0.95])

            output_file = os.path.join(self.viz_output_dir, 
                                      f"year_chart.{self.config.get('viz_format', 'png')}")
            plt.savefig(output_file, dpi=self.config.get('viz_dpi', 300))
            plt.close()
            
            safe_print(f"成功生成发表年份分布图: {output_file}", self.verbose)
            return output_file
        except Exception as e:
            safe_print(f"生成发表年份分布图出错: {e}", self.verbose)
            traceback.print_exc()
            return None

def main():
    """主程序入口"""
    try:
        visualizer = JournalVisualizer(verbose=True)
        
        chart_files = visualizer.visualize_journal_data()
        
        if chart_files:
            safe_print(f"成功生成 {len(chart_files)} 个图表:", True)
            for chart in chart_files:
                safe_print(f"  - {chart}", True)
        else:
            safe_print("未能生成任何图表", True)
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}", True)
        traceback.print_exc()

if __name__ == "__main__":
    main()
