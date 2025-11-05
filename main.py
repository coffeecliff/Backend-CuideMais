import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.database import engine, Base
from routers import auth, patients, psychologists
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

# Cria as tabelas no banco de dados
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Cuide+ API",
    description="API para sistema de agendamento psicológico",
    version="1.0.0"
)

# Configuração CORS mais segura
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Inclui os routers
app.include_router(auth.router)
app.include_router(patients.router)
app.include_router(psychologists.router)


@app.get("/")
async def root():
    return {"message": "Cuide+ API - Sistema de Agendamento Psicológico"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}