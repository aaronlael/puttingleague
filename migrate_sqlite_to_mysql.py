import argparse
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import URL


def _validate_target_tables(target_engine, tables):
    inspector = inspect(target_engine)
    available_tables = set(inspector.get_table_names())
    missing_tables = [table.name for table in tables if table.name not in available_tables]
    if missing_tables:
        raise RuntimeError(
            'Target database is missing app tables. Start the app with MySQL settings first: '
            + ', '.join(missing_tables)
        )


def _assert_target_empty(connection, tables):
    populated_tables = []
    for table in tables:
        count = connection.scalar(select(func.count()).select_from(table))
        if count:
            populated_tables.append(f'{table.name} ({count} rows)')
    if populated_tables:
        raise RuntimeError(
            'Refusing to copy into non-empty target tables: ' + ', '.join(populated_tables)
        )


def _validate_source_columns(source_inspector, source_tables, tables):
    for table in tables:
        if table.name not in source_tables:
            continue
        source_columns = {
            column['name'] for column in source_inspector.get_columns(table.name)
        }
        missing_columns = [column.name for column in table.columns if column.name not in source_columns]
        if missing_columns:
            raise RuntimeError(
                f'Source table {table.name} is missing expected columns: '
                + ', '.join(missing_columns)
            )


def copy_tables(source_engine, target_engine, tables, apply=False):
    tables = list(tables)
    _validate_target_tables(target_engine, tables)

    source_inspector = inspect(source_engine)
    source_tables = set(source_inspector.get_table_names())
    _validate_source_columns(source_inspector, source_tables, tables)

    if not apply:
        with target_engine.connect() as target_connection:
            _assert_target_empty(target_connection, tables)
        counts = {}
        with source_engine.connect() as source_connection:
            for table in tables:
                if table.name not in source_tables:
                    counts[table.name] = 0
                    continue
                counts[table.name] = source_connection.scalar(
                    select(func.count()).select_from(table)
                )
        return counts

    counts = {}
    with source_engine.connect() as source_connection, target_engine.begin() as target_connection:
        _assert_target_empty(target_connection, tables)
        for table in tables:
            if table.name not in source_tables:
                counts[table.name] = 0
                continue
            rows = source_connection.execute(select(table)).mappings().all()
            if rows:
                target_connection.execute(table.insert(), [dict(row) for row in rows])
            counts[table.name] = len(rows)
    return counts


def main():
    parser = argparse.ArgumentParser(
        description='Copy Putting League data from database.db to the configured MySQL database.'
    )
    parser.add_argument(
        '--source',
        type=Path,
        default=Path(__file__).resolve().with_name('database.db'),
        help='SQLite database path (defaults to database.db beside this script).',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Perform the copy. Without this flag, only preview the row counts.',
    )
    args = parser.parse_args()
    source_path = args.source.expanduser().resolve()
    if not source_path.is_file():
        parser.error(f'SQLite source database does not exist: {source_path}')

    project_home = Path(__file__).resolve().parent
    load_dotenv(project_home / '.env')

    from app import app, db

    target_url = app.config['SQLALCHEMY_DATABASE_URI']
    if not isinstance(target_url, URL) or target_url.get_backend_name() != 'mysql':
        parser.error('MySQL is not configured; set all PUTTING_LEAGUE_DB_* values in .env.')

    source_url = URL.create('sqlite', database=str(source_path))
    source_engine = create_engine(source_url)
    with app.app_context():
        target_engine = db.engine
        tables = db.metadata.sorted_tables

    print(f'SQLite source: {source_path}')
    print(f'MySQL target: {target_url.host}/{target_url.database}')
    counts = copy_tables(source_engine, target_engine, tables, apply=args.apply)
    for table_name, row_count in counts.items():
        print(f'  {table_name}: {row_count} rows')
    if args.apply:
        print('Migration complete. The SQLite source was left unchanged.')
    else:
        print('Preview only. Re-run with --apply to copy these rows.')


if __name__ == '__main__':
    main()