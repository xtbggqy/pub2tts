# PubMed文献一站式处理系统

一个用于自动化PubMed文献检索、处理、翻译和语音合成的集成工具。

## 一、项目简介

该系统实现了从PubMed检索文献到生成语音合成的全流程自动化处理，主要包括以下功能：

1. **文献检索**：根据关键词从PubMed获取最新文献
2. **期刊信息增强**：为文献添加期刊影响因子、分区等信息
3. **文献翻译**：调用AI将英文文献的标题、关键词和摘要翻译成中文
4. **语音合成**：将翻译后的内容转换为语音文件

## 二、系统要求

- Python 3.7+
- 需要安装的第三方库（可通过`pip install -r requirements.txt`安装）:
  - openai
  - dashscope
  - biopython
  - tqdm
  - python-dotenv
  - tiktoken

## 三、快速开始

1. **获取代码**
   - 下载本项目的ZIP压缩包并解压
   - 或使用Git克隆:
     ```bash
     git clone https://github.com/username/pubmed-processor.git
     cd pubmed-processor
     ```

2. **安装依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置参数**
   - 打开`pub.txt`文件进行配置
   - 必须配置的项目:
     - `api_key`: 阿里云通义千问API密钥 (从[阿里云百炼平台](https://bailian.console.aliyun.com/)获取)
     - `query`: PubMed搜索关键词 (如"cancer therapy")
   - 可选配置:
     - `max_results`: 检索文献数量 (默认30篇)
     - `time_period`: 文献发表时间范围 (默认2年内)
     - `max_articles`: 需要翻译的文章数 (默认3篇)

4. **运行程序**
   ```bash
   python main.py
   ```
   - 使用`-v`参数可查看详细日志: `python main.py -v`
   - 使用`-s`参数可单独执行某一步骤: `python main.py -s translate`

5. **查看结果**
   - 所有输出文件保存在`out`文件夹
   - 处理3篇文献全流程约需2-3分钟 (夜间API调用较少时约1分钟)
   - 生成的音频文件位于`out`文件夹中

6. **关于API成本**
   - 处理3篇文献的成本估算: 约0.14元人民币（查找文献完全免费）
   - 阿里云API每月有免费额度:
     - 通义千问LLM: 每月免费额度视账号类型而定（经常会有一些免费的大模型可供使用）
     - TTS语音合成: 每月前3万字符免费
   - 在免费额度内基本不产生费用
   - [阿里云学生优惠](https://university.aliyun.com/)（包括本科生和研究生），每年免费领300元优惠券

## 四、配置文件

系统通过`pub.txt`文件进行配置，主要参数包括：

### 基础配置
- `query`：PubMed搜索关键词，支持高级检索语法
- `start_date`/`end_date`：文献检索日期范围
- `time_period`：最近时期（年），如0.5表示最近6个月
- `max_results`：最大检索结果数量
- `get_citations`：是否获取引用数量(yes/no)

### 文件路径配置
- `input_sort`：期刊增强输入文件路径
- `output_sort`：期刊增强输出文件路径
- `input_llm`：翻译输入文件路径
- `output_llm`：翻译输出CSV文件路径
- `output_llm2`：翻译输出TXT文件路径（用于TTS）
- `journal_data_path`：期刊信息数据文件路径

### AI和语音配置
- `api_key`：通义千问API密钥
- `api_base_url`：API基础URL
- `ai_model`：AI模型名称
- `max_articles`：翻译处理的最大文章数
- `tts_model`：语音合成模型/音色
- `tts_format`：音频输出格式(mp3/wav)
- `tts_output_dir`：语音输出目录

## 五、组件说明

### main.py

主程序，协调调用各个模块，提供完整流程和单步执行选项。

**用法**:
```bash
# 执行完整流程
python main.py

# 执行特定步骤
python main.py -s search    # 仅执行文献检索
python main.py -s enhance   # 仅执行期刊信息增强
python main.py -s translate # 仅执行文献翻译
python main.py -s tts       # 仅执行语音合成

# 使用特定配置文件，默认配置文件为`pub.txt`
python main.py -c config.txt
```

### pub_search.py

PubMed文献检索模块，从PubMed API获取文献信息。

**独立使用**:
```bash
python pub_search.py
```

### journal_enhancement.py

期刊信息增强模块，根据期刊名称添加影响因子、分区等信息。

**独立使用**:
```bash
python journal_enhancement.py
```

### llm_understand.py

文献翻译和理解模块，使用AI对标题、关键词和摘要进行翻译，翻译进行两轮以保证其准确性。

**独立使用**:
```bash
python llm_understand.py
```

### ali2tts_ai.py

语音合成模块，将翻译后的文本转换为语音文件。

**独立使用**:
```bash
python ali2tts_ai.py
```

## 六、工作流程

1. **文献检索**：`pub_search.py`
   - 从PubMed检索符合条件的文献
   - 输出到`pubmed_results.csv`

2. **期刊信息增强**：`journal_enhancement.py`
   - 读取`pubmed_results.csv`
   - 添加期刊影响因子和分区信息
   - 输出到`pubmed_enhanced.csv`

3. **文献翻译**：`llm_understand.py`
   - 读取`pubmed_enhanced.csv`
   - 翻译标题、关键词和摘要
   - 输出到`pubmed_enhanced_llm.csv`和`pre4tts.txt`

4. **语音合成**：`ali2tts_ai.py`
   - 读取`pre4tts.txt`
   - 生成语音文件
   - 保存到`output_audio`目录

## 七、高级用法

### 自定义期刊信息数据

系统使用JSON格式的期刊数据文件来获取期刊的影响因子和分区信息。您可以通过修改`journal_data_path`指向自己的数据文件。

### 排序方式

可在配置文件中设置文章排序方式：
- `impact_factor`: 按影响因子排序(从高到低)
- `journal`: 按期刊名称排序(字母顺序)
- `quartile`: 按分区排序(Q1>Q2>Q3>Q4)
- `date`: 按发表日期排序(从新到旧)

### 语音模型选择

系统默认使用`sambert-zhichu-v1`模型，可以在配置文件中通过`tts_model`参数更改。

## 八、常见问题

1. **找不到期刊信息**
   - 检查期刊名称是否匹配
   - 确认`journal_data_path`指向正确的期刊数据文件

2. **API调用失败**
   - 确认API密钥是否正确
   - 检查网络连接
   - 查看是否超出API调用限制

3. **翻译质量问题**
   - 可以调整翻译提示词
   - 尝试其他AI模型

## 九、许可证

本项目采用MIT许可证
