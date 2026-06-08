"""
_layout_logic.py – Verteilung von Render-Blöcken in N Spalten (Greedy-Fit).
Dient als testbarer Python-Mirror der JS-Layout-Engine im Browser.
"""

from typing import Iterable


def distribute_blocks(blocks: Iterable[dict], n_cols: int,
                       available_height_per_col: int = None) -> list:
    """Verteilt Blöcke in n_cols Spalten per Greedy-Fit von links nach rechts.
    Reihenfolge der Blöcke bleibt erhalten (top-down). Cancel-Blöcke
    (`kind == "cancel"`) landen am Ende der letzten Spalte.

    Wenn `available_height_per_col` None oder <= 0 ist, packt alles in Spalte 0
    (degenerierter Fall, sollte nicht produktiv passieren).
    """
    if n_cols < 1:
        n_cols = 1

    regular = [b for b in blocks if b.get("kind") != "cancel"]
    cancels = [b for b in blocks if b.get("kind") == "cancel"]

    buckets = [[] for _ in range(n_cols)]

    if not available_height_per_col or available_height_per_col <= 0:
        # Degeneriert: alles in Spalte 0
        buckets[0] = regular[:]
    else:
        current_col = 0
        current_height = 0
        for block in regular:
            block_h = block.get("height", 0)
            # Würde dieser Block die aktuelle Spalte sprengen?
            # Aber: nur wechseln, wenn die Spalte nicht leer ist (sonst hat ein
            # Übergrößer-Block keinen Platz und würde übersprungen werden).
            if (current_height + block_h > available_height_per_col
                    and current_col < n_cols - 1
                    and len(buckets[current_col]) > 0):
                current_col += 1
                current_height = 0
            buckets[current_col].append(block)
            current_height += block_h

    # Cancel-Blöcke ans Ende der letzten Spalte
    for block in cancels:
        buckets[-1].append(block)

    return buckets


def fit_scale(content_height, available_height, scale_min, step=0.05):
    """Größter Skalierungsfaktor in {1.0, 1-step, ...} >= scale_min, bei dem
    content_height * faktor <= available_height. Passt es schon bei 1.0, kommt
    1.0 zurück; passt es selbst bei scale_min nicht, kommt scale_min zurück."""
    if content_height <= 0 or content_height <= available_height:
        return 1.0
    if available_height <= 0:
        return round(scale_min, 4)
    steps = int(round((1.0 - scale_min) / step))
    for i in range(steps + 1):
        s = round(1.0 - i * step, 4)
        if content_height * s <= available_height:
            return s
    return round(scale_min, 4)


def distribute_uncapped(block_heights, available_height_per_col):
    """Greedy-Verteilung in BELIEBIG viele Spalten (kein MAX_COLS-Limit).
    Gibt eine Liste von Spalten zurück, jede Spalte eine Liste von Block-Indizes.
    Ein übergroßer Block bekommt eine eigene Spalte (kein Überspringen)."""
    cols = [[]]
    h = 0
    for i, bh in enumerate(block_heights):
        if cols[-1] and h + bh > available_height_per_col:
            cols.append([])
            h = 0
        cols[-1].append(i)
        h += bh
    return cols
