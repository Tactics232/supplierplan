import unittest

from scripts._layout_logic import distribute_blocks


class TestDistributeBlocks(unittest.TestCase):
    """Verteilt Blöcke (mit Höhe) in N Buckets per first-fit auf das aktuell
    kleinste Bucket. Letztes Item ('cancel') landet immer im letzten Bucket."""

    def test_one_column_keine_aufteilung(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "B", "height": 80, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=1)
        self.assertEqual(len(result), 1)
        self.assertEqual([b["id"] for b in result[0]], ["A", "B"])

    def test_zwei_spalten_balanced(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "B", "height": 100, "kind": "teacher"},
            {"id": "C", "height": 80, "kind": "teacher"},
            {"id": "D", "height": 80, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=2)
        self.assertEqual(len(result), 2)
        h0 = sum(b["height"] for b in result[0])
        h1 = sum(b["height"] for b in result[1])
        # First-fit: A (100) in 0, B (100) in 1, C (80) in 0 oder 1, D restlich
        # → beide haben 180
        self.assertEqual(h0, 180)
        self.assertEqual(h1, 180)

    def test_cancel_block_kommt_in_letzte_spalte(self):
        blocks = [
            {"id": "A", "height": 100, "kind": "teacher"},
            {"id": "B", "height": 100, "kind": "teacher"},
            {"id": "C", "height": 100, "kind": "teacher"},
            {"id": "CANCEL", "height": 50, "kind": "cancel"},
        ]
        result = distribute_blocks(blocks, n_cols=3)
        # Cancel muss in der letzten Spalte sein
        last_col_ids = [b["id"] for b in result[-1]]
        self.assertIn("CANCEL", last_col_ids)

    def test_drei_spalten_first_fit(self):
        blocks = [
            {"id": "A", "height": 200, "kind": "teacher"},
            {"id": "B", "height": 50, "kind": "teacher"},
            {"id": "C", "height": 50, "kind": "teacher"},
            {"id": "D", "height": 50, "kind": "teacher"},
        ]
        result = distribute_blocks(blocks, n_cols=3)
        self.assertEqual(len(result), 3)
        # A landet in Spalte 0, B in 1, C in 2, D in (1 oder 2)
        heights = [sum(b["height"] for b in col) for col in result]
        self.assertEqual(heights[0], 200)

    def test_leere_input_liste(self):
        result = distribute_blocks([], n_cols=2)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, [[], []])


if __name__ == "__main__":
    unittest.main()
