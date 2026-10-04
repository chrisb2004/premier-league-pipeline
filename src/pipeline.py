"""Run the whole pipeline end to end: python -m src.pipeline"""
import logging
import sys
import time

from src.db import get_engine
from src.extract import extract
from src.load import load
from src.transform import clean_matches, to_team_perspective
from src.validate import ValidationError, validate_matches

log = logging.getLogger("pipeline")


def run() -> None:
    engine = get_engine()   # one engine (and connection pool) shared by every stage
    start = time.perf_counter()

    log.info("Extract: CSVs -> stg_matches")
    staged = extract(engine)
    log.info("  %d matches staged", len(staged))

    log.info("Transform (1/2): cleaning matches")
    matches = clean_matches(staged)

    log.info("Validate: running quality checks")
    validate_matches(matches)   # raises ValidationError -> nothing below runs
    log.info("  all checks passed")

    log.info("Transform (2/2): reshaping to one row per team per match")
    team_rows = to_team_perspective(matches)
    log.info("  %d team rows", len(team_rows))

    log.info("Load: rebuilding the star schema")
    for table, rows in load(team_rows, engine).items():
        log.info("  %-16s %5d rows", table, rows)

    log.info("Done in %.1f s", time.perf_counter() - start)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
    try:
        run()
    except ValidationError as error:
        log.error("Pipeline stopped, star schema left unchanged.\n%s", error)
        sys.exit(1)   # non-zero exit code tells schedulers and CI that the run failed
