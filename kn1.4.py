from tkinter import *
from tkinter import filedialog, messagebox
import os
import re
import json
import importlib.util

#Конфигурация и Глобальные переменные

config_path = 'config.json'
current_file = None
saved = True
previous_text = ''

# Глобальные переменные
root = None
editor_text = None
plugin_menu = None


def load_config():
    """Загружает или создает минимальную конфигурацию."""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cfg = {}

    default_cfg = {
        'colors': {
            'normal': [234, 234, 234],
            'keywords': [234, 95, 95],
            'comments': [95, 234, 165],
            'string': [234, 162, 95],
            'function': [95, 211, 234],
            'background': [42, 42, 42],
        },
        'font': 'Consolas 15',
        'hotkeys': {
            'save': '<Control-s>',
            'open': '<Control-o>',
            'new': '<Control-n>',
            'about': '<Control-q>',
        },
    }

    changed = False

    if 'hotkeys' in cfg and 'toggle_ide' in cfg['hotkeys']:
        del cfg['hotkeys']['toggle_ide']
        changed = True

    for key, value in default_cfg.items():
        if key not in cfg:
            cfg[key] = value
            changed = True
        elif key == 'hotkeys':
            for hk_key, hk_val in default_cfg['hotkeys'].items():
                if hk_key not in cfg['hotkeys']:
                    cfg['hotkeys'][hk_key] = hk_val
                    changed = True

    if changed:
        save_config(cfg)
    return cfg


def save_config(config=None):
    if config is None:
        config = load_config()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_color(name):
    """Безопасный доступ к цвету."""
    cfg = load_config()
    if 'colors' in cfg and name in cfg['colors']:
        r, g, b = cfg['colors'][name]
        return f'#{r:02x}{g:02x}{b:02x}'
    return '#FFFFFF'


def get_colors():
    return {k: get_color(k) for k in load_config()['colors'].keys()}


def get_font():
    return load_config()['font']


#Функции Редактора (I/O, Подсветка, Статус)

def should_highlight_syntax():
    if not current_file: return False
    _, ext = os.path.splitext(current_file)
    return ext.lower() in ['.py', '.html', '.css', '.js', '.c', '.json']


def search_re(pattern, text):
    try:
        rx = re.compile(pattern, re.MULTILINE)
        out = []
        for i, line in enumerate(text.splitlines()):
            if not line: continue
            for m in rx.finditer(line):
                out.append((f'{i + 1}.{m.start()}', f'{i + 1}.{m.end()}'))
        return out
    except re.error:
        return []


#Правила подсветки
python_rules = [
    (r'(^|\b)(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)(\b|$)',
     'keywords'), (r'""".*?"""', 'string'), (r"'''.*?'''", 'string'), (r'".*?"', 'string'), (r"'.*?'", 'string'),
    (r'#.*?$', 'comments'), ]
html_rules = [(r'&[^;]+;', 'string'), (r'<[^>]+>', 'keywords'), (r'".*?"', 'string'), (r"'.*?'", 'string'),
              (r'', 'comments'), ]
css_rules = [(r'[{}]', 'keywords'), (r'[:;]', 'function'), (r'\.[a-zA-Z][a-zA-Z0-9_-]*', 'function'),
             (r'#[a-fA-F0-9]{3,6}', 'string'), (r'//.*?$', 'comments'), (r'/\*.*?\*/', 'comments'), ]


def get_highlight_rules():
    if not current_file: return []
    _, ext = os.path.splitext(current_file)
    ext = ext.lower()
    colors = get_colors()
    if ext == '.py':
        base = python_rules
    elif ext in ['.html', '.htm']:
        base = html_rules
    elif ext == '.css':
        base = css_rules
    elif ext in ['.js', '.java', '.cpp', '.c', '.php', '.rb']:
        base = [(r'(^|\b)(function|var|let|const|if|else|for|while|return|class|import|export)(\b|$)', 'keywords'),
                (r'".*?"', 'string'), (r"'.*?'", 'string'), (r'//.*?$', 'comments'), (r'/\*.*?\*/', 'comments'), ]
    else:
        base = []
    return [(pat, colors[color]) for pat, color in base]


def update_title():
    global current_file, saved
    filename = os.path.basename(current_file) if current_file else 'Новый файл'
    status = '' if saved else '*'
    root.title(f'{filename}{status} - KirNotepad')


def confirm_unsaved():
    global saved
    if saved: return True
    result = messagebox.askyesnocancel('Несохранённые изменения', 'Сохранить изменения перед продолжением?')
    if result is None: return False
    if result: return save_file()
    return True


def new_file(event=None):
    global current_file, saved, previous_text
    if not confirm_unsaved(): return
    editor_text.delete('1.0', END)
    current_file = None
    saved = True
    previous_text = ''
    update_title()
    changes()
    return 'break'


def open_file(event=None):
    global current_file, saved, previous_text
    if not confirm_unsaved(): return
    file_path = filedialog.askopenfilename(
        filetypes=[
            ('Текстовые файлы', '*.txt'),
            ('Файлы Python', '*.py'),
            ('Все файлы', '*.*')
        ]
    )
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            editor_text.delete('1.0', END)
            editor_text.insert('1.0', content)
            current_file = file_path
            saved = True
            previous_text = content
            update_title()
            changes()
        except Exception as e:
            messagebox.showerror('Ошибка', f'Не удалось открыть файл: {e}')
    return 'break'


def save_file(event=None):
    global current_file, saved
    try:
        if current_file and os.path.exists(current_file):
            file_path = current_file
        else:
            file_path = filedialog.asksaveasfilename(
                defaultextension='.txt',
                filetypes=[
                    ('Текстовые файлы', '*.txt'),
                    ('Файлы Python', '*.py'),
                    ('Все файлы', '*.*')
                ],
                initialfile=os.path.basename(current_file) if current_file else 'Новый файл.txt'
            )
        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(editor_text.get('1.0', END))
            current_file = file_path
            saved = True
            update_title()
            changes()
            return True
    except Exception as e:
        messagebox.showerror('Ошибка', f'Не удалось сохранить файл: {e}')
    return 'break'


def about_program(event=None):
    messagebox.showinfo('О программе', 'KirNotepad\nРедактор, ориентированный на бинды.')
    return 'break'


def changes(event=None):
    global previous_text, saved
    text_now = editor_text.get('1.0', END)
    if text_now == previous_text: return

    cursor_pos = editor_text.index(INSERT)

    for tag in editor_text.tag_names():
        if tag.startswith('tag_'):
            editor_text.tag_remove(tag, '1.0', 'end')

    if should_highlight_syntax():
        rules = get_highlight_rules()
        i = 0
        for pattern, color in rules:
            for start, end in search_re(pattern, text_now):
                tag = f'tag_{i}'
                editor_text.tag_add(tag, start, end)
                editor_text.tag_config(tag, foreground=color)
                i += 1

    editor_text.mark_set(INSERT, cursor_pos)

    previous_text = text_now
    saved = False
    update_title()


#Функции Горячих Клавиш и GUI

def create_window():
    global root, editor_text, plugin_menu
    root = Tk()
    root.geometry('700x500')
    colors = get_colors()
    font = get_font()

    root.configure(bg=colors['background'])
    root.option_add('*Font', font)
    update_title()

    menubar = Menu(root)
    plugin_menu = Menu(menubar, tearoff=0)

    # ПРИВЯЗКА load_config К ROOT для безопасного доступа плагинов
    root.load_config = load_config

    editor_text = Text(
        root,
        background=colors['background'],
        foreground=colors['normal'],
        insertbackground=colors['normal'],
        relief=FLAT,
        borderwidth=0,
        font=font,
        wrap=WORD
    )
    editor_text.pack(fill=BOTH, expand=1)

    scrollbar = Scrollbar(root, command=editor_text.yview)
    scrollbar.pack(side=RIGHT, fill=Y)
    editor_text.config(yscrollcommand=scrollbar.set)

    editor_text.bind('<KeyRelease>', changes)

    hk = load_config().get('hotkeys', {})

    #Бинды
    editor_text.bind(hk.get('save', '<Control-s>'), save_file)
    editor_text.bind(hk.get('open', '<Control-o>'), open_file)
    editor_text.bind(hk.get('new', '<Control-n>'), new_file)
    editor_text.bind(hk.get('about', '<Control-q>'), about_program)

    def on_closing():
        if confirm_unsaved():
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    changes()


#Система Плагинов

def load_plugins():
    global root, editor_text, plugin_menu
    plugins_dir = 'plugins'
    print('\n--- Загрузка плагинов ---')

    plugin_context = {
        'root': root,
        'editor': editor_text,
        'get_content': lambda: editor_text.get('1.0', END),
        'set_content': lambda content: (editor_text.delete('1.0', END), editor_text.insert('1.0', content), changes()),
        'insert_text': lambda text: (editor_text.insert(INSERT, text), changes()),
        'current_file': lambda: current_file,
        'changes_notifier': changes,
        'messagebox': messagebox,
        'menu': plugin_menu,
        'get_color': get_color,
        'get_font': get_font
    }

    try:
        if not os.path.isdir(plugins_dir):
            os.makedirs(plugins_dir, exist_ok=True)

        plugin_files = [f for f in os.listdir(plugins_dir) if f.endswith('.py') and not f.startswith('_')]

        if not plugin_files:
            print("Плагины не найдены.")
            return

        for name in plugin_files:
            path = os.path.join(plugins_dir, name)
            print(f'Попытка загрузить: {name}...')

            try:
                spec = importlib.util.spec_from_file_location(name[:-3], path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)

                    spec.loader.exec_module(mod)

                    if hasattr(mod, 'setup') and callable(mod.setup):
                        mod.setup(plugin_context)

                    print(f'Плагин {name} УСПЕШНО загружен.')

            except Exception as e:
                print(f'Плагин load FAILED {name}: {e}')

    except Exception as e:
        print(f'Plugins setup error: {e}')
    print('--------------------------')


if __name__ == '__main__':
    load_config()
    create_window()
    load_plugins()
    root.mainloop()
