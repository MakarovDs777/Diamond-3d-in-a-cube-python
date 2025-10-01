import tkinter as tk
from tkinter import filedialog, messagebox
import ast
import codecs
from pathlib import Path
from datetime import datetime
import subprocess
import shutil

# --- Утилиты ---

def detect_format(data: bytes) -> str:
    """Попытка детектировать формат по заголовкам (очень простая эвристика)."""
    if not data:
        return "unknown"
    # MP3 с ID3
    if data.startswith(b"ID3"):
        return "mp3"
    # MP3 frame sync 0xFFEx или 0xFFFx (общая эвристика)
    if len(data) >= 2 and data[0] == 0xFF and ((data[1] & 0xE0) == 0xE0):
        return "mp3"
    # MP4/M4A: 'ftyp' в первых 16 байтах (обычно в offset 4)
    if b"ftyp" in data[:16]:
        # уточним контейнер
        if b"mp42" in data or b"isom" in data or b"m4a" in data or b"avc1" in data:
            return "mp4"
        return "mp4"
    # WAV: RIFF....WAVE
    if data.startswith(b"RIFF") and b"WAVE" in data[:12]:
        return "wav"
    # OGG
    if data.startswith(b"OggS"):
        return "ogg"
    # AAC ADTS: 0xFFF1 or 0xFFF9 (проверка syncword 0xFFF)
    if len(data) >= 2 and data[0] == 0xFF and (data[1] & 0xF6) in (0xF0, 0xF8, 0xF2):
        return "aac"
    return "unknown"

def ffmpeg_exists() -> bool:
    return shutil.which("ffmpeg") is not None

def convert_to_mp3_with_ffmpeg(data: bytes, out_path: Path) -> (bool, str):
    """
    Пытается запустить ffmpeg, подать байты на stdin и получить mp3 на out_path.
    Возвращает (успех: bool, stderr_text).
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", "pipe:0",    # вход — из stdin
        "-vn",             # без видеопотока
        "-acodec", "libmp3lame",
        "-b:a", "192k",
        str(out_path)
    ]
    try:
        proc = subprocess.run(cmd, input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        success = proc.returncode == 0
        stderr = proc.stderr.decode(errors="ignore")
        return success, stderr
    except Exception as e:
        return False, str(e)

# --- GUI и логика приложения ---

def setup_clipboard_bindings(widget):
    def gen(event_name):
        return lambda e: (widget.event_generate(event_name), "break")

    widget.bind("<Control-c>", gen("<<Copy>>"))
    widget.bind("<Control-v>", gen("<<Paste>>"))
    widget.bind("<Control-x>", gen("<<Cut>>"))
    widget.bind("<Control-a>", lambda e: (widget.tag_add("sel", "1.0", "end"), "break"))

    widget.bind("<Command-c>", gen("<<Copy>>"))
    widget.bind("<Command-v>", gen("<<Paste>>"))
    widget.bind("<Command-x>", gen("<<Cut>>"))
    widget.bind("<Command-a>", lambda e: (widget.tag_add("sel", "1.0", "end"), "break"))

    widget.bind("<Button-1>", lambda e: widget.focus_set())

    menu = tk.Menu(widget, tearoff=0)
    menu.add_command(label="Копировать", command=lambda: widget.event_generate("<<Copy>>"))
    menu.add_command(label="Вставить", command=lambda: widget.event_generate("<<Paste>>"))
    menu.add_command(label="Вырезать", command=lambda: widget.event_generate("<<Cut>>"))
    menu.add_separator()
    menu.add_command(label="Выделить всё", command=lambda: widget.tag_add("sel", "1.0", "end"))

    def show_menu(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    widget.bind("<Button-3>", show_menu)
    widget.bind("<Control-Button-1>", show_menu)

def load_bytes_file():
    """Открывает файл и вставляет его содержимое как bytes-литерал в табло."""
    path = filedialog.askopenfilename(title="Выберите байтовый файл", filetypes=[("All files", "*.*")])
    if not path:
        return
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось прочитать файл: {e}")
        return

    text_widget.config(state="normal")
    text_widget.delete("1.0", tk.END)
    text_widget.insert("1.0", repr(data))
    messagebox.showinfo("Загружено", f"Загружено {len(data)} байт из файла: {Path(path).name}")

def parse_bytes_from_text(txt: str) -> bytes:
    """Пытаемся безопасно получить bytes из текста: literal_eval для bytes или декодирование escape."""
    txt = txt.strip()
    if not txt:
        raise ValueError("Поле пустое.")
    try:
        val = ast.literal_eval(txt)
        if isinstance(val, bytes):
            return val
        if isinstance(val, str):
            decoded = codecs.decode(val, "unicode_escape")
            return decoded.encode("latin-1")
        raise ValueError("Ожидается bytes-литерал или строка с escape-последовательностями.")
    except Exception as e:
        raise ValueError(f"Не удалось распарсить байты: {e}")

def save_audio_from_text():
    """Основная логика: парсим байты, детектируем формат, пытаемся конвертировать в mp3 или сохраняем исходный файл."""
    txt = text_widget.get("1.0", tk.END).strip()
    try:
        data = parse_bytes_from_text(txt)
    except ValueError as e:
        messagebox.showerror("Ошибка парсинга", str(e))
        return

    # Детектируем формат
    fmt = detect_format(data)

    # Предлагаем сохранить: по умолчанию на рабочий стол с подходящим расширением
    home = Path.home()
    desktop = home / "Desktop"
    if not desktop.exists():
        desktop = home
    default_name = f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    ext_map = {"mp3":"mp3","mp4":"m4a","wav":"wav","ogg":"ogg","aac":"aac","unknown":"bin"}
    suggested_ext = ext_map.get(fmt, "bin")
    default_filename = f"{default_name}.{suggested_ext}"

    save_path = filedialog.asksaveasfilename(title="Сохранить как", initialdir=str(desktop), initialfile=default_filename, defaultextension=f".{suggested_ext}", filetypes=[("All files","*.*")])
    if not save_path:
        return
    out_path = Path(save_path)

    # Если уже MP3 — просто сохраняем
    if fmt == "mp3":
        try:
            out_path.write_bytes(data)
            messagebox.showinfo("Готово", f"MP3 сохранён: {out_path}")
        except Exception as e:
            messagebox.showerror("Ошибка записи", f"Не удалось сохранить файл: {e}")
        return

    # Формат не MP3 — попробуем конвертировать через ffmpeg (если доступен)
    if ffmpeg_exists():
        # Если пользователь выбрал .mp3 в диалоге — используем это имя,
        # иначе, если выбрал другое расширение — спросим, хочет ли он mp3
        want_mp3 = out_path.suffix.lower() == ".mp3"
        if not want_mp3:
            if messagebox.askyesno("Конвертация", "Входные байты не являются MP3. Хотите конвертировать их в MP3 при помощи ffmpeg?"):
                # если пользователь согласен, предложим файл с .mp3 рядом с выбранным
                out_mp3 = out_path.with_suffix(".mp3")
            else:
                # пользователь не захотел; сохраняем исходные байты в выбранный файл
                try:
                    out_path.write_bytes(data)
                    messagebox.showinfo("Готово", f"Файл сохранён (без конвертации): {out_path}")
                except Exception as e:
                    messagebox.showerror("Ошибка записи", f"Не удалось сохранить файл: {e}")
                return
        else:
            out_mp3 = out_path

        # Пытаемся конвертировать
        success, info = convert_to_mp3_with_ffmpeg(data, out_mp3)
        if success:
            messagebox.showinfo("Готово", f"Файл конвертирован и сохранён: {out_mp3}")
        else:
            # Конвертация провалилась — предлагем сохранить исходную на тот же путь
            try:
                out_path.write_bytes(data)
                messagebox.showwarning("Конвертация не удалась", f"ffmpeg вернул ошибку:\n{info}\n\nИсходные байты сохранены в {out_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Конвертация не удалась:\n{info}\nИ попытка сохранить исходный файл тоже провалилась:\n{e}")
        return
    else:
        # ffmpeg недоступен — просто сохраняем исходный файл с подходящим расширением и даём инструкцию
        try:
            out_path.write_bytes(data)
            messagebox.showinfo("Сохранено", f"ffmpeg не найден. Файл сохранён как {out_path}.\n\nЕсли это контейнер (mp4/m4a/...). Чтобы получить MP3 — установите ffmpeg и запустите конвертацию:\nffmpeg -i {out_path} -vn -acodec libmp3lame -b:a 192k output.mp3")
        except Exception as e:
            messagebox.showerror("Ошибка записи", f"Не удалось сохранить файл: {e}")

def clear_text():
    text_widget.config(state="normal")
    text_widget.delete("1.0", tk.END)

# --- GUI ---
root = tk.Tk()
root.title("Работа с байтовыми файлами — сохранение/конвертация в MP3")
root.geometry("960x680")

top_frame = tk.Frame(root)
top_frame.pack(fill=tk.X, padx=8, pady=6)

load_btn = tk.Button(top_frame, text="Загрузить байтовый файл", command=load_bytes_file)
load_btn.pack(side=tk.LEFT, padx=(0,6))

length_label = tk.Label(top_frame, text="Длина аудио (с):")
length_label.pack(side=tk.LEFT)
length_var = tk.StringVar()
length_entry = tk.Entry(top_frame, textvariable=length_var, width=12)
length_entry.pack(side=tk.LEFT, padx=(4,12))

save_btn = tk.Button(top_frame, text="Сохранить / Конвертировать", command=save_audio_from_text)
save_btn.pack(side=tk.LEFT, padx=(0,6))

clear_btn = tk.Button(top_frame, text="Очистить табло", command=clear_text)
clear_btn.pack(side=tk.LEFT)

text_frame = tk.Frame(root)
text_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=6)

text_widget = tk.Text(text_frame, wrap=tk.NONE, font=("Consolas", 11))
yscroll = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
xscroll = tk.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=text_widget.xview)
text_widget.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
yscroll.pack(side=tk.RIGHT, fill=tk.Y)
xscroll.pack(side=tk.BOTTOM, fill=tk.X)
text_widget.pack(fill=tk.BOTH, expand=True)

setup_clipboard_bindings(text_widget)

hint = tk.Label(root, text="Вставьте или загрузите bytes-литерал (например b'\\x00\\x01...') или строку с escape-последовательностями. Программа попытается детектировать формат и (при наличии ffmpeg) конвертировать в MP3.", anchor="w")
hint.pack(fill=tk.X, padx=8, pady=(0,8))

root.mainloop()
