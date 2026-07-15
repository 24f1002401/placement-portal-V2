from celery import Celery
from celery.schedules import crontab

from config import REDIS_URL

celery_app = Celery("ppa", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    timezone="Asia/Kolkata",
    enable_utc=False,
    beat_schedule={
        "daily-deadline-reminders": {
            "task": "tasks.jobs.send_daily_deadline_reminders",
            "schedule": crontab(hour=9, minute=0),
        },
        "monthly-activity-report": {
            "task": "tasks.jobs.send_monthly_activity_report",
            "schedule": crontab(day_of_month=1, hour=8, minute=0),
        },
    },
)

celery_app.conf.imports = ("tasks.jobs",)
