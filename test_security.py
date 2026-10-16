"""Security regressions. No live API calls, training or real credentials."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app_security import AUTH_STATE, SecurityError, authenticate, load_access_token, read_log_tail, redact_secrets
from dashboard_theme import export_theme, read_config
from supabase_store import StoreConfig, StoreError, SupabaseStore, build_snapshot, get_config
from workspace_runtime import WorkspaceBusy, run_ui_flow, workspace_lock

TOKEN = "918273645"  # Nine-character fixture, not the configured local access code.


class AccessTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ, {
            'CREATOR_INSIGHTS_ACCESS_TOKEN': TOKEN,
            'SUPABASE_URL': '', 'SUPABASE_SECRET_KEY': '', 'SUPABASE_SERVICE_ROLE_KEY': '',
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_data_and_actions_unreachable_until_valid_login(self):
        with patch('dashboard_data.load_local') as local, patch('supabase_store.get_config') as cloud:
            app = AppTest.from_file('app.py', default_timeout=30).run()
            self.assertFalse(app.exception)
            self.assertFalse(app.metric)
            self.assertFalse(app.radio)
            app.text_input(key='_access_token_input').set_value('wrong')
            next(b for b in app.button if b.label == 'כניסה').click().run()
            self.assertFalse(app.exception)
            local.assert_not_called()
            cloud.assert_not_called()
            self.assertNotIn(AUTH_STATE, app.session_state)
        app.text_input(key='_access_token_input').set_value(TOKEN)
        next(b for b in app.button if b.label == 'כניסה').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '499')
        self.assertNotIn('_access_token_input', app.session_state)
        next(b for b in app.button if b.label == 'יציאה').click().run()
        self.assertFalse(app.metric)
        self.assertNotIn(AUTH_STATE, app.session_state)

    def test_token_rotation_revokes_session(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        app.text_input(key='_access_token_input').set_value(TOKEN)
        next(b for b in app.button if b.label == 'כניסה').click().run()
        app.session_state['cloud_snapshot'] = 'private-old-snapshot'
        with patch.dict(os.environ, {'CREATOR_INSIGHTS_ACCESS_TOKEN': TOKEN + '-rotated'}):
            app.run()
        self.assertFalse(app.metric)
        self.assertNotIn('cloud_snapshot', app.session_state)
        self.assertNotIn(AUTH_STATE, app.session_state)

    def test_invalid_configuration_fails_closed(self):
        with patch.dict(os.environ, {'CREATOR_INSIGHTS_ACCESS_TOKEN': TOKEN[:-1]}):
            with patch('dashboard_data.load_local') as local:
                app = AppTest.from_file('app.py').run()
                self.assertFalse(app.exception)
                self.assertTrue(app.error)
                local.assert_not_called()

    def test_network_binding_override_fails_closed(self):
        import streamlit as st
        original = st.get_option
        with patch('streamlit.get_option', side_effect=lambda name: '0.0.0.0' if name == 'server.address' else original(name)):
            with patch('dashboard_data.load_local') as local:
                app = AppTest.from_file('app.py').run()
                self.assertFalse(app.exception)
                self.assertFalse(app.metric)
                self.assertTrue(app.error)
                local.assert_not_called()

    def test_local_token_is_private_random_persistent_and_not_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'access_token'
            with patch.dict(os.environ, {'CREATOR_INSIGHTS_ACCESS_TOKEN': ''}):
                first = load_access_token(path=path)
                self.assertEqual(first, load_access_token(path=path))
                self.assertEqual(len(first), 43)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                path.chmod(0o644)
                with self.assertRaises(SecurityError):
                    load_access_token(path=path)
                path.chmod(0o600)
                link = Path(directory) / 'symlink'
                link.symlink_to(path)
                with self.assertRaises((OSError, SecurityError)):
                    load_access_token(path=link)

    def test_failed_auth_discards_old_identity_and_input(self):
        state = {'_access_token_input': 'wrong', AUTH_STATE: 'old', 'cloud_snapshot': 'private'}
        authenticate(state, 'שגוי', TOKEN)
        self.assertNotIn(AUTH_STATE, state)
        self.assertNotIn('_access_token_input', state)
        self.assertNotIn('cloud_snapshot', state)


class RuntimeTests(unittest.TestCase):
    def test_lock_contention_cross_process_and_release_after_exception(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(RuntimeError, 'simulated'):
                with workspace_lock(directory):
                    code = 'from workspace_runtime import workspace_lock, WorkspaceBusy; import sys\ntry:\n with workspace_lock(sys.argv[1]): pass\nexcept WorkspaceBusy: sys.exit(23)'
                    result = subprocess.run([sys.executable, '-c', code, directory], capture_output=True, timeout=15)
                    self.assertEqual(result.returncode, 23, result.stderr)
                    raise RuntimeError('simulated')
            with workspace_lock(directory):
                pass

    def test_snapshot_does_not_read_during_a_flow(self):
        with tempfile.TemporaryDirectory() as directory:
            with workspace_lock(directory), patch('supabase_store._build_snapshot') as capture:
                with self.assertRaises(WorkspaceBusy):
                    build_snapshot(Path(directory))
                capture.assert_not_called()

    def test_flow_entry_rejects_before_crews_start(self):
        import project_flow
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(project_flow, 'ARTIFACTS', Path(directory)), workspace_lock(directory):
                with patch.object(project_flow, 'CreatorInsightsFlow') as factory:
                    with self.assertRaises(WorkspaceBusy):
                        project_flow.run_project()
                    factory.assert_not_called()

    def test_ui_log_masks_before_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / 'project_flow.py'
            script.write_text("print('sb_secret_fixture_should_never_persist')")
            artifacts = root / 'artifacts'
            self.assertEqual(run_ui_flow(artifacts, timeout=10), 0)
            log = artifacts / 'latest_ui_run.log'
            self.assertNotIn('sb_secret_fixture', log.read_text())
            self.assertIn('[REDACTED]', log.read_text())
            self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    @unittest.skipUnless(os.name == 'posix', 'POSIX process groups')
    def test_timeout_terminates_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / 'child-survived'
            child = 'import time; from pathlib import Path; time.sleep(1.5); Path(' + repr(str(marker)) + ').write_text("bad")'
            (root / 'project_flow.py').write_text('import subprocess, sys, time\nsubprocess.Popen([sys.executable, "-c", ' + repr(child) + '])\ntime.sleep(20)\n')
            with self.assertRaises(subprocess.TimeoutExpired):
                run_ui_flow(root / 'artifacts', timeout=.5)
            # A short bounded delay establishes that the child cannot write later.
            import time
            time.sleep(1.6)
            self.assertFalse(marker.exists())
            with workspace_lock(root / 'artifacts', name='ui_run'):
                pass


class DiagnosticTests(unittest.TestCase):
    def test_theme_export_excludes_private_sections(self):
        config = read_config()
        config['server']['cookieSecret'] = 'private-cookie-fixture'
        config['auth'] = {'client_secret': 'private-auth-fixture'}
        exported = export_theme(config)
        self.assertEqual(set(tomllib.loads(exported)), {'theme'})
        self.assertNotIn('private-', exported)
        self.assertEqual(config['server']['cookieSecret'], 'private-cookie-fixture')

    def test_masking_and_bounded_log_reads(self):
        secret = 'private-test-key-123456'
        with patch.dict(os.environ, {'ANTHROPIC_API_KEY': secret}):
            self.assertNotIn(secret, redact_secrets('failure: ' + secret))
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'log'
                path.write_text('x' * 50000 + '\n' + secret + '\nend')
                shown = read_log_tail(path, limit=100)
                self.assertLessEqual(len(shown), 100)
                self.assertNotIn(secret, shown)
                self.assertIn('[REDACTED]', shown)

    def test_flow_error_is_masked_before_write(self):
        import project_flow
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(project_flow, 'ARTIFACTS', Path(directory)):
                flow = project_flow.CreatorInsightsFlow()
                flow.fail('test', RuntimeError('sb_secret_fixture_should_not_be_saved'))
                saved = next(Path(directory).glob('flow_*.json')).read_text()
                self.assertNotIn('sb_secret_fixture', saved)
                self.assertIn('[REDACTED]', saved)

    def test_malformed_cloud_responses_and_urls_have_safe_errors(self):
        store = SupabaseStore(StoreConfig('https://example.supabase.co', 'sb_secret_fixture'))
        for payload in ({'private': 'details'}, ['bad-row'], [{'posts': [], 'reports': [], 'training': {}}]):
            with patch.object(store, '_request', return_value=payload):
                with self.assertRaises(StoreError) as caught:
                    store.latest()
                self.assertNotIn('details', str(caught.exception))
        for url in ('https://[invalid', 'https://example.supabase.co:bad', 'https://example.supabase.co:99999'):
            with self.assertRaises(StoreError):
                get_config({'SUPABASE_URL': url, 'SUPABASE_SECRET_KEY': 'sb_secret_fixture'})


if __name__ == '__main__':
    unittest.main()
