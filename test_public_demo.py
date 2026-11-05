"""Public demo mode: read-only, no login, no actions, no credentials."""
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app_security import public_demo


class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict('os.environ', {
            'CREATOR_INSIGHTS_PUBLIC_DEMO': '1',
            'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_SECRET_KEY': 'sb_secret_should_never_be_used_12345',
            'CREATOR_INSIGHTS_ACCESS_TOKEN': 'demo-test-token-not-a-secret-12345678',
        })
        environment.start()
        self.addCleanup(environment.stop)

    def test_flag_parsing(self):
        self.assertTrue(public_demo({'CREATOR_INSIGHTS_PUBLIC_DEMO': 'true'}))
        self.assertFalse(public_demo({'CREATOR_INSIGHTS_PUBLIC_DEMO': '0'}))
        with patch.dict('os.environ', {'CREATOR_INSIGHTS_PUBLIC_DEMO': ''}):
            self.assertFalse(public_demo({}))

    def test_opens_without_login_with_real_data(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.metric[0].value, '499')
        self.assertTrue(any('הדגמה ציבורית' in item.value for item in app.info))
        self.assertFalse(any(b.label == 'יציאה' for b in app.button))

    def test_actions_disabled_and_cloud_unavailable(self):
        app = AppTest.from_file('app.py', default_timeout=30).run()
        app.radio(key='page').set_value('עוד').run()
        self.assertEqual(app.selectbox(key='source').options, ['תוצרים מקומיים'])
        self.assertFalse(app.exception)
        labels = [b.label for b in app.button]
        for forbidden in ('הפעלת התהליך המלא', 'סנכרון התוצרים המקומיים לענן', 'בדיקת חיבור', 'שמירת העיצוב'):
            self.assertNotIn(forbidden, labels)

    def test_default_mode_still_requires_login(self):
        with patch.dict('os.environ', {'CREATOR_INSIGHTS_PUBLIC_DEMO': ''}):
            app = AppTest.from_file('app.py', default_timeout=30).run()
        self.assertTrue(app.text_input(key='_access_token_input'))
        self.assertEqual(len(app.metric), 0)


if __name__ == '__main__':
    unittest.main()
