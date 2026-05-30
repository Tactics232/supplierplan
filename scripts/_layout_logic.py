"""
_layout_logic.py – Verteilung von Render-Blöcken in N Spalten (first-fit-min).
Dient als testbarer Python-Mirror der JS-Layout-Engine im Browser.
"""

from typing import Iterable


def distribute_blocks(blocks: Iterable[dict], n_cols: int) -> list:
    """Verteilt `blocks` (jeweils mit `height` und `kind`) auf `n_cols` Buckets.
    Algorithmus: First-fit-min — jeder Block kommt in das gerade kleinste Bucket.
    Sonderfall: Block mit `kind == "cancel"` wird zwingend in das letzte Bucket
    eingefügt (am Ende), egal welche Höhe die anderen haben.
    """
    if n_cols < 1:
        n_cols = 1

    buckets = [[] for _ in range(n_cols)]
    heights = [0] * n_cols

    for block in blocks:
        if block.get("kind") == "cancel":
            # Cancel separat behandeln (am Ende anhängen)
            continue
        # Index des Buckets mit geringster aktueller Höhe
        idx = heights.index(min(heights))
        buckets[idx].append(block)
        heights[idx] += block.get("height", 0)

    # Cancel-Block(s) ans Ende der letzten Spalte
    for block in blocks:
        if block.get("kind") == "cancel":
            buckets[-1].append(block)

    return buckets
