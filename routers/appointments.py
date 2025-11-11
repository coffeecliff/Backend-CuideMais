# Importações principais do FastAPI e SQLAlchemy
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Importa dependência de sessão com o banco de dados
from core.database import get_db

# Importa os modelos do banco
from models.models import Appointment, User, Patient, AppointmentStatus, UserType

# Importa os schemas (Pydantic) para validar e exibir dados
from schemas.schemas import (
    AppointmentCreate,
    AppointmentUpdate,
    Appointment as AppointmentSchema
)

# Importa serviço para autenticação do usuário
from services.auth_service import get_current_user

# Cria o roteador de agendamentos
router = APIRouter(prefix="/appointments", tags=["appointments"])


# ---------------- ROTA: LISTAR AGENDAMENTOS ----------------
@router.get("/", response_model=List[AppointmentSchema])
async def get_appointments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retorna todos os agendamentos do usuário logado.
    Se for um psicólogo, retorna os agendamentos onde ele é o responsável.
    """
    appointments = []

    # Se for usuário do tipo psicólogo, busca agendamentos em que ele é responsável
    if current_user.user_type == UserType.PSICOLOGO:
        appointments = (
            db.query(Appointment)
            .filter(Appointment.psychologist_id == current_user.id)
            .all()
        )
    else:
        # Se for paciente, encontra o registro do paciente pelo e-mail
        patient = db.query(Patient).filter(Patient.email == current_user.email).first()

        # Caso o paciente não exista, retorna uma lista vazia
        if not patient:
            return []

        # Retorna os agendamentos desse paciente
        appointments = (
            db.query(Appointment)
            .filter(Appointment.patient_id == patient.id)
            .all()
        )

    return appointments


# ---------------- ROTA: CRIAR AGENDAMENTO ----------------
@router.post("/", response_model=AppointmentSchema)
async def create_appointment(
    appointment_data: AppointmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cria um novo agendamento.
    - Verifica se o horário solicitado está disponível.
    - Impede duplicidade de agendamento para o mesmo psicólogo e horário.
    """

    # Verifica se já existe agendamento no mesmo horário e psicólogo
    existing_appointment = (
        db.query(Appointment)
        .filter(
            Appointment.psychologist_id == appointment_data.psychologist_id,
            Appointment.date == appointment_data.date,
            Appointment.time == appointment_data.time,
            Appointment.status == AppointmentStatus.AGENDADO
        )
        .first()
    )

    if existing_appointment:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um agendamento para esse horário."
        )

    # Cria novo objeto de agendamento
    new_appointment = Appointment(
        **appointment_data.dict(),
        status=AppointmentStatus.AGENDADO
    )

    # Adiciona ao banco
    db.add(new_appointment)
    db.commit()
    db.refresh(new_appointment)

    return new_appointment
# ---------------- ROTA: ATUALIZAR AGENDAMENTO ----------------
@router.put("/{appointment_id}", response_model=AppointmentSchema)
async def update_appointment(
    appointment_id: int,
    update_data: AppointmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atualiza um agendamento existente.
    Permite alterar informações de data, horário ou status.
    Verifica se o usuário tem permissão para fazer a alteração.
    """

    # Busca o agendamento pelo ID
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agendamento não encontrado."
        )

    # Verifica se o psicólogo logado é o dono do agendamento
    if current_user.user_type == UserType.PSICOLOGO and appointment.psychologist_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para alterar este agendamento."
        )

    # Atualiza os campos enviados (sem sobrescrever outros)
    for field, value in update_data.dict(exclude_unset=True).items():
        setattr(appointment, field, value)

    db.commit()
    db.refresh(appointment)

    return appointment


# ---------------- ROTA: CANCELAR AGENDAMENTO ----------------
@router.delete("/{appointment_id}")
async def cancel_appointment(
    appointment_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancela um agendamento alterando seu status para 'CANCELADO'.
    """

    # Busca o agendamento
    appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agendamento não encontrado."
        )

    # Atualiza o status para CANCELADO
    appointment.status = AppointmentStatus.CANCELADO
    db.commit()

    return {"message": "Agendamento cancelado com sucesso."}


# ---------------- ROTA: VER HORÁRIOS DISPONÍVEIS ----------------
@router.get("/available-slots/")
async def get_available_slots(
    date: str,  # Exemplo: "2025-11-30"
    psychologist_id: int,
    db: Session = Depends(get_db)
):
    """
    Retorna os horários disponíveis para determinado psicólogo em uma data específica.
    """

    # Lista fixa de horários possíveis no dia
    all_slots = ["08:00", "09:00", "10:00", "14:00", "15:00", "16:00", "17:00"]

    # Busca horários já ocupados pelo psicólogo na data informada
    occupied_times = (
        db.query(Appointment.time)
        .filter(
            Appointment.psychologist_id == psychologist_id,
            Appointment.date == date,
            Appointment.status == AppointmentStatus.AGENDADO
        )
        .all()
    )

    # Converte lista de tuplas [(hora,), (hora,)] em lista simples ['hora', ...]
    occupied_times = [slot[0] for slot in occupied_times]

    # Filtra horários disponíveis
    available_slots = [slot for slot in all_slots if slot not in occupied_times]

    return available_slots
