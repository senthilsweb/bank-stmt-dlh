"""Export the public copy of this repo (maintainers only).

    python scripts/publish_public.py [--push] [--dry-run]

Reads config/publish.yaml (private, never exported): the public repo directory, the commit identity, paths to exclude,
overlays (private file or folder -> public path, e.g. config/examples -> config, a public README, public logos),
text replacements (private names -> public names, applied to file contents and file names) and lines to drop.

Steps: copy the tracked files of the current branch into a temp tree with those rules; build a deny list at run time
(every real name in the excluded config files, every .env value, every replacement key, hosts and git authors; nothing
personal is stored in this script); scan every text file and stop on the first hit (value masked); then sync into
the public repo and commit "sync: <sha> from private repo". --push pushes main. The first export is one squashed
commit, so the private history never leaves. Spec: openspec/changes/public-release.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from dotenv import dotenv_values, load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import settings  # noqa: E402

CFG_FILE = ROOT / "config" / "publish.yaml"
TEXT_EXT = {".py", ".md", ".yaml", ".yml", ".sql", ".json", ".toml", ".sample", ".txt", ".cfg", ".ini", ".lock", ".svg", ".html", ""}
BINARY_NAMES: set[str] = set()   # uv.lock is text too: its project name must follow pyproject
# .env keys whose values legitimately appear in the public tree (names, not secrets)
ENV_PUBLIC_KEYS = {"DATABRICKS_CATALOG", "MINIO_BUCKET", "SP_LIBRARY", "MAIL_MODE", "PUBLIC_REPO_DIR", "PUBLIC_GIT_AUTHOR"}
GENERIC = {"health", "starhealth", "star", "office", "rent", "auditor", "fee", "yearly", "monthly", "credit", "debit",
           "consultancy", "limited", "private", "india", "bank", "payout", "transfer", "operations", "techno",
           "technologies", "technology", "kumar"}
SECRET_PATTERNS = [re.compile(p) for p in (r"dapi[0-9a-f]{20,}", r"AKIA[0-9A-Z]{16}", r"-----BEGIN [A-Z ]*PRIVATE KEY-----", r"ghp_[A-Za-z0-9]{30,}")]


def git(*args: str, cwd: Path = ROOT) -> str:
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def load_cfg() -> dict:
    if not CFG_FILE.exists():
        sys.exit(f"{CFG_FILE.relative_to(ROOT)} missing (see config/examples/publish.yaml)")
    cfg = yaml.safe_load(CFG_FILE.read_text()) or {}
    for k, d in (("exclude", []), ("overlays", {}), ("replace", {}), ("drop_lines", []), ("deny", [])):
        cfg.setdefault(k, d)
    cfg["exclude"] = [str(e) for e in cfg["exclude"]] + [str(s) + ("/" if (ROOT / s).is_dir() else "") for s in cfg["overlays"]] + ["config/publish.yaml"]
    cfg["replace"] = sorted(((str(a), str(b)) for a, b in cfg["replace"].items()), key=lambda ab: -len(ab[0]))
    return cfg


def is_text(p: Path) -> bool:
    return p.suffix in TEXT_EXT and p.name not in BINARY_NAMES


def transform(text: str, cfg: dict) -> str:
    lines = [ln for ln in text.splitlines(keepends=True) if not any(d in ln for d in cfg["drop_lines"])]
    text = "".join(lines)
    for a, b in cfg["replace"]:
        text = text.replace(a, b)
    return text


def public_path(rel: str, cfg: dict) -> str:
    for a, b in cfg["replace"]:
        rel = rel.replace(a, b)
    return rel


def copy_one(src: Path, dst: Path, cfg: dict) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if is_text(src):
        dst.write_text(transform(src.read_text(errors="replace"), cfg))
    else:
        shutil.copy2(src, dst)


def export_tree(dest: Path, cfg: dict) -> list[Path]:
    excluded = lambda f: any(f == e.rstrip("/") or (e.endswith("/") and f.startswith(e)) for e in cfg["exclude"])
    out = []
    for f in git("ls-files").splitlines():
        if excluded(f):
            continue
        dst = dest / public_path(f, cfg)
        copy_one(ROOT / f, dst, cfg)
        out.append(dst)
    for src_rel, dst_rel in cfg["overlays"].items():
        src = ROOT / src_rel
        pairs = [(p, dest / public_path(dst_rel, cfg) / p.relative_to(src)) for p in sorted(src.rglob("*")) if p.is_file()] if src.is_dir() else [(src, dest / public_path(dst_rel, cfg))]
        for s, d in pairs:
            copy_one(s, d, cfg)
            out.append(d)
    return sorted(set(out))


def deny_terms(cfg: dict) -> dict[str, str]:
    """term -> label, built at run time and never stored."""
    terms: dict[str, str] = {}
    private_company = settings.load()["company_name"].lower()
    author = cfg.get("git_author") or os.environ.get("PUBLIC_GIT_AUTHOR") or ""
    allowed = {t.strip().lower() for t in re.split(r"[<>]", author) if t.strip()}

    def words(x, label):
        if isinstance(x, dict):
            for v in x.values():
                words(v, label)
        elif isinstance(x, list):
            for v in x:
                words(v, label)
        elif isinstance(x, str):
            s = x[3:] if x.startswith("re:") else x
            for w in re.split(r"[^A-Za-z]+", re.sub(r"\\[sSwd]\*?", " ", s)):
                if len(w) >= 5 and w.upper() == w and w.lower() not in GENERIC:
                    terms[w] = label

    for f in cfg["exclude"]:
        p = ROOT / f
        if p.is_file() and p.suffix in (".yaml", ".yml") and p.name != "publish.yaml":
            words(yaml.safe_load(p.read_text()) or {}, f)
    env = dotenv_values(ROOT / ".env") if (ROOT / ".env").exists() else {}
    for k, v in env.items():
        v = (v or "").strip()
        if len(v) < 6 or k in ENV_PUBLIC_KEYS:
            continue
        terms[v] = f".env {k}"
        host = re.sub(r"^https?://", "", v).split("/")[0]
        if "." in host and len(host) >= 6:
            terms[host] = f".env {k}"
            if len(host.split(".")[0]) >= 6:
                terms[host.split(".")[0]] = f".env {k}"
        if "@" in v:
            for part in re.split(r"[,|]", v):
                if len(part.strip()) >= 6:
                    terms[part.strip()] = f".env {k}"
    for t in git("log", "--all", "--format=%ae%n%an").splitlines():
        t = t.strip()
        if len(t) >= 6 and "noreply" not in t and t.lower() != private_company and ("@" in t or " " in t):
            terms[t] = "git author"
    for a, _ in cfg["replace"]:
        if len(a) >= 3:
            terms[a] = "replace key"
    terms[private_company] = "private company name"
    for t in cfg.get("deny") or []:
        terms[str(t)] = "deny list"
    return {t: l for t, l in terms.items() if t.lower() not in allowed}


def scan(dest: Path, files: list[Path], terms: dict[str, str]) -> int:
    hits = 0
    for p in files:
        if not is_text(p):
            continue
        for n, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            low = line.lower()
            for term, label in terms.items():
                if term.lower() in low:
                    print(f"HIT {p.relative_to(dest)}:{n}  {label}  ({term[:2]}{'*' * max(3, len(term) - 2)})")
                    hits += 1
            for rx in SECRET_PATTERNS:
                if rx.search(line):
                    print(f"HIT {p.relative_to(dest)}:{n}  secret pattern {rx.pattern[:20]}")
                    hits += 1
        if any(t.lower() in str(p.relative_to(dest)).lower() for t in terms):
            print(f"HIT path {p.relative_to(dest)}")
            hits += 1
    return hits


def main(argv: list[str]) -> int:
    load_dotenv(ROOT / ".env")
    cfg = load_cfg()
    target = Path(os.environ.get("PUBLIC_REPO_DIR") or cfg.get("public_repo_dir") or "../public-copy")
    target = (ROOT / target).resolve() if not target.is_absolute() else target
    sha, branch = git("rev-parse", "--short", "HEAD"), git("branch", "--show-current")
    if git("status", "--porcelain"):
        print("working tree not clean: commit first so the export matches a commit")
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "tree"
        files = export_tree(tree, cfg)
        terms = deny_terms(cfg)
        print(f"exported {len(files)} files from {branch}@{sha}; scanning with {len(terms)} deny terms")
        hits = scan(tree, files, terms)
        if hits:
            print(f"{hits} hit(s): nothing written to {target}")
            return 1
        print("scan clean")
        if "--dry-run" in argv:
            print(f"dry run: would sync to {target}")
            return 0
        target.mkdir(parents=True, exist_ok=True)
        if not (target / ".git").exists():
            git("init", "-q", "-b", "main", cwd=target)
        for item in target.iterdir():
            if item.name not in (".git", ".venv"):
                shutil.rmtree(item) if item.is_dir() else item.unlink()
        for p in files:
            rel = p.relative_to(tree)
            (target / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target / rel)
        git("add", "-A", cwd=target)
        if git("status", "--porcelain", cwd=target):
            author = cfg.get("git_author") or os.environ.get("PUBLIC_GIT_AUTHOR") or "Maintainer <maintainer@users.noreply.github.com>"
            name, email = re.match(r"(.*?)\s*<(.+)>", author).groups()
            git("-c", f"user.name={name}", "-c", f"user.email={email}", "commit", "-q", "-m", f"sync: {sha} from private repo", cwd=target)
            print(f"committed in {target}: {git('log', '--oneline', '-1', cwd=target)}")
        else:
            print("no change since the last export")
        if "--push" in argv:
            subprocess.check_call(["git", "push", "-u", "origin", "main"], cwd=target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
