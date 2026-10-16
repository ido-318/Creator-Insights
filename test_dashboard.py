"""Behavior checks for filters, source selection and optional private persistence."""
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import httpx
from streamlit.testing.v1 import AppTest

from dashboard_data import ARTIFACTS, POST_TYPES, filter_posts, load_local
from dashboard_theme import build_theme, read_config, save_theme
from supabase_store import StoreConfig, StoreError, SupabaseStore, build_snapshot, get_config


class DashboardTests(unittest.TestCase):
    def app(self):
        with patch.dict('os.environ', {'SUPABASE_URL': '', 'SUPABASE_SECRET_KEY': '', 'SUPABASE_SERVICE_ROLE_KEY': ''}):
            return AppTest.from_file('app.py', default_timeout=30).run()

    def test_initial_overview_uses_real_metrics(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '499')
        self.assertEqual(app.metric[1].value, '105,941')

    def test_filter_updates_metrics_and_empty_state_recovers(self):
        app = self.app()
        app.multiselect(key='types').set_value(['Video']).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '7')
        app.multiselect(key='types').set_value([]).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 0)
        self.assertTrue(any('אין פוסטים' in item.value for item in app.info))
        next(b for b in app.button if b.label == 'הצגת כל הפוסטים').click().run()
        self.assertEqual(app.metric[0].value, '499')

    def test_all_pages_and_missing_cloud(self):
        app = self.app()
        for page in ['חקר נתונים', 'מעבדת מודלים', 'דוחות', 'מערכת']:
            app.radio(key='page').set_value(page).run()
            self.assertFalse(app.exception, page)
        app.selectbox(key='source').set_value('Supabase').run()
        self.assertFalse(app.exception)
        app.radio(key='page').set_value('סקירה').run()
        self.assertFalse(app.exception)
        self.assertTrue(app.warning)

    def test_combined_filters(self):
        df, _, _ = load_local()
        actual = filter_posts(df, ['Photo'], (4, 8), 'ממומן')
        expected = df[(df.post_type == 'Photo') & df.post_month.between(4, 8) & (df.paid == 1)]
        self.assertEqual(actual.to_dict('records'), expected.to_dict('records'))

    def test_palette_updates_session_without_mutating_config(self):
        before = read_config()
        app = self.app()
        app.selectbox(key='palette').set_value('איריס').run()
        self.assertEqual(app.session_state.primary, '#6546C7')
        self.assertEqual(read_config(), before)
        self.assertFalse(app.exception)

    def test_native_theme_persistence_and_contrast(self):
        config = build_theme(read_config(), '#6546C7', '#087F8C', True)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            save_theme(config, path)
            self.assertEqual(read_config(path)['theme']['base'], 'dark')
            self.assertEqual(read_config(path)['theme']['primaryColor'], '#6546C7')
        with self.assertRaises(ValueError):
            build_theme(read_config(), '#FFFFFF', '#087F8C')


class SupabaseTests(unittest.TestCase):
    def test_config_rejects_insecure_or_public_credentials(self):
        for url, key in [('http://example.com', 'secret'), ('https://example.com/path', 'secret'), ('https://example.com', 'sb_publishable_test')]:
            with self.assertRaises(StoreError):
                get_config({'SUPABASE_URL': url, 'SUPABASE_SECRET_KEY': key})

    def test_secret_never_appears_in_repr_or_error(self):
        config = StoreConfig('https://example.supabase.co', 'sb_secret_private')
        self.assertNotIn('sb_secret_private', repr(config))
        request = httpx.Request('GET', config.url)
        response = httpx.Response(401, request=request, text='sb_secret_private')
        with patch('supabase_store.httpx.request', return_value=response):
            with self.assertRaises(StoreError) as caught:
                SupabaseStore(config).check()
        self.assertNotIn('sb_secret_private', str(caught.exception))

    def test_new_secret_key_is_not_used_as_jwt(self):
        config = StoreConfig('https://example.supabase.co', 'sb_secret_private')
        with patch('supabase_store.httpx.request', return_value=httpx.Response(200, json=[], request=httpx.Request('GET', config.url))) as call:
            SupabaseStore(config).check()
        self.assertEqual(call.call_args.kwargs['headers']['apikey'], config.key)
        self.assertNotIn('Authorization', call.call_args.kwargs['headers'])

    def test_network_failure_is_safe(self):
        with patch('supabase_store.httpx.request', side_effect=httpx.ConnectError('secret details')):
            with self.assertRaises(StoreError) as caught:
                SupabaseStore(StoreConfig('https://example.supabase.co', 'secret')).check()
        self.assertNotIn('secret details', str(caught.exception))

    def test_snapshot_idempotence_and_stale_results(self):
        first, second = build_snapshot(), build_snapshot()
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(first['row_count'], 499)
        self.assertEqual(len(first['posts']), 499)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)
            for name in ['clean_data.csv', 'dataset_contract.json', 'handoff_manifest.json', 'training_summary.json', 'test_predictions.csv', 'data_split.csv']:
                shutil.copy(ARTIFACTS / name, destination / name)
            summary = json.loads((destination / 'training_summary.json').read_text())
            summary['test_results']['selected_model_mae'] = 0
            (destination / 'training_summary.json').write_text(json.dumps(summary))
            with self.assertRaisesRegex(ValueError, 'Metric mismatch'):
                build_snapshot(destination)

    def test_no_snapshot_after_failed_run(self):
        with patch('supabase_store.flow_history', return_value=[{'status': 'failed'}]):
            with self.assertRaises(StoreError):
                build_snapshot()


if __name__ == '__main__':
    unittest.main()
