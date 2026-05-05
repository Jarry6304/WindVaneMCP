import asyncio

from wind_vane.log import setup_logging
from wind_vane.notifier.main import run_notification_check

setup_logging()
asyncio.run(run_notification_check())
