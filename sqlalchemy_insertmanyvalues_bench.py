#!/usr/bin/env python3
#
# Compare sync psycopg2 vs. sync psycopg (v3) bulk-INSERT throughput through SQLAlchemy's
# real `insertmanyvalues` engine path, at the `insertmanyvalues_page_size` Apache Airflow
# itself configures (airflow-core/src/airflow/settings.py::prepare_engine_args).
#
# This complements the existing psycopg2/psycopg3 `6-batch.json` and `5-copyfrom.json`
# scenarios in this project, which exercise each driver's raw `executemany`/`copy` calls
# directly (see `psycopg2_executemany`/`psycopg_executemany` in pgbench_python.py) -- not
# SQLAlchemy's own insertmanyvalues chunking. The two are complementary: this script isolates
# the SQLAlchemy-ORM-level cost that Airflow's own bulk writes actually go through, while the
# existing queries measure raw driver throughput. It lives as a standalone script rather than
# a new `driver` in pgbench_python.py because pgbench's harness represents queries as raw
# parameterized SQL text with positional placeholders, while insertmanyvalues is specific to
# SQLAlchemy's own Table/Insert constructs with named parameters -- the two query models don't
# fit the same per-driver dispatch shape.
#
# See https://github.com/apache/airflow/issues/68453 for the migration this was written for.

import argparse
import time
from dataclasses import dataclass

from sqlalchemy import Column, Integer, MetaData, Numeric, String, Table, create_engine, insert, text
from sqlalchemy.exc import OperationalError

DRIVERS = ('psycopg2', 'psycopg')

INSERTMANYVALUES_PAGE_SIZE = 10000
PSYCOPG2_EXECUTEMANY_MODE = 'values_plus_batch'
PSYCOPG2_EXECUTEMANY_BATCH_PAGE_SIZE = 2000


@dataclass
class BenchmarkResult:
    driver: str
    rows: int
    seconds: float

    @property
    def rows_per_second(self):
        return self.rows / self.seconds if self.seconds else float('inf')


def _build_url(driver, args):
    return 'postgresql+{}://{}:{}@{}:{}/{}'.format(
        driver, args.pguser, args.pgpassword, args.pghost, args.pgport, args.pgdatabase)


def _make_engine(driver, url):
    engine_args = {'insertmanyvalues_page_size': INSERTMANYVALUES_PAGE_SIZE}
    if driver == 'psycopg2':
        engine_args['executemany_mode'] = PSYCOPG2_EXECUTEMANY_MODE
        engine_args['executemany_batch_page_size'] = PSYCOPG2_EXECUTEMANY_BATCH_PAGE_SIZE
    return create_engine(url, **engine_args)


def _make_rows(count):
    return [
        {'a': i, 'b': i * 2, 'c': i % 7, 'd': 'row-{}'.format(i),
         'e': float(i) / 3, 'f': i * 1000, 'g': 'x' * 32}
        for i in range(count)
    ]


def run_benchmark(driver, args):
    url = _build_url(driver, args)
    try:
        engine = _make_engine(driver, url)
        with engine.connect() as conn:
            conn.execute(text(
                'CREATE TABLE IF NOT EXISTS _sqlalchemy_insertmanyvalues_bench('
                'a int, b int, c int, d text, e float, f int, g text)'))
            conn.commit()
    except OperationalError as err:
        raise SystemExit(
            'Could not connect to Postgres using driver {!r} at {}:{}. '
            'Is a Postgres instance reachable there? Original error: {}'.format(
                driver, args.pghost, args.pgport, err)) from err

    metadata = MetaData()
    table = Table(
        '_sqlalchemy_insertmanyvalues_bench', metadata,
        Column('a', Integer), Column('b', Integer), Column('c', Integer),
        Column('d', String), Column('e', Numeric), Column('f', Integer), Column('g', String),
    )
    rows = _make_rows(args.rows)

    with engine.begin() as conn:
        conn.execute(table.delete())
        start = time.monotonic()
        # A single Core insert() executed with a list of dicts triggers SQLAlchemy's real
        # insertmanyvalues chunking -- the same path Airflow's own ORM writes go through.
        conn.execute(insert(table), rows)
        elapsed = time.monotonic() - start

    with engine.begin() as conn:
        conn.execute(table.delete())
    engine.dispose()

    return BenchmarkResult(driver=driver, rows=args.rows, seconds=elapsed)


def main():
    parser = argparse.ArgumentParser(
        description='sync psycopg2 vs. psycopg3 SQLAlchemy insertmanyvalues benchmark')
    parser.add_argument('--pghost', type=str, default='127.0.0.1')
    parser.add_argument('--pgport', type=int, default=5432)
    parser.add_argument('--pguser', type=str, default='postgres')
    parser.add_argument('--pgpassword', type=str, default='')
    parser.add_argument('--pgdatabase', type=str, default='postgres')
    parser.add_argument('--rows', type=int, default=50000,
                        help='rows to insert per driver (default: 50000)')
    args = parser.parse_args()

    results = []
    for driver in DRIVERS:
        print('Running insertmanyvalues benchmark for driver={!r} ({} rows)...'.format(driver, args.rows))
        result = run_benchmark(driver, args)
        print('  {}: {:.3f}s ({:.0f} rows/s)'.format(driver, result.seconds, result.rows_per_second))
        results.append(result)

    print('\nSummary:')
    for result in results:
        print('  {:>10}: {:.3f}s, {:.0f} rows/s'.format(result.driver, result.seconds, result.rows_per_second))


if __name__ == '__main__':
    main()
