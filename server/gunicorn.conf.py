import multiprocessing
import os

bind = "0.0.0.0:" + os.environ.get("DATATILES_PORT", "8080")
worker_class = "uvicorn_worker.UvicornWorker"
workers = int(os.environ.get("DATATILES_WORKERS", str(max(2, min(8, multiprocessing.cpu_count())))))
keepalive = int(os.environ.get("DATATILES_KEEPALIVE", "5"))
timeout = int(os.environ.get("DATATILES_REQUEST_TIMEOUT", "60"))
graceful_timeout = int(os.environ.get("DATATILES_GRACEFUL_TIMEOUT", "30"))
accesslog = os.environ.get("DATATILES_ACCESS_LOG", "-")
errorlog = "-"
preload_app = False
