"""
File Name       : main.py
Author          : Eda
Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
Created Date    : 2026-02-01
Last Modified   : 2026-02-04

Description:
This file is the main entry point of the backend application.
It initializes the FastAPI server, mounts static files,
loads HTML templates, and includes API routers.

Responsibilities:
    - Start and configure the FastAPI application
    - Serve the web-based user interface (HTML, CSS, JS)
    - Register API routers (status, commands, camera, test station)
    - Act as the central integration point between UI and backend services
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request

from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from src.app.core.config import DEMO_MODE
# router baglama
from src.app.routers import status
from src.app.routers import commands
from src.app.routers import camera
from src.app.routers import plan
from src.app.routers import config as config_router


# service baglama - tset amacli
from src.app.services.robot_service import init_robot_service
from src.app.services.arduino_service import init_arduino_service
from src.app.services.plan_runner import init_plan_runner
from src.app.services.camera_service import init_camera_service

robot_service = None
arduino_service = None
camera_service = None
plan_runner = None

###


# service baglama - test amacli
# lifespan (startup/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    global robot_service, arduino_service, camera_service, plan_runner
    
    print(f"\n{'='*60}")
    print(f"SMD Pick&Place Machine Backend Starting")
    print(f"{'='*60}")
    print(f"Mode: {'DEMO' if DEMO_MODE else 'REAL'}")
    print(f"{'='*60}\n")
    
    # servisleri initialize etme
    robot_service = init_robot_service(demo_mode=DEMO_MODE, port="/dev/ttyACM0")
    arduino_service = init_arduino_service(demo_mode=DEMO_MODE, port="/dev/ttyUSB0")
    camera_service = init_camera_service(demo_mode=DEMO_MODE, device_index=0)
    plan_runner = init_plan_runner()
    
    # real:
    if not DEMO_MODE:
        print("\n[STARTUP] Connecting to hardware...")
        robot_service.connect()
        arduino_service.connect()
        camera_service.open()
    
    # polling baslatma
    print("\n[STARTUP] Starting background services...")
    robot_service.start_polling()
    arduino_service.start_polling()
    
    print("\n All services started successfully\n")
    
    yield
    
    # SHUTDOWN
    print("\n[SHUTDOWN] Stopping services...")
    robot_service.stop_polling()
    arduino_service.stop_polling()
    plan_runner.stop()
    
    if not DEMO_MODE:
        robot_service.disconnect()
        arduino_service.disconnect()
        camera_service.close()
    
    print(" Shutdown complete\n")

# web uygulamasi - fastApi
app = FastAPI(
    title="SMD Pick&Place Machine API",
    description="Backend API for ELE 495 Disertation Project : SMD Pick and Place Machine",
    version="1.0.0",
    lifespan=lifespan
)

# static dosyalar ui_files/static klasorunden geliyor : ui_files/static == localhost:8000/static/... seklinde tarayicidan erisilecek
app.mount(
    "/static", 
    StaticFiles(directory="ui_files/static"), 
    name="static"
)

# html template'i icin : index.html : Jinja2
templates = Jinja2Templates(directory="ui_files/templates")

# endpoint
@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """
    Serve the main dashboard page.

    Parameters:
        request (Request): FastAPI request object (required by Jinja2)

    Returns:
        HTMLResponse: Rendered index.html page
    """
    # templates/index.html dosyasını döndür
    return templates.TemplateResponse(
        "index.html", 
        {"request": request}
    )

# router baglama
app.include_router(status.router)
app.include_router(commands.router)
app.include_router(camera.router)
app.include_router(plan.router)
app.include_router(config_router.router)
