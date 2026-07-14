@ECHO OFF
REM From backend folder:
REM   python main.py
REM Celery (optional):
REM   celery -A tasks.celery_app.celery_app worker --loglevel=info --pool=solo
REM   celery -A tasks.celery_app.celery_app beat --loglevel=info
ECHO Run: python main.py
