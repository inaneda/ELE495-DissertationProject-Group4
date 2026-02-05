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

# router baglama
from src.app.routers import status
from src.app.routers import commands
from src.app.routers import camera
from src.app.routers import plan



# service baglama - tset amacli
from src.app.services.robot_service import robot_service
from src.app.services.arduino_service import arduino_service
from src.app.services.plan_runner import plan_runner


###


# service baglama - test amacli
# lifespan (startup/shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP
    robot_service.start()
    arduino_service.start()
    yield
    # SHUTDOWN
    robot_service.stop()
    arduino_service.stop()
    plan_runner.stop()


# web uygulamasi
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

