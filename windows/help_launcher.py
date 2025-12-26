from __future__ import annotations
import socket
import threading
import subprocess
import sys
import webbrowser
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path


def _pick_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_docs_server(docs_dir: Path) -> int:
    port = _pick_free_port()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(docs_dir), **kwargs)

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return port


def open_help():
    docs_dir = Path.cwd() / ".." / "docs"
    index = docs_dir / "index.html"
    if not index.exists():
        raise FileNotFoundError(f"未找到帮助文档：{index}")

    port = _start_docs_server(docs_dir)
    url = f"http://127.0.0.1:{port}/index.html"

    try:
        subprocess.Popen(
            [sys.executable, "-m", "help_viewer", url],
            close_fds=True,
        )
        return
    except Exception:
        pass

    webbrowser.open(url)
