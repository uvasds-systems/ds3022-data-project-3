# src/sec_prefect_flow.py

# Used ChatGPT (model 5.1) to help generate a more efficient prefect flow structure to reduce time from over an hour to around 15 minutes.

from prefect import flow, task, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner

from sec_fetch import run_fetch
from parse_filings import run_parse
from load_duckdb import load_ai_paragraphs_to_duckdb
from analyze_plot import run_analysis


# Fetch Task - hits SEC API and builds index
@task
def fetch_task(min_per_sector: int) -> str:
    logger = get_run_logger()
    logger.info("Starting SEC ingestion (fetch_task)")

    try:
        path = run_fetch(min_per_sector=min_per_sector)
    except Exception as e:
        logger.error(f"ERROR during fetch_task: {e}")
        raise

    logger.info(f"Fetch complete, index at {path}")
    return path


# Parse Task - fetches each filing and extracts AI paragraphs
@task
def parse_task(index_path: str) -> str:
    logger = get_run_logger()
    logger.info("Starting parse task")

    try:
        out = run_parse(index_path=index_path)
    except FileNotFoundError:
        logger.error(f"Index file not found at {index_path}")
        raise
    except Exception as e:
        logger.error(f"ERROR during parse_task: {e}")
        raise

    logger.info(f"Parse complete, AI paragraphs at {out}")
    return out


# DuckDB Task - loads CSV into DuckDB database
@task
def duckdb_task(ai_csv_path: str) -> str:
    logger = get_run_logger()
    logger.info("Loading AI paragraphs into DuckDB")

    try:
        load_ai_paragraphs_to_duckdb(source_csv=ai_csv_path)
    except FileNotFoundError:
        logger.error(f"CSV file not found at {ai_csv_path}")
        raise
    except Exception as e:
        logger.error(f"ERROR during DuckDB load: {e}")
        raise

    logger.info("DuckDB load complete")
    return ai_csv_path


# Analysis Task - generates all plots from DuckDB
@task
def analyze_task() -> str:
    logger = get_run_logger()
    logger.info("Starting analysis task (DuckDB)")

    try:
        plot_path = run_analysis()
    except FileNotFoundError as e:
        logger.error(f"Missing DuckDB or required tables: {e}")
        raise
    except Exception as e:
        logger.error(f"ERROR during analysis_task: {e}")
        raise

    logger.info(f"Analysis complete, plot at {plot_path}")
    return plot_path


# Main Prefect Flow
# Uses ConcurrentTaskRunner so independent tasks can run in parallel
@flow(
    name="SEC AI Trends Pipeline",
    log_prints=True,
    task_runner=ConcurrentTaskRunner(),
)
def sec_ai_trends_flow(min_per_sector: int = 60):
    logger = get_run_logger()
    logger.info("Flow started: SEC AI Trends Pipeline")

    # Step 1: submit fetch task
    idx_future = fetch_task.submit(min_per_sector=min_per_sector)

    # Step 2: submit parse task that depends on fetch_task
    # Prefect will wait for idx_future internally
    ai_future = parse_task.submit(index_path=idx_future)

    # Step 3: submit DuckDB load, depends on parse_task
    duck_future = duckdb_task.submit(ai_future)

    # Step 4: submit analysis, depends on DuckDB load
    plot_future = analyze_task.submit(wait_for=[duck_future])

    # Resolve the final result so it is visible in logs and Python call
    plot_path = plot_future.result()
    logger.info(f"Flow finished successfully. Main plot saved at: {plot_path}")


if __name__ == "__main__":
    sec_ai_trends_flow(min_per_sector=60)