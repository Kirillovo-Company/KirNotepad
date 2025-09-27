from tkinter import *
from tkinter import filedialog, messagebox
import re
import os
import json

# Конфигурация
config_path = 'config.json'
current_file = None
saved = True
previous_text = ''

# Загрузка конфигурации
def load_config():
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        default_config = {
            "colors": {
                "normal": [234, 234, 234],
                "keywords": [234, 95, 95],
                "comments": [95, 234, 165],
                "string": [234, 162, 95],
                "function": [95, 211, 234],
                "background": [42, 42, 42]
            },
            "font": "Consolas 15"
        }
        save_config(default_config)
        return default_config

def save_config(config=None):
    if config is None:
        config = load_config()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def get_color(name):
    config = load_config()
    rgb_tuple = tuple(config['colors'][name])
    return "#%02x%02x%02x" % rgb_tuple

def get_font():
    config = load_config()
    return config['font']

# Проверка, нужно ли подсвечивать синтаксис для текущего файла
def should_highlight_syntax():
    global current_file
    if not current_file:
        return False
    
    # Расширения файлов, для которых включаем подсветку
    highlight_extensions = ['.py', '.html', '.htm', '.css', '.js', '.java', '.cpp', '.c', '.php', '.rb', '.json', '.xml']
    
    # Получаем расширение файла
    _, ext = os.path.splitext(current_file)
    return ext.lower() in highlight_extensions

# Обновление заголовка окна
def update_title():
    global current_file, saved
    filename = current_file if current_file else "Безымянный"
    status = "" if saved else "*"
    root.title(f"{filename}{status} - KirNotepad 1.3")

# Подтверждение несохраненных изменений
def confirm_unsaved():
    global saved
    if saved:
        return True
    result = messagebox.askyesnocancel(
        "Несохраненные изменения",
        "Сохранить изменения перед продолжением?"
    )
    if result is None:  # Cancel
        return False
    if result:  # Yes
        save_file()
    return True

# Новый файл
def new_file(event=None):
    global current_file, saved
    if not confirm_unsaved():
        return
    edit_area.delete('1.0', END)
    current_file = None
    saved = True
    update_title()
    changes()  # Обновляем подсветку

# Открытие файла
def open_file(event=None):
    global current_file, saved
    if not confirm_unsaved():
        return
        
    file_path = filedialog.askopenfilename(
        filetypes=[("Текстовые файлы", "*.txt"), ("Python файлы", "*.py"), ("HTML файлы", "*.html"), ("Все файлы", "*.*")]
    )
    if file_path:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        edit_area.delete('1.0', END)
        edit_area.insert('1.0', content)
        current_file = os.path.basename(file_path)
        saved = True
        update_title()
        changes()  # Обновляем подсветку

# Сохранение файла
def save_file(event=None):
    global current_file, saved
    if current_file:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Python файлы", "*.py"), ("HTML файлы", "*.html"), ("Все файлы", "*.*")],
            initialfile=current_file
        )
    else:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Python файлы", "*.py"), ("HTML файлы", "*.html"), ("Все файлы", "*.*")]
        )
    
    if file_path:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(edit_area.get('1.0', END))
        current_file = os.path.basename(file_path)
        saved = True
        update_title()
        changes()  # Обновляем подсветку

# Поиск совпадений для подсветки синтаксиса
def search_re(pattern, text):
    matches = []
    text = text.splitlines()
    for i, line in enumerate(text):
        for match in re.finditer(pattern, line):
            matches.append((f"{i + 1}.{match.start()}", f"{i + 1}.{match.end()}"))
    return matches

# Правила подсветки для Python
python_rules = [
    ['(^| )(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)($| )', 'keywords'],
    ['".*?"', 'string'],
    ['\'.*?\'', 'string'],
    ['#.*?$', 'comments'],
]

# Правила подсветки для HTML
html_rules = [
    ['&[^;]+;', 'string'],  # HTML entities
    ['<[^>]+>', 'keywords'],  # HTML tags
    ['".*?"', 'string'],  # Атрибуты в двойных кавычках
    ['\'.*?\'', 'string'],  # Атрибуты в одинарных кавычках
    ['<!--.*?-->', 'comments'],  # HTML комментарии
]

# Правила подсветки для CSS
css_rules = [
    ['[{}]', 'keywords'],  # Скобки
    ['[:;]', 'function'],  # Разделители
    ['\.[a-zA-Z][a-zA-Z0-9_-]*', 'function'],  # CSS классы
    ['#[a-fA-F0-9]{3,6}', 'string'],  # HEX цвета
    ['//.*?$', 'comments'],  # Комментарии
    ['/\*.*?\*/', 'comments'],  # Многострочные комментарии
]

# Получение правил подсветки для текущего файла
def get_highlight_rules():
    global current_file
    if not current_file:
        return []
    
    _, ext = os.path.splitext(current_file)
    ext = ext.lower()
    
    config = load_config()
    colors = {name: get_color(name) for name in ['normal', 'keywords', 'comments', 'string', 'function', 'background']}
    
    if ext == '.py':
        return [(pattern, colors[color_name]) for pattern, color_name in python_rules]
    elif ext in ['.html', '.htm']:
        return [(pattern, colors[color_name]) for pattern, color_name in html_rules]
    elif ext == '.css':
        return [(pattern, colors[color_name]) for pattern, color_name in css_rules]
    elif ext in ['.js', '.java', '.cpp', '.c', '.php', '.rb']:
        # Базовые правила для C-подобных языков
        return [
            ['(^| )(function|var|let|const|if|else|for|while|return|class|import|export)($| )', colors['keywords']],
            ['".*?"', colors['string']],
            ['\'.*?\'', colors['string']],
            ['//.*?$', colors['comments']],
            ['/\*.*?\*/', colors['comments']],
        ]
    else:
        return []  # Нет подсветки для других файлов

# Обновление подсветки синтаксиса
def changes(event=None):
    global previous_text, saved

    if edit_area.get('1.0', END) == previous_text:
        return

    # Удаляем старые теги
    for tag in edit_area.tag_names():
        edit_area.tag_remove(tag, "1.0", "end")

    # Применяем подсветку только если нужно
    if should_highlight_syntax():
        rules = get_highlight_rules()
        i = 0
        for pattern, color in rules:
            for start, end in search_re(pattern, edit_area.get('1.0', END)):
                edit_area.tag_add(f'{i}', start, end)
                edit_area.tag_config(f'{i}', foreground=color)
                i += 1

    previous_text = edit_area.get('1.0', END)
    saved = False
    update_title()

# Обработка горячих клавиш
def handle_hotkeys(e):
    # Ctrl+C, Ctrl+V, Ctrl+X
    if e.state == 4 and e.keysym in ['c', 'v', 'x']:
        return  # Разрешаем стандартное поведение
    elif e.keycode == 86 and e.keysym != 'v':  # Ctrl+V
        edit_area.event_generate("<<Paste>>")
    elif e.keycode == 67 and e.keysym != 'c':  # Ctrl+C
        edit_area.event_generate("<<Copy>>")
    elif e.keycode == 88 and e.keysym != 'x':  # Ctrl+X
        edit_area.event_generate("<<Cut>>")

# Меню "О программе"
def about_program(event=None):
    about_text = "KirNotepad 1.3\nПростой кроссплатформенный текстовый редактор с подсветкой синтаксиса"
    messagebox.showinfo("О программе", about_text)

# Создание главного окна
def create_window():
    global root, edit_area
    
    root = Tk()
    root.geometry('700x500')
    update_title()
    
    # Загрузка конфигурации
    config = load_config()
    colors = {name: get_color(name) for name in ['normal', 'keywords', 'comments', 'string', 'function', 'background']}
    font = get_font()
    
    # Создание текстовой области
    edit_area = Text(
        root, 
        background=colors['background'], 
        foreground=colors['normal'], 
        insertbackground=colors['normal'], 
        relief=FLAT, 
        borderwidth=30, 
        font=font
    )
    edit_area.pack(fill=BOTH, expand=1)
    
    # Привязка событий
    edit_area.bind('<KeyRelease>', changes)
    root.bind("<Control-KeyPress>", handle_hotkeys)
    root.bind('<Control-s>', save_file)
    root.bind('<Control-o>', open_file)
    root.bind('<Control-n>', new_file)
    root.bind('<Control-q>', about_program)
    
    # Первоначальная подсветка
    changes()

# Запуск приложения
if __name__ == "__main__":
    create_window()
    root.mainloop()
