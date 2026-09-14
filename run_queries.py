"""
Run every query in sql/ against the warehouse and print its result.

Usage:
    python scripts/run_queries.py            # run all, pretty-print
    python scripts/run_queries.py --markdown # emit Markdown tables (for README)
    python scripts/run_queries.py 04         # run only the file starting with '04'

Requires warehouse.duckdb (build it first: python scripts/build_warehouse.py).
"""
import os
import sys
import glob
import duckdb

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(REPO_ROOT, "sql")
DB_PATH = os.path.join(REPO_ROOT, "warehouse.duckdb")


def load_sql(path):
    with open(path, "r") as f:
        return f.read()


def first_comment_line(sql_text):
    for line in sql_text.splitlines():
        s = line.strip()
        if s.startswith("--"):
            return s.lstrip("- ").strip()
    return ""


def run_all(filter_prefix=None, as_markdown=False):
    if not os.path.exists(DB_PATH):
        sys.exit("warehouse.duckdb not found - run scripts/build_warehouse.py first.")

    con = duckdb.connect(DB_PATH, read_only=True)
    files = sorted(glob.glob(os.path.join(SQL_DIR, "*.sql")))
    if filter_prefix:
        files = [f for f in files if os.path.basename(f).startswith(filter_prefix)]

    for path in files:
        name = os.path.basename(path)
        sql_text = load_sql(path)
        title = first_comment_line(sql_text)
        df = con.execute(sql_text).df()

        if as_markdown:
            print(f"\n### `{name}`\n")
            print(f"*{title}*\n")
            print(df.to_markdown(index=False))
            print()
        else:
            print("=" * 78)
            print(f"{name}  -  {title}")
            print("=" * 78)
            with_opts = df.to_string(index=False, max_rows=20)
            print(with_opts)
            print(f"\n({len(df)} rows)\n")

    con.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    as_md = "--markdown" in args
    args = [a for a in args if a != "--markdown"]
    prefix = args[0] if args else None
    run_all(filter_prefix=prefix, as_markdown=as_md)
