"""Offline checks using synthetic observations, with no reference music."""
from pathlib import Path
import csv
import tempfile
import unittest

from generator import export_collection, load_palettes, load_rows, select_sets


class SoundSetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.folder = Path(temporary.name)
        self.source = self.folder / 'synthetic.csv'
        with self.source.open('w', encoding='utf-8', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(['scope', 'rank', 'track_id', 'title', 'producer', 'bpm', 'tags', 'ad'])
            writer.writerow(['all_time', 1, '100', 'Synthetic trap study', 'Test fixture', 140, 'trap', ''])
            writer.writerow(['all_time', 2, '101', 'Advertisement fixture', 'Test fixture', 140, 'trap', 'yes'])

    def test_ads_excluded_and_original_source_unchanged(self):
        original = self.source.read_bytes()
        rows = load_rows(self.source)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['track_id'], '100')
        self.assertEqual(self.source.read_bytes(), original)

    def test_synthetic_palette_export_has_midi_roles_and_unique_folders(self):
        rows, palettes = load_rows(self.source), load_palettes()
        active, unmatched = select_sets(rows, palettes)
        self.assertTrue(active)
        self.assertFalse(unmatched)
        first, report = export_collection(self.folder / 'exports', rows, palettes, '2026-01-01')
        second, _ = export_collection(self.folder / 'exports', rows, palettes, '2026-01-01')
        self.assertNotEqual(first, second)
        self.assertEqual(report['sets'], len(active))
        midi_files = list(first.rglob('*.mid'))
        self.assertEqual(len(midi_files), len(active))
        self.assertTrue(all(path.read_bytes().startswith(b'MThd') for path in midi_files))
        self.assertEqual(len(list(first.rglob('Roles.json'))), len(active))
        self.assertTrue((first / 'START HERE.html').is_file())

    def test_header_only_template_requests_observations(self):
        with self.assertRaisesRegex(ValueError, 'No non-ad'):
            load_rows(Path(__file__).parent / 'observations.example.csv')

    def test_startup_without_a_private_snapshot_is_normal(self):
        from soundset_app import SoundSetApp
        class Value:
            def set(self, value):
                self.value = value
        app = object.__new__(SoundSetApp)
        app.source_path = self.folder / 'not-bundled.csv'
        app.status = Value()
        app.summary = Value()
        app._refresh_sets = lambda: None
        app._load_initial()
        self.assertTrue(app.palettes)
        self.assertIn('No chart data is bundled', app.status.value)


if __name__ == '__main__':
    unittest.main()
