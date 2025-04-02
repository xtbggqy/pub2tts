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
   - 使用`-s`参数可执行一个或多个步骤:
     ```bash
     # 单个步骤
     python main.py -s search
     
     # 多个步骤（按照顺序执行）
     python main.py -s search enhance
     
     # 跳过语音合成步骤
     python main.py --no-tts
     ```

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

### TTS内容选择功能

系统支持自定义选择要转换为语音的内容部分：

1. 在`pub.txt`配置文件中设置`tts_content`参数：
   ```
   # TTS内容选择（用逗号分隔，可多选）
   tts_content=title_zh,abstract_zh,authors
   ```

2. 可选的内容组件：
   - `title_zh`: 翻译后的中文标题
   - `title_en`: 原始英文标题
   - `keywords_zh`: 翻译后的中文关键词
   - `keywords_en`: 原始英文关键词
   - `abstract_zh`: 翻译后的中文摘要
   - `abstract_en`: 原始英文摘要
   - `authors`: 作者名单
   - `journal`: 期刊名称（含影响因子和分区信息）
   - `impact_factor`: 单独添加影响因子信息
   - `quartile`: 单独添加分区信息
   
3. 预设组合（快捷选项）：
   - `all_zh`: 所有中文内容（标题、关键词、摘要）
   - `all_en`: 所有英文内容（标题、关键词、摘要）
   - `mixed`: 优先使用中文，如某部分无中文翻译则使用英文
   - `journal_full`: 包含期刊名称、影响因子和分区信息

4. 使用效果：
   - 纯内容输出：选择`tts_content=journal,title_zh`时，输出不包含"期刊："、"标题："等前缀标签
   - 简洁输出：语音文件中只包含所选内容，避免不必要的信息

5. 示例配置：
   - 仅合成中文标题和摘要：`tts_content=title_zh,abstract_zh`
   - 中英文标题都合成：`tts_content=title_zh,title_en`
   - 仅合成期刊名称和中文标题：`tts_content=journal,title_zh`
   - 合成完整文献信息：`tts_content=title_zh,keywords_zh,abstract_zh,authors,journal`

该功能使您可以根据需求灵活选择要转换为语音的内容组合，既可以减少不必要的语音合成时间，也能根据不同场景定制语音内容。输出内容不包含任何标签（如"标题："），使语音输出更加自然流畅。

## 五、组件说明

### main.py

主程序，协调调用各个模块，提供完整流程和单步执行选项。

**用法**:
```bash
# 执行完整流程
python main.py

# 执行特定步骤（可以同时执行多个步骤），前提是你准备需要的文件和参数
python main.py -s search                   # 仅执行文献检索
python main.py -s search enhance           # 执行检索和增强
python main.py -s enhance translate tts    # 执行增强、翻译和语音合成
python main.py --no-tts                    # 执行前三个步骤，跳过语音合成

# 使用特定配置文件，默认配置文件为`pub.txt`
python main.py -c custom_config.txt
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
   - 输出所有翻译结果到`pubmed_enhanced_llm.csv`
   - 输出用于TTS的结构化数据到`pre4tts.txt`

4. **语音合成**：`ali2tts_ai.py`
   - 读取`pre4tts.txt`中的结构化数据
   - 根据配置文件中的`tts_content`设置提取所需内容
   - 生成语音文件并保存到输出目录

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

### 搜索词增强机制

系统搜索词润色功能采用了双轮优化策略：

1. **第一轮转换**：将简单关键词转换为PubMed高级检索格式
   - 分析核心概念，寻找MeSH主题词和相关同义词
   - 添加合适的字段限定词和布尔运算符
   - 构建初步的检索式

2. **第二轮校正**：对第一轮结果进行优化和简化
   - 确保检索式简洁有效，术语数量控制在5个以内
   - 优先使用通用字段如`[All Fields]`和`[MeSH Terms]`
   - 修复语法错误和格式问题

3. **安全机制**：
   - 对常见基础关键词（如plant、genome等）使用预设的简单检索式，避免过度复杂化
   - 当检索式缺少必要字段时，自动添加全局字段确保检索有效
   - 处理失败时返回安全的基本检索式

这种多轮优化策略确保了搜索词的准确性和简洁性，特别适合复杂学术检索和基础关键词检索。

### 数据流优化

系统数据流处理逻辑优化：

1. **结构化数据传递**：
   - `pre4tts.txt`文件使用JSON结构保存文章数据
   - 通过`@@DATA_BEGIN@@`和`@@DATA_END@@`标记包围JSON数据
   - TTS组件根据用户配置智能提取需要的内容部分

2. **输出文件分离**：
   - `pubmed_enhanced_llm.csv`：保存完整的翻译结果，包含原文和译文
   - `pre4tts.txt`：仅包含TTS所需的结构化数据

3. **内存效率**：
   - 数据处理采用流式处理，减少内存占用
   - 大型CSV文件处理采用分批读取和处理策略

## 八、新增日志功能

系统现在支持同时将日志输出到终端和文件：

1. **默认配置**:
   - 日志文件保存在 `out/pub.log`
   - 日志包含详细的操作记录和错误信息
   - 每次运行会在日志文件中添加新的记录，而不是覆盖

2. **命令行选项**:
   - 使用 `-l, --log` 参数指定自定义日志文件路径：
     ```bash
     python main.py --log my_custom_log.txt
     ```
   - 使用 `--no-log` 参数完全禁用日志文件：
     ```bash
     python main.py --no-log
     ```

3. **日志级别**:
   - 日志文件中包含更详细的信息，包括时间戳和级别
   - 级别包括：INFO, WARNING, ERROR, SUCCESS, DEBUG
   - 使用 `-v, --verbose` 参数可以获取更详细的日志输出

4. **日志查看**:
   - 可以随时查看日志文件来了解过去的运行情况
   - 日志文件可以用任何文本编辑器打开
   - 每次运行会在日志中添加明显的分隔标记

这个功能使系统更容易排错和记录运行历史，特别是对于长时间运行的批处理任务。

## 九、常见问题

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

4. **TTS内容选择问题**
   - 问题：使用`tts_content`设置但语音内容不符合预期
   - 解决：确认配置文件中参数名称和值的正确性，多个值用逗号分隔
   - 检查：验证`pre4tts.txt`文件内容是否包含JSON数据块

5. **API密钥和访问问题**
   - 确保API密钥正确无误并具有足够权限
   - 检查网络连接是否稳定
   - 确认API服务是否可用，必要时查看服务提供商的状态页面

## 十、许可证

本项目采用MIT许可证
