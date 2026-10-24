import unittest
from unittest.mock import patch
import radar


class GrowthTests(unittest.TestCase):
    def test_requires_a_full_history_window(self):
        repo = dict(id=1, stars=120, fetched_at='2026-10-24T12:00:00+00:00')
        short = dict(repositories=[dict(id=1, stars=100, fetched_at='2026-10-18T12:00:00+00:00')])
        self.assertIsNone(radar.growth(repo, [short], 7))

    def test_uses_identity_across_rename_and_allows_negative_growth(self):
        repo = dict(id=1, repository='new/name', stars=90, fetched_at='2026-10-24T12:00:00+00:00')
        old = dict(repositories=[dict(id=1, repository='old/name', stars=100, fetched_at='2026-10-17T12:00:00+00:00')])
        self.assertEqual(radar.growth(repo, [old], 7), -10)
        self.assertIsNone(radar.growth(repo, [old], 30))

    def test_does_not_use_stale_snapshot_or_other_repository(self):
        repo = dict(id=1, stars=120, fetched_at='2026-10-24T12:00:00+00:00')
        history = [dict(repositories=[dict(id=1, stars=100, fetched_at='2026-10-16T12:00:00+00:00'),
                                      dict(id=2, stars=10, fetched_at='2026-10-17T12:00:00+00:00')])]
        self.assertIsNone(radar.growth(repo, history, 7))

    def test_failed_lookup_is_explicit(self):
        with patch('radar.api', side_effect=RuntimeError('HTTP 404')):
            result = radar.collect_one(dict(repository='missing/repo', category='Agents', reason='test'))
        self.assertEqual(result['error'], 'HTTP 404')
        self.assertNotIn('stars', result)

    def test_empty_collection_does_not_write_report(self):
        with patch('radar.read_seeds', return_value=[dict(repository='missing/repo')]), \
             patch('radar.collect_one', return_value=dict(repository='missing/repo', error='404')), \
             patch('radar.write_json') as writer:
            with self.assertRaises(RuntimeError):
                radar.collect()
            writer.assert_not_called()


if __name__ == '__main__':
    unittest.main()
