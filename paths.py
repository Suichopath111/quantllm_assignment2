"""统一数据、产物和本地任务目录。"""
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent

def data_directory(value=None):
    """优先显式路径、环境变量，再寻找启动目录或项目旁的行情。"""
    if value or os.environ.get("QUANTLAB_DATA"):
        return Path(value or os.environ["QUANTLAB_DATA"]).expanduser().resolve()
    candidates = (Path.cwd()/"feathers", ROOT/"feathers", ROOT.parent/"feathers")
    return next((p.resolve() for p in candidates if (p/"close.feather").is_file()), candidates[-1].resolve())

def state_directory(value=None):
    return Path(value or os.environ.get("QUANTLAB_STATE") or ROOT/".web-state").resolve()
