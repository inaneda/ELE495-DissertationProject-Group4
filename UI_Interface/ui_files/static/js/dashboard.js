/**
* File Name       : dashboard.js
* Author          : Eda
* Project         : ELE 495 Dissertation Project - SMD Pick and Place Machine
* Created Date    : 2026-01-25
* Last Modified   : 2026-02-01
* 
* Description:
* This file implements the client-side logic of the web-based user interface.
* Main responsibilities include:
*   - Periodically fetching machine status data from the FastAPI backend
*   - Updating UI elements such as machine status, test results, and task history
*   - Sending control commands (start, stop, reset, test mode selection)
*   - Managing PCB placement selection logic
*   - Handling connection status indicators
*   - Updating the real-time clock on the dashboard
*
* The script communicates with the backend via REST API endpoints
* and is designed for real-time monitoring and control.
*/

"use strict";

// API key
let API_KEY = null;


let selectedPart = null;
// pad - komponent atamalarini tutuyor : { "konum-a": "d1" ... }
const assignments = {};

// ekranda “Pick Order - Place Order” olarak gostermek icin tiklama sirasi
// [{ part:"d1", padName:"konum-a", padLabel:"a" }, ...]
const pairings = [];
// NOTE: pairingOrder is the single source of truth used by the UI logic
const pairingOrder = pairings;
let CAMERA_OK = false;




// DOM - HTML yardimcilari
function $(id){
    return document.getElementById(id);
}

function setText(id, value){
    const el = $(id);
    if (el) el.textContent = value;
}


// UI - arayuzdeki komponent secimi
function setSelectedPart(part){
    selectedPart = part;
    setText("selectedPart", part ? part.toUpperCase() : "-");   // "SELECTED: -" kisminin guncellenmesi icin
    
    // class guncellemesi
    document.querySelectorAll(".pick-btn").forEach((btn) => {
        const p = btn.dataset.pick;          // d1/d2/r1/r2
        btn.classList.toggle("selected", p === part);
    });
}

// UI - arayuzdeki pad butonundaki yazinin guncellenmesi : a -> a (D1) 
function updatePadButton(padName, part){
  const btn = document.querySelector(`.place-btn[data-pad="${padName}"]`);
  if (!btn) return;

  const label = btn.dataset.place || padName; // a/b/c/d
  if (part){
    btn.textContent = `${label} (${part.toUpperCase()})`;
  } else{
    btn.textContent = label;
  }
}


// Pairing panelinin gosterilmesi - rendering
function renderPairingList(){
    const list = $("pairingList");
    if (!list) return;

    // eslestirme yok ise
    if (pairingOrder.length === 0){
        list.innerHTML = `<div class="pairing-empty">Component and pad mapping has not been done yet.</div>`;
        return;
    }
    // satirlar
    const rowsHtml = pairingOrder.map((it) =>{
        return `<div class="pairing-row">
                <span class="pairing-pill">${it.part.toUpperCase()}</span>
                <span class="pairing-arrow">→</span>
                <span class="pairing-pill">${it.padLabel.toUpperCase()}</span>
                </div>`;
    }).join("");

  list.innerHTML = rowsHtml;
}


// eslestirilecek yer secme
function assignPad(padName){
    if(!selectedPart){
        alert(" No component selected; component must be selected first.\n(D1/D2/R1/R2).");
        return;
    }
    const btn = document.querySelector(`.place-btn[data-pad="${padName}"]`);
    const padLabel = btn?.dataset?.place ?? padName;
    
    const alreadyUsedPad = Object.keys(assignments).find(
        (k) => assignments[k] === selectedPart && k !== padName
    );
    if(alreadyUsedPad){
        alert(`${selectedPart.toUpperCase()} already assigned.\n(Choose a different component.)`);
        return;
    }

    // assignments guncellemesi
    assignments[padName] = selectedPart;

    // pad butonunun guncellemesi
    updatePadButton(padName, selectedPart);

    // eslestirme siralamai
    // ayni pad daha once eklendiyse guncellenir, yoksa eklenir?????????????????
    const idx = pairingOrder.findIndex(x => x.padName === padName);
    const item = { part: selectedPart, padName, padLabel };

    if (idx >= 0){
        pairingOrder[idx] = item;
    } else{
        pairingOrder.push(item);
    }

    renderPairingList();
}


// olaylarin baglanmasi
function bindUIEvents(){
    // secme butonlari - pick
    document.querySelectorAll(".pick-btn").forEach((btn) =>{
        
        btn.addEventListener("click", () => {
            const part = btn.dataset.pick; // D1/D2/R1/R2
            setSelectedPart(part);
        });
    });

    // yerlestirme butonlari - place
    document.querySelectorAll(".place-btn").forEach((btn) =>{
        
        btn.addEventListener("click", () => {
            const padName = btn.dataset.pad;       // konum-a ...
            const padLabel = btn.dataset.place;    // a/b/c/d
            assignPad(padName, padLabel);
        });
    });
}


//
//
//

/** BACKEND
* polling - yenileme hizi
* task history, machine status, test station panellerini dolduracak verilerin alımı
* Pi, Arduino, Camera durumu guncellemesi
* START, STOP, RESET butonlarinin calismasi
* pnp dosyasinin robota iletilmesi - sira ve komponent-pad eslestirmesi 
*/

async function apiFetch(url, options = {}){
    const headers = options.headers ? {...options.headers} : {};
    if (API_KEY) headers["X-API-Key"] = API_KEY;

    // content type eklemek icin
    if (options.body && !headers["Content-Type"]){
        headers["Content-Type"] = "application/json";
    }
    return fetch(url, { ...options, headers });
}


// backend config
async function loadConfig() {
    const res = await fetch("/api/config");
    const data = await res.json();
    API_KEY = data.api_key;
}


// backend'e komut gonderme - robot ve test istasyonu icin
async function sendCmd(name, payload=null){
    try{
        const res = await apiFetch("/api/commands/",{
            method: "POST",
            headers: {
                'Content-Type': 'application/json',
                'X-API-Key': API_KEY
            },
            body: JSON.stringify({ name, payload })
        });

        if(!res.ok){
            const txt = await res.text();
            console.error("Command failed:", name, txt);
            alert(`Command failed: ${name}
${txt}`);
            return;
        }

        const data = await res.json();

        if (name === 'reset') {
            // Backend reset succeeded -> clear UI pairing state too
            resetPairingUI();
        }

        console.log(`Command ${name} sent:`, data);

    }catch(error){
        console.error('Command error:', error);
        alert("Command error. Check console.");
    }
}


// send plan butonu icin fonksiyon
async function sendPlan(){
    if (pairingOrder.length === 0){
        alert("Plan is empty. Please do component-pad pairing first.");
        return;
    }
    try{
        const res = await apiFetch("/api/plan",{
            method: "POST",
            body: JSON.stringify({ items: pairingOrder })
        });

        if(!res.ok){
        const txt = await res.text();
        alert("Plan send failed.\n" + txt);
        return;
        }

        const data = await res.json();
        alert(`Plan sent successfully. Steps: ${data.count}`);
    }catch(e){
        console.warn("Plan send error:", e);
        alert("Plan send error. Check console.");
    }
    await fetchStatus();
}


// baglanti durumu icin
function setBadge(id, ok, label){
    const el = document.getElementById(id);
    if(!el) return;

    if(ok === true){
        el.className = "badge text-bg-success";
        el.textContent = `${label}: OK`;
    }else if(ok === false){
        el.className = "badge text-bg-danger";
        el.textContent = `${label}: NO`;
    }else{
        el.className = "badge text-bg-secondary";
        el.textContent = `${label}: ?`;
    }
}


// sistemin tum durumlari icin
async function fetchStatus(){
    try{
        const res = await apiFetch("/api/status/");
        if(!res.ok) 
            return;
        const data = await res.json();

        const planCount = (data.plan || []).length;
        const planTs = data.plan_received_at;

        if (planCount > 0) {
        setText("planInfo", `PLAN: LOADED (${planCount})  ${planTs ?? ""}`.trim());
        } else {
        setText("planInfo", "PLAN: EMPTY");
}

        // robot
        setText("robotStatus", data.robot?.status ?? "-");
        setText("robotTask", data.robot?.current_task ?? "-");
        setText("posX", data.robot?.x ?? "-");
        setText("posY", data.robot?.y ?? "-");
        setText("posZ", data.robot?.z ?? "-");

        // test
        setText("testMode", data.teststation?.mode ?? "-");
        setText("testAdc", data.teststation?.last_adc ?? "-");
        setText("testV", data.teststation?.last_voltage_v ?? "-");
        setText("testResult", data.teststation?.last_result ?? "-");
        setText("testUpdated", data.teststation?.last_updated ?? "-");

        // logs -> gorev gecmisi
        const logs = data.logs || [];
        const historyBox = document.getElementById("historyBox");
        if (historyBox) historyBox.textContent = logs.join("\n");

        // baglanti durumu
        setBadge("badgePi", true, "Pi");
        const conn = data.connections || {};
        
        // yeni connection yapisi (object icinde status var)
        const cam = conn.camera || {};

        // badge guncelle
        setBadge("badgeCamera", cam.status, "Camera");

        // global kamera bilgisi
        CAMERA_OK = cam.status === true;

        // kamera placeholder kontrolu
        const camOk = cam.status === true;

        const anyArduinoOk =
        (conn.arduino_motors?.status === true) ||
            (conn.arduino_teststation?.status === true);
        setBadge("badgeArduino", anyArduinoOk, "Arduino");

        // summary
        document.getElementById("connSummary").textContent = "local network (demo)";

        // kamera placeholder : suan JPEG kullaniyoruz sonra MJPEG'e gecebiliriz
        const camImg = document.getElementById("cameraImg");
        const camPh = document.getElementById("cameraPlaceholder");
        
    
        if (camImg && camPh){
            if(camOk){
                camImg.style.display = "block";
                camPh.style.display = "none";
            } else{
                camImg.style.display = "none";
                camPh.style.display = "grid";
                camImg.src = "";
            }
        }
    }catch(e){
        console.warn("Status fetch error:", e);
        setBadge("badgePi", false, "Pi");
        setBadge("badgeArduino", null, "Arduino");
        setBadge("badgeCamera", null, "Camera");
        document.getElementById("connSummary").textContent = "no connection";
    }
}

// kamera icin yineleme
function refreshCamera(){
    const camImg = document.getElementById("cameraImg");
    if(!camImg) return;
    if(!API_KEY || !CAMERA_OK) return;
    camImg.src = `/api/camera/snapshot?token=${encodeURIComponent(API_KEY)}&t=${Date.now()}`;
}

// start-stop-reset butonlari + send plan butonu
function bindCommandButtons() {
    const startBtn = document.getElementById("btnStart");
    const stopBtn = document.getElementById("btnStop");
    const resetBtn = document.getElementById("btnReset");
    const sendPlanBtn = document.getElementById("btnSendPlan");

    if (startBtn) startBtn.addEventListener("click", () => sendCmd("start"));
    if (stopBtn) stopBtn.addEventListener("click", () => sendCmd("stop"));
    if (resetBtn) resetBtn.addEventListener("click", () => sendCmd("reset"));
    if (sendPlanBtn) sendPlanBtn.addEventListener("click", sendPlan);   
}


// sayfa ilk acildiginda calisacak kod - init
document.addEventListener("DOMContentLoaded",  async () =>{
    
    await loadConfig(); // ilk key alinmali

    setSelectedPart(null);
    renderPairingList();

    bindUIEvents();
    bindCommandButtons();




    fetchStatus();
    setInterval(fetchStatus, 400); // 400ms polling - yenileme
    
    // status ve camera icin yenileme farkli : status 400, camera 1000
    setInterval(refreshCamera, 1000); // 1 FPS
    refreshCamera();
});


// reset ve undo butonu
function resetPairingUI() {
    setSelectedPart(null);

    pairingOrder.length = 0;
    for(const k of Object.keys(assignments)) delete assignments[k];

    document.querySelectorAll('.place-btn').forEach(btn => {
        const originalLabel = btn.getAttribute('data-place'); // "a", "b", "c", "d"
        btn.textContent = originalLabel;
        btn.classList.remove('assigned');
        btn.disabled = false; // tekrar tiklanabilir
    });

    renderPairingList();

    // selected kismini temizleme (setSelectedPart zaten yapar)
    console.log('[RESET] Pairing UI cleared');
}

function undoLastPairing() {
    if (pairingOrder.length === 0) {
        alert("No pairing to undo!");
        return;
    }

    const lastPair = pairingOrder.pop();

    if(lastPair && lastPair.padName){
        delete assignments[lastPair.padName];

        // padleri resetleme
        const placeBtn = document.querySelector(`.place-btn[data-pad="${lastPair.padName}"]`);
        if (placeBtn) {
            const originalLabel = placeBtn.getAttribute('data-place');
            placeBtn.textContent = originalLabel;
            placeBtn.classList.remove('assigned');
            placeBtn.disabled = false;
        }
    }

    renderPairingList();
    console.log('[UNDO] Last pairing removed:', lastPair);
}
