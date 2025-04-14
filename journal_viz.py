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

# 设置matplotlib支持中文
try:
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'STHeiti', 'sans-serif']
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
            'viz_show_if': True,                       # 是否显示影响因子趋势
            'viz_show_quartile': True,                 # 是否显示分区分布
            'viz_show_journals': True,                 # 是否显示期刊分布
            'viz_show_years': True,                    # 是否显示发表年份分布
            'viz_color_theme': 'default',              # 颜色主题
            'viz_font_size': 11,                       # 字体大小
            'viz_title_size': 14,                      # 标题字体大小
            'viz_label_size': 12,                      # 标签字体大小
            'viz_grid_alpha': 0.3,                     # 网格透明度
            'input_sort': 'out/pubmed_enhanced.csv',   # 期刊增强后的输入文件
            'viz_interactive': False,                  # 是否启用交互式图表
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
                                           'viz_show_journals', 'viz_show_years', 'viz_interactive']:
                                    config[key] = value.lower() in ['true', 'yes', 'y', '1']
                                # 处理数值
                                elif key in ['viz_dpi', 'viz_font_size', 'viz_title_size', 'viz_label_size']:
                                    try:
                                        config[key] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的{key}值: {value}，使用默认值", self.verbose)
                                elif key == 'viz_grid_alpha':
                                    try:
                                        config[key] = float(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的网格透明度值: {value}，使用默认值: 0.3", self.verbose)
                                # 处理其他字符串值
                                elif key in config:
                                    config[key] = value
                                # 输入文件特殊处理
                                elif key == 'output_sort':
                                    config['input_sort'] = value
                
                # 检查是否缺少配置项，如果是，则添加到配置文件
                self._check_and_update_config(config_file, config)
                
                safe_print("已从配置文件加载可视化设置", self.verbose)
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置", self.verbose)
        except Exception as e:
            safe_print(f"读取配置文件出错: {e}", self.verbose)
            safe_print("使用默认可视化设置", self.verbose)
        
        return config
    
    def _check_and_update_config(self, config_file, config):
        """检查并更新配置文件，添加缺失的配置项"""
        needed_params = {
            'viz_enabled': '# 是否启用可视化功能(yes/no)\nviz_enabled=yes\n\n',
            'viz_output_dir': '# 可视化输出目录\nviz_output_dir=out/viz\n\n',
            'viz_format': '# 图表格式(png, jpg, pdf, svg)\nviz_format=png\n\n',
            'viz_style': '# 图表样式(ggplot, seaborn, classic, dark_background等)\nviz_style=ggplot\n\n',
            'viz_dpi': '# 图表DPI(分辨率)\nviz_dpi=300\n\n',
            'viz_figsize': '# 图表大小(宽,高，单位为英寸)\nviz_figsize=10,6\n\n',
            'viz_show_if': '# 是否显示影响因子趋势(yes/no)\nviz_show_if=yes\n\n',
            'viz_show_quartile': '# 是否显示分区分布(yes/no)\nviz_show_quartile=yes\n\n',
            'viz_show_journals': '# 是否显示期刊分布(yes/no)\nviz_show_journals=yes\n\n',
            'viz_show_years': '# 是否显示发表年份分布(yes/no)\nviz_show_years=yes\n\n',
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
            
            # 影响因子趋势图
            if self.config.get('viz_show_if', True):
                if_chart = self._create_impact_factor_chart(data)
                if if_chart:
                    chart_files.append(if_chart)
            
            # 分区分布图
            if self.config.get('viz_show_quartile', True):
                quartile_chart = self._create_quartile_chart(data)
                if quartile_chart:
                    chart_files.append(quartile_chart)
            
            # 期刊分布图
            if self.config.get('viz_show_journals', True):
                journal_chart = self._create_journal_chart(data)
                if journal_chart:
                    chart_files.append(journal_chart)
            
            # 发表年份分布图
            if self.config.get('viz_show_years', True):
                year_chart = self._create_year_chart(data)
                if year_chart:
                    chart_files.append(year_chart)
            
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
                        'pub_date': row.get('pub_date', '').strip()
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
            # 统计期刊出现次数
            journal_counts = Counter([item['journal'] for item in data if item['journal']])
            
            # 如果数据过多，只保留前10个
            if len(journal_counts) > 10:
                # 获取出现频率最高的10个期刊
                top_journals = journal_counts.most_common(10)
                journal_names = [j[0] for j in top_journals]
                journal_counts = [j[1] for j in top_journals]
            else:
                # 直接使用所有数据，并按频率排序
                top_journals = journal_counts.most_common()
                journal_names = [j[0] for j in top_journals]
                journal_counts = [j[1] for j in top_journals]
            
            # 如果没有有效数据，返回None
            if not journal_names:
                safe_print("警告: 没有有效的期刊数据可供可视化", self.verbose)
                return None
            
            # 处理过长的期刊名称
            shortened_names = []
            for name in journal_names:
                if len(name) > 25:  # 如果期刊名称太长，截断并添加省略号
                    shortened_names.append(name[:22] + '...')
                else:
                    shortened_names.append(name)
            
            # 获取设置
            colors = self.COLOR_THEMES[self.theme]['journal']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            # 创建图表
            fig, ax = plt.subplots(figsize=figsize)
            
            # 应用颜色主题和样式
            self._setup_figure_style(ax)
            
            # 创建水平条形图
            bars = ax.barh(
                range(len(shortened_names)), 
                journal_counts, 
                color=[colors[i % len(colors)] for i in range(len(journal_counts))],
                alpha=0.8,
                height=0.6  # 稍微窄一点的条形，看起来更精致
            )
            
            # 设置渐变色条形图
            for i, bar in enumerate(bars):
                # 使用循环的颜色
                color_index = i % len(colors)
                
                # 添加渐变填充
                grad = matplotlib.colors.LinearSegmentedColormap.from_list(
                    f"grad{i}", 
                    [matplotlib.colors.to_rgba(colors[color_index], 0.7), 
                     matplotlib.colors.to_rgba(colors[color_index], 1.0)]
                )
                
                # 获取条形的位置和大小
                x, y = bar.get_xy()
                w, h = bar.get_width(), bar.get_height()
                
                # 在每个条形上添加数值
                ax.text(
                    w + 0.1,                # 略微偏离条形图右侧
                    y + h/2,                # 垂直居中
                    str(int(w)),            # 显示整数值
                    va='center',
                    ha='left',
                    fontsize=label_size,
                    fontweight='bold',
                    color=self.COLOR_THEMES[self.theme]['text']
                )
                
                # 使用渐变色填充条形图
                ax.imshow(
                    np.array([[0, 1]]), 
                    cmap=grad, 
                    aspect='auto',
                    extent=[x, x+w, y, y+h],
                    alpha=0.8
                )
            
            # 设置y轴标签
            ax.set_yticks(range(len(shortened_names)))
            ax.set_yticklabels(shortened_names)
            
            # 为期刊名称与原名称不同时添加工具提示（仅在启用交互式时有效）
            if self.config.get('viz_interactive', False):
                for i, (short_name, full_name) in enumerate(zip(shortened_names, journal_names)):
                    if short_name != full_name:
                        # 使用annotate创建工具提示
                        ax.annotate(
                            full_name,
                            xy=(0, i),
                            xytext=(10, 0),
                            textcoords="offset points",
                            bbox=dict(boxstyle="round,pad=0.3", fc="yellow", alpha=0.8),
                            arrowprops=dict(arrowstyle="->"),
                            visible=False
                        )
            
            # 设置标题和标签
            ax.set_title('期刊分布', fontsize=title_size, fontweight='bold', pad=20)
            ax.set_xlabel('文章数量', fontsize=label_size, fontweight='bold')
            ax.set_ylabel('期刊名称', fontsize=label_size, fontweight='bold')
            
            # 删除上边框和右边框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # 只保留x轴网格线
            ax.xaxis.grid(True)
            ax.yaxis.grid(False)
            
            # 在图表底部添加注释
            total_journals = len(set([item['journal'] for item in data if item['journal']]))
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献, 共{total_journals}种期刊, 显示频率最高的{len(journal_names)}种",
                ha='center', 
                fontsize=label_size-2,
                color=self.COLOR_THEMES[self.theme]['text'],
                alpha=0.7
            )
            
            # 调整布局
            plt.tight_layout(pad=1.5)
            
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
            # 从发表日期中提取年份
            years = []
            for item in data:
                pub_date = item.get('pub_date', '')
                if pub_date:
                    # 尝试提取年份
                    year_match = re.search(r'(\d{4})', pub_date)
                    if year_match:
                        years.append(int(year_match.group(1)))
            
            # 如果没有年份数据，返回None
            if not years:
                safe_print("警告: 没有有效的发表年份数据可供可视化", self.verbose)
                return None
            
            # 统计每年的文章数量
            year_counts = Counter(years)
            
            # 按年份排序
            sorted_years = sorted(year_counts.keys())
            article_counts = [year_counts[year] for year in sorted_years]
            
            # 获取设置
            colors = self.COLOR_THEMES[self.theme]['year']
            figsize = self._parse_figsize(self.config.get('viz_figsize', '10,6'))
            title_size = self.config.get('viz_title_size', 14)
            label_size = self.config.get('viz_label_size', 12)
            
            # 创建图表
            fig, ax = plt.subplots(figsize=figsize)
            
            # 应用颜色主题和样式
            self._setup_figure_style(ax)
            
            # 创建线性渐变色
            color1 = colors[0]
            color2 = colors[1]
            num_years = len(sorted_years)
            color_list = [matplotlib.colors.to_rgba(color1, 0.8)]
            
            # 创建平滑曲线
            x_smooth = np.linspace(min(sorted_years), max(sorted_years), 100)
            
            # 如果只有一个数据点，简单显示
            if len(sorted_years) == 1:
                # 绘制单点
                ax.plot(sorted_years, article_counts, 'o', color=color1, markersize=10)
                ax.text(sorted_years[0], article_counts[0] + 0.2, str(article_counts[0]), 
                        ha='center', va='bottom', fontweight='bold')
            else:
                # 使用色彩渐变区域图
                ax.fill_between(
                    sorted_years, 
                    article_counts,
                    color=color2,
                    alpha=0.2
                )
                
                # 绘制折线图，使用渐变色
                for i in range(len(sorted_years)-1):
                    seg_color = colors[i % len(colors)]
                    plt.plot(
                        [sorted_years[i], sorted_years[i+1]],
                        [article_counts[i], article_counts[i+1]],
                        '-', 
                        color=seg_color, 
                        linewidth=2.5
                    )
                
                # 添加数据点
                for i in range(len(sorted_years)):
                    marker_color = colors[i % len(colors)]
                    ax.plot(
                        sorted_years[i], 
                        article_counts[i], 
                        'o', 
                        color=marker_color,
                        markersize=8,
                        markeredgecolor='white',
                        markeredgewidth=1.5
                    )
                
                # 在每个点上方添加数值
                for i, (x, y) in enumerate(zip(sorted_years, article_counts)):
                    ax.annotate(
                        str(y),
                        xy=(x, y),
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
            ax.set_title('文章发表年份分布', fontsize=title_size, fontweight='bold', pad=20)
            ax.set_xlabel('年份', fontsize=label_size, fontweight='bold')
            ax.set_ylabel('文章数量', fontsize=label_size, fontweight='bold')
            
            # 设置x轴刻度
            ax.set_xticks(sorted_years)
            ax.set_xticklabels([str(y) for y in sorted_years], rotation=45)
            
            # 确保y轴从0开始
            ax.set_ylim(bottom=0)
            
            # 让y轴有一点额外空间，避免注释被截断
            y_max = max(article_counts)
            ax.set_ylim(top=y_max * 1.2)
            
            # 添加网格线
            ax.grid(True, linestyle='--', alpha=self.config.get('viz_grid_alpha', 0.3))
            
            # 删除上边框和右边框
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            
            # 在图表底部添加注释
            plt.figtext(
                0.5, 0.01, 
                f"基于{len(data)}篇文献，跨度{max(sorted_years)-min(sorted_years)}年 ({min(sorted_years)}-{max(sorted_years)})",
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
