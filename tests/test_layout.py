import unittest

from scripts._layout_logic import distribute_blocks


class TestDistributeBlocksGreedy(unittest.TestCase):
    """Block-Reihenfolge + Greedy-Fit: Lehrer alphabetisch (Eingabe-Reihenfolge)
    durchgehen, aktuelle Spalte füllen bis available-Höhe fast erreicht,
    dann nächste Spalte. Cancel-Blöcke ans Ende der letzten Spalte."""

    def test_block_reihenfolge_erhalten(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "B", "height": 100, "kind": "teacher"},
            {"id": "C", "height": 100, "kind": "teacher"},
            {"id": "D", "height": 100, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=2, available_height_per_col=250)
        # A+B = 200 ≤ 250, C würde 300 → wechsel zu Spalte 1, C+D = 200 ≤ 250
        self.assertEqual([b["id"] for b in result[0]], ["A", "B"])
        self.assertEqual([b["id"] for b in result[1]], ["C", "D"])

    def test_uebergroesse_einzelblock_bekommt_eigene_spalte(self):
        blocks = [
            {"id": "BIG", "height": 500, "kind": "teacher"},
            {"id": "small", "height": 100, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=2, available_height_per_col=300)
        # BIG passt nirgendwo, aber Spalte 0 ist leer → kommt rein
        # small würde 600 in Spalte 0 sprengen → in Spalte 1
        self.assertEqual([b["id"] for b in result[0]], ["BIG"])
        self.assertEqual([b["id"] for b in result[1]], ["small"])

    def test_cancel_immer_letzte_spalte(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "CANCEL", "height": 50, "kind": "cancel"},
        ]
        result = distribute_blocks(blocks, n_cols=3, available_height_per_col=300)
        # A in Spalte 0, Spalte 1 leer (kein weiterer regulärer Block),
        # Cancel landet in Spalte 2 (letzte)
        self.assertEqual([b["id"] for b in result[0]], ["A"])
        self.assertEqual(result[1], [])
        self.assertEqual([b["id"] for b in result[2]], ["CANCEL"])

    def test_alle_in_eine_spalte_wenn_platz_reicht(self):
        blocks = [
            {"id": "A", "height": 50, "kind": "teacher"},
            {"id": "B", "height": 50, "kind": "teacher"},
            {"id": "C", "height": 50, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=2, available_height_per_col=300)
        self.assertEqual([b["id"] for b in result[0]], ["A", "B", "C"])
        self.assertEqual(result[1], [])

    def test_leere_input_liste(self):
        result = distribute_blocks([], n_cols=2, available_height_per_col=300)
        self.assertEqual(result, [[], []])

    def test_cancel_zusammen_mit_teacher_in_letzter_spalte(self):
        blocks = [
            {"id": "A", "height": 200, "kind": "teacher"},
            {"id": "B", "height": 200, "kind": "teacher"},
            {"id": "CANCEL", "height": 80, "kind": "cancel"},
        ]
        result = distribute_blocks(blocks, n_cols=2, available_height_per_col=250)
        # A in Spalte 0, B würde 400 → wechsel zu Spalte 1
        # Cancel ans Ende der letzten = Spalte 1, nach B
        self.assertEqual([b["id"] for b in result[0]], ["A"])
        self.assertEqual([b["id"] for b in result[1]], ["B", "CANCEL"])


if __name__ == "__main__":
    unittest.main()
