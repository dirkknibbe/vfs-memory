#!/usr/bin/env python3
"""Static security checks: no runtime deps, no banned imports, no shell/dynamic-code.

Replaces an earlier grep-based check, which was bypassable by string
concatenation. AST walk catches direct and aliased imports; the small
substring scan covers the remaining patterns.
"""
import ast
import pathlib
import subprocess
import sys
import zipfile


BANNED_IMPORTS = {
    "urllib", "urllib.request", "urllib.parse", "urllib.error",
    "http", "http.client", "http.server",
    "socket", "ssl", "ftplib", "smtplib", "telnetlib",
    "requests", "httpx", "aiohttp",
    "subprocess",
}

# Constructed at runtime so this file isn't flagged by an equivalent grep.
SHELL_CALL = "o" + "s.system("
EVAL_CALL = "e" + "val("
EXEC_CALL = "e" + "xec("
BANNED_SUBSTRINGS = (SHELL_CALL, EVAL_CALL, EXEC_CALL, "__builtins__")


def _imported_names(tree: ast.AST):
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def check_no_banned_imports(pkg_root: pathlib.Path) -> list:
    findings = []
    for py in sorted(pkg_root.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError as e:
            findings.append((py, f"unparseable: {e}"))
            continue
        for name in _imported_names(tree):
            for banned in BANNED_IMPORTS:
                if name == banned or name.startswith(banned + "."):
                    findings.append((py, name))
    return findings


def check_no_banned_substrings(pkg_root: pathlib.Path) -> list:
    findings = []
    for py in sorted(pkg_root.rglob("*.py")):
        src = py.read_text(encoding="utf-8")
        for pattern in BANNED_SUBSTRINGS:
            if pattern in src:
                findings.append((py, pattern))
    return findings


def check_no_runtime_deps(repo_root: pathlib.Path) -> list:
    dist = repo_root / "dist"
    dist.mkdir(exist_ok=True)
    for old in dist.glob("*.whl"):
        old.unlink()
    subprocess.check_call(
        [sys.executable, "-m", "build", "--wheel", "-q"],
        cwd=str(repo_root),
    )
    wheels = list(dist.glob("*.whl"))
    if not wheels:
        return [("build", "no wheel produced")]
    findings = []
    with zipfile.ZipFile(wheels[0]) as zf:
        for name in zf.namelist():
            if name.endswith("METADATA"):
                content = zf.read(name).decode("utf-8")
                for line in content.split("\n"):
                    if not line.startswith("Requires-Dist:"):
                        continue
                    # Dev/test extras are fine — they aren't runtime deps.
                    if "extra ==" in line:
                        continue
                    findings.append((wheels[0].name, line))
    return findings


def main():
    repo_root = pathlib.Path(__file__).resolve().parents[1]
    pkg_root = repo_root / "agent_vfs"
    failed = False

    print("[1/3] no banned imports (AST)")
    findings = check_no_banned_imports(pkg_root)
    if findings:
        for f, name in findings:
            print(f"  FAIL: {f}: imports {name!r}")
        failed = True
    else:
        print("  ok")

    print("[2/3] no banned substrings")
    findings = check_no_banned_substrings(pkg_root)
    if findings:
        for f, pat in findings:
            print(f"  FAIL: {f}: contains {pat!r}")
        failed = True
    else:
        print("  ok")

    print("[3/3] no runtime deps in built wheel")
    findings = check_no_runtime_deps(repo_root)
    if findings:
        for f, line in findings:
            print(f"  FAIL: {f}: {line}")
        failed = True
    else:
        print("  ok")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
