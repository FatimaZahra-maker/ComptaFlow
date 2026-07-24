"""
app/tasks/__init__.py

Importer explicitement le module ici garantit que la tâche est
enregistrée quand Celery importe le package `app.tasks` (via
autodiscover_tasks(["app"])).
"""
from app.tasks.document_processing import process_document  # noqa: F401