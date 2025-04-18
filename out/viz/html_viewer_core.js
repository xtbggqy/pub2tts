/**
 * PubMed文献浏览器核心JavaScript
 * 提供数据表格、搜索筛选和图表可视化功能
 */

console.log("Script start");
let articles = [];
let chartData = {};
// 声明为全局变量，方便各函数访问
let fields = [];
// 添加默认字段配置
let defaultVisibleColumns = null;
let defaultSearchField = null;

function getAllFields(data) {
    const fields = new Set();
    if (!Array.isArray(data)) {
        console.error("getAllFields: Input data is not an array", data);
        return [];
    }
    data.forEach(row => {
        if (typeof row === 'object' && row !== null) {
            Object.keys(row).forEach(k => fields.add(k));
        } else {
            console.warn("getAllFields: Skipping invalid row", row);
        }
    });
    const priority = [
        'id','title','translated_title','authors','journal','year','pmid','doi','url','abstract','translated_abstract','keywords','translated_keywords','quartile','impact_factor',
        'publish_time','pub_time','publication_date','date','time','datetime','created_at','updated_at'
    ];
    const sorted = priority.filter(f => fields.has(f));
    priority.forEach(f => fields.delete(f));
    return sorted.concat(Array.from(fields));
}

function renderColumnSelector() {
    console.log("Rendering column selector...");
    const selectorContainer = document.createElement('div');
    selectorContainer.className = "column-selector-container";
    const selectorDiv = document.createElement('div');
    selectorDiv.innerHTML = `<label class="form-label fw-bold d-block mb-2">选择显示的列：</label>`;
    
    // 添加字段搜索下拉框
    const searchFieldDiv = document.createElement('div');
    searchFieldDiv.className = "mb-3";
    searchFieldDiv.innerHTML = `
        <label class="form-label fw-bold d-block mb-2">按字段搜索：</label>
        <div class="row">
            <div class="col-md-4 mb-2">
                <select id="searchField" class="form-select">
                    <option value="">全文搜索</option>
                    ${fields.map(field => {
                        let showName = getDisplayName(field);
                        let selected = field === defaultSearchField ? 'selected' : '';
                        return `<option value="${field}" ${selected}>${showName}</option>`;
                    }).join('')}
                </select>
            </div>
            <div class="col-md-8">
                <input type="text" id="fieldSearchInput" class="form-control" placeholder="输入搜索内容...">
            </div>
        </div>
    `;
    selectorContainer.appendChild(searchFieldDiv);
    
    if (fields.length === 0) {
         console.warn("No fields found for column selector.");
         selectorDiv.innerHTML += '<p class="text-muted">未检测到数据列。</p>';
    } else {
        fields.forEach((field, idx) => {
            let showName = getDisplayName(field);
            // 检查是否应该默认显示该列
            let checked = 'checked';
            if (defaultVisibleColumns && Array.isArray(defaultVisibleColumns)) {
                checked = defaultVisibleColumns.includes(field) ? 'checked' : '';
            }
            
            selectorDiv.innerHTML += `
                <div class="form-check form-check-inline">
                    <input class="form-check-input column-toggle" type="checkbox" id="col-toggle-${idx}" data-field="${field}" ${checked}>
                    <label class="form-check-label" for="col-toggle-${idx}">${showName}</label>
                </div>
            `;
        });
    }
    selectorContainer.appendChild(selectorDiv);
    
    // 添加保存按钮
    const saveButtonDiv = document.createElement('div');
    saveButtonDiv.className = "mt-2";
    saveButtonDiv.innerHTML = `
        <button id="saveColumnsBtn" class="btn btn-sm btn-primary">
            <i class="fa fa-save"></i> 保存列设置
        </button>
    `;
    selectorDiv.appendChild(saveButtonDiv);
    
    const insertBeforeElement = document.querySelector('.main-card .row.mb-3');
    if (insertBeforeElement) {
         document.querySelector('.main-card').insertBefore(selectorContainer, insertBeforeElement);
         console.log("Column selector rendered.");
    } else {
         console.error("Could not find element to insert column selector before.");
    }
}

// 添加获取显示名称的辅助函数
function getDisplayName(field) {
    if (['publish_time','pub_time','publication_date','date','time','datetime','created_at','updated_at'].includes(field)) return '时间';
    else if (field === 'title') return '标题';
    else if (field === 'translated_title') return '翻译标题';
    else if (field === 'authors') return '作者';
    else if (field === 'journal') return '期刊';
    else if (field === 'year') return '年份';
    else if (field === 'pmid') return 'PMID';
    else if (field === 'doi') return 'DOI';
    else if (field === 'url') return '链接';
    else if (field === 'abstract') return '摘要';
    else if (field === 'translated_abstract') return '翻译摘要';
    else if (field === 'keywords') return '关键词';
    else if (field === 'translated_keywords') return '翻译关键词';
    else if (field === 'quartile') return '分区';
    else if (field === 'impact_factor') return '影响因子';
    return field;
}

function renderInitialHeader(allFields) {
    console.log("Rendering initial header...");
    const headerRow = document.getElementById('tableHeader');
    if (!headerRow) { console.error("Header row element not found!"); return; }
    headerRow.innerHTML = '';
    if (allFields.length === 0) {
         console.warn("No fields for header.");
         headerRow.innerHTML = '<th>无数据</th>';
         return;
    }
    allFields.forEach(field => {
        let showName = getDisplayName(field);
        const th = document.createElement('th');
        th.textContent = showName;
        headerRow.appendChild(th);
    });
    console.log("Initial header rendered.");
}

function renderInitialTable(data, allFields) {
    console.log("Rendering initial table body...");
    const tableBody = document.getElementById('tableBody');
    if (!tableBody) { console.error("Table body element not found!"); return; }
    tableBody.innerHTML = '';
    const articleCountElement = document.getElementById('articleCount');

    if (!Array.isArray(data) || data.length === 0 || allFields.length === 0) {
        console.warn("No data or fields to render in table body.");
        const colCount = allFields.length > 0 ? allFields.length : 1;
        tableBody.innerHTML = `<tr class="no-data-row"><td colspan="${colCount}" class="text-center text-muted">没有可显示的文献记录。</td></tr>`;
        if(articleCountElement) articleCountElement.textContent = '0';
        return;
    }

    data.forEach(row => {
        const tr = document.createElement('tr');
        allFields.forEach(field => {
            let val = (row && typeof row === 'object' && row[field] !== undefined) ? row[field] : '';
            if (field.toLowerCase() === 'pmid' && val) {
                val = `<a href="https://pubmed.ncbi.nlm.nih.gov/${val}" target="_blank">${val}</a>`;
            }
            if (field.toLowerCase() === 'doi' && val) {
                val = `<a href="https://doi.org/${val}" target="_blank">${val}</a>`;
            }
            if (field.toLowerCase() === 'url' && val) {
                val = `<a href="${val}" target="_blank">链接</a>`;
            }
            const td = document.createElement('td');
            td.innerHTML = val;
            tr.appendChild(td);
        });
        tableBody.appendChild(tr);
    });
    if(articleCountElement) articleCountElement.textContent = data.length;
    console.log(`Initial table body rendered with ${data.length} rows.`);
}

function initializeDataFromJson() {
    try {
        // 实际的数据会在Python生成HTML时注入
        articles = ARTICLES_DATA || [];
        chartData = CHART_DATA || {};
        // 获取默认列设置
        defaultVisibleColumns = DEFAULT_VISIBLE_COLUMNS || null;
        defaultSearchField = DEFAULT_SEARCH_FIELD || null;
    } catch (e) {
        console.error("Error parsing initial data:", e);
        const mainCard = document.querySelector('.main-card');
        if (mainCard) {
            mainCard.innerHTML = '<div class="alert alert-danger">加载数据时出错，请检查输入文件或联系管理员。</div>' + mainCard.innerHTML;
        }
    }

    console.log("Articles data:", articles);
    console.log("Chart data:", chartData);
    console.log("Default visible columns:", defaultVisibleColumns);
    console.log("Default search field:", defaultSearchField);

    // 获取所有字段并保存到全局变量
    fields = getAllFields(articles);
    console.log("Detected fields:", fields);

    // 渲染初始界面
    try {
        renderColumnSelector();
        renderInitialHeader(fields);
        renderInitialTable(articles, fields);
    } catch (e) {
        console.error("Error during initial rendering:", e);
    }

    return fields;
}

function initializeDataTable(fields) {
    let dataTable = null;
    
    $(document).ready(function() {
        console.log("Document ready. Initializing DataTable...");
        try {
            if ($('#articlesTable tbody tr.no-data-row').length === 0 && $('#articlesTable tbody tr').length > 0) {
                dataTable = $('#articlesTable').DataTable({
                    dom: 'Bfrtip',
                    buttons: [
                        { extend: 'copy', text: '<i class="fa fa-copy"></i> 复制' },
                        { extend: 'csv', text: '<i class="fa fa-file-csv"></i> 导出CSV' },
                        { extend: 'excel', text: '<i class="fa fa-file-excel"></i> Excel' },
                        { extend: 'pdf', text: '<i class="fa fa-file-pdf"></i> PDF' },
                        { extend: 'print', text: '<i class="fa fa-print"></i> 打印' }
                    ],
                    pageLength: ARTICLES_PER_PAGE || 20,
                    language: { url: "//cdn.datatables.net/plug-ins/1.13.4/i18n/zh-CN.json" },
                    order: [[0, 'asc']],
                    scrollX: true
                });
                console.log("DataTable initialized successfully.");

                // 处理列显示切换
                console.log("Attaching column toggle listeners...");
                document.querySelectorAll('.column-toggle').forEach(cb => {
                    // 应用默认列显示
                    if (defaultVisibleColumns && Array.isArray(defaultVisibleColumns)) {
                        const field = cb.getAttribute('data-field');
                        const columnIndex = fields.indexOf(field);
                        if (columnIndex > -1 && dataTable) {
                            try {
                                const column = dataTable.column(columnIndex);
                                const isVisible = defaultVisibleColumns.includes(field);
                                column.visible(isVisible);
                                cb.checked = isVisible;
                            } catch (e) {
                                console.error(`Error setting default column visibility for '${field}':`, e);
                            }
                        }
                    }
                    
                    cb.addEventListener('change', function() {
                        const field = this.getAttribute('data-field');
                        const columnIndex = fields.indexOf(field);
                        if (columnIndex > -1 && dataTable) {
                            try {
                                const column = dataTable.column(columnIndex);
                                column.visible(this.checked);
                                console.log(`Column '${field}' visibility set to ${this.checked}`);
                            } catch (e) {
                                console.error(`Error toggling column '${field}':`, e);
                            }
                        } else {
                            console.warn(`Could not find column index for field '${field}' or DataTable not ready.`);
                        }
                    });
                });
                console.log("Column toggle listeners attached.");
                
                // 保存列设置的处理
                document.getElementById('saveColumnsBtn')?.addEventListener('click', function() {
                    try {
                        const visibleColumns = [];
                        document.querySelectorAll('.column-toggle:checked').forEach(cb => {
                            visibleColumns.push(cb.getAttribute('data-field'));
                        });
                        localStorage.setItem('literatureViewerColumns', JSON.stringify(visibleColumns));
                        
                        // 获取当前选中的搜索字段
                        const searchField = document.getElementById('searchField')?.value;
                        localStorage.setItem('literatureViewerSearchField', searchField || '');
                        
                        alert('列设置已保存到浏览器本地存储。下次访问时将使用这些设置。');
                    } catch (e) {
                        console.error("Error saving column settings:", e);
                        alert('保存设置失败: ' + e.message);
                    }
                });
                
                // 处理按字段搜索功能
                const fieldSearchInput = document.getElementById('fieldSearchInput');
                const searchFieldSelect = document.getElementById('searchField');
                
                if (fieldSearchInput && searchFieldSelect) {
                    fieldSearchInput.addEventListener('input', function() {
                        if (dataTable) {
                            const searchField = searchFieldSelect.value;
                            const searchTerm = this.value;
                            
                            if (searchField) {
                                // 按特定字段搜索
                                dataTable.column(fields.indexOf(searchField)).search(searchTerm).draw();
                            } else {
                                // 全文搜索
                                dataTable.search(searchTerm).draw();
                            }
                        }
                    });
                    
                    searchFieldSelect.addEventListener('change', function() {
                        if (dataTable && fieldSearchInput.value) {
                            const searchField = this.value;
                            const searchTerm = fieldSearchInput.value;
                            
                            // 先清除所有列的搜索
                            dataTable.columns().search('').draw();
                            
                            if (searchField) {
                                // 按特定字段搜索
                                dataTable.column(fields.indexOf(searchField)).search(searchTerm).draw();
                            } else {
                                // 全文搜索
                                dataTable.search(searchTerm).draw();
                            }
                        }
                    });
                    
                    // 如果有默认搜索字段，激活它
                    if (defaultSearchField) {
                        searchFieldSelect.value = defaultSearchField;
                    }
                }
            } else {
                console.warn("DataTable initialization skipped: Table body is empty or contains 'no data' row.");
                 $('.dt-buttons, .dataTables_filter, .dataTables_info, .dataTables_paginate').hide();
            }
        } catch (e) {
            console.error("Error initializing DataTable:", e);
        }

        // 隐藏原始搜索框，因为我们有自己的搜索字段
        $('.dataTables_filter').hide();
        
        // 处理全局搜索框，确保它与我们的字段搜索一起工作
        const globalSearchInput = document.getElementById('globalSearch');
        if (globalSearchInput) {
            globalSearchInput.addEventListener('input', function() {
                if (dataTable) {
                    const searchField = document.getElementById('searchField')?.value;
                    const searchTerm = this.value;
                    
                    // 清除字段搜索框
                    if (document.getElementById('fieldSearchInput')) {
                        document.getElementById('fieldSearchInput').value = '';
                    }
                    
                    // 清除所有列的搜索
                    dataTable.columns().search('').draw();
                    
                    if (searchField) {
                        // 按特定字段搜索
                        dataTable.column(fields.indexOf(searchField)).search(searchTerm).draw();
                    } else {
                        // 全文搜索
                        dataTable.search(searchTerm).draw();
                    }
                } else {
                    console.warn("Search ignored: DataTable not initialized.");
                }
            });
        } else {
            console.error("Global search input element not found!");
        }
    });
}

function initializeCharts() {
    document.addEventListener('DOMContentLoaded', function() {
        console.log("DOM fully loaded. Rendering chart...");
        const chartContainer = document.querySelector('.chart-container');
        const chartCanvas = document.getElementById('chartCanvas');
        let chartInstance = null;

        function renderChart() {
            if (chartInstance) {
                chartInstance.destroy();
            }

            let labels, data, titleText;
            let chartShouldBeVisible = false;

            if (chartData && chartData.time && typeof chartData.time === 'object' && Object.keys(chartData.time).length > 0) {
                labels = Object.keys(chartData.time);
                data = Object.values(chartData.time);
                titleText = `文章发布时间分布 (${chartData.time_field || '未知时间字段'})`;
                chartShouldBeVisible = true;
            } else if (chartData && chartData.years && typeof chartData.years === 'object' && Object.keys(chartData.years).length > 0) {
                labels = Object.keys(chartData.years);
                data = Object.values(chartData.years);
                titleText = '文章年份分布';
                chartShouldBeVisible = true;
            } else {
                console.warn("No valid time or year data for chart.");
                chartShouldBeVisible = false;
            }

            if (chartContainer) {
                chartContainer.style.display = chartShouldBeVisible ? 'block' : 'none';
            } else {
                 console.error("Chart container element not found!");
                 return;
            }

            if (!chartShouldBeVisible) {
                return;
            }

            if (!chartCanvas) {
                 console.error("Chart canvas element not found!");
                 return;
            }

            const ctx = chartCanvas.getContext('2d');
            try {
                chartInstance = new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: '文章数量',
                            data: data,
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'top' },
                            title: { display: true, text: titleText }
                        },
                        scales: {
                            x: { ticks: { autoSkip: true, maxRotation: 45, minRotation: 0 } }
                        }
                    }
                });
                console.log("Chart rendered successfully.");
            } catch (e) {
                console.error("Error rendering chart:", e);
            }
        }
        
        if (articles && articles.length > 0) {
             renderChart();
        } else {
             console.warn("Skipping chart rendering due to data parsing error.");
        }
    });
}

// Main initialization
document.addEventListener('DOMContentLoaded', function() {
    const detectedFields = initializeDataFromJson();
    initializeDataTable(fields); // 使用全局fields变量
    initializeCharts();
});

console.log("Script end");
