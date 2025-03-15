from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.services.notifications import (
    check_and_send_medication_notifications,
    get_notification_check_history,
)
from app.api.deps import get_current_user_with_role, get_current_active_user

router = APIRouter()


@router.post("/check-medications")
async def check_medications(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    # Solo administrador y doctores pueden forzar la revisión
    current_user=Depends(get_current_user_with_role(["admin", "doctor"])),
):
    background_tasks.add_task(check_and_send_medication_notifications, db)
    return {"message": "Medication check scheduled in background task"}


@router.get("/check-status")
async def check_status(current_user=Depends(get_current_active_user)):
    """
    Devuelve el estado de las verificaciones recientes de medicaciones
    """
    history = get_notification_check_history()

    # Formatear el historial para la respuesta JSON
    formatted_history = []
    for check in history:
        formatted_history.append(
            {
                "timestamp": check["timestamp"].strftime("%Y-%m-%d %H:%M:%S"),
                "pending_count": check["pending_count"],
            }
        )

    return {
        "total_checks": len(history),
        "last_check": formatted_history[-1] if formatted_history else None,
        "history": formatted_history,
    }
