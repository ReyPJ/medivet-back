from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.db_session_middleware import DBSessionMiddleware
from datetime import datetime
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.init_db import init_db
from app.api.routes import auth, users, patients, notifications
from app.services.notifications import (
    check_and_send_dose_notifications,  # Usamos solo esta función
    get_notification_check_history,
)
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from sqlalchemy.orm import Session
from app.db.base import SessionLocal
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    logger.info("🚀 Iniciando aplicación...")
    db = SessionLocal()
    try:
        init_db(db)

        # Configurar el scheduler con un solo worker para evitar ejecuciones paralelas
        executors = {"default": ThreadPoolExecutor(1)}  # Limitar a un solo worker

        job_defaults = {
            "coalesce": True,  # Combinar ejecuciones perdidas
            "max_instances": 1,  # Solo una instancia a la vez
            "misfire_grace_time": 15 * 60,  # 15 minutos de gracia
        }

        scheduler = BackgroundScheduler(executors=executors, job_defaults=job_defaults)

        # IMPORTANTE: Solo usar UN trabajo para verificar dosis
        # Eliminamos check_medications_job que causaba duplicaciones
        scheduler.add_job(check_doses_job, "interval", minutes=1, id="check_doses")

        scheduler.start()
        logger.info("⏲️ Programador de tareas iniciado - Verificando dosis cada minuto")

    finally:
        db.close()
    yield
    if scheduler:
        scheduler.shutdown()
        logger.info("⏲️ Programador de tareas apagado")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    lifespan=lifespan,
    description="API para gestión veterinaria con sistema avanzado de tratamientos y dosificación",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(DBSessionMiddleware)


app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(patients.router, prefix="/patients", tags=["patients"])
app.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)


@app.get("/check-health", tags=["Health Check"])
def health_check():
    global scheduler

    # Obtener información de los jobs programados
    dose_next_run = "No programado"

    if scheduler:
        dose_job = scheduler.get_job("check_doses")
        if dose_job and dose_job.next_run_time:
            dose_next_run = dose_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S")

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
            "dose_check": {
                "next_run": dose_next_run,
            },
            "pending_doses_found": (last_check["pending_count"] if last_check else 0),
        },
    }


# Esta función ya no se usa, pero la mantenemos como referencia comentada
# def check_medications_job():
#     """Tarea programada para verificar medicaciones pendientes (sistema anterior)"""
#     db: Session = SessionLocal()
#     try:
#         check_and_send_medication_notifications(db)
#     finally:
#         db.close()


def check_doses_job():
    """Tarea programada para verificar dosis individuales pendientes"""
    db: Session = SessionLocal()
    try:
        check_and_send_dose_notifications(db)
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
