import os
import re
import sys
import subprocess
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
from tkinter.font import Font, families

THEME = {
    "bg_main": "#181715",
    "bg_gutter": "#21201c",
    "bg_tab_bar": "#151412",
    "bg_tab_active": "#181715",
    "bg_tab_inactive": "#1f1d1a",
    "bg_status": "#121110",
    "bg_panel": "#26241f",
    "bg_console": "#141311",
    
    "fg_text": "#f3eee2",
    "fg_gutter": "#787265",
    "fg_gutter_active": "#ffb300",
    "fg_tab": "#b0a897",
    "fg_tab_active": "#ffb300",
    "fg_status": "#9e9687",
    "fg_status_accent": "#ff9800",
    "fg_link": "#4fc3f7",
    
    "cursor": "#ffa726",
    "select_bg": "#3e3825",
    "current_line": "#201e1a",
    
    "syn_keyword": "#ff7043",
    "syn_builtin": "#ffb74d",
    "syn_string": "#d4e157",
    "syn_comment": "#7e8267",
    "syn_number": "#ffa000",
    "syn_def": "#ffd54f",
    "syn_decorator": "#26c6da",
}

PROJECT_URL = "https://github.com/sharagin/rezzcode"


class LineNumbers(tk.Canvas):
    def __init__(self, parent, text_widget, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.text_widget = text_widget
        self.config(bg=THEME["bg_gutter"], bd=0, highlightthickness=0, width=52)

    def redraw(self):
        self.delete("all")
        i = self.text_widget.index("@0,0")
        while True:
            dline = self.text_widget.dlineinfo(i)
            if dline is None:
                break
            y = dline[1]
            line_num = str(i).split(".")[0]
            cur_line = self.text_widget.index(tk.INSERT).split(".")[0]
            color = THEME["fg_gutter_active"] if line_num == cur_line else THEME["fg_gutter"]

            self.create_text(
                44, y, anchor="ne", text=line_num,
                fill=color, font=self.text_widget.cget("font")
            )
            i = self.text_widget.index(f"{i}+1line")


class SublimeText(tk.Text):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.font_size = 11
        self.font_family = "Consolas"
        self.apply_font()
        
        for tag, col in [
            ("keyword", THEME["syn_keyword"]),
            ("builtin", THEME["syn_builtin"]),
            ("string", THEME["syn_string"]),
            ("comment", THEME["syn_comment"]),
            ("number", THEME["syn_number"]),
            ("definition", THEME["syn_def"]),
            ("decorator", THEME["syn_decorator"]),
        ]:
            self.tag_configure(tag, foreground=col)

        self.tag_configure("url_link", foreground=THEME["fg_link"], underline=True)
        self.tag_configure("current_line", background=THEME["current_line"])
        self.tag_raise("sel")

        self.bind("<Return>", self.on_enter)
        self.bind("<Tab>", self.on_tab)
        self.bind("<BackSpace>", self.on_backspace)
        self.bind("<KeyRelease>", self.on_key_release)
        self.bind("<Motion>", self.on_mouse_move)
        self.bind("<Button-1>", self.on_mouse_click)

    def apply_font(self):
        self.config(font=(self.font_family, self.font_size))
        f = Font(font=(self.font_family, self.font_size))
        tab_width = f.measure("    ")
        self.config(tabs=(tab_width,))

    def on_mouse_move(self, event):
        idx = self.index(f"@{event.x},{event.y}")
        tags = self.tag_names(idx)
        if "url_link" in tags:
            self.config(cursor="hand2")
        else:
            self.config(cursor="xterm")

    def on_mouse_click(self, event):
        idx = self.index(f"@{event.x},{event.y}")
        tags = self.tag_names(idx)
        if "url_link" in tags:
            range_bounds = self.tag_prevrange("url_link", f"{idx}+1c")
            if range_bounds:
                url = self.get(range_bounds[0], range_bounds[1])
                webbrowser.open(url)
                return "break"
        return None

    def on_tab(self, event):
        if self.tag_ranges("sel"):
            sel_start = self.index(tk.SEL_FIRST)
            sel_end = self.index(tk.SEL_LAST)
            start_l = int(sel_start.split(".")[0])
            end_l = int(sel_end.split(".")[0])
            for l in range(start_l, end_l + 1):
                self.insert(f"{l}.0", "    ")
            return "break"
        self.insert(tk.INSERT, "    ")
        return "break"

    def on_backspace(self, event):
        cursor = self.index(tk.INSERT)
        col = int(cursor.split(".")[1])
        line_idx = cursor.split(".")[0]
        if col >= 4:
            prev_chars = self.get(f"{line_idx}.{col-4}", cursor)
            if prev_chars == "    ":
                self.delete(f"{line_idx}.{col-4}", cursor)
                return "break"
        return None

    def on_enter(self, event):
        line = self.get("insert linestart", "insert")
        indent = re.match(r"^\s*", line).group(0)
        if line.strip().endswith(":"):
            indent += "    "
        self.insert(tk.INSERT, "\n" + indent)
        self.see(tk.INSERT)
        return "break"

    def toggle_comment(self):
        try:
            sel_start = self.index(tk.SEL_FIRST)
            sel_end = self.index(tk.SEL_LAST)
            start_l = int(sel_start.split(".")[0])
            end_l = int(sel_end.split(".")[0])
        except tk.TclError:
            cur = self.index(tk.INSERT)
            start_l = end_l = int(cur.split(".")[0])

        all_commented = True
        for l in range(start_l, end_l + 1):
            line_str = self.get(f"{l}.0", f"{l}.end")
            if line_str.strip() and not line_str.strip().startswith("#"):
                all_commented = False
                break

        for l in range(start_l, end_l + 1):
            line_str = self.get(f"{l}.0", f"{l}.end")
            if all_commented:
                new_line = re.sub(r"^(\s*)#\s?", r"\1", line_str)
            else:
                new_line = re.sub(r"^(\s*)", r"\1# ", line_str)
            self.delete(f"{l}.0", f"{l}.end")
            self.insert(f"{l}.0", new_line)

        self.highlight_syntax()

    def duplicate_line(self):
        cur = self.index(tk.INSERT)
        line_idx = cur.split(".")[0]
        line_text = self.get(f"{line_idx}.0", f"{line_idx}.end")
        self.insert(f"{line_idx}.end", "\n" + line_text)
        self.highlight_syntax()

    def delete_line(self):
        cur = self.index(tk.INSERT)
        line_idx = cur.split(".")[0]
        self.delete(f"{line_idx}.0", f"{int(line_idx)+1}.0")
        self.highlight_syntax()

    def highlight_syntax(self):
        content = self.get("1.0", "end-1c")
        for tag in ["keyword", "builtin", "string", "comment", "number", "definition", "decorator", "url_link"]:
            self.tag_remove(tag, "1.0", tk.END)

        patterns = [
            (r'#[^\n]*', "comment"),
            (r'"""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'', "string"),
            (r'"[^"\\]*(\\.[^"\\]*)*"|\'[^\'\\]*(\\.[^\'\\]*)*\'', "string"),
            (r'@[a-zA-Z_]\w*', "decorator"),
            (r'\b(def|class)\s+([a-zA-Z_]\w*)', "definition"),
            (r'\b(self|cls|True|False|None)\b', "builtin"),
            (r'\b(int|float|str|list|dict|set|tuple|print|len|range|enumerate|zip|open|isinstance)\b', "builtin"),
            (r'\b(and|as|assert|async|await|break|continue|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield)\b', "keyword"),
            (r'\b\d+(\.\d+)?\b', "number"),
            (r'https?://[^\s<>"\']+', "url_link"),
        ]

        for pattern, tag in patterns:
            for match in re.finditer(pattern, content):
                start_idx = f"1.0 + {match.start()} chars"
                end_idx = f"1.0 + {match.end()} chars"
                if tag == "definition":
                    def_start = f"1.0 + {match.start(2)} chars"
                    def_end = f"1.0 + {match.end(2)} chars"
                    self.tag_add("definition", def_start, def_end)
                    kw_end = f"1.0 + {match.start(2) - 1} chars"
                    self.tag_add("keyword", start_idx, kw_end)
                else:
                    self.tag_add(tag, start_idx, end_idx)

    def on_key_release(self, event=None):
        self.highlight_syntax()


class RezzcodeTab:
    def __init__(self, parent, path=None, name="untitled", font_family="Consolas", font_size=11):
        self.parent = parent
        self.path = path
        self.name = name
        self.modified = False

        self.frame = tk.Frame(parent, bg=THEME["bg_main"])
        
        self.text = SublimeText(
            self.frame,
            wrap="none",
            undo=True,
            bg=THEME["bg_main"],
            fg=THEME["fg_text"],
            insertbackground=THEME["cursor"],
            insertwidth=2,
            selectbackground=THEME["select_bg"],
            selectforeground=THEME["fg_text"],
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=6
        )
        self.text.font_family = font_family
        self.text.font_size = font_size
        self.text.apply_font()

        self.gutter = LineNumbers(self.frame, self.text)
        self.v_scroll = tk.Scrollbar(self.frame, orient="vertical", command=self.on_scroll)
        self.text.config(yscrollcommand=self.on_text_scroll)

        self.gutter.pack(side="left", fill="y")
        self.v_scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.bind("<KeyPress>", self.mark_modified)
        self.text.bind("<ButtonRelease>", lambda e: self.update_view())
        self.text.bind("<KeyRelease>", lambda e: self.update_view())
        self.text.bind("<Configure>", lambda e: self.gutter.redraw())

    def on_scroll(self, *args):
        self.text.yview(*args)
        self.gutter.redraw()

    def on_text_scroll(self, *args):
        self.v_scroll.set(*args)
        self.gutter.redraw()

    def update_view(self):
        self.gutter.redraw()
        self.text.highlight_syntax()

    def mark_modified(self, event=None):
        if event and event.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R"):
            return
        if not self.modified:
            self.modified = True
            self.parent.master_app.update_tab_headers()


class RezzcodeApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("rezzcode")
        self.geometry("1000x680")
        self.configure(bg=THEME["bg_main"])

        available_fonts = [f.lower() for f in families(self)]
        if "consolas" in available_fonts:
            self.editor_font_family = "Consolas"
        elif "monaco" in available_fonts:
            self.editor_font_family = "Monaco"
        elif "dejavu sans mono" in available_fonts:
            self.editor_font_family = "DejaVu Sans Mono"
        else:
            self.editor_font_family = "Courier New"

        self.font_size = 11
        self.tabs = []
        self.active_tab_idx = -1
        self.word_wrap_enabled = False

        self.setup_menu()
        self.setup_ui()
        self.setup_keybindings()
        self.new_file()
        self.init_demo_code()

    def setup_menu(self):
        menubar = tk.Menu(self, bg=THEME["bg_tab_bar"], fg=THEME["fg_text"], bd=0, activebackground=THEME["select_bg"], activeforeground=THEME["fg_tab_active"])

        file_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_tab_bar"], fg=THEME["fg_text"], activebackground=THEME["select_bg"], activeforeground=THEME["fg_tab_active"])
        file_menu.add_command(label="New File", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="Open File...", accelerator="Ctrl+O", command=self.open_file)
        file_menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_command(label="Save As...", accelerator="Ctrl+Shift+S", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Close Tab", accelerator="Ctrl+W", command=self.close_current_tab)
        file_menu.add_command(label="Exit", accelerator="Ctrl+Q", command=self.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_tab_bar"], fg=THEME["fg_text"], activebackground=THEME["select_bg"], activeforeground=THEME["fg_tab_active"])
        edit_menu.add_command(label="Undo", accelerator="Ctrl+Z", command=self.action_undo)
        edit_menu.add_command(label="Redo", accelerator="Ctrl+Y", command=self.action_redo)
        edit_menu.add_separator()
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self.action_cut)
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self.action_copy)
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self.action_paste)
        edit_menu.add_command(label="Select All", accelerator="Ctrl+A", command=self.action_select_all)
        edit_menu.add_separator()
        edit_menu.add_command(label="Toggle Line Comment", accelerator="Ctrl+/", command=self.action_toggle_comment)
        edit_menu.add_command(label="Duplicate Line", accelerator="Ctrl+Shift+D", command=self.action_duplicate_line)
        edit_menu.add_command(label="Delete Line", accelerator="Ctrl+Shift+K", command=self.action_delete_line)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        find_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_tab_bar"], fg=THEME["fg_text"], activebackground=THEME["select_bg"], activeforeground=THEME["fg_tab_active"])
        find_menu.add_command(label="Find...", accelerator="Ctrl+F", command=lambda: self.toggle_find_bar(True, replace=False))
        find_menu.add_command(label="Replace...", accelerator="Ctrl+H", command=lambda: self.toggle_find_bar(True, replace=True))
        find_menu.add_command(label="Find Next", accelerator="F3", command=self.find_next)
        find_menu.add_separator()
        find_menu.add_command(label="Goto Line...", accelerator="Ctrl+G", command=self.goto_line_dialog)
        menubar.add_cascade(label="Find", menu=find_menu)

        view_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_tab_bar"], fg=THEME["fg_text"], activebackground=THEME["select_bg"], activeforeground=THEME["fg_tab_active"])
        view_menu.add_command(label="Zoom In", accelerator="Ctrl+Plus", command=self.zoom_in)
        view_menu.add_command(label="Zoom Out", accelerator="Ctrl+Minus", command=self.zoom_out)
        view_menu.add_command(label="Reset Zoom", accelerator="Ctrl+0", command=self.zoom_reset)
        view_menu.add_separator()
        view_menu.add_command(label="Toggle Word Wrap", command=self.toggle_word_wrap)
        view_menu.add_command(label="Toggle Console", accelerator="F4", command=self.toggle_console)
        menubar.add_cascade(label="View", menu=view_menu)

        run_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_tab_bar"], fg=THEME["fg_text"], activebackground=THEME["select_bg"], activeforeground=THEME["fg_tab_active"])
        run_menu.add_command(label="Run Python Script", accelerator="F5", command=self.run_current_script)
        menubar.add_cascade(label="Run", menu=run_menu)

        help_menu = tk.Menu(menubar, tearoff=0, bg=THEME["bg_tab_bar"], fg=THEME["fg_text"], activebackground=THEME["select_bg"], activeforeground=THEME["fg_tab_active"])
        help_menu.add_command(label="Project Repository", command=lambda: webbrowser.open(PROJECT_URL))
        help_menu.add_command(label="Documentation & Keys", command=self.show_shortcuts_info)
        help_menu.add_separator()
        help_menu.add_command(label="About rezzcode", command=self.show_about_dialog)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def setup_ui(self):
        self.tab_bar = tk.Frame(self, bg=THEME["bg_tab_bar"], height=34)
        self.tab_bar.pack(side="top", fill="x")

        self.editor_container = tk.Frame(self, bg=THEME["bg_main"])
        self.editor_container.master_app = self
        self.editor_container.pack(side="top", fill="both", expand=True)

        self.find_bar = tk.Frame(self, bg=THEME["bg_panel"], height=36)
        
        tk.Label(self.find_bar, text="FIND:", fg=THEME["fg_status_accent"], bg=THEME["bg_panel"], font=("Consolas", 9, "bold")).pack(side="left", padx=(8, 2))
        self.find_entry = tk.Entry(self.find_bar, bg=THEME["bg_main"], fg=THEME["fg_text"], insertbackground=THEME["cursor"], bd=1, relief="flat", font=("Consolas", 10))
        self.find_entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        self.find_entry.bind("<Return>", lambda e: self.find_next())
        self.find_entry.bind("<Escape>", lambda e: self.toggle_find_bar(False))

        self.replace_label = tk.Label(self.find_bar, text="REPLACE:", fg=THEME["fg_status_accent"], bg=THEME["bg_panel"], font=("Consolas", 9, "bold"))
        self.replace_entry = tk.Entry(self.find_bar, bg=THEME["bg_main"], fg=THEME["fg_text"], insertbackground=THEME["cursor"], bd=1, relief="flat", font=("Consolas", 10))
        self.replace_entry.bind("<Return>", lambda e: self.replace_current())
        self.replace_entry.bind("<Escape>", lambda e: self.toggle_find_bar(False))

        self.btn_find = tk.Button(self.find_bar, text="Find", bg=THEME["bg_tab_inactive"], fg=THEME["fg_text"], bd=0, padx=6, command=self.find_next)
        self.btn_find.pack(side="left", padx=2)

        self.btn_replace = tk.Button(self.find_bar, text="Replace", bg=THEME["bg_tab_inactive"], fg=THEME["fg_text"], bd=0, padx=6, command=self.replace_current)
        self.btn_replace_all = tk.Button(self.find_bar, text="Replace All", bg=THEME["bg_tab_inactive"], fg=THEME["fg_text"], bd=0, padx=6, command=self.replace_all)

        btn_close_find = tk.Button(self.find_bar, text="✕", bg=THEME["bg_panel"], fg=THEME["fg_tab"], relief="flat", bd=0, command=lambda: self.toggle_find_bar(False))
        btn_close_find.pack(side="right", padx=6)

        self.console_panel = tk.Frame(self, bg=THEME["bg_console"], height=160)
        self.console_header = tk.Frame(self.console_panel, bg=THEME["bg_panel"], height=24)
        self.console_header.pack(side="top", fill="x")
        
        tk.Label(self.console_header, text="OUTPUT CONSOLE", fg=THEME["fg_status_accent"], bg=THEME["bg_panel"], font=("Consolas", 9, "bold")).pack(side="left", padx=8)
        btn_close_console = tk.Button(self.console_header, text="✕", bg=THEME["bg_panel"], fg=THEME["fg_tab"], relief="flat", bd=0, command=self.toggle_console)
        btn_close_console.pack(side="right", padx=6)

        self.console_text = tk.Text(self.console_panel, bg=THEME["bg_console"], fg=THEME["fg_text"], bd=0, font=("Consolas", 10), state="disabled", padx=8, pady=6)
        self.console_scroll = tk.Scrollbar(self.console_panel, orient="vertical", command=self.console_text.yview)
        self.console_text.config(yscrollcommand=self.console_scroll.set)
        self.console_scroll.pack(side="right", fill="y")
        self.console_text.pack(side="left", fill="both", expand=True)

        self.status_bar = tk.Frame(self, bg=THEME["bg_status"], height=24)
        self.status_bar.pack(side="bottom", fill="x")

        self.status_left = tk.Label(self.status_bar, text="rezzcode :: citrus", bg=THEME["bg_status"], fg=THEME["fg_status_accent"], font=("Consolas", 9), cursor="hand2")
        self.status_left.pack(side="left", padx=10)
        self.status_left.bind("<Button-1>", lambda e: webbrowser.open(PROJECT_URL))

        self.status_right = tk.Label(self.status_bar, text="Line 1, Column 1   |   Spaces: 4   |   Python   |   UTF-8", bg=THEME["bg_status"], fg=THEME["fg_status"], font=("Consolas", 9))
        self.status_right.pack(side="right", padx=10)

        self.bind_all("<KeyRelease>", self.update_status_cursor)
        self.bind_all("<ButtonRelease>", self.update_status_cursor)

    def setup_keybindings(self):
        self.bind("<Control-n>", lambda e: self.new_file())
        self.bind("<Control-o>", lambda e: self.open_file())
        self.bind("<Control-s>", lambda e: self.save_file())
        self.bind("<Control-Shift-S>", lambda e: self.save_file_as())
        self.bind("<Control-w>", lambda e: self.close_current_tab())
        self.bind("<Control-q>", lambda e: self.destroy())
        self.bind("<Control-f>", lambda e: self.toggle_find_bar(True, replace=False))
        self.bind("<Control-h>", lambda e: self.toggle_find_bar(True, replace=True))
        self.bind("<Control-g>", lambda e: self.goto_line_dialog())
        self.bind("<Control-slash>", lambda e: self.action_toggle_comment())
        self.bind("<Control-Shift-D>", lambda e: self.action_duplicate_line())
        self.bind("<Control-Shift-K>", lambda e: self.action_delete_line())
        self.bind("<Control-equal>", lambda e: self.zoom_in())
        self.bind("<Control-plus>", lambda e: self.zoom_in())
        self.bind("<Control-minus>", lambda e: self.zoom_out())
        self.bind("<Control-0>", lambda e: self.zoom_reset)
        self.bind("<F3>", lambda e: self.find_next())
        self.bind("<F4>", lambda e: self.toggle_console())
        self.bind("<F5>", lambda e: self.run_current_script())

    def update_tab_headers(self):
        for widget in self.tab_bar.winfo_children():
            widget.destroy()

        for idx, tab in enumerate(self.tabs):
            is_active = (idx == self.active_tab_idx)
            bg = THEME["bg_tab_active"] if is_active else THEME["bg_tab_inactive"]
            fg = THEME["fg_tab_active"] if is_active else THEME["fg_tab"]
            
            f = tk.Frame(self.tab_bar, bg=bg)
            f.pack(side="left", fill="y", padx=(0, 2))

            title = f" {tab.name}{'*' if tab.modified else ''} "
            tab_btn = tk.Button(
                f, text=title, bg=bg, fg=fg, bd=0, padx=6, pady=4, relief="flat",
                font=("Consolas", 9, "bold" if is_active else "normal"),
                command=lambda i=idx: self.select_tab(i)
            )
            tab_btn.pack(side="left", fill="y")

            close_btn = tk.Button(
                f, text="×", bg=bg, fg=fg, bd=0, padx=4, relief="flat",
                font=("Consolas", 10),
                command=lambda i=idx: self.close_tab_at(i)
            )
            close_btn.pack(side="left", fill="y")

        new_tab_btn = tk.Button(
            self.tab_bar, text="+", bg=THEME["bg_tab_bar"], fg=THEME["fg_tab"],
            bd=0, padx=8, relief="flat", font=("Consolas", 11, "bold"),
            command=self.new_file
        )
        new_tab_btn.pack(side="left", fill="y")

    def select_tab(self, idx):
        if 0 <= idx < len(self.tabs):
            if self.active_tab_idx != -1 and self.active_tab_idx < len(self.tabs):
                self.tabs[self.active_tab_idx].frame.pack_forget()
            
            self.active_tab_idx = idx
            tab = self.tabs[idx]
            tab.frame.pack(fill="both", expand=True)
            self.update_tab_headers()
            tab.text.focus_set()
            tab.update_view()

    def new_file(self):
        tab = RezzcodeTab(self.editor_container, name=f"untitled_{len(self.tabs)+1}.py", font_family=self.editor_font_family, font_size=self.font_size)
        self.tabs.append(tab)
        self.select_tab(len(self.tabs) - 1)

    def open_file(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            tab = RezzcodeTab(self.editor_container, path=filepath, name=os.path.basename(filepath), font_family=self.editor_font_family, font_size=self.font_size)
            tab.text.insert("1.0", content)
            tab.modified = False
            self.tabs.append(tab)
            self.select_tab(len(self.tabs) - 1)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file:\n{e}")

    def save_file(self):
        if self.active_tab_idx == -1:
            return
        tab = self.tabs[self.active_tab_idx]
        if tab.path:
            try:
                content = tab.text.get("1.0", "end-1c")
                with open(tab.path, "w", encoding="utf-8") as f:
                    f.write(content)
                tab.modified = False
                self.update_tab_headers()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file:\n{e}")
        else:
            self.save_file_as()

    def save_file_as(self):
        if self.active_tab_idx == -1:
            return
        tab = self.tabs[self.active_tab_idx]
        filepath = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python Files", "*.py"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        tab.path = filepath
        tab.name = os.path.basename(filepath)
        self.save_file()

    def close_current_tab(self):
        if self.active_tab_idx != -1:
            self.close_tab_at(self.active_tab_idx)

    def close_tab_at(self, idx):
        if not (0 <= idx < len(self.tabs)):
            return
        tab = self.tabs[idx]
        if tab.modified:
            ans = messagebox.askyesnocancel("Save Changes", f"Do you want to save changes to '{tab.name}'?")
            if ans is True:
                self.select_tab(idx)
                self.save_file()
            elif ans is None:
                return

        tab.frame.destroy()
        self.tabs.pop(idx)
        if self.tabs:
            new_idx = max(0, idx - 1)
            self.active_tab_idx = -1
            self.select_tab(new_idx)
        else:
            self.active_tab_idx = -1
            self.update_tab_headers()
            self.new_file()

    def action_undo(self):
        if self.active_tab_idx != -1:
            try:
                self.tabs[self.active_tab_idx].text.edit_undo()
                self.tabs[self.active_tab_idx].update_view()
            except tk.TclError:
                pass

    def action_redo(self):
        if self.active_tab_idx != -1:
            try:
                self.tabs[self.active_tab_idx].text.edit_redo()
                self.tabs[self.active_tab_idx].update_view()
            except tk.TclError:
                pass

    def action_cut(self):
        if self.active_tab_idx != -1:
            self.tabs[self.active_tab_idx].text.event_generate("<<Cut>>")

    def action_copy(self):
        if self.active_tab_idx != -1:
            self.tabs[self.active_tab_idx].text.event_generate("<<Copy>>")

    def action_paste(self):
        if self.active_tab_idx != -1:
            self.tabs[self.active_tab_idx].text.event_generate("<<Paste>>")

    def action_select_all(self):
        if self.active_tab_idx != -1:
            self.tabs[self.active_tab_idx].text.tag_add("sel", "1.0", "end")

    def action_toggle_comment(self):
        if self.active_tab_idx != -1:
            self.tabs[self.active_tab_idx].text.toggle_comment()

    def action_duplicate_line(self):
        if self.active_tab_idx != -1:
            self.tabs[self.active_tab_idx].text.duplicate_line()

    def action_delete_line(self):
        if self.active_tab_idx != -1:
            self.tabs[self.active_tab_idx].text.delete_line()

    def goto_line_dialog(self):
        if self.active_tab_idx == -1:
            return
        line = simpledialog.askinteger("Goto Line", "Enter line number:", parent=self)
        if line:
            text = self.tabs[self.active_tab_idx].text
            text.mark_set(tk.INSERT, f"{line}.0")
            text.see(f"{line}.0")

    def zoom_in(self):
        self.font_size += 1
        for tab in self.tabs:
            tab.text.font_size = self.font_size
            tab.text.apply_font()
            tab.gutter.redraw()

    def zoom_out(self):
        if self.font_size > 7:
            self.font_size -= 1
            for tab in self.tabs:
                tab.text.font_size = self.font_size
                tab.text.apply_font()
                tab.gutter.redraw()

    def zoom_reset(self):
        self.font_size = 11
        for tab in self.tabs:
            tab.text.font_size = self.font_size
            tab.text.apply_font()
            tab.gutter.redraw()

    def toggle_word_wrap(self):
        self.word_wrap_enabled = not self.word_wrap_enabled
        wrap_mode = "char" if self.word_wrap_enabled else "none"
        for tab in self.tabs:
            tab.text.config(wrap=wrap_mode)
            tab.gutter.redraw()

    def toggle_find_bar(self, show, replace=False):
        if show:
            self.find_bar.pack(before=self.status_bar, fill="x")
            if replace:
                self.replace_label.pack(side="left", padx=(8, 2))
                self.replace_entry.pack(side="left", fill="x", expand=True, padx=4, pady=4)
                self.btn_replace.pack(side="left", padx=2)
                self.btn_replace_all.pack(side="left", padx=2)
            else:
                self.replace_label.pack_forget()
                self.replace_entry.pack_forget()
                self.btn_replace.pack_forget()
                self.btn_replace_all.pack_forget()
            
            self.find_entry.focus_set()
            self.find_entry.select_range(0, tk.END)
        else:
            self.find_bar.pack_forget()
            if self.active_tab_idx != -1:
                self.tabs[self.active_tab_idx].text.focus_set()

    def find_next(self):
        if self.active_tab_idx == -1:
            return
        text = self.tabs[self.active_tab_idx].text
        query = self.find_entry.get()
        if not query:
            return
        
        curr = text.index(tk.INSERT)
        pos = text.search(query, f"{curr}+1c", stopindex=tk.END)
        if not pos:
            pos = text.search(query, "1.0", stopindex=tk.END)
        
        if pos:
            end_pos = f"{pos}+{len(query)}c"
            text.tag_remove("sel", "1.0", tk.END)
            text.tag_add("sel", pos, end_pos)
            text.mark_set(tk.INSERT, end_pos)
            text.see(pos)

    def replace_current(self):
        if self.active_tab_idx == -1:
            return
        text = self.tabs[self.active_tab_idx].text
        query = self.find_entry.get()
        repl = self.replace_entry.get()
        if not query:
            return
        
        if text.tag_ranges("sel"):
            sel_text = text.get(tk.SEL_FIRST, tk.SEL_LAST)
            if sel_text == query:
                start = text.index(tk.SEL_FIRST)
                text.delete(tk.SEL_FIRST, tk.SEL_LAST)
                text.insert(start, repl)
        self.find_next()

    def replace_all(self):
        if self.active_tab_idx == -1:
            return
        text = self.tabs[self.active_tab_idx].text
        query = self.find_entry.get()
        repl = self.replace_entry.get()
        if not query:
            return

        pos = "1.0"
        while True:
            pos = text.search(query, pos, stopindex=tk.END)
            if not pos:
                break
            end_pos = f"{pos}+{len(query)}c"
            text.delete(pos, end_pos)
            text.insert(pos, repl)
            pos = f"{pos}+{len(repl)}c"
        
        self.tabs[self.active_tab_idx].update_view()

    def toggle_console(self):
        if self.console_panel.winfo_ismapped():
            self.console_panel.pack_forget()
        else:
            self.console_panel.pack(before=self.status_bar, fill="x")

    def run_current_script(self):
        if self.active_tab_idx == -1:
            return
        tab = self.tabs[self.active_tab_idx]
        if not tab.path:
            self.save_file_as()
            if not tab.path:
                return
        else:
            self.save_file()

        if not self.console_panel.winfo_ismapped():
            self.console_panel.pack(before=self.status_bar, fill="x")

        self.console_text.config(state="normal")
        self.console_text.delete("1.0", tk.END)
        self.console_text.insert(tk.END, f">>> Running {tab.path} ...\n\n")
        self.console_text.config(state="disabled")

        try:
            res = subprocess.run(
                [sys.executable, tab.path],
                capture_output=True,
                text=True,
                timeout=30
            )
            output = res.stdout + res.stderr
            if res.returncode == 0:
                output += f"\n>>> Process finished with exit code {res.returncode}\n"
            else:
                output += f"\n>>> Process failed with exit code {res.returncode}\n"
        except Exception as e:
            output = f"\n>>> Execution Error: {e}\n"

        self.console_text.config(state="normal")
        self.console_text.insert(tk.END, output)
        self.console_text.see(tk.END)
        self.console_text.config(state="disabled")

    def update_status_cursor(self, event=None):
        if self.active_tab_idx != -1 and self.tabs:
            text = self.tabs[self.active_tab_idx].text
            cursor = text.index(tk.INSERT)
            line, col = cursor.split(".")
            self.status_right.config(
                text=f"Line {line}, Column {int(col)+1}   |   Spaces: 4   |   Python   |   UTF-8"
            )

    def show_about_dialog(self):
        msg = f"rezzcode :: citrus code editor\nVersion 1.0\n\nInspired by Sublime Text minimalism.\nProject repository:\n{PROJECT_URL}"
        messagebox.showinfo("About rezzcode", msg)

    def show_shortcuts_info(self):
        info = (
            "File:\n"
            "  Ctrl+N : New Tab\n"
            "  Ctrl+O : Open File\n"
            "  Ctrl+S : Save File\n"
            "  Ctrl+Shift+S : Save As\n"
            "  Ctrl+W : Close Tab\n\n"
            "Edit:\n"
            "  Ctrl+Z : Undo\n"
            "  Ctrl+Y : Redo\n"
            "  Ctrl+/ : Toggle Comment\n"
            "  Ctrl+Shift+D : Duplicate Line\n"
            "  Ctrl+Shift+K : Delete Line\n\n"
            "Navigation & Tools:\n"
            "  Ctrl+F : Find\n"
            "  Ctrl+H : Find & Replace\n"
            "  Ctrl+G : Goto Line\n"
            "  F3 : Find Next\n"
            "  F4 : Toggle Console\n"
            "  F5 : Run Python Script\n"
            "  Ctrl+Plus / Minus : Zoom In/Out"
        )
        messagebox.showinfo("Shortcuts & Commands", info)

    def init_demo_code(self):
        code = '''import os
import sys

class CitrusEngine:
    def __init__(self, mode="lime"):
        self.mode = mode
        self.flavors = ["orange", "grapefruit", "lemon", "lime"]
        self.repository = "https://github.com/SalvatoreBonpinsiero/RezzCode"

    @property
    def summary(self):
        return f"Flavor: {self.mode.upper()}, Link: {self.repository}"

    def run(self, iterations=6):
        print(f"Launching rezzcode engine with mode={self.mode}...")
        for i in range(iterations):
            print(f"[{i+1}/{iterations}] Citrus burst initialized!")
        return self.summary

if __name__ == "__main__":
    app = CitrusEngine(mode="citrus-prime")
    result = app.run()
    print("\\nExecution Result:", result)
'''
        tab = self.tabs[self.active_tab_idx]
        tab.text.insert("1.0", code)
        tab.modified = False
        tab.update_view()
        self.update_tab_headers()


if __name__ == "__main__":
    app = RezzcodeApp()
    app.mainloop()
