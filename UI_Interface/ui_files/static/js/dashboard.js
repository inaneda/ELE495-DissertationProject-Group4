/**
* File Name       : dashboard.js
* Author          : Eda
* Project         : ELE 496 Dissertation Project - SMD Pick and Place Machine
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

let selectedPart = null;
// pad - komponent atamalarini tutuyor : { "konum-a": "d1" ... }
const assignments = {};

// ekranda “Pick Order - Place Order” olarak gostermek icin tiklama sirasi
// [{ part:"d1", padName:"konum-a", padLabel:"a" }, ...]
const pairingOrder = [];


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

// backend'e komut gonderme - robot ve test istasyonu icin
async function sendCmd(name, payload=null){
    try{
        await fetch("/api/commands/",{
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({name, payload})
        });
    }catch(e){
        console.warn("Command error:", e);
    }
    await fetchStatus(); // komuttan sonra yenile
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
        const res = await fetch("/api/status/");
        if(!res.ok) 
            return;
        const data = await res.json();

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
        setBadge("badgeArduino", conn.arduino, "Arduino");
        setBadge("badgeCamera", conn.camera, "Camera");

        // summary
        document.getElementById("connSummary").textContent = "local network (demo)";

        // kamera placeholder: simdilik bos sonra bak !!!!!!
        const camImg = document.getElementById("cameraImg");
        const camPh = document.getElementById("cameraPlaceholder");
        if (camImg && camPh){
            if(camImg.src && camImg.src.length > 0){
                camImg.style.display = "block";
                camPh.style.display = "none";
            } else{
                camImg.style.display = "none";
                camPh.style.display = "grid";
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

// start-stop-reset butonlari
function bindCommandButtons() {
    const startBtn = document.getElementById("btnStart");
    const stopBtn = document.getElementById("btnStop");
    const resetBtn = document.getElementById("btnReset");

    if (startBtn) startBtn.addEventListener("click", () => sendCmd("start"));
    if (stopBtn) stopBtn.addEventListener("click", () => sendCmd("stop"));
    if (resetBtn) resetBtn.addEventListener("click", () => sendCmd("reset"));
}


// sayfa ilk acildiginda calisacak kod - init
document.addEventListener("DOMContentLoaded", () =>{
    setSelectedPart(null);
    renderPairingList();
    bindUIEvents();
    bindCommandButtons();
    fetchStatus();
    setInterval(fetchStatus, 400); // 400ms polling - yenileme
});

