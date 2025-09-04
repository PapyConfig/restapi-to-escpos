from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import logging
from typing import Dict
from .models import PrintJob, PrintResponse
from .printer_service import ThermalPrinterService

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Thermal Printer API",
    description="API REST pour envoyer des commandes ESC/POS à une imprimante thermique",
    version="1.0.0"
)

# Variables d'environnement (nouveaux noms)
PRINTER_DEFAULT_IP = os.getenv("PRINTER_IP", "192.168.1.100")
PRINTER_DEFAULT_PORT = int(os.getenv("PRINTER_PORT", "9100"))

# Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Stockage temporaire des jobs
jobs_status: Dict[str, str] = {}

@app.get("/")
async def root():
    return {
        "message": "Thermal Printer API is running",
        "default_printer_ip": PRINTER_DEFAULT_IP,
        "default_printer_port": PRINTER_DEFAULT_PORT
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/print", response_model=PrintResponse)
async def print_receipt(print_job: PrintJob, printer_ip: str = None, printer_port: int = None):
    """Endpoint principal pour l'impression"""
    # Utilisation des valeurs par défaut si non fournies
    ip = printer_ip or PRINTER_DEFAULT_IP
    port = printer_port or PRINTER_DEFAULT_PORT
    
    job_id = str(uuid.uuid4())
    jobs_status[job_id] = "processing"
    
    try:
        printer_service = ThermalPrinterService()
        success = printer_service.print_job(
            printer_ip=ip,
            printer_port=port,
            commands=print_job.commands,
            encoding=print_job.encoding
        )
        
        if success:
            jobs_status[job_id] = "completed"
            return PrintResponse(
                success=True,
                message="Impression réussie",
                job_id=job_id
            )
        else:
            jobs_status[job_id] = "failed"
            raise HTTPException(status_code=500, detail="Échec de l'impression")
            
    except Exception as e:
        jobs_status[job_id] = "failed"
        logger.error(f"Erreur d'impression: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Récupère le statut d'un job d'impression"""
    status = jobs_status.get(job_id, "not_found")
    if status == "not_found":
        raise HTTPException(status_code=404, detail="Job non trouvé")
    return {"job_id": job_id, "status": status}

@app.get("/examples")
async def get_examples():
    """Retourne des exemples de commandes valides"""
    examples = {
        "simple_text": {
            "commands": [
                {"align": "center"},
                {"bold": True},
                {"text": "TEST D'IMPRESSION\n"},
                {"cut": "PART"}
            ]
        },
        "complex_receipt": {
            "commands": [
                {"align": "center"},
                {"bold": True},
                {"text": "MA BOUTIQUE\n"},
                {"text": "================\n"},
                {"align": "left"},
                {"bold": False},
                {"text": "Article 1      10.00€\n"},
                {"text": "Article 2      15.50€\n"},
                {"text": "================\n"},
                {"align": "right"},
                {"bold": True},
                {"text": "TOTAL:     25.50€\n"},
                {"qr": "https://example.com, size=4, ec=0"},
                {"cut": "PART"}
            ]
        },
        "qr_example": {
            "commands": [
                {"align": "center"},
                {"text": "SCANNEZ CE QR CODE\n"},
                {"qr": "https://example.com, size=3, ec=0, model=2"},
                {"cut": "FULL"}
            ]
        },
        "barcode_example": {
            "commands": [
                {"align": "center"},
                {"text": "CODE-BARRES:\n"},
                {"barcode": "123456789012, bc=CODE128, height=64, width=3"},
                {"cut": "PART"}
            ]
        }
    }
    return examples
