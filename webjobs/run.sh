#!/bin/bash

# Dynamically identify the path
CELERY_PATH=$(find /tmp -path "*/antenv/bin/celery" -type f | head -n 1)

APP_HOME=$(find /tmp -type d -name elroy | head -n 1)/..

echo "changing dir to $APP_HOME"

cd $APP_HOME

$CELERY_PATH -A elroy.workers.worker worker --beat --loglevel=info -s /home/celerybeat-schedule
