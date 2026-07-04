"""Laesst die JS-Layout-Core-Tests (node --test) im selben `python -m unittest`
Lauf mitlaufen. Findet node mit denselben Fallbacks wie der pre-commit-Hook;
ist keiner da -> LAUT skippen (nicht gruen durchwinken)."""
import glob
import os
import shutil
import subprocess
import unittest

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JS_TESTS = os.path.join(_HERE, "tests", "js")


def _find_node():
    cand = os.environ.get("SUPPLIERPLAN_NODE") or shutil.which("node")
    if cand and (cand == "node" or os.path.exists(cand)):
        return cand
    for p in (os.path.expanduser("~/.local/bin/node"), "/usr/bin/node"):
        if os.path.exists(p):
            return p
    return None


class TestLayoutCoreJS(unittest.TestCase):
    def test_node_layout_suite_passes(self):
        node = _find_node()
        if not node:
            self.skipTest("node fehlt — Layout-Core-Tests uebersprungen "
                          "(installiere node oder setze SUPPLIERPLAN_NODE)")
        test_files = sorted(glob.glob(os.path.join(_JS_TESTS, "*.test.js")))
        self.assertTrue(test_files, "keine *.test.js in tests/js gefunden")
        proc = subprocess.run(
            [node, "--test"] + test_files,
            cwd=_HERE, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(
            proc.returncode, 0,
            "node --test tests/js/*.test.js fehlgeschlagen:\n"
            + proc.stdout + "\n" + proc.stderr,
        )


if __name__ == "__main__":
    unittest.main()
