#!/usr/bin/env python3
"""Local runner for the MLP and DL & GenAI notes. It binds only to loopback."""
import ast, base64, contextlib, io, json, re, sys, threading, traceback, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = "127.0.0.1"
PORT = 8767
NOTES_DIR = Path(__file__).resolve().parent
HTML_FILES = {
    "/MLP_Final_Notes.html": NOTES_DIR / "MLP_Final_Notes.html",
    "/DL_GenAI_Final_Notes.html": NOTES_DIR / "DL_GenAI_Final_Notes.html",
}
EXPECTED_ORIGIN = f"http://{HOST}:{PORT}"
SESSIONS = {}
SESSION_LOCK = threading.RLock()

class Handler(BaseHTTPRequestHandler):
    server_version = "StudyNotesLocal/1.0"
    def log_message(self, fmt, *args):
        # Avoid printing cell source or outputs to the terminal.
        print(fmt % args)
    
    # Renamed from 'headers' to prevent conflicting with Python's built-in self.headers property
    def send_custom_headers(self, status=200, content_type="application/json; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        
    def json_response(self, data, status=200):
        body=json.dumps(data).encode("utf-8")
        self.send_custom_headers(status)
        self.wfile.write(body)
        
    def do_GET(self):
        if self.headers.get("Host") not in (f"{HOST}:{PORT}", f"localhost:{PORT}"):
            return self.json_response({"error":"Use the localhost URL printed by the launcher."},400)
        if self.path == "/health":
            return self.json_response({"ok":True,"python":sys.version.split()[0]})
        if self.path == "/":
            self.send_response(302)
            self.send_header("Location", "/MLP_Final_Notes.html")
            self.end_headers()
            return
        html_file = HTML_FILES.get(self.path)
        if html_file is None:
            return self.json_response({"error":"Not found"},404)
        if not html_file.exists():
            return self.json_response({"error":"HTML notes file is missing"},404)
        data=html_file.read_bytes()
        self.send_custom_headers(200,"text/html; charset=utf-8")
        self.wfile.write(data)
        
    def do_POST(self):
        if self.headers.get("Origin") != EXPECTED_ORIGIN:
            return self.json_response({"error":"Request origin rejected. Open notes using the local launcher."},403)
        if self.headers.get("Host") not in (f"{HOST}:{PORT}", f"localhost:{PORT}"):
            return self.json_response({"error":"Host rejected"},403)
        try:
            length=int(self.headers.get("Content-Length","0"))
            if length<1 or length>300000:
                return self.json_response({"error":"Request is empty or too large."},413)
            payload=json.loads(self.rfile.read(length))
            session=payload.get("session","")
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,120}",session):
                return self.json_response({"error":"Invalid notebook session id."},400)
            if self.path=="/reset":
                with SESSION_LOCK: SESSIONS.pop(session,None)
                return self.json_response({"ok":True})
            if self.path!="/execute":
                return self.json_response({"error":"Not found"},404)
            code=payload.get("code","")
            if not isinstance(code,str) or len(code)>250000:
                return self.json_response({"error":"Invalid or too-large code cell."},413)
            return self.execute_cell(session,code)
        except Exception as exc:
            return self.json_response({"stdout":"","stderr":str(exc),"images":[]},400)
            
    def execute_cell(self,session,code):
        import os
        os.environ.setdefault("MPLBACKEND","Agg")
        stdout,stderr=io.StringIO(),io.StringIO()
        images=[]
        with SESSION_LOCK:
            namespace=SESSIONS.setdefault(session,{"__builtins__":__builtins__,"__name__":"__study_notes__"})
            try:
                tree=ast.parse(code,filename="<study-notes-cell>",mode="exec")
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    if tree.body and isinstance(tree.body[-1],ast.Expr):
                        last=ast.Expression(tree.body.pop().value)
                        if tree.body: exec(compile(ast.Module(body=tree.body,type_ignores=[]),"<study-notes-cell>","exec"),namespace,namespace)
                        value=eval(compile(last,"<study-notes-cell>","eval"),namespace,namespace)
                        if value is not None: print(repr(value))
                    elif tree.body:
                        exec(compile(tree,"<study-notes-cell>","exec"),namespace,namespace)
                try:
                    import matplotlib.pyplot as plt
                    for number in plt.get_fignums():
                        fig=plt.figure(number); buffer=io.BytesIO(); fig.savefig(buffer,format="png",bbox_inches="tight",dpi=120); images.append(base64.b64encode(buffer.getvalue()).decode("ascii")); plt.close(fig)
                except ImportError:
                    pass
            except BaseException:
                traceback.print_exc(file=stderr)
                try:
                    import matplotlib.pyplot as plt
                    plt.close("all")
                except Exception: pass
                return self.json_response({"stdout":stdout.getvalue(),"stderr":stderr.getvalue(),"images":images},200)
        return self.json_response({"stdout":stdout.getvalue(),"stderr":stderr.getvalue(),"images":images},200)

if __name__ == "__main__":
    server=ThreadingHTTPServer((HOST,PORT),Handler)
    url=f"http://{HOST}:{PORT}/MLP_Final_Notes.html"
    print("MLP notes:", url)
    print("DL & GenAI notes:", f"http://{HOST}:{PORT}/DL_GenAI_Final_Notes.html")
    print("Press Ctrl+C in this window to stop it.")
    try:
        threading.Timer(0.6,lambda:webbrowser.open(url)).start()
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping study notes runner.")
    finally:
        server.server_close()
