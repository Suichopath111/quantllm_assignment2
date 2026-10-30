"""SQLite任务记录与单进程回测队列。"""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4
from quantlab.paths import ROOT


def now():
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "runs.sqlite3"
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, strategy TEXT NOT NULL,
                status TEXT NOT NULL, config TEXT NOT NULL, folder TEXT NOT NULL,
                created_at TEXT NOT NULL, started_at TEXT, finished_at TEXT, error TEXT
            )""")

    def connect(self):
        conn = sqlite3.connect(self.db, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def list(self):
        with self.connect() as conn:
            return [self.decode(row) for row in conn.execute("SELECT * FROM runs ORDER BY created_at DESC, id")]

    @staticmethod
    def decode(row):
        result = dict(row)
        result["config"] = json.loads(result["config"])
        return result

    def get(self, identifier):
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (identifier,)).fetchone()
        return self.decode(row) if row else None

    def add(self, identifier, name, strategy, config, folder, status="queued"):
        with self.connect() as conn:
            conn.execute("INSERT OR IGNORE INTO runs VALUES (?,?,?,?,?,?,?,?,?,?)", (identifier,name,strategy,status,json.dumps(config,ensure_ascii=False),str(Path(folder).resolve()),now(),None,now() if status=="completed" else None,None))

    def update(self, identifier, **fields):
        allowed = {"status", "started_at", "finished_at", "error"}
        if not fields or not set(fields) <= allowed:
            raise ValueError("无效的任务更新字段")
        with self.connect() as conn:
            conn.execute("UPDATE runs SET " + ",".join(f"{key}=?" for key in fields) + " WHERE id=?", [*fields.values(),identifier])

    def interrupt_unfinished(self):
        with self.connect() as conn:
            conn.execute("UPDATE runs SET status='interrupted', finished_at=?, error='服务上次退出时任务尚未完成，请重新提交' WHERE status IN ('running','queued')",(now(),))


class JobManager:
    def __init__(self, store, data_dir):
        self.store = store
        self.data_dir = Path(data_dir).resolve()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="backtest")
        self.lock = threading.RLock()
        self.processes = {}
        self.closed = False

    def submit(self, payload):
        with self.lock:
            if self.closed:
                raise RuntimeError("服务正在关闭")
            if sum(r["status"] in ("queued","running") for r in self.store.list()) >= 10:
                raise ValueError("回测队列已满，请等待已有任务完成")
            identifier = uuid4().hex
            folder = self.store.root / "runs" / identifier
            folder.mkdir(parents=True)
            (folder / "request.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
            self.store.add(identifier,payload["name"],payload["strategy"],payload["config"],folder)
            self.pool.submit(self._execute,identifier)
            return self.store.get(identifier)

    def _execute(self, identifier):
        folder = Path(self.store.get(identifier)["folder"])
        try:
            with self.lock:
                row = self.store.get(identifier)
                if self.closed or row["status"] != "queued":
                    return
                self.store.update(identifier,status="running",started_at=now())
                log = (folder / "worker.log").open("w",encoding="utf-8")
                try:
                    process = subprocess.Popen([sys.executable,"-u","-m","quantlab.webapp.worker","--data",str(self.data_dir),"--output",str(folder)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,"PYTHONIOENCODING":"utf-8"},creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
                except Exception:
                    log.close()
                    raise
                self.processes[identifier] = process
            try:
                code = process.wait()
            finally:
                log.close()
            with self.lock:
                self.processes.pop(identifier,None)
                if self.store.get(identifier)["status"] != "running":
                    return
                if code == 0 and (folder / "summary.json").exists():
                    self.store.update(identifier,status="completed",finished_at=now())
                else:
                    error_path = folder / "error.json"
                    error = json.loads(error_path.read_text(encoding="utf-8"))["error"] if error_path.exists() else f"回测进程异常退出（{code}），详见本地worker.log"
                    self.store.update(identifier,status="failed",finished_at=now(),error=error)
        except Exception as exc:
            with self.lock:
                self.processes.pop(identifier,None)
                if self.store.get(identifier)["status"] not in ("cancelled","interrupted"):
                    self.store.update(identifier,status="failed",finished_at=now(),error=str(exc))

    def cancel(self, identifier):
        with self.lock:
            row = self.store.get(identifier)
            if row is None:
                raise KeyError(identifier)
            if row["status"] not in ("queued","running"):
                raise ValueError("该任务已结束")
            self.store.update(identifier,status="cancelled",finished_at=now())
            process = self.processes.get(identifier)
            if process and process.poll() is None:
                process.terminate()

    def close(self):
        with self.lock:
            self.closed = True
            for identifier,process in self.processes.items():
                self.store.update(identifier,status="interrupted",finished_at=now(),error="服务关闭，回测已中断")
                if process.poll() is None:
                    process.terminate()
            for row in self.store.list():
                if row["status"]=="queued":
                    self.store.update(row["id"],status="interrupted",finished_at=now(),error="服务关闭，排队任务已中断")
        self.pool.shutdown(wait=True,cancel_futures=True)
