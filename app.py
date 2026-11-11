"""ArenaLink desktop companion. Run with Python 3.11+."""
import json
import queue
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from core import validate, execute

PORT = 47831

class Bridge:
    def __init__(self):
        self.token = secrets.token_urlsafe(32)
        self.workspace = None
        self.pending = queue.Queue(maxsize=1)
        self.busy = threading.Lock()

    def request(self, plan):
        if not self.workspace:
            raise ValueError('Choose a workspace in ArenaLink first.')
        if not self.busy.acquire(blocking=False):
            raise ValueError('Another request is already pending.')
        try:
            root = self.workspace
            validate(root, plan)
            item = {'root': root, 'plan': plan, 'event': threading.Event(), 'expires': time.monotonic() + 120}
            self.pending.put_nowait(item)
            if not item['event'].wait(120):
                raise ValueError('Approval expired. Nothing else will run.')
            return item['result']
        finally:
            self.busy.release()

def make_server(bridge, port=PORT):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def reply(self, status, result):
            data = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass
        def do_POST(self):
            self.connection.settimeout(130)
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                return self.reply(403, {'error': 'Invalid host.'})
            supplied = self.headers.get('Authorization', '')
            if not secrets.compare_digest(supplied, 'Bearer ' + bridge.token):
                return self.reply(401, {'error': 'Invalid pairing token.'})
            if self.path != '/actions':
                return self.reply(404, {'error': 'Unknown endpoint.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 1_000_000:
                    raise ValueError('Request must be between 1 byte and 1 MB.')
                if self.headers.get_content_type() != 'application/json':
                    raise ValueError('Expected application/json.')
                data = self.rfile.read(length)
                plan = json.loads(data)
                self.reply(200, bridge.request(plan))
            except (ValueError, OSError, queue.Full) as error:
                self.reply(400, {'error': str(error)})
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    return server

class App:
    def __init__(self):
        self.bridge = Bridge()
        self.window = tk.Tk()
        self.window.title('ArenaLink · Local workspace')
        self.window.geometry('850x760')
        self.window.configure(bg='#101018')
        self.active = None
        self.label('ArenaLink', 30, '#c5adff').pack(anchor='w', padx=28, pady=(24, 0))
        self.label('Your workspace. Your approval.', 12).pack(anchor='w', padx=30, pady=(0, 18))
        self.folder = tk.StringVar(value='Choose a folder to get started')
        self.label_var(self.folder).pack(anchor='w', padx=30)
        self.button('Choose workspace', self.choose).pack(anchor='w', padx=30, pady=10)
        self.button('Copy pairing token', self.copy_token).pack(anchor='w', padx=30)
        self.status = tk.StringVar(value=f'Listening locally on 127.0.0.1:{PORT}')
        self.label_var(self.status).pack(anchor='w', padx=30, pady=14)
        self.label('Review requested actions', 15).pack(anchor='w', padx=30)
        self.preview = scrolledtext.ScrolledText(self.window, height=12, bg='#1c1c29', fg='#eeeaf8', insertbackground='white', font=('Consolas', 10))
        self.preview.pack(fill='both', expand=True, padx=30, pady=10)
        controls = tk.Frame(self.window, bg='#101018')
        controls.pack(fill='x', padx=30)
        self.approve = self.button('Approve and run', lambda: self.decide(True), controls)
        self.approve.pack(side='left', padx=(0, 10))
        self.reject = self.button('Reject', lambda: self.decide(False), controls)
        self.reject.pack(side='left')
        self.approve.configure(state='disabled')
        self.reject.configure(state='disabled')
        self.label('Results / activity', 12).pack(anchor='w', padx=30, pady=(12, 0))
        self.log = scrolledtext.ScrolledText(self.window, height=7, bg='#171720', fg='#aeb5c7', font=('Consolas', 9))
        self.log.pack(fill='x', padx=30, pady=(5, 20))
        try:
            self.server = make_server(self.bridge)
        except OSError as error:
            messagebox.showerror('ArenaLink', f'Cannot start local connection: {error}')
            self.window.destroy()
            raise SystemExit(1)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.after(150, self.poll)

    def label(self, text, size, color='#c3bfd0'):
        return tk.Label(self.window, text=text, font=('Segoe UI', size), bg='#101018', fg=color)
    def label_var(self, var):
        return tk.Label(self.window, textvariable=var, font=('Segoe UI', 10), bg='#101018', fg='#c3bfd0', wraplength=780, justify='left')
    def button(self, text, command, parent=None):
        return tk.Button(parent or self.window, text=text, command=command, bg='#7650c9', fg='white', activebackground='#946ee8', relief='flat', padx=16, pady=8, font=('Segoe UI', 10))
    def choose(self):
        if self.active or self.bridge.busy.locked():
            return messagebox.showinfo('ArenaLink', 'Finish the pending request first.')
        folder = filedialog.askdirectory()
        if folder:
            self.bridge.workspace = str(Path(folder).resolve())
            self.folder.set(self.bridge.workspace)
    def copy_token(self):
        self.window.clipboard_clear()
        self.window.clipboard_append(self.bridge.token)
        self.status.set('Token copied. Paste it into the ArenaLink extension. It changes on restart.')
    def poll(self):
        if self.active and time.monotonic() >= self.active['expires']:
            self.decide(False)
        if self.active is None:
            try:
                item = self.bridge.pending.get_nowait()
                if time.monotonic() < item['expires']:
                    self.active = item
                    self.preview.delete('1.0', 'end')
                    self.preview.insert('end', json.dumps(item['plan'], indent=2, ensure_ascii=False))
                    self.approve.configure(state='normal')
                    self.reject.configure(state='normal')
                    self.status.set('Approval required — review paths, content, and overwrite flags. Expires in 2 minutes.')
                    self.window.bell()
            except queue.Empty:
                pass
        self.window.after(150, self.poll)
    def decide(self, approved):
        if not self.active:
            return
        item = self.active
        self.active = None
        if approved and time.monotonic() < item['expires']:
            try:
                result = execute(item['root'], item['plan'])
            except (ValueError, OSError) as error:
                result = {'error': str(error)}
        else:
            result = {'error': 'Request rejected or expired.'}
        item['result'] = result
        item['event'].set()
        self.log.insert('end', json.dumps(result, ensure_ascii=False) + '\n')
        self.log.see('end')
        self.approve.configure(state='disabled')
        self.reject.configure(state='disabled')
        self.status.set('Ready for the next request.')
    def close(self):
        if self.active:
            self.decide(False)
        self.server.shutdown()
        self.server.server_close()
        self.window.destroy()
    def run(self):
        self.window.mainloop()

if __name__ == '__main__':
    App().run()
