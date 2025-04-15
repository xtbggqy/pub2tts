"""
翻译缓存模块
提供翻译结果缓存，避免重复翻译
"""
import os
import json
import threading
from utils import safe_print, get_hash, create_directory_if_not_exists

class TranslationCache:
    """翻译结果缓存，避免重复翻译"""
    
    def __init__(self, cache_file="translation_cache.json", max_size=1000):
        """初始化缓存
        
        Args:
            cache_file: 缓存文件路径
            max_size: 最大缓存条目数
        """
        self.cache_file = cache_file
        self.max_size = max_size
        self.cache = {}
        self.lock = threading.RLock()
        self.load_cache()
        
    def load_cache(self):
        """从文件加载缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.cache = json.load(f)
                safe_print(f"已从 {self.cache_file} 加载 {len(self.cache)} 条翻译缓存", False)
        except Exception as e:
            safe_print(f"加载翻译缓存失败: {e}", False)
            self.cache = {}
            
    def save_cache(self):
        """保存缓存到文件"""
        try:
            # 确保缓存文件目录存在
            cache_dir = os.path.dirname(self.cache_file)
            create_directory_if_not_exists(cache_dir)
                
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            safe_print(f"保存翻译缓存失败: {e}", False)
            
    def get(self, key):
        """获取缓存内容
        
        Args:
            key: 缓存键(文本哈希)
            
        Returns:
            缓存的翻译结果或None
        """
        with self.lock:
            return self.cache.get(key)
            
    def set(self, key, value):
        """设置缓存内容
        
        Args:
            key: 缓存键(文本哈希)
            value: 翻译结果
        """
        with self.lock:
            # 如果缓存已满，删除最早的项
            if len(self.cache) >= self.max_size:
                # 创建排序后的键列表，较早添加的在前面
                keys = list(self.cache.keys())
                # 删除前10%的缓存项
                for old_key in keys[:max(1, int(self.max_size * 0.1))]:
                    self.cache.pop(old_key, None)
                    
            self.cache[key] = value
            
    def get_hash(self, text, prefix=""):
        """计算文本的哈希值，用作缓存键
        
        Args:
            text: 要计算哈希的文本
            prefix: 前缀，如"title", "abstract"等
            
        Returns:
            哈希字符串
        """
        return get_hash(text, prefix)
        
    def close(self):
        """关闭缓存，保存数据"""
        self.save_cache()
