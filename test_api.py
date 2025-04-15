"""
API连接测试脚本
用于测试通义千问API连接是否正常
"""
import os
import sys
import time
import argparse
from error_handler import safe_print, ErrorTracker
from llm_translator import LLMTranslator

def load_config(config_file="pub.txt"):
    """从配置文件加载设置"""
    # 默认最小配置
    config = {
        'api_key': '',
        'api_base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'ai_model': 'qwen-turbo',
        'ai_timeout': 30,
        'verbose': True
    }
    
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
                            
                            # 只读取我们需要的配置项
                            if key in ['api_key', 'api_base_url', 'ai_model', 'ai_timeout']:
                                config[key] = value
    except Exception as e:
        safe_print(f"读取配置文件失败: {e}", True)
    
    return config

def test_api(config):
    """测试API连接"""
    safe_print("开始测试API连接...", True)
    
    translator = LLMTranslator(config)
    
    if not translator.client:
        safe_print("错误: AI客户端初始化失败", True)
        return False
    
    try:
        # 简单的测试翻译
        test_text = "Hello, this is a test message."
        safe_print(f"测试文本: {test_text}", True)
        
        start_time = time.time()
        result = translator.translate_text(test_text, "测试")
        elapsed = time.time() - start_time
        
        safe_print(f"翻译结果: {result}", True)
        safe_print(f"API响应时间: {elapsed:.2f}秒", True)
        
        # 获取token使用统计
        stats = translator.get_statistics()
        safe_print(f"输入tokens: {stats['input_tokens']}", True)
        safe_print(f"输出tokens: {stats['output_tokens']}", True)
        
        safe_print("API连接测试成功!", True)
        return True
    except Exception as e:
        safe_print(f"API测试失败: {e}", True)
        ErrorTracker().track_error(
            "APITestError", 
            f"API测试失败: {str(e)}",
            source="test_api"
        )
        return False

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="通义千问API连接测试工具")
    parser.add_argument("-c", "--config", default="pub.txt", help="配置文件路径")
    
    args = parser.parse_args()
    
    config = load_config(args.config)
    
    if not config['api_key']:
        safe_print("错误: 未设置API密钥", True)
        safe_print("请在配置文件中设置api_key或设置DASHSCOPE_API_KEY环境变量", True)
        return 1
    
    result = test_api(config)
    return 0 if result else 1

if __name__ == "__main__":
    sys.exit(main())
