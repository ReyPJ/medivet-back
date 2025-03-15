from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.init_db import init_db
from app.api.routes import auth, users, patients, notifications
from app.services.notifications import (
    check_and_send_medication_notifications,
    get_notification_check_history,
)
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

last_scheduler_check = None
scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler, last_scheduler_check
    logger.info("🚀 Iniciando aplicación...")
    db = SessionLocal()
    try:
        init_db(db)
        scheduler = BackgroundScheduler()
        scheduler.add_job(check_medications_job, "interval", minutes=1)
        scheduler.start()
        logger.info(
            "⏲️ Programador de tareas iniciado - Verificando medicaciones cada minuto"
        )

    finally:
        db.close()
    yield
    if scheduler:
        scheduler.shutdown()
        logger.info("⏲️ Programador de tareas apagado")


app = FastAPI(title=settings.PROJECT_NAME, version="0.1.0", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)


@app.get("/check-health", tags=["Health Check"])
def health_check():
    global last_scheduler_check, scheduler

    # Obtener información del próximo job programado
    next_run = None
    if scheduler:
        job = scheduler.get_job("check_medications")
        if job:
            next_run = (
                job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
                if job.next_run_time
                else "No programado"
            )

    # Obtener el último check del historial
    check_history = get_notification_check_history()
    last_check = check_history[-1] if check_history else None
    last_check_time = (
        last_check["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if last_check else "Nunca"
    )

    return {
        "status": "ok",
        "message": "Server is running",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "version": "0.1.0",
        "scheduler_status": {
            "active": scheduler.running if scheduler else False,
            "last_check": last_check_time,
            "next_check": next_run,
            "pending_medications_found": (
                last_check["pending_count"] if last_check else 0
            ),
        },
    }


def check_medications_job():
    global last_scheduler_check

    # Actualizar el timestamp de la última verificación
    last_scheduler_check = datetime.now()
    logger.info(
        f"⏲️ Ejecutando verificación programada de medicaciones: {last_scheduler_check.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    db: Session = SessionLocal()
    try:
        check_and_send_medication_notifications(db)
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
