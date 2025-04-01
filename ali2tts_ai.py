import dashscope
from dashscope.audio.tts import SpeechSynthesizer
import os
import datetime
import glob
import sys

def safe_print(msg, verbose=True):
    """安全打印，处理编码问题"""
    if not verbose:
        # 检查是否为重要消息
        if not any(key in msg for key in ["成功", "完成", "错误", "失败", "警告", "TTS费用", "字符统计"]):
            return
            
    try:
        print(msg)
        sys.stdout.flush()
    except:
        print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
        sys.stdout.flush()

class TtsConverter:
    def __init__(self, config_file="pub.txt", verbose=False):
        """初始化语音合成工具"""
        self.verbose = verbose  # 先设置verbose属性，因为_read_config会使用它打印日志
        self.config = self._read_config(config_file)
        self._init_api_client()
        self._ensure_output_dir()
        
        # 添加字符计数
        self.total_characters = 0
        self.file_count = 0
        
        safe_print("语音合成工具初始化完成", self.verbose)
    
    def _read_config(self, config_file):
        """从配置文件读取设置"""
        config = {
            'api_key': '',  # 通义千问 API 密钥
            'tts_model': 'sambert-zhichu-v1',  # 默认 TTS 模型
            'tts_input': 'pre4tts.txt',  # 默认输入文件
            'tts_output_dir': 'output_audio',  # 默认输出目录
            'tts_format': 'mp3',  # 默认音频格式
            'tts_sample_rate': 48000,  # 默认采样率
            'process_directory': False,  # 是否处理整个目录
            'tts_directory': '',  # 要处理的目录
            'tts_price': 1.0,  # 默认TTS价格：3元/万字符（超出免费额度后）
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
                                
                                if key == 'api_key':
                                    config['api_key'] = value
                                elif key == 'tts_model':
                                    config['tts_model'] = value
                                elif key == 'tts_input':
                                    config['tts_input'] = value
                                elif key == 'tts_output_dir':
                                    config['tts_output_dir'] = value
                                elif key == 'tts_format':
                                    config['tts_format'] = value
                                elif key == 'tts_sample_rate':
                                    try:
                                        config['tts_sample_rate'] = int(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的采样率: {value}，使用默认值: 48000", self.verbose)
                                elif key == 'process_directory':
                                    config['process_directory'] = value.lower() in ['true', 'yes', 'y', '1']
                                elif key == 'tts_directory':
                                    config['tts_directory'] = value
                                elif key == 'tts_price':  # 新增，读取TTS价格
                                    try:
                                        config['tts_price'] = float(value)
                                    except ValueError:
                                        safe_print(f"警告: 无效的TTS价格: {value}，使用默认值: 3.0元/万字符", self.verbose)
                
                # 检查是否缺少配置项，如果是，则添加到配置文件
                self._check_and_update_config(config_file, config)
                
                safe_print(f"已从 {config_file} 加载TTS配置", self.verbose)
            else:
                safe_print(f"配置文件 {config_file} 不存在，使用默认设置", self.verbose)
        except Exception as e:
            safe_print(f"读取配置文件出错: {e}", self.verbose)
            safe_print("使用默认设置", self.verbose)
        
        return config
    
    def _check_and_update_config(self, config_file, config):
        """检查并更新配置文件，添加缺失的配置项"""
        needed_params = {
            'tts_model': '# TTS模型/音色\ntts_model=sambert-zhichu-v1\n\n',
            'tts_input': '# TTS输入文件路径\ntts_input=pre4tts.txt\n\n',
            'tts_output_dir': '# TTS输出目录\ntts_output_dir=output_audio\n\n',
            'tts_format': '# 音频格式(mp3/wav)\ntts_format=mp3\n\n',
            'tts_sample_rate': '# 音频采样率\ntts_sample_rate=48000\n\n',
            'process_directory': '# 是否处理整个目录(yes/no)\nprocess_directory=no\n\n',
            'tts_directory': '# 要处理的目录路径\ntts_directory=\n\n',
            'tts_price': '# TTS API价格设置（元/万字符，超过免费额度后）\ntts_price=3.0  # 语音合成价格，每月前三万字符免费，超出后按此价格计费\n\n',
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
                    f.write("\n# 语音合成(TTS)设置\n")
                    for addition in additions:
                        f.write(addition)
                safe_print(f"已向 {config_file} 添加TTS设置", self.verbose)
        except Exception as e:
            safe_print(f"更新配置文件出错: {e}", self.verbose)
    
    def _init_api_client(self):
        """初始化API客户端"""
        # 从配置读取API密钥
        api_key = self.config.get('api_key', '')
        
        if not api_key:
            safe_print("警告: API密钥未设置，TTS功能将无法使用", self.verbose)
            return
        
        try:
            # 设置API密钥
            dashscope.api_key = api_key
            safe_print("TTS API客户端初始化成功", self.verbose)
        except Exception as e:
            safe_print(f"初始化API客户端失败: {e}", self.verbose)
    
    def _ensure_output_dir(self):
        """确保输出目录存在"""
        output_dir = self.config.get('tts_output_dir')
        if not output_dir:
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_audio")
            self.config['tts_output_dir'] = output_dir
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            safe_print(f"已创建输出目录: {output_dir}", self.verbose)
    
    def _count_characters(self, text):
        """计算字符数（中文按2字符，其他按1字符计算）
        
        阿里云计费标准：每个汉字、假名或标点符号计为1个字符，每个字母或数字计为0.5个字符
        我们这里采用简化统计：
        - 汉字、日韩文等宽字符按1个字符
        - 英文字母、数字、符号等半宽字符按0.5个字符
        最后向上取整
        """
        if not text:
            return 0
        
        # 统计全角字符（如中文、日韩文等）
        fullwidth_count = sum(1 for char in text if ord(char) > 0x2E80)
        # 统计半角字符（如英文字母、数字等）
        halfwidth_count = len(text) - fullwidth_count
        
        # 按阿里云计费规则：全角1个字符，半角0.5个字符
        total_chars = fullwidth_count + (halfwidth_count / 2)
        # 向上取整
        return int(total_chars + 0.5)

    def text_to_speech(self, text, output_file=None):
        """将文本转换为语音并保存到文件"""
        model = self.config.get('tts_model')
        sample_rate = self.config.get('tts_sample_rate')
        audio_format = self.config.get('tts_format')
        output_dir = self.config.get('tts_output_dir')
        
        if output_file is None:
            # 生成带时间戳的输出文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(output_dir, f"{model}_{timestamp}.{audio_format}")
        
        # 统计字符数
        char_count = self._count_characters(text)
        self.total_characters += char_count
        self.file_count += 1
        
        safe_print(f"开始合成语音，使用模型: {model}", self.verbose)
        safe_print(f"文本长度: {len(text)}个字符，计费字符数: {char_count}", self.verbose)
        safe_print(f"文本内容: {text[:50]}{'...' if len(text) > 50 else ''}", self.verbose)
        
        try:
            result = SpeechSynthesizer.call(
                model=model,
                text=text,
                sample_rate=sample_rate,
                format=audio_format
            )
            
            request_id = result.get_response().get('request_id', '未知')
            safe_print(f'请求ID: {request_id}', self.verbose)
            
            if result.get_audio_data() is not None:
                with open(output_file, 'wb') as f:
                    f.write(result.get_audio_data())
                safe_print(f'语音合成成功，已保存到: {output_file}', True)
                return output_file
            else:
                error = result.get_response().get('message', '未知错误')
                safe_print(f'语音合成失败: {error}', True)
                return None
        except Exception as e:
            safe_print(f"语音合成过程出错: {e}", True)
            return None
    
    def read_text_file(self, file_path):
        """从文件中读取文本"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            safe_print(f"读取文件失败: {e}", self.verbose)
            return None
    
    def process_directory(self):
        """处理目录中的所有文本文件"""
        directory = self.config.get('tts_directory', '')
        if not directory:
            safe_print("未指定要处理的目录", self.verbose)
            return False
        
        if not os.path.exists(directory):
            safe_print(f"目录不存在: {directory}", self.verbose)
            return False
        
        # 获取目录中所有.txt文件
        text_files = glob.glob(os.path.join(directory, "*.txt"))
        if not text_files:
            safe_print(f"目录中没有找到.txt文件: {directory}", self.verbose)
            return False
        
        success_count = 0
        for file_path in text_files:
            safe_print(f"\n处理文件: {file_path}", self.verbose)
            text = self.read_text_file(file_path)
            if text:
                # 使用原文件名作为输出文件名
                base_name = os.path.splitext(os.path.basename(file_path))[0]
                output_file = os.path.join(self.config.get('tts_output_dir'), f"{base_name}.{self.config.get('tts_format', 'mp3')}")
                
                if self.text_to_speech(text, output_file):
                    success_count += 1
        
        safe_print(f"目录处理完成，成功转换 {success_count}/{len(text_files)} 个文件", self.verbose)
        return success_count > 0
    
    def process_single_file(self):
        """处理单个文本文件"""
        input_file = self.config.get('tts_input', '')
        if not input_file:
            safe_print("未指定输入文件", self.verbose)
            return False
        
        if not os.path.exists(input_file):
            safe_print(f"输入文件不存在: {input_file}", self.verbose)
            return False
        
        text = self.read_text_file(input_file)
        if not text:
            safe_print("文件内容为空或读取失败", self.verbose)
            return False
        
        # 使用原文件名作为输出文件名
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(self.config.get('tts_output_dir'), f"{base_name}.{self.config.get('tts_format', 'mp3')}")
        
        return self.text_to_speech(text, output_file) is not None
    
    def run(self):
        """运行TTS转换"""
        # 检查是否有API密钥
        if not dashscope.api_key:
            safe_print("错误: 未设置API密钥，无法进行语音合成", True)
            return False
        
        # 重置统计
        self.total_characters = 0
        self.file_count = 0
        
        # 根据配置选择处理模式
        result = False
        if self.config.get('process_directory', False):
            result = self.process_directory()
        else:
            result = self.process_single_file()
        
        # 显示统计信息
        self._print_statistics()
        
        return result
    
    def _print_statistics(self):
        """打印TTS字符统计和费用估算"""
        safe_print("\n" + "="*50, True)
        safe_print("TTS 字符统计:", True)
        safe_print(f"处理文件数: {self.file_count}", True)
        safe_print(f"总字符数: {self.total_characters}", True)
        
        # 计算费用
        try:
            # 从配置中读取价格设置（元/万字符）
            price_per_10k = self.config.get('tts_price', 1.0)
            
            # 考虑免费额度
            free_chars = 30000  # 每月免费3万字符
            charged_chars = max(0, self.total_characters - free_chars)
            
            # 计算假设性收费（如果全部计费）
            full_cost = self.total_characters * (price_per_10k / 10000)
            
            if charged_chars > 0:
                # 计算实际费用
                total_cost = charged_chars * (price_per_10k / 10000)
                safe_print(f"免费额度: 30,000字符/月", True)
                safe_print(f"超出免费额度: {charged_chars}字符", True)
                safe_print(f"估算费用: ¥{total_cost:.2f} (按¥{price_per_10k}/万字符计算)", True)
                safe_print(f"注意: 每月前3万字符免费，超出部分按¥{price_per_10k}/万字符计费", True)
            else:
                safe_print(f"本次使用字符数: {self.total_characters}，在免费额度(30,000字符/月)内", True)
                safe_print(f"若不考虑免费额度，全部计费金额为: ¥{full_cost:.2f} (按¥{price_per_10k}/万字符计算)", True)
                safe_print("注意: 免费额度统计以服务提供商的月度结算为准", True)
        except Exception as e:
            safe_print(f"无法估算费用: {e}", True)
        
        safe_print("="*50, True)

def main():
    """主程序入口"""
    try:
        # 初始化TTS转换器
        converter = TtsConverter()
        
        # 运行转换
        converter.run()
            
    except Exception as e:
        safe_print(f"程序运行出错: {e}", True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()