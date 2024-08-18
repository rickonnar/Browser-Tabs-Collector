import subprocess
import threading
import os
import logging
import tkinter as tk
from tkinter import messagebox, scrolledtext
import configparser
import argparse
import socket
import time
from urllib.error import URLError

# 配置和语言字典
config = configparser.ConfigParser()
config.read('config.ini')

LANGUAGES = {
    'en': {
        'title': 'Browser Tabs Collector',
        'start_button': 'Start Collection',
        'select_browser': 'Select Browsers',
        'select_language': 'Select Language',
        'enable_logging': 'Enable Logging',
        'about': 'About',
        'about_info': 'Program source: github.com/rickonnar/Browser-Tabs-Collector',
        'saved_message': 'Saved {browser} tabs to {filename}',
        'no_tabs_message': 'No tabs collected for {browser}',
        'all_saved_message': 'All browser tabs collected and saved to all_browsers_tabs.txt',
        'warning': 'Warning',
        'warning_message': 'Please select at least one browser!',
        'network_error': 'Network error: Unable to connect.',
        'file_error': 'File operation error: {error}',
        'script_error': 'AppleScript execution error: {error}',
        'unknown_error': 'An unknown error occurred: {error}',
        'retry_prompt': 'Network error, retrying... ({retry_count}/{max_retries})'
    },
    'zh': {
        'title': 'Browser Tabs Collector',  # 保持标题不变
        'start_button': '开始收集',
        'select_browser': '选择浏览器',
        'select_language': '选择语言',
        'enable_logging': '启用日志记录',
        'about': '关于',
        'about_info': '程序出处：github.com/rickonnar/Browser-Tabs-Collector',
        'saved_message': '已保存 {browser} 的标签页到 {filename}',
        'no_tabs_message': '{browser} 无标签页被收集',
        'all_saved_message': '所有浏览器的标签页已收集并保存到 all_browsers_tabs.txt',
        'warning': '警告',
        'warning_message': '请至少选择一个浏览器！',
        'network_error': '网络错误：无法连接。',
        'file_error': '文件操作错误：{error}',
        'script_error': 'AppleScript 执行错误：{error}',
        'unknown_error': '发生未知错误：{error}',
        'retry_prompt': '网络错误，正在重试...（{retry_count}/{max_retries}）'
    }
}

def setup_logging(log_level):
    logging.basicConfig(level=log_level,
                        format='%(asctime)s - %(levelname)s - %(message)s')

def handle_exceptions(exception_type, max_retries, delay):
    def decorator(func):
        def wrapper(*args, **kwargs):
            lang = LANGUAGES[kwargs.get('language', 'en')]
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exception_type as e:
                    if attempt < max_retries - 1:
                        print(lang['retry_prompt'].format(retry_count=attempt + 1, max_retries=max_retries))
                        time.sleep(delay)
                    else:
                        logging.error(str(e))
                        raise e
                except Exception as e:
                    logging.error(lang['unknown_error'].format(error=str(e)))
                    raise e
        return wrapper
    return decorator

def check_network_connection():
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=5)
        return True
    except OSError:
        return False

@handle_exceptions(URLError, int(config['DEFAULT'].get('network_max_retries', 3)), int(config['DEFAULT'].get('network_retry_delay', 2)))
def get_tabs(browser_name, language):
    lang = LANGUAGES[language]
    if not check_network_connection():
        raise URLError(lang['network_error'])

    scripts = {
        'Safari': '''
            tell application "Safari"
                set tabList to ""
                repeat with win in windows
                    repeat with t in tabs of win
                        set tabList to tabList & (URL of t) & linefeed
                    end repeat
                end repeat
                return tabList
            end tell
        ''',
        'Google Chrome': '''
            tell application "Google Chrome"
                set tabList to ""
                repeat with win in windows
                    repeat with t in tabs of win
                        set tabList to tabList & (URL of t) & linefeed
                    end repeat
                end repeat
                return tabList
            end tell
        ''',
        'Firefox': '''
            tell application "Firefox"
                activate
                set tabList to ""
                tell application "System Events"
                    keystroke "l" using command down
                    keystroke "c" using command down
                    set tabURL to the clipboard
                    set tabList to tabList & tabURL & linefeed
                end tell
                return tabList
            end tell
        ''',
        'Microsoft Edge': '''
            tell application "Microsoft Edge"
                set tabList to ""
                repeat with win in windows
                    repeat with t in tabs of win
                        set tabList to tabList & (URL of t) & linefeed
                    end repeat
                end repeat
                return tabList
            end tell
        '''
    }

    if browser_name not in scripts:
        return f"Unsupported browser: {browser_name}"

    result = subprocess.check_output(['osascript', '-e', scripts[browser_name]])
    return result.decode('utf-8').strip().splitlines()

@handle_exceptions(OSError, int(config['DEFAULT'].get('file_max_retries', 1)), int(config['DEFAULT'].get('file_retry_delay', 1)))
def collect_tabs(browser_name, output_area, language, logging_enabled):
    tabs = get_tabs(browser_name, language)
    lang = LANGUAGES[language]
    if tabs:
        filename = f'{browser_name}_tabs.txt'
        with open(filename, 'w') as f:
            f.writelines(f"{tab}\n" for tab in tabs)
        if logging_enabled:
            logging.info(lang['saved_message'].format(browser=browser_name, filename=filename))
        output_area.insert(tk.END, lang['saved_message'].format(browser=browser_name, filename=filename) + '\n')
    else:
        if logging_enabled:
            logging.warning(lang['no_tabs_message'].format(browser=browser_name))
        output_area.insert(tk.END, lang['no_tabs_message'].format(browser=browser_name) + '\n')

def start_collection(selected_browsers, output_area, language, logging_enabled):
    output_area.delete(1.0, tk.END)
    threads = [
        threading.Thread(target=collect_tabs, args=(browser, output_area, language, logging_enabled))
        for browser in selected_browsers
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lang = LANGUAGES[language]
    try:
        with open('all_browsers_tabs.txt', 'w') as outfile:
            for browser in selected_browsers:
                filename = f'{browser}_tabs.txt'
                if os.path.exists(filename):
                    with open(filename, 'r') as infile:
                        outfile.write(f"Tabs from {browser}:\n")
                        outfile.write(infile.read())
                        outfile.write("\n\n")
        output_area.insert(tk.END, lang['all_saved_message'] + '\n')
        if logging_enabled:
            logging.info(lang['all_saved_message'])
    except OSError as e:
        logging.error(lang['file_error'].format(error=str(e)))
        output_area.insert(tk.END, lang['file_error'].format(error=str(e)) + '\n')

def on_start_button_click(selected_browsers, output_area, language, logging_enabled):
    lang = LANGUAGES[language]
    if not selected_browsers:
        messagebox.showwarning(lang['warning'], lang['warning_message'])
    else:
        if not logging_enabled:
            logging.disable(logging.CRITICAL)
        threading.Thread(target=start_collection, args=(selected_browsers, output_area, language, logging_enabled)).start()

def show_about(language):
    lang = LANGUAGES[language]
    about_window = tk.Toplevel()
    about_window.title(LANGUAGES[language]['about'])
    tk.Label(about_window, text=lang['about_info'], padx=20, pady=20).pack()
    tk.Button(about_window, text="OK", command=about_window.destroy).pack(pady=10)

def main():
    root = tk.Tk()
    selected_language = tk.StringVar(value='en')
    logging_enabled = tk.BooleanVar(value=True)

    def update_language():
        lang = LANGUAGES[selected_language.get()]
        # 保持标题不变
        start_button.config(text=lang['start_button'])
        select_browser_label.config(text=lang['select_browser'])
        select_language_label.config(text=lang['select_language'])
        logging_checkbox.config(text=lang['enable_logging'])
        about_button.config(text=lang['about'])

    root.title(LANGUAGES['en']['title'])  # 固定标题
    selected_browsers = []
    browsers = ['Safari', 'Google Chrome', 'Firefox', 'Microsoft Edge']

    select_browser_label = tk.Label(root, text=LANGUAGES['en']['select_browser'])
    select_browser_label.pack(anchor='w')
    
    for browser in browsers:
        var = tk.BooleanVar()
        checkbox = tk.Checkbutton(root, text=browser, variable=var)
        checkbox.pack(anchor='w')
        selected_browsers.append((var, browser))
    
    select_language_label = tk.Label(root, text=LANGUAGES['en']['select_language'])
    select_language_label.pack(anchor='w', pady=(20, 0))
    
    lang_frame = tk.Frame(root)
    lang_frame.pack(anchor='w')
    
    en_radio = tk.Radiobutton(lang_frame, text="English", variable=selected_language, value='en', command=update_language)
    zh_radio = tk.Radiobutton(lang_frame, text="中文", variable=selected_language, value='zh', command=update_language)
    en_radio.pack(side=tk.LEFT)
    zh_radio.pack(side=tk.LEFT)

    logging_checkbox = tk.Checkbutton(root, text=LANGUAGES['en']['enable_logging'], variable=logging_enabled)
    logging_checkbox.pack(anchor='w', pady=(10, 0))

    output_area = scrolledtext.ScrolledText(root, width=50, height=15, wrap=tk.WORD)
    output_area.pack(pady=10)
    
    start_button = tk.Button(root, text=LANGUAGES['en']['start_button'], command=lambda: on_start_button_click(
        [browser for var, browser in selected_browsers if var.get()], output_area, selected_language.get(), logging_enabled.get()))
    start_button.pack(pady=10)

    about_button = tk.Button(root, text=LANGUAGES['en']['about'], command=lambda: show_about(selected_language.get()))
    about_button.pack(pady=10)

    root.mainloop()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Browser Tabs Collector')
    parser.add_argument('--log-level', help='Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)', default='INFO')
    parser.add_argument('--config', help='Specify the path to the configuration file', default='config.ini')
    args = parser.parse_args()

    if args.config:
        config.read(args.config)

    setup_logging(getattr(logging, args.log_level.upper(), logging.INFO))
    main()
