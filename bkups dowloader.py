import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox, filedialog
import yt_dlp
import threading
import os
import sys
import subprocess
import queue
import shutil
import time
import datetime
import platform
import re

ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('blue')
APP_TITLE = 'The Video Downloader'
AUTHOR = 'yasin ullah'
APP_SIZE = '800x650'
HISTORY_FILE = 'download_history.txt'

class MyLogger:
    """Redirects yt-dlp logs to the GUI queue."""
    def __init__(self, log_queue):
        self.log_queue = log_queue
    def debug(self, msg):
        if not msg.startswith('[debug] '):
            self.write(msg)
    def info(self, msg):
        self.write(msg)
    def warning(self, msg):
        self.write(f'WARNING: {msg}')
    def error(self, msg):
        self.write(f'ERROR: {msg}')
    def write(self, msg):
        self.log_queue.put(('log', msg))

class TextProgressBar(tk.Canvas):
    """Custom Progress Bar with Text and Smooth Animation"""
    def __init__(self, parent, height=30, bg='#2b2b2b', fill_color='#2ecc71', text_color='white'):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, relief='flat')
        self.fill_color = fill_color
        self.value = 0.0
        self.target_value = 0.0
        self.width = 0
        self.height = height
        self.rect_id = self.create_rectangle(0, 0, 0, height, fill=fill_color, width=0)
        self.text_id = self.create_text(0, 0, text='0%', fill=text_color, font=('Segoe UI', 12, 'bold'))
        self.bind('<Configure>', self.on_resize)
        
    def on_resize(self, event):
        self.width = event.width
        self.coords(self.text_id, self.width / 2, self.height / 2)
        self.draw()
        
    def set(self, val):
        """Sets value (0.0 to 1.0) with animation"""
        target = max(0.0, min(1.0, float(val)))
        if target == 0 or abs(target - self.value) < 0.01:
            self.value = target
            self.draw()
        else:
            self.animate_to(target)
            
    def animate_to(self, target):
        step = (target - self.value) / 5
        def _step(count):
            if count > 0:
                self.value += step
                self.draw()
                self.after(10, lambda: _step(count - 1))
            else:
                self.value = target
                self.draw()
        _step(5)
        
    def draw(self):
        if self.width > 0:
            fill_w = self.width * self.value
            self.coords(self.rect_id, 0, 0, fill_w, self.height)
        percent = int(self.value * 100)
        self.itemconfigure(self.text_id, text=f'{percent}%')
        self.tag_raise(self.text_id)

class UniversalDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_TITLE} | By {AUTHOR}")
        self.root.geometry(APP_SIZE)
        os.environ['PATH'] += os.pathsep + os.getcwd()
        self.has_ffmpeg = shutil.which('ffmpeg') is not None
        self.gui_queue = queue.Queue()
        self.is_downloading = False
        self.is_paused = False
        self.cancel_requested = False
        self.last_clipboard = ''
        self.setup_ui()
        self.process_queue()
        self.start_clipboard_monitor()
        self.log_message(f'App Started. FFmpeg detected: {self.has_ffmpeg}')
        if not self.has_ffmpeg:
            self.log_message('NOTICE: FFmpeg missing. Using Safe Mode (Guaranteed Audio).')
            
    def setup_ui(self):
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.tabs = ctk.CTkTabview(self.main_frame)
        self.tabs.pack(fill='both', expand=True, padx=10, pady=(0, 10))
        self.tab_single = self.tabs.add('  ⬇️ Single Download  ')
        self.tab_batch = self.tabs.add('  📚 Batch Queue  ')
        self.tab_settings = self.tabs.add('  ⚙️ Settings  ')
        
        self.build_single_tab()
        self.build_batch_tab()
        self.build_settings_tab()
        
        self.footer_frame = ctk.CTkFrame(self.main_frame, height=40, fg_color='transparent')
        self.footer_frame.pack(fill='x', padx=10, pady=5)
        self.lbl_status = ctk.CTkLabel(self.footer_frame, text='Ready', text_color='gray')
        self.lbl_status.pack(side='left')
        
        self.lbl_author = ctk.CTkLabel(self.footer_frame, text=f'Developed by: {AUTHOR}', text_color='#2ecc71', font=('Segoe UI', 11, 'italic'))
        self.lbl_author.pack(side='left', padx=20)
        
        self.btn_logs = ctk.CTkButton(self.footer_frame, text='Show Logs', width=100, height=25, fg_color='#444', hover_color='#555', command=self.toggle_logs)
        self.btn_logs.pack(side='right')
        self.log_window = ctk.CTkTextbox(self.root, height=150, text_color='#00ff00', fg_color='#111')
        
    def build_single_tab(self):
        input_frame = ctk.CTkFrame(self.tab_single, fg_color='transparent')
        input_frame.pack(fill='x', pady=10, padx=10)
        self.entry_url = ctk.CTkEntry(input_frame, placeholder_text='Paste Video URL here...', height=40, font=('Segoe UI', 12))
        self.entry_url.pack(side='left', fill='x', expand=True, padx=(0, 10))
        btn_paste = ctk.CTkButton(input_frame, text='Paste', width=80, height=40, command=self.manual_paste)
        btn_paste.pack(side='right')
        
        mid_frame = ctk.CTkFrame(self.tab_single, fg_color='transparent')
        mid_frame.pack(fill='x', padx=10, pady=10)
        opts_frame = ctk.CTkFrame(mid_frame)
        opts_frame.pack(fill='x', expand=True)
        ctk.CTkLabel(opts_frame, text='Download Options', font=('Segoe UI', 14, 'bold')).pack(pady=10)
        
        grid_inner = ctk.CTkFrame(opts_frame, fg_color='transparent')
        grid_inner.pack(fill='x', padx=20, pady=10)
        
        self.var_format = ctk.StringVar(value='video')
        self.radio_vid = ctk.CTkRadioButton(grid_inner, text='Video (MP4)', variable=self.var_format, value='video')
        self.radio_vid.grid(row=0, column=0, padx=20, pady=10, sticky='w')
        self.radio_audio = ctk.CTkRadioButton(grid_inner, text='Audio (MP3)', variable=self.var_format, value='audio')
        self.radio_audio.grid(row=0, column=1, padx=20, pady=10, sticky='w')
        
        ctk.CTkLabel(grid_inner, text='Quality Limit:').grid(row=1, column=0, padx=20, pady=5, sticky='w')
        self.combo_quality = ctk.CTkComboBox(grid_inner, values=['Best Available', '4K', '1080p', '720p', '480p'])
        self.combo_quality.grid(row=1, column=1, padx=20, pady=5, sticky='w')
        
        ctk.CTkLabel(grid_inner, text='Save Folder:').grid(row=2, column=0, padx=20, pady=15, sticky='w')
        folder_row = ctk.CTkFrame(grid_inner, fg_color='transparent')
        folder_row.grid(row=2, column=1, padx=20, pady=15, sticky='ew')
        
        self.lbl_path = ctk.CTkLabel(folder_row, text=os.getcwd()[-30:] + '...', text_color='gray', anchor='w')
        self.lbl_path.pack(side='left', fill='x', expand=True)
        self.var_path = os.getcwd()
        
        ctk.CTkButton(folder_row, text='📂', width=40, command=self.browse_folder).pack(side='right')
        ctk.CTkButton(folder_row, text='Open', width=50, fg_color='#555', hover_color='#666', command=self.open_current_folder).pack(side='right', padx=(0, 5))
        
        action_frame = ctk.CTkFrame(self.tab_single, fg_color='transparent')
        action_frame.pack(fill='x', padx=10, pady=20)
        
        self.progress_bar = TextProgressBar(action_frame, height=35, bg='#333333', fill_color='#2ecc71')
        self.progress_bar.pack(fill='x', pady=(0, 10))
        
        self.btn_start = ctk.CTkButton(action_frame, text='🚀 START DOWNLOAD', height=50, font=('Segoe UI', 16, 'bold'), fg_color='#2ecc71', hover_color='#27ae60', command=self.handle_button_click)
        self.btn_start.pack(fill='x')
        self.btn_cancel = ctk.CTkButton(action_frame, text='❌ CANCEL PROCESS', height=40, font=('Segoe UI', 12, 'bold'), fg_color='#e74c3c', hover_color='#c0392b', state='disabled', command=self.cancel_download)
        self.btn_cancel.pack(fill='x', pady=(10, 0))
        
    def build_batch_tab(self):
        ctk.CTkLabel(self.tab_batch, text='Paste multiple links (one per line):').pack(anchor='w', padx=10, pady=5)
        self.txt_batch = ctk.CTkTextbox(self.tab_batch)
        self.txt_batch.pack(fill='both', expand=True, padx=10, pady=5)
        btn_frame = ctk.CTkFrame(self.tab_batch, fg_color='transparent')
        btn_frame.pack(fill='x', padx=10, pady=10)
        ctk.CTkButton(btn_frame, text='Clear List', fg_color='#e74c3c', hover_color='#c0392b', command=lambda: self.txt_batch.delete('0.0', 'end')).pack(side='left')
        self.btn_batch_start = ctk.CTkButton(btn_frame, text='Process Queue', command=self.start_batch_download)
        self.btn_batch_start.pack(side='right')
        
    def build_settings_tab(self):
        ctk.CTkLabel(self.tab_settings, text='Application Settings', font=('Segoe UI', 16, 'bold')).pack(pady=10)
        
        self.var_clipboard = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.tab_settings, text='Auto-Paste Links from Clipboard', variable=self.var_clipboard).pack(anchor='w', padx=20, pady=5)
        
        self.var_playlist = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(self.tab_settings, text='Create Subfolder for Playlists', variable=self.var_playlist).pack(anchor='w', padx=20, pady=5)
        
        self.var_thumb_embed = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(self.tab_settings, text='Embed Thumbnail in File', variable=self.var_thumb_embed).pack(anchor='w', padx=20, pady=5)
        
        ctk.CTkLabel(self.tab_settings, text='\nAdvanced:', font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=20)
        update_frame = ctk.CTkFrame(self.tab_settings, fg_color='transparent')
        update_frame.pack(fill='x', padx=20, pady=5)
        ctk.CTkLabel(update_frame, text='Core Library (yt-dlp):').pack(side='left')
        ctk.CTkButton(update_frame, text='Check for Updates', width=120, command=self.update_core).pack(side='right')
        
    def start_clipboard_monitor(self):
        self.root.after(1000, self.check_clipboard)
        
    def check_clipboard(self):
        if self.var_clipboard.get():
            try:
                content = self.root.clipboard_get()
                if content != self.last_clipboard and ('youtube.com' in content or 'youtu.be' in content) and (self.entry_url.get() == ''):
                    self.entry_url.insert(0, content)
                    self.last_clipboard = content
            except:
                pass
        self.root.after(1500, self.check_clipboard)
        
    def manual_paste(self):
        try:
            content = self.root.clipboard_get()
            self.entry_url.delete(0, 'end')
            self.entry_url.insert(0, content)
        except:
            pass
            
    def browse_folder(self):
        path = filedialog.askdirectory()
        if path:
            self.var_path = path
            display = path if len(path) < 30 else '...' + path[-30:]
            self.lbl_path.configure(text=display)
            
    def open_current_folder(self):
        path = self.var_path
        try:
            if platform.system() == 'Windows':
                os.startfile(path)
            elif platform.system() == 'Darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except Exception as e:
            messagebox.showerror('Error', f'Could not open folder: {e}')
            
    def toggle_logs(self):
        if self.log_window.winfo_ismapped():
            self.log_window.pack_forget()
            self.btn_logs.configure(text='Show Logs', fg_color='#444')
            self.root.geometry(APP_SIZE)
        else:
            self.log_window.pack(fill='both', padx=10, pady=5, side='bottom')
            self.btn_logs.configure(text='Hide Logs', fg_color='#222')
            self.root.geometry('800x800')
            
    def update_core(self):
        self.log_message('Updating yt-dlp...')
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'yt-dlp'])
            self.log_message('Update Successful!')
            messagebox.showinfo('Updater', 'Core components updated successfully!')
        except Exception as e:
            self.log_message(f'Update Failed: {e}')
            messagebox.showerror('Error', f'Update Failed: {e}')
            
    def handle_button_click(self):
        if not self.is_downloading:
            url = self.entry_url.get().strip()
            if not url:
                return
            self.start_download([url])
        else:
            if self.is_downloading and not self.is_paused:
                self.is_paused = True
                self.btn_start.configure(text='▶ RESUME', fg_color='#f39c12')
                self.lbl_status.configure(text='Paused')
            elif self.is_downloading and self.is_paused:
                self.is_paused = False
                self.btn_start.configure(text='⏸ PAUSE', fg_color='#f39c12')
                self.lbl_status.configure(text='Resuming...')
                
    def start_batch_download(self):
        raw_text = self.txt_batch.get('0.0', 'end').strip()
        if not raw_text:
            return
        urls = [line.strip() for line in raw_text.split('\n') if line.strip()]
        self.start_download(urls)
        
    def cancel_download(self):
        if self.is_downloading:
            self.cancel_requested = True
            self.btn_cancel.configure(state='disabled', text='Stopping...')
            self.lbl_status.configure(text='Cancelling... Please wait')
            
    def start_download(self, urls):
        self.is_downloading = True
        self.is_paused = False
        self.cancel_requested = False
        self.btn_start.configure(text='⏳ INITIALIZING...', fg_color='#555', state='disabled')
        self.btn_batch_start.configure(state='disabled')
        self.btn_cancel.configure(state='normal', text='❌ CANCEL PROCESS')
        self.progress_bar.set(0)
        threading.Thread(target=self.worker, args=(urls,), daemon=True).start()
        
    def get_opts(self):
        fmt = self.var_format.get()
        qual = self.combo_quality.get()
        h_map = {'4K': 2160, '1080p': 1080, '720p': 720, '480p': 480}
        limit = h_map.get(qual)
        opts = {
            'logger': MyLogger(self.gui_queue),
            'progress_hooks': [self.progress_hook],
            'ignoreerrors': True,
            'writethumbnail': self.var_thumb_embed.get(),
            'outtmpl': os.path.join(self.var_path, '%(title)s.%(ext)s')
        }
        
        if self.var_playlist.get():
            opts['outtmpl'] = os.path.join(self.var_path, '%(playlist_title)s', '%(playlist_index)s - %(title)s.%(ext)s')
            opts['yes_playlist'] = True
        else:
            opts['noplaylist'] = True
            
        if fmt == 'audio':
            if self.has_ffmpeg:
                opts['format'] = 'bestaudio/best'
                opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]
                if self.var_thumb_embed.get():
                    opts['postprocessors'].append({'key': 'EmbedThumbnail'})
            else:
                self.log_message('⚠️ FFmpeg missing: Cannot convert to MP3. Downloading best available raw audio (m4a/webm).')
                opts['format'] = 'bestaudio/best'
            return opts
        else:
            if self.has_ffmpeg:
                if limit:
                    opts['format'] = f'bestvideo[height<={limit}]+bestaudio/best[height<={limit}][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]'
                else:
                    opts['format'] = 'bestvideo+bestaudio/best[vcodec!=none][acodec!=none]'
                opts['merge_output_format'] = 'mp4'
            else:
                self.log_message('Safe Mode: Forcing Pre-merged MP4...')
                if limit:
                    opts['format'] = f'best[height<={limit}][ext=mp4][vcodec!=none][acodec!=none]/best[height<={limit}][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]'
                else:
                    opts['format'] = 'best[ext=mp4][vcodec!=none][acodec!=none]/best[vcodec!=none][acodec!=none]'
            return opts
            
    def worker(self, urls):
        opts = self.get_opts()
        with yt_dlp.YoutubeDL(opts) as ydl:
            for idx, url in enumerate(urls):
                if self.cancel_requested:
                    break
                self.gui_queue.put(('status', f'Processing {idx + 1}/{len(urls)}...'))
                try:
                    ydl.download([url])
                    if self.cancel_requested:
                        break
                    self.log_to_history(url)
                except Exception as e:
                    if self.cancel_requested:
                        self.log_message(f'Cancelled checking {url}')
                    else:
                        self.gui_queue.put(('error', str(e)))
                        
            if self.cancel_requested:
                self.gui_queue.put(('cancelled',))
            else:
                self.gui_queue.put(('done',))
                
    def progress_hook(self, d):
        if self.cancel_requested:
            raise Exception('Download Cancelled by User')
            
        while self.is_paused:
            time.sleep(0.5)
            if self.cancel_requested:
                raise Exception('Download Cancelled by User')
                
        if d['status'] == 'downloading':
            try:
                # Remove ANSI escape codes from percentage string
                p_str = d.get('_percent_str', '0%')
                p_clean = re.sub(r'\x1b\[[0-9;]*m', '', p_str).replace('%', '').strip()
                val = float(p_clean) / 100
                
                speed = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_speed_str', 'N/A')).strip()
                eta = re.sub(r'\x1b\[[0-9;]*m', '', d.get('_eta_str', 'N/A')).strip()
                
                status = f"Downloading: {p_clean}% | Speed: {speed} | ETA: {eta}"
                self.gui_queue.put(('progress', val, status))
            except:
                pass
        elif d['status'] == 'finished':
            self.gui_queue.put(('status', 'Finalizing...'))
            self.gui_queue.put(('progress', 1.0, 'Processing...'))
            
    def log_to_history(self, url):
        try:
            timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(HISTORY_FILE, 'a', encoding='utf-8') as f:
                f.write(f'[{timestamp}] {url}\n')
        except:
            pass
            
    def log_message(self, msg):
        self.gui_queue.put(('log', msg))
        
    def process_queue(self):
        try:
            while True:
                task = self.gui_queue.get_nowait()
                m_type = task[0]
                if m_type == 'progress':
                    self.progress_bar.set(task[1])
                    self.lbl_status.configure(text=task[2])
                    if not self.is_paused and self.btn_start.cget('text') != '⏸ PAUSE':
                        self.btn_start.configure(text='⏸ PAUSE', fg_color='#f39c12', state='normal')
                elif m_type == 'status':
                    self.lbl_status.configure(text=task[1])
                elif m_type == 'log':
                    self.log_window.insert('end', task[1] + '\n')
                    self.log_window.see('end')
                elif m_type == 'done':
                    messagebox.showinfo('Success', 'All downloads completed!')
                    self.reset_ui()
                elif m_type == 'cancelled':
                    self.log_message('Process Cancelled by User.')
                    self.reset_ui()
                    self.lbl_status.configure(text='Download Cancelled')
                elif m_type == 'error':
                    messagebox.showerror('Error', task[1])
                    self.reset_ui()
                self.gui_queue.task_done()
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)
        
    def reset_ui(self):
        self.is_downloading = False
        self.is_paused = False
        self.cancel_requested = False
        self.btn_start.configure(text='🚀 START DOWNLOAD', fg_color='#2ecc71', state='normal')
        self.btn_batch_start.configure(state='normal')
        self.btn_cancel.configure(state='disabled', text='❌ CANCEL PROCESS')
        self.progress_bar.set(0)
        self.lbl_status.configure(text='Ready')

if __name__ == '__main__':
    app = ctk.CTk()
    UniversalDownloaderApp(app)
    app.mainloop()