#!/usr/bin/env python3
"""Generate docs/CODEMAP.md — an auto-maintained function index for AI/human navigation.

Parses every tracked Python module with `ast` and emits, per module, a table of its
top-level functions and classes: line number, signature, and the first docstring line.
Deterministic (sorted) so re-runs produce stable diffs. Run by the git pre-commit hook
on every commit; the narrative "why" lives in CLAUDE.md, not here.

Usage:  python scripts/gen_codemap.py        # writes docs/CODEMAP.md
        python scripts/gen_codemap.py --check # exit 1 if the file is out of date
"""
import ast
import os
import sys

# Repo root = parent of this script's directory.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "CODEMAP.md")

# Directories to scan (relative to ROOT). __pycache__ and api_dump are skipped.
SCAN_DIRS = ["scripts", "tray"]
SKIP_DIR_NAMES = {"__pycache__", "api_dump"}


def py_files():
    """Yield repo-relative paths of all .py files under SCAN_DIRS, sorted."""
    found = []
    for d in SCAN_DIRS:
        base = os.path.join(ROOT, d)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x not in SKIP_DIR_NAMES]
            for fn in filenames:
                if fn.endswith(".py"):
                    rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
                    found.append(rel.replace(os.sep, "/"))
    return sorted(found)


def _ann(node):
    """Render an annotation/expression node back to source, best-effort."""
    if node is None:
        return ""
    try:
        return ast.unparse(node)  # Python 3.9+
    except Exception:
        return ""


def format_signature(args):
    """Reconstruct a readable parameter list from an ast.arguments node."""
    parts = []
    posonly = getattr(args, "posonlyargs", [])
    positional = posonly + args.args
    # Defaults align to the right of the positional args.
    defaults = list(args.defaults)
    n_no_default = len(positional) - len(defaults)
    for i, a in enumerate(positional):
        piece = a.arg
        ann = _ann(a.annotation)
        if ann:
            piece += ": " + ann
        if i >= n_no_default:
            piece += "=" + _ann(defaults[i - n_no_default])
        parts.append(piece)
        if posonly and a is posonly[-1]:
            parts.append("/")
    if args.vararg:
        parts.append("*" + args.vararg.arg)
    elif args.kwonlyargs:
        parts.append("*")
    for a, d in zip(args.kwonlyargs, args.kw_defaults):
        piece = a.arg
        ann = _ann(a.annotation)
        if ann:
            piece += ": " + ann
        if d is not None:
            piece += "=" + _ann(d)
        parts.append(piece)
    if args.kwarg:
        parts.append("**" + args.kwarg.arg)
    return ", ".join(parts)


def first_doc_line(node):
    """First non-empty line of a node's docstring, or '' if none."""
    doc = ast.get_docstring(node)
    if not doc:
        return ""
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def md_escape(s):
    """Escape the few characters that would break a Markdown table cell."""
    return s.replace("|", "\\|").replace("\n", " ")


def collect(path):
    """Return (module_doc, rows) for one file. rows = (lineno, label, sig, summary)."""
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        src = fh.read()
    tree = ast.parse(src, filename=path)
    module_doc = first_doc_line(tree)
    rows = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sig = format_signature(node.args)
            rows.append((node.lineno, node.name, sig, first_doc_line(node)))
        elif isinstance(node, ast.ClassDef):
            rows.append((node.lineno, "class " + node.name, "", first_doc_line(node)))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig = format_signature(sub.args)
                    rows.append((sub.lineno, node.name + "." + sub.name, sig,
                                 first_doc_line(sub)))
    rows.sort(key=lambda r: r[0])
    return module_doc, rows


def render():
    """Build the full CODEMAP.md text."""
    out = []
    out.append("# Code Map")
    out.append("")
    out.append("> **Auto-generated** by `scripts/gen_codemap.py` — do not edit by hand.")
    out.append("> Regenerated on every commit (git pre-commit hook). The narrative *why*")
    out.append("> (heuristics, design decisions) lives in [`CLAUDE.md`](../CLAUDE.md);")
    out.append("> deep internals in [`docs/index.html`](index.html). This file is the")
    out.append("> **navigation index**: find the right function here, then open the code.")
    out.append("")
    files = py_files()
    # Table of contents.
    out.append("## Modules")
    out.append("")
    for path in files:
        anchor = path.replace("/", "").replace(".", "").replace("_", "")
        out.append("- [`{}`](#{})".format(path, anchor))
    out.append("")
    total_funcs = 0
    for path in files:
        module_doc, rows = collect(path)
        n_funcs = sum(1 for r in rows if not r[1].startswith("class "))
        total_funcs += n_funcs
        anchor = path.replace("/", "").replace(".", "").replace("_", "")
        out.append('<h2 id="{}">{}</h2>'.format(anchor, path))
        out.append("")
        if module_doc:
            out.append("_{}_".format(md_escape(module_doc)))
            out.append("")
        if not rows:
            out.append("_(no top-level functions or classes)_")
            out.append("")
            continue
        out.append("| Line | Definition | Summary |")
        out.append("|---:|---|---|")
        for lineno, label, sig, summary in rows:
            if label.startswith("class "):
                name = "**`{}`**".format(label)
            elif "." in label:
                name = "&nbsp;&nbsp;`{}({})`".format(label, sig)
            else:
                name = "`{}({})`".format(label, sig)
            out.append("| {} | {} | {} |".format(lineno, md_escape(name),
                                                 md_escape(summary) or "—"))
        out.append("")
    out.insert(1, "")
    out.insert(2, "_{} functions across {} modules._".format(total_funcs, len(files)))
    return "\n".join(out).rstrip() + "\n"


def main():
    text = render()
    check = "--check" in sys.argv
    if check:
        try:
            with open(OUT, encoding="utf-8") as fh:
                current = fh.read()
        except FileNotFoundError:
            current = None
        if current != text:
            sys.stderr.write("CODEMAP.md is out of date — run python scripts/gen_codemap.py\n")
            return 1
        return 0
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    sys.stderr.write("wrote {}\n".format(os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
