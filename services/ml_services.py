from sqlalchemy.orm import Session
from models.models import Patient, Appointment, AppointmentStatus
from datetime import datetime, timedelta
from typing import List, Dict
 
 
class RiskLevel:
    BAIXO = "Baixo"
    MEDIO = "Médio"
    ALTO = "Alto"
 
 
def calculate_patiente_risk(db: Session, psychologist_id: int) -> List[Dict]:
    """
    Calcula risco dos pacientes baseado em padrões de frequência
    """
 
    patients = db.query(Patient).filter(Patient.psychologist_id == psychologist_id).all()
    risk_analysis = []
 
    for patient in patients:
        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.patient_id == patient.id,
                Appointment.psychologist_id == psychologist_id,
            )
            .order_by(Appointment.date.desc())
            .all()
        )
 
        if not appointments:
            continue
 
        metrics = _extract_patiente_metrics(appointments)
        risk_score = _calculate_risk_score(metrics)
        risk_level = _determine_risk_level(risk_score)
        risk_reason = _identify_risk_reason(metrics)
 
        risk_analysis.append({
            "id": patient.id,
            "patient": patient.name,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "reason": risk_reason,
            "last_appointment": appointments[0].date.isoformat() if appointments else None,
            "metrics": metrics,
        })
 
    return sorted(risk_analysis, key=lambda x: x["risk_score"], reverse=True)
 
 
def _extract_patiente_metrics(appointments: List[Appointment]) -> Dict:
    """Extrai métricas relevantes do paciente"""
    now = datetime.now().date()
 
    completed = [apt for apt in appointments if apt.status == AppointmentStatus.CONCLUIDO]
    canceled = [apt for apt in appointments if apt.status == AppointmentStatus.CANCELADO]
    scheduled = [apt for apt in appointments if apt.status == AppointmentStatus.AGENDADO]
 
    last_30_days = [apt for apt in appointments if (now - apt.date).days <= 30]
    last_60_days = [apt for apt in appointments if (now - apt.date).days <= 60]
    last_90_days = [apt for apt in appointments if (now - apt.date).days <= 90]
 
    days_since_last = (now - appointments[0].date).days if appointments else 999
 
    total_appointments = len(appointments)
    cancellation_rate = len(canceled) / total_appointments if total_appointments > 0 else 0
 
    # Frequência mensal
    if appointments:
        first_appointment = min(apt.date for apt in appointments)
        months_active = max(1, (now - first_appointment).days / 30)
        frequency_per_month = len(appointments) / months_active
    else:
        frequency_per_month = 0
 
    recent_completed = len([apt for apt in completed if (now - apt.date).days <= 30])
    previous_completed = len([apt for apt in completed if 30 < (now - apt.date).days <= 60])
 
    return {
        "total_appointments": total_appointments,
        "completed_appointments": len(completed),
        "canceled_appointments": len(canceled),
        "cancellation_rate": cancellation_rate,
        "days_since_last": days_since_last,
        "frequency_per_month": frequency_per_month,
        "appointments_last_30": len(last_30_days),
        "appointments_last_60": len(last_60_days),
        "appointments_last_90": len(last_90_days),
        "recent_trend": recent_completed - previous_completed,
        "has_future_appointments": len(scheduled) > 0,
    }
 
 
def _calculate_risk_score(metrics: Dict) -> int:
    """
    Calcula score de risco (0-100) baseado nas métricas
    Maior score = maior risco
    """
    score = 0
 
    # Dias sem consulta (30%)
    days_factor = min(metrics["days_since_last"] / 60, 1.0)
    score += days_factor * 30
 
    # Cancelamentos (25%)
    score += metrics["cancellation_rate"] * 25
 
    # Frequência baixa (20%)
    if metrics["frequency_per_month"] < 1:
        score += 20
    elif metrics["frequency_per_month"] < 2:
        score += 10
 
    # Ausência recente (15%)
    if metrics["appointments_last_30"] == 0:
        score += 15
    elif metrics["appointments_last_60"] == 0:
        score += 10
 
    # Tendência negativa (10%)
    if metrics["recent_trend"] < -1:
        score += 10
    elif metrics["recent_trend"] < 0:
        score += 5
 
    # Sem futuros agendamentos (5%)
    if not metrics["has_future_appointments"]:
        score += 5
 
    return min(int(score), 100)
 
 
def _determine_risk_level(risk_score: int) -> str:
    """Determina nível de risco baseado no score"""
    if risk_score >= 70:
        return RiskLevel.ALTO
    elif risk_score >= 40:
        return RiskLevel.MEDIO
    else:
        return RiskLevel.BAIXO
 
 
def _identify_risk_reason(metrics: Dict) -> str:
    """Identifica a principal razão do risco"""
    reasons = []
 
    if metrics["days_since_last"] > 45:
        reasons.append("Ausente há mais de 45 dias")
    elif metrics["days_since_last"] > 30:
        reasons.append("Ausente há mais de 30 dias")
 
    if metrics["cancellation_rate"] > 0.3:
        reasons.append("Alta taxa de cancelamentos")
    elif metrics["cancellation_rate"] > 0.2:
        reasons.append("Cancelamentos frequentes")
 
    if metrics["frequency_per_month"] < 1:
        reasons.append("Baixa frequência de consultas")
 
    if metrics["appointments_last_30"] == 0:
        reasons.append("Sem consultas no último mês")
 
    if metrics["recent_trend"] < -1:
        reasons.append("Diminuição na frequência")
 
    if not metrics["has_future_appointments"]:
        reasons.append("Sem agendamentos futuros")
 
    return reasons[0] if reasons else "Padrão normal de consultas"
 
 