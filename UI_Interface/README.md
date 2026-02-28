# ELE 495 – SMD Pick and Place Machine Backend

This repository contains the backend software for the ELE 495 Dissertation Project:
SMD Pick and Place Machine with Vision-Based Verification and Test Station Integration.

The system controls a pick-and-place robot, performs component recognition using a YOLO-based ONNX model, verifies placement accuracy, and integrates a test station for electrical validation.

---

## Project Overview

The backend is built using FastAPI and follows a modular service-based architecture.  
It integrates:

- GRBL-based robot motion control (serial communication)
- Vision-based component detection (YOLO ONNX)
- Placement accuracy verification (distance-based metric)
- Arduino-based test station measurement
- Secure API access (DEMO and REAL modes)
- Web UI integration (snapshot and overlay endpoints)

---

## Project Structure
src/app
|--- core # Configuration and environment settings
|--- routers # API endpoint definitions
|--- services # Robot, camera, vision, and execution logic
|--- vision # YOLO runtime and placement verification
|--- main.py # FastAPI application entry point

---

## Vision System

The vision system is based on a YOLO-style ONNX model.

Key components:

- `yolo_runtime.py`  
  Single source of truth for model loading, preprocessing, postprocessing, and inference.

- `vision_service.py`  
  Backend wrapper that connects the runtime to API endpoints.

- `placement_verify.py`  
  Computes placement accuracy based on:
  - Bounding box center
  - Expected pad center (pixel coordinates)
  - Distance tolerance threshold

### Placement Accuracy Logic

Placement accuracy is calculated using the pixel distance between:

- Detected component center
- Expected pad center

The verification returns:

- Distance in pixels
- Tolerance threshold
- Accuracy score (0–100%)
- Status (OK or FAIL)

---

## Pick and Place Execution Flow

The execution pipeline is managed by `plan_runner.py`:

1. Pick component from feeder
2. Optional vision verification
3. Move to test station
4. Electrical measurement (Arduino ADC)
5. Place component on PCB pad
6. Placement verification using vision

---

## Security Model

The backend operates in two modes:

### DEMO Mode

- Accepts authentication via:
  - Query parameter (`?token=`)
  - `X-API-Key` header

### REAL Mode

- Accepts only `X-API-Key` header
- `/api/config` does not expose the API key
- Prevents API key leakage via URL logging

---

## Environment Configuration

Create a `.env` file in the project root.

Example configuration:
DEMO_MODE=true
API_KEY=your-secret-key

PNP_ROBOT_PORT=/dev/ttyACM0
PNP_ARDUINO_PORT=/dev/ttyUSB0
PNP_CAMERA_INDEX=0

PNP_VISION_MODEL=src/app/vision/best.onnx
PNP_VISION_CONF=0.6

---

## Running the Backend

### 1. Running on a Development PC (Windows / Linux / macOS) [DEMO_MODE]

#### Step 1 - Create a virtual environment
Windows:
python -m venv .venv
.venv\Scripts\activate

Linux / macOS:
python -m venv .venv
source .venv/bin/activate

#### Step 2 - Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

#### Step 3 - Start the server
uvicorn src.app.main:app --host 0.0.0.0 --port 8000

The backend will be available at:
http://localhost:8000

If you want to access it from another device in the same network:
http://YOUR_PC_IP:8000


### 2. Running on Raspberry Pi (LAN / WLAN)

#### Step 1 - Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

#### Step 2 - Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

#### Step 3 - Start the server
uvicorn src.app.main:app --host 0.0.0.0 --port 8000

Accessing from Another Device (LAN/WLAN)
hostname -I

From another device in the same network:
http://RASPBERRY_IP:8000


Access via Tailscale (Remote Access, WAN)

Install Tailscale:

sudo apt install -y tailscale

After connecting the device to your Tailscale network, you can access:
http://100.x.x.x:8000

Replace 100.x.x.x with the Tailscale IP assigned to the Raspberry Pi.

---

## Camera Endpoints

- `GET /api/camera/snapshot`
- `GET /api/camera/overlay`
- `POST /api/camera/restart`

All endpoints require authentication.

---

## Robot and Test Station Integration

- Robot motion is handled via GRBL over serial.
- The test station communicates with Arduino to obtain ADC measurements.
- High-level motion logic is implemented in `robot_actions.py`.
- Coordinate maps are configurable and intended to be calibrated during deployment.

---

## Calibration and Integration Areas

The following modules require calibration depending on hardware setup:

- `robot_actions.py`  
  Feeder coordinates, pad coordinates, and test station position.

- `placement_verify.py`  
  Pad pixel center calibration for accurate placement scoring.

- G-code tuning and mechanical calibration.


---

ELE 495 Dissertation Project  
2026
