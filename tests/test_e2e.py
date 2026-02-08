import os
import tempfile
import sqlite3
import unittest
import sys

# اطمینان از اینکه ریشه پروژه در sys.path هست (برای اجرا از هر مسیر)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# نکته: قبل از import کردن app باید مسیر دیتابیس تست را ست کنیم


def create_test_db(db_path: str):
    # دیتابیس را با اسکیما جدید می‌سازیم
    from db_setup import create_database
    create_database(db_path)


class StartupSandboxE2E(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, 'test_startup.db')
        os.environ['STARTUP_DB_PATH'] = self.db_path
        os.environ['FLASK_SECRET_KEY'] = 'test_secret'
        # GROQ_API_KEY را عمداً ست نمی‌کنیم تا fallback فعال شود

        create_test_db(self.db_path)

        # import بعد از ست کردن env
        import importlib
        if 'app' in sys.modules:
            self.app_module = importlib.reload(sys.modules['app'])
        else:
            self.app_module = importlib.import_module('app')
        self.app = self.app_module.app
        self.app.config.update(TESTING=True)
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _get_game_id(self):
        with self.client.session_transaction() as sess:
            return sess.get('game_id')

    def test_full_happy_path(self):
        # 1) Landing
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)

        # 2) New game
        r = self.client.post('/new_game', data={'username': 'ali', 'startup_name': 'TestCo'}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        game_id = self._get_game_id()
        self.assertIsNotNone(game_id)

        # 3) Ensure a scenario exists and choices exist
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        scenario = conn.execute('SELECT * FROM scenarios WHERE game_id = ? ORDER BY id DESC LIMIT 1', (game_id,)).fetchone()
        self.assertIsNotNone(scenario)
        choice = conn.execute('SELECT * FROM choices WHERE scenario_id = ? ORDER BY id LIMIT 1', (scenario['id'],)).fetchone()
        self.assertIsNotNone(choice)
        conn.close()

        # 4) Take action
        r = self.client.post('/action', data={'choice_id': str(choice['id'])}, follow_redirects=True)
        self.assertEqual(r.status_code, 200)

        # 5) Next turn
        r = self.client.get('/next_turn', follow_redirects=True)
        self.assertEqual(r.status_code, 200)

        # 6) Game over path (force budget = 0)
        conn = sqlite3.connect(self.db_path)
        conn.execute('UPDATE games SET budget = 0 WHERE id = ?', (game_id,))
        conn.commit()
        conn.close()

        r = self.client.get('/game', follow_redirects=True)
        self.assertEqual(r.status_code, 200)
        # صفحه game_over.html باید شامل چیزی از template باشد
        body = r.data.decode('utf-8', errors='ignore')
        self.assertTrue(('Game Over' in body) or ('پايان' in body) or ('پایان' in body))


if __name__ == '__main__':
    unittest.main()
