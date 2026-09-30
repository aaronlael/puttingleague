import tempfile
import unittest
from pathlib import Path

from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, create_engine, select

from migrate_sqlite_to_mysql import copy_tables


class SQLiteMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        source_path = Path(self.temp_directory.name) / 'source.db'
        target_path = Path(self.temp_directory.name) / 'target.db'
        self.source_engine = create_engine(f'sqlite:///{source_path.as_posix()}')
        self.target_engine = create_engine(f'sqlite:///{target_path.as_posix()}')

        self.metadata = MetaData()
        self.users = Table(
            'user',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(80), nullable=False),
        )
        self.entries = Table(
            'weekly_entry',
            self.metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', Integer, ForeignKey('user.id'), nullable=False),
        )
        self.metadata.create_all(self.source_engine)
        self.metadata.create_all(self.target_engine)
        with self.source_engine.begin() as connection:
            connection.execute(self.users.insert(), [{'id': 7, 'name': 'Alex'}])
            connection.execute(self.entries.insert(), [{'id': 13, 'user_id': 7}])

    def tearDown(self):
        self.source_engine.dispose()
        self.target_engine.dispose()
        self.temp_directory.cleanup()

    def test_preview_does_not_write_and_apply_preserves_ids(self):
        tables = self.metadata.sorted_tables
        preview = copy_tables(self.source_engine, self.target_engine, tables)
        self.assertEqual(preview, {'user': 1, 'weekly_entry': 1})
        with self.target_engine.connect() as connection:
            self.assertEqual(connection.scalar(select(self.users.c.id)), None)

        copied = copy_tables(self.source_engine, self.target_engine, tables, apply=True)
        self.assertEqual(copied, {'user': 1, 'weekly_entry': 1})
        with self.target_engine.connect() as connection:
            self.assertEqual(connection.scalar(select(self.users.c.id)), 7)
            self.assertEqual(connection.scalar(select(self.entries.c.user_id)), 7)

    def test_refuses_to_copy_into_populated_target(self):
        with self.target_engine.begin() as connection:
            connection.execute(self.users.insert(), {'id': 2, 'name': 'Existing'})

        with self.assertRaisesRegex(RuntimeError, 'non-empty target tables'):
            copy_tables(self.source_engine, self.target_engine, self.metadata.sorted_tables, apply=True)


if __name__ == '__main__':
    unittest.main()