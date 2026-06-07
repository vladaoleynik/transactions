import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_worker() -> None:
    logger.info("Worker started TBD")
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    run_worker()
