import json
import os
import threading

from agent_vfs.diagnostic import DiagnosticLog


def test_append_one(tmp_path):
    log = DiagnosticLog(str(tmp_path / "diag.log"))
    log.append({"op": "write", "key": "foo"})
    with open(tmp_path / "diag.log") as fp:
        line = fp.readline()
    rec = json.loads(line)
    assert rec["op"] == "write"
    assert rec["key"] == "foo"
    assert "ts" in rec
    assert rec["caller_pid"] == os.getpid()


def test_concurrent_appends_well_formed(tmp_path):
    log_path = str(tmp_path / "diag.log")
    log = DiagnosticLog(log_path)
    N = 50

    def worker(i):
        log.append({"op": "write", "key": f"k{i}"})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    with open(log_path) as fp:
        lines = fp.readlines()
    assert len(lines) == N
    parsed = [json.loads(line) for line in lines]
    keys = sorted(p["key"] for p in parsed)
    assert keys == sorted(f"k{i}" for i in range(N))


def test_rotation(tmp_path, monkeypatch):
    log_path = str(tmp_path / "diag.log")
    monkeypatch.setenv("VFS_MAX_DIAGNOSTIC_LOG_BYTES", "200")
    log = DiagnosticLog(log_path)
    for i in range(20):
        log.append({"op": "write", "key": f"k{i:04d}"})
    assert os.path.exists(log_path)
    assert os.path.exists(log_path + ".1")
