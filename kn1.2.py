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

# Обновление заголовка окна
def update_title():
    global current_file, saved
    filename = current_file if current_file else "Безымянный"
    status = "" if saved else "*"
    root.title(f"{filename}{status} - KirNotepad 1.2")

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

# Открытие файла
def open_file(event=None):
    global current_file, saved
    if not confirm_unsaved():
        return
        
    file_path = filedialog.askopenfilename(
        filetypes=[("Текстовые файлы", "*.txt"), ("Python файлы", "*.py"), ("Все файлы", "*.*")]
    )
    if file_path:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        edit_area.delete('1.0', END)
        edit_area.insert('1.0', content)
        current_file = os.path.basename(file_path)
        saved = True
        update_title()

# Сохранение файла
def save_file(event=None):
    global current_file, saved
    if current_file:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Python файлы", "*.py"), ("Все файлы", "*.*")],
            initialfile=current_file
        )
    else:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Текстовые файлы", "*.txt"), ("Python файлы", "*.py"), ("Все файлы", "*.*")]
        )
    
    if file_path:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(edit_area.get('1.0', END))
        current_file = os.path.basename(file_path)
        saved = True
        update_title()

# Поиск совпадений для подсветки синтаксиса
def search_re(pattern, text):
    matches = []
    text = text.splitlines()
    for i, line in enumerate(text):
        for match in re.finditer(pattern, line):
            matches.append((f"{i + 1}.{match.start()}", f"{i + 1}.{match.end()}"))
    return matches

# Обновление подсветки синтаксиса
def changes(event=None):
    global previous_text, saved

    if edit_area.get('1.0', END) == previous_text:
        return

    # Удаляем старые теги
    for tag in edit_area.tag_names():
        edit_area.tag_remove(tag, "1.0", "end")

    # Применяем новую подсветку
    i = 0
    for pattern, color in repl:
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
    about_text = "KirNotepad 1.2\nПростой кроссплатформенный текстовый редактор с подсветкой синтаксиса"
    messagebox.showinfo("О программе", about_text)

# Создание главного окна
def create_window():
    global root, edit_area, repl
    
    root = Tk()
    root.geometry('700x500')
    update_title()
    
    # Загрузка конфигурации
    config = load_config()
    colors = {name: get_color(name) for name in ['normal', 'keywords', 'comments', 'string', 'function', 'background']}
    font = get_font()
    
    # Правила подсветки синтаксиса
    repl = [
        ['(^| )(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)($| )', colors['keywords']],
        ['".*?"', colors['string']],
        ['\'.*?\'', colors['string']],
        ['#.*?$', colors['comments']],
    ]
    
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
