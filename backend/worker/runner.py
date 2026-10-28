"""Worker entry-point.

Polls the jobs table and dispatches work to provider implementations.
Full implementation in Phase P4; this stub lets Docker Compose start the
service without errors.
"""

import logging
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Worker started (scaffold – no job processing yet)")
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        logger.info("Worker shutting down")


if __name__ == "__main__":
    main()
