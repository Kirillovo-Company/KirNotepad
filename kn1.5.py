from tkinter import *
from tkinter import filedialog, messagebox, TclError, ttk
import os
import re
import json
import importlib.util
from typing import Dict, Any, Optional, Callable, List, Tuple

# === Конфигурация и Глобальные переменные ===

config_path = 'config.json'
saved: bool = True  # Глобальный статус сохранения (теперь для активной вкладки)

# Глобальные переменные Tkinter
root: Optional[Tk] = None
# Новый виджет: Notebook для управления вкладками
notebook: Optional[ttk.Notebook] = None
plugin_menu: Optional[Menu] = None

# Словарь для хранения информации о каждой вкладке: {frame: {'path': str, 'text_widget': Text, 'saved': bool}}
# Ключ - Frame вкладки, значение - словарь с метаданными.
open_files_data: Dict[Frame, Dict[str, Any]] = {}


# === Функции Конфигурации (Без изменений) ===
# ... (load_config, save_config, get_color, get_colors, get_font остаются без изменений)
def load_config() -> Dict[str, Any]:
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
            'close_tab': '<Control-w>',
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


def save_config(config: Optional[Dict[str, Any]] = None):
    """Сохраняет конфигурацию."""
    if config is None:
        config = load_config()
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_color(name: str) -> str:
    """Безопасный доступ к цвету в формате #RRGGBB."""
    cfg = load_config()
    if 'colors' in cfg and name in cfg['colors']:
        r, g, b = cfg['colors'][name]
        return f'#{r:02x}{g:02x}{b:02x}'
    return '#FFFFFF'


def get_colors() -> Dict[str, str]:
    """Возвращает словарь всех цветов."""
    return {k: get_color(k) for k in load_config().get('colors', {}).keys()}


def get_font() -> str:
    """Возвращает строку шрифта."""
    return load_config().get('font', 'Consolas 15')


# === Вспомогательные функции для вкладок ===

def get_active_tab_info() -> Optional[Dict[str, Any]]:
    """Возвращает словарь с данными активной вкладки, или None."""
    if not notebook or not open_files_data:
        return None

    # Получаем Frame текущей вкладки
    try:
        current_frame = notebook.nametowidget(notebook.select())
        return open_files_data.get(current_frame)
    except Exception:
        return None


def get_active_editor() -> Optional[Text]:
    """Возвращает виджет Text активной вкладки."""
    info = get_active_tab_info()
    return info.get('text_widget') if info else None


def get_active_file_path() -> Optional[str]:
    """Возвращает путь к файлу активной вкладки."""
    info = get_active_tab_info()
    return info.get('path') if info else None


# === Функции Редактора (I/O, Подсветка, Статус) ===

def should_highlight_syntax() -> bool:
    """Определяет, нужно ли включать подсветку синтаксиса для активного файла."""
    file_path = get_active_file_path()
    if not file_path: return False
    _, ext = os.path.splitext(file_path)
    return ext.lower() in ['.py', '.html', '.css', '.js', '.c', '.json']


def search_re(pattern: str, text: str, editor: Text) -> list[tuple[str, str]]:
    """Ищет совпадения по регулярному выражению и возвращает индексы Tkinter."""
    try:
        rx = re.compile(pattern, re.MULTILINE | re.DOTALL)
        out = []
        for m in rx.finditer(text):
            start_index = editor.index(f'1.0 + {m.start()} chars')
            end_index = editor.index(f'1.0 + {m.end()} chars')
            out.append((start_index, end_index))
        return out
    except re.error:
        return []


# Правила подсветки (без изменений)
python_rules = [
    (r'(^|\b)(False|None|True|and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)(\b|$)',
     'keywords'),
    (r'""".*?"""', 'string'),
    (r"'''.*?'''", 'string'),
    (r'".*?"', 'string'),
    (r"'.*?'", 'string'),
    (r'#.*?$', 'comments'),
]
html_rules = [(r'&[^;]+;', 'string'), (r'<[^>]+>', 'keywords'), (r'".*?"', 'string'), (r"'.*?'", 'string'),
              (r'', 'comments'), ]
css_rules = [(r'[{}]', 'keywords'), (r'[:;]', 'function'), (r'\.[a-zA-Z][a-zA-Z0-9_-]*', 'function'),
             (r'#[a-fA-F0-9]{3,6}', 'string'), (r'//.*?$', 'comments'), (r'/\*.*?\*/', 'comments'), ]


def get_highlight_rules() -> list[tuple[str, str]]:
    """Возвращает правила подсветки для текущего типа файла."""
    file_path = get_active_file_path()
    if not file_path: return []
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    colors = get_colors()

    base: list[Tuple[str, str]]

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
        return []

    color_rules = []
    for pattern, color_name in base:
        if color_name in colors:
            color_rules.append((pattern, colors[color_name]))

    return color_rules


def update_title():
    """Обновляет заголовок окна на основе активной вкладки."""
    global root
    if not root: return

    info = get_active_tab_info()
    if info:
        filename = os.path.basename(info['path']) if info['path'] else 'Новый файл'
        status = '' if info['saved'] else '*'
        root.title(f'{filename}{status} - KirNotepad 1.5')
    else:
        root.title('KirNotepad 1.5')


def confirm_unsaved() -> bool:
    """Проверяет несохраненные изменения во всех вкладках перед закрытием/открытием."""

    unsaved_paths = []
    for info in open_files_data.values():
        if not info['saved']:
            path = os.path.basename(info['path']) if info['path'] else 'Новый файл'
            unsaved_paths.append(path)

    if not unsaved_paths: return True

    # Спрашиваем, если есть несохраненные файлы
    result = messagebox.askyesnocancel('Несохранённые изменения',
                                       f'Следующие файлы не сохранены:\n{", ".join(unsaved_paths)}\n\nСохранить все перед продолжением?')

    if result is None: return False

    if result:
        # Пытаемся сохранить все
        all_saved = True
        for frame, info in list(open_files_data.items()):  # Создаем копию, чтобы избежать ошибки при удалении
            if not info['saved']:
                # Делаем эту вкладку активной, чтобы save_file работал корректно
                notebook.select(frame)
                if not save_file():
                    all_saved = False  # Если пользователь отменил сохранение
        return all_saved

    return True


# === Управление вкладками ===

def create_new_tab(file_path: Optional[str] = None, content: str = '') -> Optional[Text]:
    """Создает новую вкладку с редактором и скроллбаром."""
    global notebook, open_files_data
    if not notebook: return None

    colors = get_colors()
    font = get_font()

    # 1. Фрейм для вкладки
    tab_frame = Frame(notebook, background=colors['background'])
    tab_frame.grid_columnconfigure(0, weight=1)  # Редактор
    tab_frame.grid_columnconfigure(1, weight=0)  # Скроллбар
    tab_frame.grid_rowconfigure(0, weight=1)

    # 2. Текстовый виджет (Editor)
    editor = Text(
        tab_frame,
        background=colors['background'],
        foreground=colors['normal'],
        insertbackground=colors['normal'],
        relief=FLAT,
        borderwidth=0,
        font=font,
        wrap=WORD
    )
    editor.grid(row=0, column=0, sticky=N + S + E + W)

    # 3. Скроллбар
    scrollbar = Scrollbar(tab_frame, command=editor.yview)
    scrollbar.grid(row=0, column=1, sticky=N + S)
    editor.config(yscrollcommand=scrollbar.set)

    # 4. Настройка содержимого и метаданных
    editor.insert('1.0', content)

    path_name = os.path.basename(file_path) if file_path else 'Новый файл'

    # Добавляем фрейм как вкладку
    notebook.add(tab_frame, text=path_name)

    # Сохраняем данные о вкладке
    open_files_data[tab_frame] = {
        'path': file_path,
        'text_widget': editor,
        'saved': True,
        'previous_text': editor.get('1.0', END)
    }

    # 5. Бинды для редактора (привязываем изменения к каждому редактору)
    editor.bind('<KeyRelease>', changes)

    # Привязываем глобальные бинды к виджету Text, чтобы они работали
    hk = load_config().get('hotkeys', {})
    editor.bind(hk.get('save', '<Control-s>'), save_file)
    editor.bind(hk.get('open', '<Control-o>'), open_file)
    editor.bind(hk.get('new', '<Control-n>'), new_file)
    editor.bind(hk.get('about', '<Control-q>'), about_program)
    editor.bind(hk.get('close_tab', '<Control-w>'), close_active_tab)

    # Делаем новую вкладку активной и обновляем заголовок
    notebook.select(tab_frame)
    update_title()

    return editor


def close_active_tab(event=None):
    """Закрывает активную вкладку, если нет несохраненных изменений."""
    global notebook, open_files_data
    if not notebook: return 'break'

    current_frame = notebook.nametowidget(notebook.select())
    info = open_files_data.get(current_frame)

    if info and not info['saved']:
        filename = os.path.basename(info['path']) if info['path'] else 'Новый файл'
        result = messagebox.askyesnocancel('Несохранённые изменения',
                                           f'Сохранить изменения в "{filename}" перед закрытием?')

        if result is None:
            return 'break'  # Отмена

        if result:
            if not save_file():
                return 'break'  # Отмена сохранения

    # Если сохранили или решили не сохранять, удаляем вкладку
    if current_frame in open_files_data:
        del open_files_data[current_frame]
        notebook.forget(current_frame)

    # Если вкладок не осталось, создаем новую пустую
    if not open_files_data:
        create_new_tab()

    update_title()
    return 'break'


def on_tab_change(event):
    """Обработчик переключения вкладок."""
    update_title()
    # Перезапускаем изменения, чтобы обновить подсветку для новой вкладки
    changes()


# === I/O функции ===

def new_file(event=None):
    """Создает новый файл (новую вкладку)."""
    create_new_tab()
    return 'break'


def _load_file_to_editor(file_path: str):
    """Загружает содержимое файла в новую вкладку или активирует существующую."""
    global notebook, open_files_data

    # Проверяем, не открыт ли уже этот файл
    for frame, info in open_files_data.items():
        if info['path'] == file_path:
            notebook.select(frame)
            update_title()
            changes()  # Обновляем подсветку
            return

    # Если файл не найден, создаем новую вкладку
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        editor = create_new_tab(file_path=file_path, content=content)
        if editor:
            info = get_active_tab_info()
            if info:
                info['saved'] = True
                info['previous_text'] = editor.get('1.0', END)
            update_title()
            changes()

    except Exception as e:
        messagebox.showerror('Ошибка', f'Не удалось открыть файл: {e}')


def open_file(event=None):
    """Открывает файл, используя диалог."""
    file_path = filedialog.askopenfilename(
        filetypes=[
            ('Текстовые файлы', '*.txt'),
            ('Файлы Python', '*.py'),
            ('Все файлы', '*.*')
        ]
    )
    if file_path:
        _load_file_to_editor(file_path)
    return 'break'


def save_file(event=None) -> bool:
    """Сохраняет текущий активный файл."""
    info = get_active_tab_info()
    editor = get_active_editor()
    if not editor or not info: return False

    try:
        file_path = info['path']
        if not file_path or not os.path.exists(file_path):
            file_path = filedialog.asksaveasfilename(
                defaultextension='.txt',
                filetypes=[
                    ('Текстовые файлы', '*.txt'),
                    ('Файлы Python', '*.py'),
                    ('Все файлы', '*.*')
                ],
                initialfile=os.path.basename(file_path) if file_path else 'Новый файл.txt'
            )

        if file_path:
            with open(file_path, 'w', encoding='utf-8') as f:
                content = editor.get('1.0', 'end - 1c')
                f.write(content)

            # Обновляем метаданные вкладки
            info['path'] = file_path
            info['saved'] = True
            info['previous_text'] = editor.get('1.0', END)

            # Обновляем текст на вкладке
            path_name = os.path.basename(file_path)
            notebook.tab(notebook.select(), text=path_name)

            update_title()
            changes()
            return True

    except Exception as e:
        messagebox.showerror('Ошибка', f'Не удалось сохранить файл: {e}')
    return False


def about_program(event=None):
    """Показывает информацию о программе."""
    messagebox.showinfo('О программе', 'KirNotepad 1.5\nРедактор, ориентированный на бинды и вкладки.')
    return 'break'


def changes(event=None):
    """Обрабатывает изменения текста (подсветка синтаксиса и обновление статуса)."""
    info = get_active_tab_info()
    editor = get_active_editor()
    if not editor or not info: return

    text_now = editor.get('1.0', END)

    # 1. Проверка изменений и статуса
    if text_now == info['previous_text']: return

    cursor_pos = editor.index(INSERT)

    # 2. Сброс подсветки
    for tag in editor.tag_names():
        if tag.startswith('tag_'):
            editor.tag_remove(tag, '1.0', 'end')

    # 3. Новая подсветка
    if should_highlight_syntax():
        rules = get_highlight_rules()
        i = 0
        for pattern, color in rules:
            for start, end in search_re(pattern, text_now, editor):
                tag = f'tag_{i}'
                editor.tag_add(tag, start, end)
                editor.tag_config(tag, foreground=color)
                i += 1

    # 4. Восстановление курсора
    editor.mark_set(INSERT, cursor_pos)

    # 5. Обновление статуса
    info['previous_text'] = text_now
    info['saved'] = False

    # Обновляем текст на вкладке, добавляя '*'
    current_frame = notebook.nametowidget(notebook.select())
    path_name = os.path.basename(info['path']) if info['path'] else 'Новый файл'
    notebook.tab(current_frame, text=f'{path_name}*')

    update_title()


# === API для Плагинов (Обновлено) ===

class PluginAPI:
    """
    Класс, предоставляющий безопасный и структурированный API для плагинов.
    Теперь работает с активной вкладкой.
    """

    def __init__(self, tk_root: Tk, tk_notebook: ttk.Notebook, plugin_menu_obj: Optional[Menu],
                 changes_callback: Callable):
        self._root = tk_root
        self._notebook = tk_notebook
        self.menu = plugin_menu_obj
        self._changes_callback = changes_callback

    def get_content(self) -> str:
        """Возвращает весь текст из активного редактора."""
        editor = get_active_editor()
        return editor.get('1.0', 'end - 1c') if editor else ""

    def set_content(self, content: str):
        """Устанавливает весь текст в активном редакторе и запускает обновление."""
        editor = get_active_editor()
        if editor:
            editor.delete('1.0', END)
            editor.insert('1.0', content)
            self._changes_callback()

    def insert_text(self, text: str):
        """Вставляет текст в текущую позицию курсора активного редактора."""
        editor = get_active_editor()
        if editor:
            editor.insert(INSERT, text)
            self._changes_callback()

    # ... (Остальные методы API используют get_active_editor)
    def replace_selection(self, text: str):
        """Заменяет выделенный текст активного редактора."""
        editor = get_active_editor()
        if not editor: return
        try:
            sel_start = editor.index(SEL_FIRST)
            sel_end = editor.index(SEL_LAST)
            editor.delete(sel_start, sel_end)
            editor.insert(sel_start, text)
            self._changes_callback()
        except TclError:
            self.insert_text(text)

    def get_selection(self) -> str:
        """Возвращает выделенный текст активного редактора."""
        editor = get_active_editor()
        if not editor: return ""
        try:
            return editor.get(SEL_FIRST, SEL_LAST)
        except TclError:
            return ""

    def current_file(self) -> Optional[str]:
        """Возвращает путь к текущему файлу активной вкладки."""
        return get_active_file_path()

    def open_file_in_editor(self, file_path: str):
        """Открывает файл по указанному пути в новой или существующей вкладке."""
        _load_file_to_editor(file_path)

    def bind_hotkey(self, sequence: str, func: Callable):
        """Привязывает горячую клавишу к корневому окну (глобальный бинд)."""
        self._root.bind(sequence, lambda e: func())

    def get_config_value(self, *keys: str) -> Any:
        """Безопасный доступ к значению конфигурации по ключам."""
        cfg = load_config()
        value = cfg
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        return value

    def get_root_window(self) -> Tk:
        """Возвращает корневое окно Tkinter."""
        return self._root

    def get_editor_widget(self) -> Text:
        """
        Возвращает виджет Text активного редактора.
        Использовать осторожно, так как он меняется при переключении вкладок.
        """
        return get_active_editor()


# === Инициализация и Запуск ===

def create_window():
    """Инициализирует главное окно и виджеты."""
    global root, notebook, plugin_menu

    root = Tk()
    root.geometry('1000x500')
    colors = get_colors()

    root.configure(bg=colors['background'])
    root.option_add('*Font', get_font())
    update_title()

    # --- Настройка Grid ---
    # Колонка 0: Для плагинов (дерево файлов). Не растягивается (weight=0).
    root.grid_columnconfigure(0, weight=0)
    # Колонка 1: Для Notebook (вкладки). Растягивается (weight=1).
    root.grid_columnconfigure(1, weight=1)
    # Строка 0: Основное содержимое. Растягивается (weight=1).
    root.grid_rowconfigure(0, weight=1)

    # 1. Notebook (система вкладок)
    style = ttk.Style()
    style.theme_use('default')
    style.configure('TNotebook', background=colors['background'], borderwidth=0)
    style.configure('TNotebook.Tab', background='#333333', foreground=colors['normal'], padding=[10, 5])
    style.map('TNotebook.Tab', background=[('selected', colors['background'])],
              foreground=[('selected', colors['normal'])])

    notebook = ttk.Notebook(root, style='TNotebook')
    notebook.grid(row=0, column=1, sticky=N + S + E + W)
    notebook.bind('<<NotebookTabChanged>>', on_tab_change)

    # 2. Создаем первую (пустую) вкладку
    create_new_tab()

    # 3. Бинды, привязанные к корневому окну
    def on_closing():
        if confirm_unsaved():
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)

    # Привязываем глобальные бинды к root, чтобы они работали, даже если редактор не в фокусе
    hk = load_config().get('hotkeys', {})
    root.bind(hk.get('save', '<Control-s>'), save_file)
    root.bind(hk.get('open', '<Control-o>'), open_file)
    root.bind(hk.get('new', '<Control-n>'), new_file)
    root.bind(hk.get('about', '<Control-q>'), about_program)
    root.bind(hk.get('close_tab', '<Control-w>'), close_active_tab)

    update_title()


def load_plugins():
    """Загружает плагины, предоставляя им чистый API."""
    global root, notebook, plugin_menu
    if not root or not notebook: return

    plugins_dir = 'plugins'
    print('\n--- Загрузка плагинов ---')

    if plugin_menu is None:
        plugin_menu = Menu(root, tearoff=0)

        # Инициализируем API
    plugin_api = PluginAPI(
        tk_root=root,
        tk_notebook=notebook,
        plugin_menu_obj=plugin_menu,
        changes_callback=changes
    )

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
                spec = importlib.util.spec_from_file_location(f'kirnotepad.plugin.{name[:-3]}', path)
                if spec and spec.loader:
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)

                    if hasattr(mod, 'setup') and callable(mod.setup):
                        mod.setup(plugin_api)
                        print(f'Плагин {name} УСПЕШНО загружен.')
                    else:
                        print(f'Плагин {name} пропущен: отсутствует функция setup(api).')

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
