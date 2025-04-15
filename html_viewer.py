"""
交互式文献浏览器生成工具 - 命令行入口
"""
import argparse
import sys

try:
    from error_handler import safe_print, ErrorTracker
except ImportError:
    def safe_print(msg, verbose=True):
        if verbose:
            print(msg)

from html_viewer_core import HTMLViewerGenerator

def main():
    parser = argparse.ArgumentParser(description="交互式HTML文献浏览器生成工具")
    parser.add_argument("-c", "--config", default="pub2.txt", help="配置文件路径")
    parser.add_argument("-v", "--verbose", action="store_true", help="输出详细日志")
    parser.add_argument("-i", "--input", help="输入CSV文件路径")
    parser.add_argument("-o", "--output", help="输出HTML文件路径")
    args = parser.parse_args()

    try:
        generator = HTMLViewerGenerator(config_file=args.config, verbose=args.verbose)
        if args.input:
            generator.config['input_html'] = args.input
        if args.output:
            generator.config['output_html'] = args.output
        result = generator.process()
        if result:
            safe_print(f"HTML文献浏览器已生成: {generator.config['output_html']}", True)
            # # 检查是否需要自动打开HTML文件 (注释掉)
            # try:
            #     html_auto_open = False
            #     with open(generator.config_file, 'r', encoding='utf-8') as f:
            #         for line in f:
            #             if line.strip().startswith('html_auto_open='):
            #                 value = line.strip().split('=', 1)[1].strip()
            #                 html_auto_open = value.lower() in ['yes', 'true', 'y', '1']
            #                 break
            #     if html_auto_open:
            #         safe_print("自动打开HTML文件...", True)
            #         import webbrowser
            #         webbrowser.open('file://' + generator.config['output_html'])
            # except Exception as e:
            #     safe_print(f"打开HTML文件失败: {e}", args.verbose)
            return 0
        else:
            safe_print("HTML文献浏览器生成失败", True)
            return 1
    except Exception as e:
        safe_print(f"处理错误: {e}", True)
        try:
            from error_handler import ErrorTracker
            ErrorTracker().track_error(
                "ViewerGenerationError",
                f"生成HTML浏览器时发生错误: {str(e)}",
                source="main"
            )
            ErrorTracker().generate_report(save_to_file=True)
        except ImportError:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())
