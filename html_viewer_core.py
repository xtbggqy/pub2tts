"""
HTML文献浏览器核心功能模块
"""
import os
import csv
import json
from collections import Counter, defaultdict

try:
    from error_handler import safe_print, safe_file_operation
except ImportError:
    def safe_print(msg, verbose=True):
        if verbose:
            print(msg)
    def safe_file_operation(operation_type="read"):
        def decorator(func):
            return func
        return decorator

class HTMLViewerGenerator:
    """HTML文献浏览器生成器"""

    def __init__(self, config_file="pub2.txt", verbose=False):
        self.verbose = verbose
        self.config_file = config_file
        self.config = self._read_config(config_file)
        self.config['verbose'] = verbose
        self.stats = {
            'total_articles': 0,
            'journals': set(),
            'years': set(),
            'keywords': Counter(),
            'authors': Counter()
        }
        safe_print("HTML文献浏览器生成器初始化完成", True)

    def _read_config(self, config_file):
        config = {
            'input_html': 'out/pubmed_enhanced_llm.csv',
            'output_html': 'out/literature_viewer.html',
            'page_title': '文献浏览器',
            'articles_per_page': 20,
            'enable_charts': True,
            'highlight_keywords': True,
            'dark_mode': False,
            'show_english': True,
            'show_statistics': True,
            'max_keyword_cloud': 50,
        }
        key_mapping = {
            'output_llm': 'input_html',
            'html_page_title': 'page_title',
            'html_show_english': 'show_english',
            'html_dark_mode': 'dark_mode',
            'html_highlight_keywords': 'highlight_keywords',
            'viz_wordcloud_max': 'max_keyword_cloud',
            'html_articles_per_page': 'articles_per_page',
            'html_enable_charts': 'enable_charts',
            'html_show_statistics': 'show_statistics'
        }
        int_config_keys = ['max_keyword_cloud', 'articles_per_page']
        bool_config_keys = ['show_english', 'dark_mode', 'highlight_keywords', 'enable_charts', 'show_statistics']
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split('=', 1)
                            if len(parts) == 2:
                                key = parts[0].strip()
                                value = parts[1].strip().split('#', 1)[0].strip()
                                config_key = key_mapping.get(key, key)
                                if config_key in bool_config_keys:
                                    if value and isinstance(value, str):
                                        config[config_key] = value.lower() in ['yes', 'true', 'y', '1']
                                elif config_key in int_config_keys:
                                    try:
                                        if value:
                                            config[config_key] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的整数配置项 {key}={value}，使用默认值", self.verbose)
                                else:
                                    config[config_key] = value
                                if key == 'viz_output_dir':
                                    base_dir = value
                                    os.makedirs(base_dir, exist_ok=True)
                                    config['output_html'] = os.path.join(base_dir, 'literature_viewer.html')
                safe_print(f"已从 {config_file} 加载HTML生成器配置", self.verbose)
            else:
                safe_print(f"警告: 配置文件 {config_file} 不存在，使用默认设置", True)
        except Exception as e:
            safe_print(f"错误: 读取配置文件失败: {e}", True)
            safe_print("使用默认设置继续执行，请检查配置文件格式", True)
        return config

    @safe_file_operation(operation_type="read")
    def read_articles_from_csv(self, file_path):
        if not os.path.exists(file_path):
            safe_print(f"错误: 输入文件不存在: {file_path}", True)
            return []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                articles = list(reader)
            safe_print(f"已从 {file_path} 读取 {len(articles)} 篇文章", True)
            return articles
        except Exception as e:
            safe_print(f"读取CSV文件失败: {str(e)}", True)
            return []

    def preprocess_data(self, articles):
        processed_articles = []
        journals_data = defaultdict(list)
        years_data = defaultdict(int)
        time_data = defaultdict(int)
        all_keywords = []
        self.stats['journals'] = set()
        self.stats['years'] = set()
        time_field_found = None

        has_pub_date_column = False
        if articles:
            has_pub_date_column = 'pub_date' in articles[0]

        for i, article in enumerate(articles):
            try:
                processed_article = {
                    'id': i + 1,
                    'title': article.get('title', ''),
                    'authors': article.get('authors', ''),
                    'journal': article.get('journal', ''),
                    'year': article.get('year', ''), # 初始年份
                    'pmid': article.get('pmid', ''),
                    'doi': article.get('doi', ''),
                    'abstract': article.get('abstract', ''),
                    'keywords': article.get('keywords', ''),
                    'translated_title': article.get('translated_title', ''),
                    'translated_abstract': article.get('translated_abstract', ''),
                    'translated_keywords': article.get('translated_keywords', ''),
                    'quartile': article.get('quartile', ''),
                    'impact_factor': article.get('impact_factor', ''),
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{article.get('pmid', '')}"
                }
                for key, value in article.items():
                    if key not in processed_article:
                        processed_article[key] = value

                time_value_for_chart = None
                extracted_year = None
                time_source_field = None

                pub_date_val = processed_article.get('pub_date') if has_pub_date_column else None
                if pub_date_val:
                    time_source_field = 'pub_date'
                    time_value_for_chart = pub_date_val
                    try:
                        year_str = ''.join(filter(str.isdigit, pub_date_val))[:4]
                        if len(year_str) == 4: extracted_year = int(year_str)
                    except: pass
                else:
                    possible_time_fields = ['publish_time', 'pub_time', 'publication_date', 'date', 'time', 'datetime', 'created_at', 'updated_at']
                    for field in possible_time_fields:
                        time_val = processed_article.get(field)
                        if time_val:
                            time_source_field = field
                            time_value_for_chart = time_val
                            try:
                                year_str = ''.join(filter(str.isdigit, time_val))[:4]
                                if len(year_str) == 4: extracted_year = int(year_str)
                            except: pass
                            break

                if extracted_year:
                    processed_article['year'] = str(extracted_year)

                if time_value_for_chart:
                    time_field_found = time_source_field
                    try:
                        chart_time_key = time_value_for_chart.split(' ')[0]
                        time_data[chart_time_key] += 1
                    except:
                        time_data[str(time_value_for_chart)] += 1

                current_year_for_stats = None
                year_val_str = processed_article.get('year')
                if year_val_str:
                    try:
                        year_int = int(year_val_str)
                        current_year_for_stats = str(year_int)
                        self.stats['years'].add(current_year_for_stats)
                        years_data[current_year_for_stats] += 1
                    except (ValueError, TypeError):
                        pass

                journal = processed_article['journal']
                if journal:
                    self.stats['journals'].add(journal)
                    impact_factor = 0
                    try:
                        if processed_article['impact_factor']:
                            impact_factor = float(processed_article['impact_factor'])
                    except (ValueError, TypeError):
                        pass
                    journals_data[journal].append({
                        'id': processed_article['id'],
                        'impact_factor': impact_factor,
                        'quartile': processed_article['quartile']
                    })
                if processed_article['authors']:
                    authors = processed_article['authors'].split(', ')
                    for author in authors:
                        if author:
                            self.stats['authors'][author] += 1
                if processed_article['translated_keywords']:
                    keywords = [k.strip() for k in processed_article['translated_keywords'].split(';')]
                    all_keywords.extend(keywords)
                    for keyword in keywords:
                        if keyword:
                            self.stats['keywords'][keyword] += 1

                processed_articles.append(processed_article)
            except Exception as e:
                safe_print(f"警告: 处理第{i+1}条数据时出错: {e}", self.verbose)

        self.stats['total_articles'] = len(processed_articles)
        self.stats['journals'] = list(self.stats['journals'])
        self.stats['years'] = sorted(list(self.stats['years']), reverse=True)

        chart_data = {
            'time_field': time_field_found if time_data else None,
            'time': {str(t): count for t, count in sorted(time_data.items())} if time_data else None,
            'years': {str(year): count for year, count in sorted(years_data.items())} if years_data else None,
            'journals': {journal: len(data) for journal, data in journals_data.items() if len(data) > 1},
            'keywords': {k: v for k, v in self.stats['keywords'].most_common(self.config['max_keyword_cloud'])}
        }
        safe_print(f"DEBUG: Preprocessed articles count: {len(processed_articles)}", self.verbose)
        safe_print(f"DEBUG: Chart data generated: {json.dumps(chart_data, indent=2, ensure_ascii=False)}", self.verbose)
        if not processed_articles and self.verbose:
             safe_print("DEBUG: No articles were processed. Check input file and preprocessing logic.", True)

        return processed_articles, chart_data

    @safe_file_operation(operation_type="write")
    def generate_html(self, articles, chart_data, output_file):
        try:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            articles_json = json.dumps(articles, ensure_ascii=False)
            chart_data_json = json.dumps(chart_data, ensure_ascii=False)
            html_content = self._generate_html_template(articles_json, chart_data_json)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            safe_print(f"已生成HTML文件: {output_file}", True)
            return True
        except Exception as e:
            safe_print(f"生成HTML文件失败: {str(e)}", True)
            return False

    def _generate_html_template(self, articles_json, chart_data_json):
        """
        生成HTML模板
        Args:
            articles_json: 文章JSON字符串
            chart_data_json: 图表数据JSON字符串
        Returns:
            HTML内容字符串
        """
        dark_mode = 'dark' if self.config['dark_mode'] else 'light'
        template = f"""<!DOCTYPE html>
<html lang="zh-CN" data-bs-theme="{dark_mode}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{self.config['page_title']}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.datatables.net/1.13.4/css/dataTables.bootstrap5.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/jquery.dataTables.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.4/js/dataTables.bootstrap5.min.js"></script>
    <style>
        body {{
            background: {('#212529' if self.config['dark_mode'] else '#f8f9fa')};
            color: {('#f8f9fa' if self.config['dark_mode'] else '#212529')};
            padding-top: 1rem; /* Add some top padding */
        }}
        .main-card {{
            background: {('#23272b' if self.config['dark_mode'] else '#fff')};
            border-radius: 16px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.10);
            padding: 1.5rem; /* Adjusted padding */
            margin-bottom: 2rem;
        }}
        .table-responsive {{ margin-top: 1rem; }} /* Reduced top margin */
        .dataTables_wrapper .dataTables_filter label {{ width: 100%; }}
        .dataTables_wrapper .dt-buttons {{ margin-bottom: 0.5rem; }} /* Add space below buttons */
        .dt-buttons .btn {{
            margin-right: 5px;
            border-radius: 20px;
            margin-bottom: 5px; /* Allow buttons to wrap */
        }}
        .table-striped>tbody>tr:nth-of-type(odd)>* {{
            background-color: {('#2c3136' if self.config['dark_mode'] else '#f9fbfd')}; /* Slightly adjusted odd row color */
        }}
        .table-striped>tbody>tr:hover>* {{
            background-color: {('#343a40' if self.config['dark_mode'] else '#e9ecef')}; /* Adjusted hover color */
            transition: background 0.2s;
        }}
        .dataTables_wrapper .dataTables_paginate .paginate_button {{
            border-radius: 50px !important;
            margin: 0 2px;
        }}
        .form-control:focus {{
            border-color: #86b7fe;
            box-shadow: 0 0 0 0.2rem rgba(13,110,253,.25);
        }}
        .chart-container {{
            background: {('#23272b' if self.config['dark_mode'] else '#fff')};
            border-radius: 16px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            padding: 1.5rem;
        }}
        .btn-primary {{
            border-radius: 20px;
        }}
        .dataTables_length select,
        .dataTables_filter input {{
            border-radius: 20px;
            padding: 0.375rem 0.75rem; /* Ensure consistent padding */
        }}
        /* Ensure table takes full width within its container */
        #articlesTable {{
            width: 100% !important;
        }}
        /* Adjust column selector spacing */
        .column-selector-container {{
             margin-bottom: 1rem;
             padding: 1rem;
             background-color: {('#2c3136' if self.config['dark_mode'] else '#f1f3f5')};
             border-radius: 8px;
        }}
        .column-selector-container .form-check {{
             margin-bottom: 0.5rem; /* Add space between checkboxes */
        }}
    </style>
</head>
<body>
    <div class="container-fluid py-4">
        <div class="main-card">
            <h1 class="text-center mb-4"><i class="fa fa-book-open-reader me-2"></i>{self.config['page_title']}</h1>
            <div class="row mb-3">
                <div class="col-md-6 mb-2 mb-md-0">
                    <input type="text" id="globalSearch" class="form-control" placeholder="全文搜索/筛选...">
                </div>
                <div class="col-md-6 text-end">
                    <span class="badge bg-primary fs-6">共 <span id="articleCount"></span> 条记录</span>
                </div>
            </div>
            <div class="table-responsive">
                <table id="articlesTable" class="table table-striped table-bordered w-100 align-middle">
                    <thead>
                        <tr id="tableHeader"></tr>
                    </thead>
                    <tbody id="tableBody"></tbody>
                </table>
            </div>
            <div class="chart-container mt-4" style="display: none;">
                <canvas id="chartCanvas" height="200"></canvas>
            </div>
        </div>
        <footer class="text-center text-muted small mt-4 mb-2">
            Powered by <b>HTMLViewerGenerator</b>
        </footer>
    </div>
    <script>
        console.log("Script start");
        let articles = [];
        let chartData = {{}};
        try {{
            articles = JSON.parse({json.dumps(articles_json)});
            chartData = JSON.parse({json.dumps(chart_data_json)});
        }} catch (e) {{
            console.error("Error parsing initial data:", e);
            const mainCard = document.querySelector('.main-card');
            if (mainCard) {{
                mainCard.innerHTML = '<div class="alert alert-danger">加载数据时出错，请检查输入文件或联系管理员。</div>' + mainCard.innerHTML;
            }}
        }}

        console.log("Articles data:", articles);
        console.log("Chart data:", chartData);

        function getAllFields(data) {{
            const fields = new Set();
            if (!Array.isArray(data)) {{
                console.error("getAllFields: Input data is not an array", data);
                return [];
            }}
            data.forEach(row => {{
                if (typeof row === 'object' && row !== null) {{
                    Object.keys(row).forEach(k => fields.add(k));
                }} else {{
                    console.warn("getAllFields: Skipping invalid row", row);
                }}
            }});
            const priority = [
                'id','title','translated_title','authors','journal','year','pmid','doi','url','abstract','translated_abstract','keywords','translated_keywords','quartile','impact_factor',
                'publish_time','pub_time','publication_date','date','time','datetime','created_at','updated_at'
            ];
            const sorted = priority.filter(f => fields.has(f));
            priority.forEach(f => fields.delete(f));
            return sorted.concat(Array.from(fields));
        }}
        const fields = getAllFields(articles);
        console.log("Detected fields:", fields);

        function renderColumnSelector() {{
            console.log("Rendering column selector...");
            const selectorContainer = document.createElement('div');
            selectorContainer.className = "column-selector-container";
            const selectorDiv = document.createElement('div');
            selectorDiv.innerHTML = `<label class="form-label fw-bold d-block mb-2">选择显示的列：</label>`;
            if (fields.length === 0) {{
                 console.warn("No fields found for column selector.");
                 selectorDiv.innerHTML += '<p class="text-muted">未检测到数据列。</p>';
            }} else {{
                fields.forEach((field, idx) => {{
                    let showName = field;
                    if (['publish_time','pub_time','publication_date','date','time','datetime','created_at','updated_at'].includes(field)) showName = '时间';
                    else if (field === 'title') showName = '标题';
                    else if (field === 'translated_title') showName = '翻译标题';
                    else if (field === 'authors') showName = '作者';
                    else if (field === 'journal') showName = '期刊';
                    else if (field === 'year') showName = '年份';
                    else if (field === 'pmid') showName = 'PMID';
                    else if (field === 'doi') showName = 'DOI';
                    else if (field === 'url') showName = '链接';
                    else if (field === 'abstract') showName = '摘要';
                    else if (field === 'translated_abstract') showName = '翻译摘要';
                    else if (field === 'keywords') showName = '关键词';
                    else if (field === 'translated_keywords') showName = '翻译关键词';
                    else if (field === 'quartile') showName = '分区';
                    else if (field === 'impact_factor') showName = '影响因子';
                    selectorDiv.innerHTML += `
                        <div class="form-check form-check-inline">
                            <input class="form-check-input column-toggle" type="checkbox" id="col-toggle-${{idx}}" data-field="${{field}}" checked>
                            <label class="form-check-label" for="col-toggle-${{idx}}">${{showName}}</label>
                        </div>
                    `;
                }});
            }}
            selectorContainer.appendChild(selectorDiv);
            const insertBeforeElement = document.querySelector('.main-card .row.mb-3');
            if (insertBeforeElement) {{
                 document.querySelector('.main-card').insertBefore(selectorContainer, insertBeforeElement);
                 console.log("Column selector rendered.");
            }} else {{
                 console.error("Could not find element to insert column selector before.");
            }}
        }}

        const headerRow = document.getElementById('tableHeader');
        function renderInitialHeader(allFields) {{
            console.log("Rendering initial header...");
            if (!headerRow) {{ console.error("Header row element not found!"); return; }}
            headerRow.innerHTML = '';
            if (allFields.length === 0) {{
                 console.warn("No fields for header.");
                 headerRow.innerHTML = '<th>无数据</th>';
                 return;
            }}
            allFields.forEach(field => {{
                let showName = field;
                if (['publish_time','pub_time','publication_date','date','time','datetime','created_at','updated_at'].includes(field)) showName = '时间';
                else if (field === 'title') showName = '标题';
                else if (field === 'translated_title') showName = '翻译标题';
                else if (field === 'authors') showName = '作者';
                else if (field === 'journal') showName = '期刊';
                else if (field === 'year') showName = '年份';
                else if (field === 'pmid') showName = 'PMID';
                else if (field === 'doi') showName = 'DOI';
                else if (field === 'url') showName = '链接';
                else if (field === 'abstract') showName = '摘要';
                else if (field === 'translated_abstract') showName = '翻译摘要';
                else if (field === 'keywords') showName = '关键词';
                else if (field === 'translated_keywords') showName = '翻译关键词';
                else if (field === 'quartile') showName = '分区';
                else if (field === 'impact_factor') showName = '影响因子';
                const th = document.createElement('th');
                th.textContent = showName;
                headerRow.appendChild(th);
            }});
            console.log("Initial header rendered.");
        }}

        const tableBody = document.getElementById('tableBody');
        function renderInitialTable(data, allFields) {{
            console.log("Rendering initial table body...");
            if (!tableBody) {{ console.error("Table body element not found!"); return; }}
            tableBody.innerHTML = '';
            const articleCountElement = document.getElementById('articleCount');

            if (!Array.isArray(data) || data.length === 0 || allFields.length === 0) {{
                console.warn("No data or fields to render in table body.");
                const colCount = allFields.length > 0 ? allFields.length : 1;
                tableBody.innerHTML = `<tr class="no-data-row"><td colspan="${{colCount}}" class="text-center text-muted">没有可显示的文献记录。</td></tr>`;
                if(articleCountElement) articleCountElement.textContent = '0';
                return;
            }}

            data.forEach(row => {{
                const tr = document.createElement('tr');
                allFields.forEach(field => {{
                    let val = (row && typeof row === 'object' && row[field] !== undefined) ? row[field] : '';
                    if (field.toLowerCase() === 'pmid' && val) {{
                        val = `<a href="https://pubmed.ncbi.nlm.nih.gov/${{val}}" target="_blank">${{val}}</a>`;
                    }}
                    if (field.toLowerCase() === 'doi' && val) {{
                        val = `<a href="https://doi.org/${{val}}" target="_blank">${{val}}</a>`;
                    }}
                    if (field.toLowerCase() === 'url' && val) {{
                        val = `<a href="${{val}}" target="_blank">链接</a>`;
                    }}
                    const td = document.createElement('td');
                    td.innerHTML = val;
                    tr.appendChild(td);
                }});
                tableBody.appendChild(tr);
            }});
            if(articleCountElement) articleCountElement.textContent = data.length;
            console.log(`Initial table body rendered with ${{data.length}} rows.`);
        }}

        try {{
            renderColumnSelector();
            renderInitialHeader(fields);
            renderInitialTable(articles, fields);
        }} catch (e) {{
            console.error("Error during initial rendering:", e);
        }}

        let dataTable = null;
        $(document).ready(function() {{
            console.log("Document ready. Initializing DataTable...");
            try {{
                if ($('#articlesTable tbody tr.no-data-row').length === 0 && $('#articlesTable tbody tr').length > 0) {{
                    dataTable = $('#articlesTable').DataTable({{
                        dom: 'Bfrtip',
                        buttons: [
                            {{ extend: 'copy', text: '<i class="fa fa-copy"></i> 复制' }},
                            {{ extend: 'csv', text: '<i class="fa fa-file-csv"></i> 导出CSV' }},
                            {{ extend: 'excel', text: '<i class="fa fa-file-excel"></i> Excel' }},
                            {{ extend: 'pdf', text: '<i class="fa fa-file-pdf"></i> PDF' }},
                            {{ extend: 'print', text: '<i class="fa fa-print"></i> 打印' }}
                        ],
                        pageLength: {self.config['articles_per_page']},
                        language: {{ url: "//cdn.datatables.net/plug-ins/1.13.4/i18n/zh-CN.json" }},
                        order: [[0, 'asc']],
                        scrollX: true
                    }});
                    console.log("DataTable initialized successfully.");

                    console.log("Attaching column toggle listeners...");
                    document.querySelectorAll('.column-toggle').forEach(cb => {{
                        cb.addEventListener('change', function() {{
                            const field = this.getAttribute('data-field');
                            const columnIndex = fields.indexOf(field);
                            if (columnIndex > -1 && dataTable) {{
                                try {{
                                    const column = dataTable.column(columnIndex);
                                    column.visible(this.checked);
                                    console.log(`Column '${{field}}' visibility set to ${{this.checked}}`);
                                }} catch (e) {{
                                    console.error(`Error toggling column '${{field}}':`, e);
                                }}
                            }} else {{
                                console.warn(`Could not find column index for field '${{field}}' or DataTable not ready.`);
                            }}
                        }});
                    }});
                    console.log("Column toggle listeners attached.");
                }} else {{
                    console.warn("DataTable initialization skipped: Table body is empty or contains 'no data' row.");
                     $('.dt-buttons, .dataTables_filter, .dataTables_info, .dataTables_paginate').hide();
                }}
            }} catch (e) {{
                console.error("Error initializing DataTable:", e);
            }}

            const globalSearchInput = document.getElementById('globalSearch');
            if (globalSearchInput) {{
                globalSearchInput.addEventListener('input', function() {{
                    if (dataTable) {{
                        dataTable.search(this.value).draw();
                    }} else {{
                        console.warn("Search ignored: DataTable not initialized.");
                    }}
                }});
            }} else {{
                console.error("Global search input element not found!");
            }}
        }});

        document.addEventListener('DOMContentLoaded', function() {{
            console.log("DOM fully loaded. Rendering chart...");
            const chartContainer = document.querySelector('.chart-container');
            const chartCanvas = document.getElementById('chartCanvas');
            let chartInstance = null;

            function renderChart() {{
                if (chartInstance) {{
                    chartInstance.destroy();
                }}

                let labels, data, titleText;
                let chartShouldBeVisible = false;

                if (chartData && chartData.time && typeof chartData.time === 'object' && Object.keys(chartData.time).length > 0) {{
                    labels = Object.keys(chartData.time);
                    data = Object.values(chartData.time);
                    titleText = `文章发布时间分布 (${{chartData.time_field || '未知时间字段'}})`;
                    chartShouldBeVisible = true;
                }} else if (chartData && chartData.years && typeof chartData.years === 'object' && Object.keys(chartData.years).length > 0) {{
                    labels = Object.keys(chartData.years);
                    data = Object.values(chartData.years);
                    titleText = '文章年份分布';
                    chartShouldBeVisible = true;
                }} else {{
                    console.warn("No valid time or year data for chart.");
                    chartShouldBeVisible = false;
                }}

                if (chartContainer) {{
                    chartContainer.style.display = chartShouldBeVisible ? 'block' : 'none';
                }} else {{
                     console.error("Chart container element not found!");
                     return;
                }}

                if (!chartShouldBeVisible) {{
                    return;
                }}

                if (!chartCanvas) {{
                     console.error("Chart canvas element not found!");
                     return;
                }}

                const ctx = chartCanvas.getContext('2d');
                try {{
                    chartInstance = new Chart(ctx, {{
                        type: 'bar',
                        data: {{
                            labels: labels,
                            datasets: [{{
                                label: '文章数量',
                                data: data,
                                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                borderColor: 'rgba(75, 192, 192, 1)',
                                borderWidth: 1
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {{
                                legend: {{ position: 'top' }},
                                title: {{ display: true, text: titleText }}
                            }},
                            scales: {{
                                x: {{ ticks: {{ autoSkip: true, maxRotation: 45, minRotation: 0 }} }}
                            }}
                        }}
                    }});
                    console.log("Chart rendered successfully.");
                }} catch (e) {{
                    console.error("Error rendering chart:", e);
                }}
            }}
            if (articles) {{
                 renderChart();
            }} else {{
                 console.warn("Skipping chart rendering due to data parsing error.");
            }}
        }});
        console.log("Script end");
    </script>
</body>
</html>
"""
        return template

    def process(self):
        safe_print("开始生成HTML文献浏览器...", True)
        try:
            articles = self.read_articles_from_csv(self.config['input_html'])
            if not articles:
                safe_print("错误: 没有文章数据可处理", True)
                return False
            processed_articles, chart_data = self.preprocess_data(articles)
            result = self.generate_html(processed_articles, chart_data, self.config['output_html'])
            return result
        except Exception as e:
            safe_print(f"生成HTML文件失败: {str(e)}", True)
            import traceback
            safe_print(traceback.format_exc(), self.verbose)
            return False