"""
文献内容理解增强工具
读取CSV文件中的文献数据，调用AI对标题、关键词和摘要进行翻译和优化,
并将结果输出到新的CSV文件和文本文件中。
"""
import os
import csv
import json
import time
from tqdm import tqdm
from openai import OpenAI
from dotenv import load_dotenv

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

class LiteratureTranslator:
    def __init__(self, config_file="pub.txt"):
        """初始化文献翻译工具"""
        self.config = self._read_config(config_file)
        self._init_ai_client()
        safe_print("文献内容理解增强工具初始化完成")
    
    def _read_config(self, config_file):
        """从配置文件读取设置"""
        config = {
            'input_llm': 'pubmed_enhanced.csv',
            'output_llm': 'pubmed_enhanced_llm.csv',
            'output_llm2': 'pre4tts.txt',
            'max_articles': 5,  # 默认处理前5篇文献
            'ai_model': 'qwen-plus',
            'ai_timeout': 60,  # 单位：秒
            'retry_times': 3,
            'api_key': '',      # 新增，API密钥
            'api_base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',  # 新增，API基础URL
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
                                
                                if key == 'input_llm':
                                    config['input_llm'] = value
                                elif key == 'output_llm':
                                    config['output_llm'] = value
                                elif key == 'output_llm2':
                                    config['output_llm2'] = value
                                elif key == 'max_articles':
                                    try:
                                        config['max_articles'] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的最大文章数: {value}，使用默认值: 5")
                                elif key == 'ai_model':
                                    config['ai_model'] = value
                                elif key == 'ai_timeout':
                                    try:
                                        config['ai_timeout'] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的AI超时设置: {value}，使用默认值: 60")
                                elif key == 'retry_times':
                                    try:
                                        config['retry_times'] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的重试次数: {value}，使用默认值: 3")
                                elif key == 'api_key':  # 新增，读取API密钥
                                    config['api_key'] = value
                                elif key == 'api_base_url':  # 新增，读取API基础URL
                                    config['api_base_url'] = value
                
                # 检查是否缺少配置项，如果是，则添加到配置文件
                self._check_and_update_config(config_file, config)
                
                safe_print(f"已从 {config_file} 加载配置")
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置")
                self._create_default_config(config_file, config)
        except Exception as e:
            safe_print(f"读取配置文件出错: {e}")
            safe_print("使用默认设置")
        
        return config
    
    def _check_and_update_config(self, config_file, config):
        """检查并更新配置文件，添加缺失的配置项"""
        needed_params = {
            'max_articles': '# 处理的最大文章数\nmax_articles=5\n\n',
            'ai_model': '# AI模型名称\nai_model=qwen-plus\n\n',
            'ai_timeout': '# AI调用超时时间(秒)\nai_timeout=60\n\n',
            'retry_times': '# 调用API失败时的重试次数\nretry_times=3\n\n',
            'api_key': '# 通义千问API密钥\napi_key=\n\n',  # 新增
            'api_base_url': '# API基础URL\napi_base_url=https://dashscope.aliyuncs.com/compatible-mode/v1\n\n'  # 新增
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
                    f.write("\n# AI翻译和理解设置\n")
                    for addition in additions:
                        f.write(addition)
                safe_print(f"已向 {config_file} 添加AI翻译和理解设置")
        except Exception as e:
            safe_print(f"更新配置文件出错: {e}")
    
    def _create_default_config(self, config_file, config):
        """创建默认配置文件"""
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                f.write("# 文献理解增强配置文件\n")
                f.write("# 使用格式: 参数=值\n\n")
                f.write("# 输入文件路径(文献数据)\n")
                f.write(f"input_llm={config['input_llm']}\n\n")
                f.write("# 输出CSV文件路径(增强后的文献数据)\n")
                f.write(f"output_llm={config['output_llm']}\n\n")
                f.write("# 输出TXT文件路径(用于文本转语音)\n")
                f.write(f"output_llm2={config['output_llm2']}\n\n")
                f.write("# 处理的最大文章数\n")
                f.write(f"max_articles={config['max_articles']}\n\n")
                f.write("# AI模型名称\n")
                f.write(f"ai_model={config['ai_model']}\n\n")
                f.write("# AI调用超时时间(秒)\n")
                f.write(f"ai_timeout={config['ai_timeout']}\n\n")
                f.write("# 调用API失败时的重试次数\n")
                f.write(f"retry_times={config['retry_times']}\n\n")
                f.write("# 通义千问API密钥\n")
                f.write(f"api_key={config['api_key']}\n\n")
                f.write("# API基础URL\n")
                f.write(f"api_base_url={config['api_base_url']}\n")
            safe_print(f"已创建默认配置文件: {config_file}")
        except Exception as e:
            safe_print(f"创建默认配置文件失败: {e}")
    
    def _init_ai_client(self):
        """初始化AI客户端"""
        # 从配置中获取 API 密钥
        api_key = self.config.get('api_key', '')
        api_base_url = self.config.get('api_base_url', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
        
        # 如果配置中没有 API 密钥，尝试从环境变量获取
        if not api_key:
            api_key = os.getenv("DASHSCOPE_API_KEY", '')
            if api_key:
                safe_print("从环境变量加载 API 密钥")
        
        if not api_key:
            safe_print("警告: 未找到API密钥，请在配置文件或环境变量中设置")
        
        try:
            self.client = OpenAI(
                api_key=api_key,
                base_url=api_base_url,
            )
            safe_print("AI客户端初始化成功")
            # 测试API连接
            if api_key:
                try:
                    test_response = self.client.chat.completions.create(
                        model=self.config['ai_model'],
                        messages=[
                            {'role': 'system', 'content': '你是一个助手'},
                            {'role': 'user', 'content': '请回复"API连接测试成功"'}
                        ],
                        timeout=5
                    )
                    safe_print(f"API连接测试结果: {test_response.choices[0].message.content}")
                except Exception as e:
                    safe_print(f"API连接测试失败: {e}")
        except Exception as e:
            safe_print(f"AI客户端初始化失败: {e}")
            self.client = None
    
    def translate_and_enhance(self):
        """处理并翻译文献"""
        input_file = self.config['input_llm']
        output_file = self.config['output_llm']
        output_txt = self.config['output_llm2']
        max_articles = self.config['max_articles']
        
        if not os.path.exists(input_file):
            safe_print(f"输入文件不存在: {input_file}")
            return False
        
        if not self.client:
            safe_print("AI客户端未初始化，无法进行翻译")
            return False
        
        try:
            # 读取CSV文件
            with open(input_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                articles = list(reader)
            
            safe_print(f"成功读取 {len(articles)} 篇文章，将处理前 {min(max_articles, len(articles))} 篇")
            
            # 限制处理的文章数量
            articles_to_process = articles[:min(max_articles, len(articles))]
            
            # 准备输出的TXT文件内容
            txt_output = []
            
            # 处理每篇文章
            with tqdm(total=len(articles_to_process), desc="翻译文献", unit="篇") as pbar:
                for idx, article in enumerate(articles_to_process):
                    safe_print(f"\n正在处理第 {idx+1} 篇文章: {article.get('title', '无标题')}")
                    
                    # 增强文章信息
                    enhanced_article = article.copy()  # 复制原始文章数据
                    
                    # 翻译标题
                    title = article.get('title', '')
                    if title:
                        translated_title = self._translate_with_verification("标题", title)
                        enhanced_article['translated_title'] = translated_title
                    else:
                        enhanced_article['translated_title'] = ""
                    
                    # 翻译关键词
                    keywords = article.get('keywords', '')
                    if keywords:
                        translated_keywords = self._translate_with_verification("关键词", keywords)
                        enhanced_article['translated_keywords'] = translated_keywords
                    else:
                        enhanced_article['translated_keywords'] = ""
                    
                    # 翻译摘要
                    abstract = article.get('abstract', '')
                    if abstract:
                        translated_abstract = self._translate_with_verification("摘要", abstract)
                        enhanced_article['translated_abstract'] = translated_abstract
                    else:
                        enhanced_article['translated_abstract'] = ""
                    
                    # 将当前文章添加到结果中
                    articles[idx] = enhanced_article
                    
                    # 添加到TXT输出
                    txt_content = self._format_for_txt(enhanced_article)
                    txt_output.append(txt_content)
                    
                    pbar.update(1)
            
            # 保存到CSV文件
            self._save_to_csv(articles, output_file)
            
            # 保存到TXT文件
            self._save_to_txt(txt_output, output_txt)
            
            return True
            
        except Exception as e:
            safe_print(f"处理文献出错: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _translate_with_verification(self, content_type, text):
        """翻译内容并进行二次校验"""
        safe_print(f"正在翻译{content_type}...")
        
        # 第一轮：基础翻译
        first_translation = self._call_ai_api(
            f"请将以下{content_type}翻译成中文，保持学术专业性:\n\n{text}"
        )
        
        # 第二轮：校验和优化
        verification_prompt = (
            f"请对以下翻译进行校对和优化，确保翻译结果准确、符合学术论文的专业性，"
            f"并且合乎中文科研写作习惯:\n\n"
            f"原文: {text}\n\n"
            f"当前翻译: {first_translation}\n\n"
            f"请给出最终优化版本的翻译结果，不需要解释修改理由，"
            f"直接返回最终翻译结果。"
        )
        
        final_translation = self._call_ai_api(verification_prompt)
        
        safe_print(f"{content_type}翻译并校验完成")
        return final_translation
    
    def _call_ai_api(self, prompt, retries=None):
        """调用AI API进行翻译"""
        if retries is None:
            retries = self.config['retry_times']
        
        model = self.config['ai_model']
        timeout = self.config['ai_timeout']
        
        for attempt in range(retries):
            try:
                start_time = time.time()
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {'role': 'system', 'content': '你是一个专业的学术翻译助手，擅长将英文学术文献准确翻译为符合中文学术习惯的表述。'},
                        {'role': 'user', 'content': prompt}
                    ],
                    timeout=timeout
                )
                
                # 获取响应内容
                result = response.choices[0].message.content
                
                # 计算并显示耗时
                elapsed_time = time.time() - start_time
                safe_print(f"API调用完成，耗时: {elapsed_time:.2f}秒")
                
                return result
                
            except Exception as e:
                safe_print(f"API调用失败 (尝试 {attempt+1}/{retries}): {str(e)}")
                if attempt < retries - 1:
                    sleep_time = 2 ** attempt  # 指数退避策略
                    safe_print(f"将在 {sleep_time} 秒后重试...")
                    time.sleep(sleep_time)
                else:
                    safe_print("所有重试均失败")
                    return "翻译失败，API调用错误"
    
    def _format_for_txt(self, article):
        """格式化文章内容，用于TXT输出"""
        title = article.get('translated_title', '')
        keywords = article.get('translated_keywords', '')
        abstract = article.get('translated_abstract', '')
        
        # 如果翻译字段为空，使用原文
        if not title:
            title = article.get('title', '')
        if not keywords:
            keywords = article.get('keywords', '')
        if not abstract:
            abstract = article.get('abstract', '')
        
        # 格式化输出 - 移除分隔符，简化格式
        formatted_text = f"标题：{title}\n\n关键词：{keywords}\n\n摘要：{abstract}\n\n\n"
        return formatted_text
    
    def _save_to_csv(self, articles, output_file):
        """保存到CSV文件"""
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 获取所有字段
            fieldnames = []
            if articles:
                fieldnames = list(articles[0].keys())
            
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(articles)
            
            safe_print(f"成功保存 {len(articles)} 篇文章到 {output_file}")
            return True
        except Exception as e:
            safe_print(f"保存CSV文件失败: {e}")
            return False
    
    def _save_to_txt(self, contents, output_file):
        """保存到TXT文件"""
        try:
            # 确保输出目录存在
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.writelines(contents)
            
            safe_print(f"成功保存翻译结果到 {output_file}")
            return True
        except Exception as e:
            safe_print(f"保存TXT文件失败: {e}")
            return False

def main():
    """主程序入口"""
    try:
        # 初始化文献翻译工具
        translator = LiteratureTranslator()
        
        # 翻译并增强文献
        translator.translate_and_enhance()
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
