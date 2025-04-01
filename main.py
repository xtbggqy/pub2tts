"""
PubMed文献处理主程序
一站式完成从文献检索到语音合成的全流程处理
"""
import os
import sys
import time
import argparse
from datetime import datetime
import threading

# 导入各模块
try:
    from pub_search import PubMedFetcher
    from journal_enhancement import JournalEnhancer
    from llm_understand import LiteratureTranslator
    from ali2tts_ai import TtsConverter
except ImportError as e:
    print(f"导入模块失败: {e}")
    print("请确保所有必要的程序文件在同一目录下")
    sys.exit(1)

# 全局变量控制日志输出级别
VERBOSE_OUTPUT = False

def safe_print(msg, always_print=False):
    """安全打印，处理编码问题
    
    Args:
        msg: 要打印的消息
        always_print: 是否始终打印此消息，无视全局verbose设置
    """
    # 如果不是详细模式，且不是必须打印的消息，则跳过
    if not VERBOSE_OUTPUT and not always_print:
        # 以下类型的消息总是打印
        if not any([
            msg.startswith("==="),                # 步骤标题
            "步骤" in msg and "完成" in msg,       # 步骤完成消息
            "失败" in msg,                         # 失败消息
            "错误" in msg,                         # 错误消息
            "警告" in msg,                         # 警告消息
            "成功" in msg and "保存" in msg,       # 成功保存消息
            "Token 使用统计" in msg,               # Token统计
            "未找到" in msg and "终止" in msg       # 终止消息
        ]):
            return

    try:
        # 暂时清除进度条
        ProgressDisplay.clear_progress()
        
        print(msg)
        sys.stdout.flush()
        
        # 重新显示进度条
        ProgressDisplay.show_progress()
    except:
        print(str(msg).encode('utf-8', 'ignore').decode('utf-8', 'ignore'))
        sys.stdout.flush()
        ProgressDisplay.show_progress()

class ProgressDisplay:
    """进度显示管理器，固定在终端底部"""
    current_step = 0
    total_steps = 4
    step_names = ["文献检索", "期刊信息增强", "文献翻译与理解", "文本转语音"]
    start_time = None
    active = False
    lock = threading.Lock()
    animation_thread = None
    running = False
    step_status = ["待处理", "待处理", "待处理", "待处理"]
    last_update = 0  # 上次更新时间
    
    @classmethod
    def start(cls):
        """开始进度显示"""
        cls.active = True
        cls.start_time = datetime.now()
        cls.running = True
        cls.animation_thread = threading.Thread(target=cls.animation_loop)
        cls.animation_thread.daemon = True
        cls.animation_thread.start()
    
    @classmethod
    def update_step(cls, step, status="进行中"):
        """更新当前步骤"""
        with cls.lock:
            cls.current_step = step
            cls.step_status[step-1] = status
    
    @classmethod
    def animation_loop(cls):
        """进度条动画循环"""
        spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        idx = 0
        
        while cls.running:
            if cls.active:
                cls.show_progress(spinner[idx])
                idx = (idx + 1) % len(spinner)
            time.sleep(0.2)  # 降低刷新频率
    
    @classmethod
    def show_progress(cls, spinner_char="⠋"):
        """显示进度条"""
        if not cls.active:
            return
        
        # 降低更新频率，减少屏幕刷新
        current_time = time.time()
        if current_time - cls.last_update < 0.5 and cls.last_update > 0:  # 最少0.5秒更新一次
            return
        cls.last_update = current_time
        
        # 获取终端大小
        try:
            term_size = os.get_terminal_size()
            width = term_size.columns
        except:
            width = 80
        
        # 计算耗时
        elapsed = datetime.now() - cls.start_time if cls.start_time else datetime.timedelta(0)
        hours, remainder = divmod(elapsed.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        elapsed_str = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
        
        # 创建更简洁的进度信息
        progress_info = f"{spinner_char} 进度:[{cls.current_step}/{cls.total_steps}] {elapsed_str} | "
        
        # 只显示当前正在进行的步骤，省略其他步骤
        current_step_info = f"{cls.step_names[cls.current_step-1]}[{cls.step_status[cls.current_step-1]}]"
        progress_info += current_step_info
        
        # 裁剪到终端宽度
        if len(progress_info) > width:
            progress_info = progress_info[:width-3] + "..."
        
        # 保存光标位置，移动到最后一行
        sys.stdout.write("\033[s")  # 保存当前光标位置
        sys.stdout.write(f"\033[{term_size.lines};0H")  # 移动到最后一行
        sys.stdout.write("\033[K")  # 清除该行
        
        # 绘制进度条
        sys.stdout.write(progress_info)
        
        # 恢复光标位置
        sys.stdout.write("\033[u")
        sys.stdout.flush()
    
    @classmethod
    def clear_progress(cls):
        """临时清除进度条"""
        if not cls.active:
            return
        
        try:
            term_size = os.get_terminal_size()
            # 保存位置，移到底部，清除行，恢复位置
            sys.stdout.write("\033[s")
            sys.stdout.write(f"\033[{term_size.lines};0H")
            sys.stdout.write("\033[K")
            sys.stdout.write("\033[u")
            sys.stdout.flush()
        except:
            pass
    
    @classmethod
    def stop(cls):
        """停止进度显示"""
        cls.running = False
        cls.active = False
        if cls.animation_thread:
            cls.animation_thread.join(timeout=1)
        
        # 清除进度条
        cls.clear_progress()

class PubMedProcessor:
    def __init__(self, config_file="pub.txt"):
        """初始化文献处理器"""
        self.config_file = config_file
        self.start_time = datetime.now()
        ProgressDisplay.start()
        safe_print(f"=== 文献处理流程开始 [{self.start_time.strftime('%Y-%m-%d %H:%M:%S')}] ===", True)
    
    def run_full_process(self):
        """运行完整的文献处理流程"""
        try:
            # 步骤 1: 文献检索
            ProgressDisplay.update_step(1)
            if not self._run_pub_search():
                ProgressDisplay.step_status[0] = "失败"
                return False
            ProgressDisplay.step_status[0] = "完成"
            
            # 步骤 2: 期刊信息增强
            ProgressDisplay.update_step(2)
            if not self._run_journal_enhancement():
                ProgressDisplay.step_status[1] = "失败"
                return False
            ProgressDisplay.step_status[1] = "完成"
            
            # 步骤 3: 文献翻译与理解
            ProgressDisplay.update_step(3)
            if not self._run_llm_understand():
                ProgressDisplay.step_status[2] = "失败"
                return False
            ProgressDisplay.step_status[2] = "完成"
            
            # 步骤 4: 文本转语音
            ProgressDisplay.update_step(4)
            if not self._run_tts_conversion():
                ProgressDisplay.step_status[3] = "失败"
                return False
            ProgressDisplay.step_status[3] = "完成"
            
            # 完成所有流程
            self._print_summary()
            return True
        finally:
            ProgressDisplay.stop()
    
    def _run_pub_search(self):
        """运行文献检索"""
        safe_print("\n=== 步骤 1: 文献检索 ===", True)
        try:
            # 初始化PubMed检索工具
            fetcher = PubMedFetcher("default@example.com", self.config_file, verbose=VERBOSE_OUTPUT)
            
            # 获取文献
            publications = fetcher.fetch_publications()
            
            if publications:
                # 导出到CSV
                fetcher.export_to_csv(publications)
                safe_print("文献检索完成", True)
                return True
            else:
                safe_print("未找到符合条件的文献，流程终止", True)
                return False
                
        except Exception as e:
            safe_print(f"文献检索失败: {e}", True)
            if VERBOSE_OUTPUT:
                import traceback
                traceback.print_exc()
            return False
    
    def _run_journal_enhancement(self):
        """运行期刊信息增强"""
        safe_print("\n=== 步骤 2: 期刊信息增强 ===", True)
        try:
            # 初始化期刊增强工具
            enhancer = JournalEnhancer(self.config_file, verbose=VERBOSE_OUTPUT)
            
            # 增强文章信息
            enhanced_articles = enhancer.enhance_articles()
            
            if enhanced_articles:
                # 导出增强后的文章
                enhancer.export_to_csv(enhanced_articles)
                safe_print("期刊信息增强完成", True)
                return True
            else:
                safe_print("没有可增强的文章，继续执行下一步骤", True)
                return True  # 允许流程继续
            
        except Exception as e:
            safe_print(f"期刊信息增强失败: {e}", True)
            if VERBOSE_OUTPUT:
                import traceback
                traceback.print_exc()
            return False
    
    def _run_llm_understand(self):
        """运行文献翻译与理解"""
        safe_print("\n=== 步骤 3: 文献翻译与理解 ===", True)
        try:
            # 初始化文献翻译工具
            translator = LiteratureTranslator(self.config_file, verbose=VERBOSE_OUTPUT)
            
            # 翻译并增强文献
            if translator.translate_and_enhance():
                safe_print("文献翻译与理解完成", True)
                return True
            else:
                safe_print("文献翻译失败，但允许流程继续", True)
                return True  # 允许流程继续
            
        except Exception as e:
            safe_print(f"文献翻译失败: {e}", True)
            if VERBOSE_OUTPUT:
                import traceback
                traceback.print_exc()
            return False
    
    def _run_tts_conversion(self):
        """运行文本转语音"""
        safe_print("\n=== 步骤 4: 文本转语音 ===", True)
        try:
            # 初始化TTS转换器
            converter = TtsConverter(self.config_file, verbose=VERBOSE_OUTPUT)
            
            # 运行转换
            if converter.run():
                safe_print("文本转语音完成", True)
                return True
            else:
                safe_print("语音合成失败，流程完成", True)
                return True  # 流程完成
            
        except Exception as e:
            safe_print(f"文本转语音失败: {e}", True)
            if VERBOSE_OUTPUT:
                import traceback
                traceback.print_exc()
            return False
    
    def _print_summary(self):
        """打印处理总结"""
        end_time = datetime.now()
        duration = end_time - self.start_time
        minutes, seconds = divmod(duration.total_seconds(), 60)
        
        safe_print("\n" + "="*50, True)
        safe_print(f"文献处理流程完成", True)
        safe_print(f"开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}", True)
        safe_print(f"结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", True)
        safe_print(f"总耗时: {int(minutes)}分钟 {int(seconds)}秒", True)
        safe_print("="*50, True)
    
    def run_single_step(self, step):
        """运行单个步骤"""
        try:
            ProgressDisplay.start()
            
            steps = {
                'search': (self._run_pub_search, 1),
                'enhance': (self._run_journal_enhancement, 2),
                'translate': (self._run_llm_understand, 3),
                'tts': (self._run_tts_conversion, 4)
            }
            
            if step not in steps:
                safe_print(f"未知的步骤: {step}", True)
                safe_print(f"可用步骤: {', '.join(steps.keys())}", True)
                return False
            
            # 更新当前步骤
            func, step_idx = steps[step]
            ProgressDisplay.update_step(step_idx)
            
            # 执行对应函数
            result = func()
            
            # 更新状态
            if result:
                ProgressDisplay.step_status[step_idx-1] = "完成"
            else:
                ProgressDisplay.step_status[step_idx-1] = "失败"
                
            return result
        finally:
            ProgressDisplay.stop()

def main():
    """主程序入口"""
    # 添加对Windows终端的特殊处理
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except:
            safe_print("警告: 无法启用Windows终端的ANSI支持，进度条显示可能异常", True)
    
    parser = argparse.ArgumentParser(description='PubMed文献处理全流程工具')
    parser.add_argument('-s', '--step', choices=['search', 'enhance', 'translate', 'tts'], 
                        help='仅执行特定步骤')
    parser.add_argument('-c', '--config', default='pub.txt', 
                        help='配置文件路径(默认: pub.txt)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='输出详细日志信息')
    args = parser.parse_args()
    
    # 设置全局日志输出级别
    global VERBOSE_OUTPUT
    VERBOSE_OUTPUT = args.verbose
    
    # 创建out目录(如果不存在)
    os.makedirs("out", exist_ok=True)
    
    try:
        processor = PubMedProcessor(args.config)
        
        if args.step:
            safe_print(f"仅执行步骤: {args.step}", True)
            processor.run_single_step(args.step)
        else:
            processor.run_full_process()
            
    except Exception as e:
        ProgressDisplay.stop()  # 确保停止进度显示
        safe_print(f"程序运行出错: {e}", True)
        if VERBOSE_OUTPUT:
            import traceback
            traceback.print_exc()
    finally:
        # 确保结束时进度条被清除
        ProgressDisplay.stop()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        ProgressDisplay.stop()
        safe_print("\n程序被用户中断", True)
        sys.exit(1)
