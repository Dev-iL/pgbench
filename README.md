# PostgreSQL Driver Benchmarks

Benchmarks for Python PostgreSQL client drivers, measuring throughput and latency across a range of query types and concurrency levels.

## Drivers

| Benchmark name | Library | Mode |
|---|---|---|
| `python-asyncpg` | [asyncpg](https://github.com/MagicStack/asyncpg) | async |
| `python-aiopg` | [aiopg](https://github.com/aio-libs/aiopg) | async (dict rows) |
| `python-aiopg-tuples` | [aiopg](https://github.com/aio-libs/aiopg) | async (tuple rows) |
| `python-psycopg3` | [psycopg](https://www.psycopg.org/) v3 | sync |
| `python-psycopg3-async` | [psycopg](https://www.psycopg.org/) v3 | async |
| `python-psycopg2` | [psycopg2](https://www.psycopg.org/docs/) | sync (thread pool) |

## Queries

Seven benchmark queries cover different driver workloads:

| File | Description |
|---|---|
| `1-pg_type.json` | Read from `pg_type` system catalog |
| `2-generate_series.json` | Server-side row generation |
| `3-large_object.json` | Fetch a large binary object |
| `4-arrays.json` | Array column decoding |
| `5-copyfrom.json` | Bulk-load via `COPY FROM STDIN` |
| `6-batch.json` | Batch `INSERT` |
| `7-oneplusone.json` | Minimal round-trip (`SELECT 1+1`) |

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
make        # runs uv sync
```

Or directly:

```sh
uv sync
```

## Running

```sh
./pgbench [OPTIONS] [benchmark ...]
```

With no benchmark arguments all six drivers are run. Pass one or more names to run a subset:

```sh
./pgbench python-asyncpg python-psycopg3-async
```

Key options:

| Flag | Default | Description |
|---|---|---|
| `--concurrency-levels` | `10` | Comma-separated list of concurrency values |
| `--duration` | `30` | Seconds per benchmark run |
| `--warmup-time` | `5` | Warmup seconds before measurement |
| `--pghost` | *(temp cluster)* | PostgreSQL host; omit to spin up a temporary cluster |
| `--pgport` | `5432` | PostgreSQL port |
| `--pguser` | `postgres` | PostgreSQL user |
| `--save-json` / `-J` | — | Write results to a JSON file |
| `--save-html` / `-H` | — | Write results to an HTML report |
| `--queryfiles` | *(all)* | Comma-separated list of query JSON files |

### Example

```sh
./pgbench --concurrency-levels=1,10,50 --duration=60 \
          --save-html=results.html \
          python-asyncpg python-psycopg3-async
```

## Low-level runner

`pgbench_python` is the per-driver runner called by the orchestrator. It can also be invoked directly:

```sh
./pgbench_python [OPTIONS] <driver> <queryfile>
```

Drivers: `asyncpg`, `aiopg`, `aiopg-tuples`, `psycopg3`, `psycopg3-async`, `psycopg2`
