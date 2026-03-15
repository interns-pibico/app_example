#!/bin/bash
cd /home/erpnext/.services/app_example
venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8555 &
echo $! > /tmp/uvicorn_8555.pid
