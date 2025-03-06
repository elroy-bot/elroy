#!/usr/bin/env python3

"""
Celery application for the benchmarking setup.
This module defines the Celery app and tasks for processing benchmark jobs.
"""

import os

from celery import Celery

# Create Celery app
app = Celery("benchmark_tasks")

# Configure Celery to use Redis as the broker and backend
app.conf.broker_url = f"redis://:{os.environ.get('REDIS_PASSWORD', 'password')}@redis:6379/0"
app.conf.result_backend = f"redis://:{os.environ.get('REDIS_PASSWORD', 'password')}@redis:6379/0"

# Configure Celery to serialize tasks using JSON
app.conf.task_serializer = "json"
app.conf.result_serializer = "json"
app.conf.accept_content = ["json"]

# Configure Celery to acknowledge tasks only after they are completed
app.conf.task_acks_late = True

# Configure Celery to prefetch only one task at a time
app.conf.worker_prefetch_multiplier = 1

# Import tasks to ensure they are registered with the Celery app
from celery_tasks import *  # noqa
