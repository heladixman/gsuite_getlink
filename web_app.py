import asyncio
import json
import os
import sys
import time
from typing import Dict, List, Optional
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
import uvicorn

from capcut_worker import CapcutWorker, RESULTS_FILE, OUTPUT_FILE, cleanup_project_data
from core.config import get_max_threads, get_cooling_delay

app = FastAPI(title="CapCut Multi-Thread Dashboard")

# Global state
log_queue = asyncio.Queue()
latest_frame: bytes = b""
latest_url: str = "about:blank"
is_running = False
should_stop_global = False
active_workers_map: Dict[str, CapcutWorker] = {}
cancelled_emails = set()
account_statuses = []


def on_new_log(log_msg: str):
    try:
        log_queue.put_nowait(log_msg)
    except Exception:
        pass


def on_new_frame(frame_bytes: bytes, current_url: str):
    global latest_frame, latest_url
    latest_frame = frame_bytes
    latest_url = current_url


HTML_CONTENT = """<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CapCut Multi-Thread Dashboard (Max 4 Threads)</title>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #0b0f19;
            --bg-card: #131b2e;
            --bg-card-hover: #1a243d;
            --border: #1e293b;
            --accent-blue: #3b82f6;
            --accent-blue-hover: #2563eb;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --accent-yellow: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', sans-serif;
        }

        body {
            background-color: var(--bg-main);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .header {
            background: #0f172a;
            border-bottom: 1px solid var(--border);
            padding: 14px 28px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .header-title {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1.15rem;
            font-weight: 800;
        }

        .container {
            display: grid;
            grid-template-columns: 480px 1fr;
            gap: 20px;
            padding: 24px 28px;
            flex: 1;
        }

        .card {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
        }

        .card-header {
            font-size: 0.9rem;
            font-weight: 700;
            color: #e2e8f0;
            margin-bottom: 12px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        textarea {
            width: 100%;
            height: 140px;
            background: #0b1120;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 10px;
            color: #38bdf8;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            resize: vertical;
            outline: none;
        }

        .offer-options-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 6px;
        }

        .offer-btn {
            display: flex;
            flex-direction: column;
            align-items: flex-start;
            padding: 12px 14px;
            background: #0b1120;
            border: 1.5px solid #334155;
            border-radius: 10px;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
            user-select: none;
            text-align: left;
            outline: none;
            width: 100%;
        }

        .offer-btn:hover {
            border-color: #64748b;
            background: #111a2e;
        }

        .offer-btn.active {
            border-color: #3b82f6;
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.18), rgba(30, 58, 138, 0.32));
            box-shadow: 0 0 14px rgba(59, 130, 246, 0.25), inset 0 0 0 1px #3b82f6;
        }

        .offer-btn-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            width: 100%;
            margin-bottom: 5px;
        }

        .offer-btn-title {
            font-size: 0.88rem;
            font-weight: 700;
            color: #94a3b8;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: color 0.2s;
        }

        .offer-btn.active .offer-btn-title {
            color: #60a5fa;
        }

        .offer-btn-badge {
            font-size: 0.68rem;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 999px;
            background: #1e293b;
            color: #64748b;
            border: 1px solid #334155;
            transition: all 0.2s;
        }

        .offer-btn.active .offer-btn-badge {
            background: #3b82f6;
            color: #ffffff;
            border-color: #60a5fa;
            box-shadow: 0 0 8px rgba(59, 130, 246, 0.4);
        }

        .offer-btn-desc {
            font-size: 0.72rem;
            color: #64748b;
            line-height: 1.35;
            transition: color 0.2s;
        }

        .offer-btn.active .offer-btn-desc {
            color: #bfdbfe;
        }

        /* Modal Alert Styles */
        .modal-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            width: 100vw;
            height: 100vh;
            background: rgba(11, 15, 25, 0.8);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 9999;
            animation: fadeIn 0.2s ease-out;
        }
        .modal-box {
            background: var(--bg-card);
            border: 1px solid #334155;
            border-radius: 14px;
            padding: 24px;
            width: 90%;
            max-width: 420px;
            text-align: center;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.5);
            animation: scaleIn 0.2s ease-out;
        }
        .modal-title {
            font-size: 1.15rem;
            font-weight: 800;
            color: #f8fafc;
            margin-bottom: 8px;
        }
        .modal-desc {
            font-size: 0.85rem;
            color: #94a3b8;
            line-height: 1.5;
            margin-bottom: 12px;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes scaleIn {
            from { transform: scale(0.95); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }

        /* Proxy Toggle Switch Styles */
        .proxy-toggle-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(15, 23, 42, 0.75);
            border: 1px solid rgba(51, 65, 85, 0.9);
            border-radius: 10px;
            padding: 10px 14px;
            margin-top: 12px;
            margin-bottom: 6px;
            box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3);
            transition: all 0.2s ease;
        }
        .proxy-toggle-container:hover {
            border-color: rgba(56, 189, 248, 0.5);
        }
        .switch {
            position: relative;
            display: inline-block;
            width: 46px;
            height: 24px;
            flex-shrink: 0;
        }
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #334155;
            transition: 0.25s ease-in-out;
            border-radius: 24px;
            border: 1px solid #475569;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 2px;
            bottom: 2px;
            background-color: #f8fafc;
            transition: 0.25s ease-in-out;
            border-radius: 50%;
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.4);
        }
        input:checked + .slider {
            background-color: #0284c7;
            border-color: #38bdf8;
            box-shadow: 0 0 10px rgba(56, 189, 248, 0.4);
        }
        input:checked + .slider:before {
            transform: translateX(22px);
            background-color: #ffffff;
        }

        .btn-group {
            display: flex;
            gap: 10px;
            margin-top: 12px;
        }

        .btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            padding: 10px 16px;
            font-size: 0.85rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            border: none;
            transition: all 0.2s;
        }

        .btn-primary {
            background-color: var(--accent-blue);
            color: white;
            flex: 1;
        }

        .btn-primary:hover {
            background-color: var(--accent-blue-hover);
        }

        .btn-danger {
            background-color: var(--accent-red);
            color: white;
            padding: 10px 20px;
        }

        .btn-sm {
            padding: 4px 8px;
            font-size: 0.75rem;
            background: #1e293b;
            color: #cbd5e1;
            border: 1px solid #334155;
            border-radius: 4px;
            cursor: pointer;
        }

        .btn-action-cancel {
            padding: 3px 8px;
            font-size: 0.7rem;
            font-weight: 600;
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-action-cancel:hover { background: rgba(239, 68, 68, 0.35); }

        .btn-action-stop {
            padding: 3px 8px;
            font-size: 0.7rem;
            font-weight: 600;
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-action-stop:hover { background: rgba(245, 158, 11, 0.35); }

        .btn-action-copy {
            padding: 3px 8px;
            font-size: 0.7rem;
            font-weight: 600;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-action-copy:hover { background: rgba(16, 185, 129, 0.35); }

        .status-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.8rem;
            margin-top: 8px;
        }

        .status-table th {
            text-align: left;
            padding: 8px 6px;
            font-size: 0.75rem;
            color: #64748b;
            border-bottom: 1px solid #1e293b;
            font-weight: 600;
        }

        .status-table td {
            padding: 9px 6px;
            border-bottom: 1px solid #1e293b;
        }

        .badge-status {
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            font-weight: 700;
            text-transform: uppercase;
            display: inline-block;
        }

        .badge-waiting {
            background: rgba(245, 158, 11, 0.15);
            color: #fbbf24;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .badge-processing {
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border: 1px solid rgba(59, 130, 246, 0.3);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { opacity: 0.7; }
            50% { opacity: 1; }
            100% { opacity: 0.7; }
        }

        .badge-success {
            background: rgba(16, 185, 129, 0.2);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .badge-failed {
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .duration-text {
            font-size: 0.7rem;
            color: #94a3b8;
            margin-left: 4px;
            font-family: 'JetBrains Mono', monospace;
        }

        .browser-window {
            background: #020617;
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 400px;
            box-shadow: 0 4px 25px rgba(0, 0, 0, 0.4);
            margin-bottom: 16px;
        }

        .browser-header {
            background: #0f172a;
            padding: 8px 14px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .browser-view {
            flex: 1;
            background: #050b14;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        .browser-view img {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }

        .terminal-card {
            background: #020617;
            border: 1px solid var(--border);
            border-radius: 12px;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            height: 320px;
        }

        .terminal-header {
            background: #0f172a;
            padding: 8px 14px;
            border-bottom: 1px solid var(--border);
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: #94a3b8;
        }

        .terminal-body {
            flex: 1;
            padding: 12px;
            overflow-y: auto;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            line-height: 1.5;
            color: #cbd5e1;
            background: #050b14;
        }

        .log-entry { margin-bottom: 3px; }
        .log-success { color: #4ade80; }
        .log-err { color: #f87171; }
        .log-warn { color: #facc15; }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-title">
            <span style="color: #38bdf8;">CapCut</span> Multi-Thread Dashboard
        </div>
        <div style="display: flex; align-items: center; gap: 14px;">
            <div style="font-size: 0.8rem; color: #94a3b8;">
                Maksimal Thread: <strong style="color: #38bdf8;">3 Browser</strong>
            </div>
            <button class="btn-sm" onclick="cleanData()" style="background: rgba(239, 68, 68, 0.15); color: #f87171; border-color: rgba(239, 68, 68, 0.3);">
                🧹 Bersihkan Cache & Profile
            </button>
        </div>
    </div>

    <div class="container">
        <!-- Left Column: Input & Controls -->
        <div>
            <!-- Account Input Card -->
            <div class="card">
                <div class="card-header">
                    <span>Input Akun (email|password)</span>
                    <button class="btn-sm" onclick="document.getElementById('accountsInput').value=''">Bersihkan</button>
                </div>
                <textarea id="accountsInput" placeholder="email1@gmail.com|pass1&#10;email2@gmail.com|pass2&#10;email3@gmail.com|pass3"></textarea>

                <div style="margin-top: 14px; margin-bottom: 6px;">
                    <div style="display: flex; align-items: center; justify-content: space-between; font-size: 0.8rem; font-weight: 700; color: #cbd5e1; margin-bottom: 6px;">
                        <span>🎯 Pilih Trial Offer:</span>
                        <span style="color: #38bdf8; font-size: 0.72rem; font-weight: 600;">Klik untuk memilih</span>
                    </div>
                    <input type="hidden" id="selectedOfferInput" value="5seat" />
                    <div class="offer-options-grid">
                        <button type="button" id="opt-5seat" class="offer-btn active" onclick="selectOffer('5seat')">
                            <div class="offer-btn-header">
                                <span class="offer-btn-title">👥 5-Seat Team</span>
                                <span class="offer-btn-badge">✓ Terpilih</span>
                            </div>
                            <div class="offer-btn-desc">Offer 5-Seat Team (Join Team)</div>
                        </button>
                        <button type="button" id="opt-individual" class="offer-btn" onclick="selectOffer('individual')">
                            <div class="offer-btn-header">
                                <span class="offer-btn-title">👤 Individual</span>
                                <span class="offer-btn-badge">Pilih</span>
                            </div>
                            <div class="offer-btn-desc">Offer 30D Pro (Individual)</div>
                        </button>
                    </div>
                </div>

                <!-- Proxy Toggle Card -->
                <div class="proxy-toggle-container">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 1.25rem;">🛡️</span>
                        <div>
                            <div style="font-size: 0.82rem; font-weight: 700; color: #f1f5f9;">Gunakan Proxy (proxy.txt)</div>
                            <div id="proxyStatusLabel" style="font-size: 0.72rem; color: #38bdf8; font-weight: 500;">
                                Proxy Aktif (Pengujian Kecepatan & Rotating IP)
                            </div>
                        </div>
                    </div>
                    <label class="switch" title="Toggle On/Off Proxy untuk Browser">
                        <input type="checkbox" id="useProxyToggle" checked onchange="toggleProxyState()">
                        <span class="slider"></span>
                    </label>
                </div>

                <div class="btn-group">
                    <button id="btnStart" class="btn btn-primary" onclick="startBot()">
                        <span id="btnStartText">🚀 Jalankan Multi-Thread</span>
                    </button>
                    <button id="btnStop" class="btn btn-danger" onclick="stopGlobalBot()">
                        <span>⏹️ Stop Semua</span>
                    </button>
                </div>
            </div>

            <!-- Status Akun Terkini -->
            <div class="card">
                <div class="card-header">
                    <span>STATUS AKUN TERKINI</span>
                </div>
                <table class="status-table" id="statusTable">
                    <thead>
                        <tr>
                            <th>Akun Email</th>
                            <th>Status & Durasi</th>
                            <th style="text-align: right;">Aksi</th>
                        </tr>
                    </thead>
                    <tbody id="statusTableBody">
                        <tr><td colspan="3" style="color: #64748b; text-align: center; padding: 12px;">Belum ada antrean akun.</td></tr>
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Right Column: Live Monitor & Logs -->
        <div>
            <div class="browser-window">
                <div class="browser-header">
                    <span style="font-size: 0.8rem; font-weight: 600; color: #cbd5e1;">Live Browser Monitor</span>
                    <span id="currentUrl" style="font-size: 0.75rem; color: #64748b; font-family: monospace;">about:blank</span>
                </div>
                <div class="browser-view">
                    <img id="browserStream" src="/api/stream" alt="Live Browser Stream" />
                </div>
            </div>

            <div class="terminal-card">
                <div class="terminal-header">
                    <span>&gt;_ Terminal Log Stream</span>
                    <button class="btn-sm" onclick="clearLogs()">Clear</button>
                </div>
                <div class="terminal-body" id="logBody">
                    <div class="log-entry">[Ready] Dashboard Multi-Thread siap.</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function clearLogs() {
            document.getElementById('logBody').innerHTML = '';
        }

        function addLog(msg) {
            const body = document.getElementById('logBody');
            const div = document.createElement('div');
            div.className = 'log-entry';
            if (msg.includes('SUKSES') || msg.includes('BERHASIL') || msg.includes('pipopay.com') || msg.includes('berhasil')) div.className += ' log-success';
            else if (msg.includes('Error') || msg.includes('GAGAL') || msg.includes('DIHENTIKAN')) div.className += ' log-err';
            else if (msg.includes('Formulir') || msg.includes('Memilih') || msg.includes('Memasukkan')) div.className += ' log-warn';
            div.innerText = msg;
            body.appendChild(div);
            body.scrollTop = body.scrollHeight;
        }

        const evtSource = new EventSource('/api/logs');
        evtSource.onmessage = function(e) {
            try {
                const data = JSON.parse(e.data);
                if (data.log) addLog(data.log);
                if (data.url) document.getElementById('currentUrl').innerText = data.url;
            } catch(err) {
                addLog(e.data);
            }
        };

        async function cancelSingleAccount(email) {
            await fetch('/api/cancel-single', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: email})
            });
            addLog(`[!] Antrean akun ${email} dibatalkan.`);
            fetchStatus();
        }

        async function stopSingleAccount(email) {
            await fetch('/api/stop-single', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email: email})
            });
            addLog(`[!] Menghentikan worker untuk ${email}...`);
            fetchStatus();
        }

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                const tbody = document.getElementById('statusTableBody');
                
                if (data.accounts && data.accounts.length > 0) {
                    tbody.innerHTML = '';
                    data.accounts.forEach(acc => {
                        const tr = document.createElement('tr');
                        
                        let badgeClass = 'badge-waiting';
                        let actionHtml = '';

                        if (acc.status === 'MENUNGGU') {
                            badgeClass = 'badge-waiting';
                            actionHtml = `<button class="btn-action-cancel" onclick="cancelSingleAccount('${acc.email}')">Batalkan</button>`;
                        } else if (acc.status === 'DIPROSES') {
                            badgeClass = 'badge-processing';
                            actionHtml = `<button class="btn-action-stop" onclick="stopSingleAccount('${acc.email}')">Hentikan</button>`;
                        } else if (acc.status === 'SUKSES') {
                            badgeClass = 'badge-success';
                            if (acc.link) {
                                actionHtml = `<button class="btn-action-copy" onclick="navigator.clipboard.writeText('${acc.link}'); alert('Link copied!');">📋 Copy Link</button>`;
                            }
                        } else {
                            badgeClass = 'badge-failed';
                            actionHtml = `<span style="color: #64748b; font-size: 0.7rem;">-</span>`;
                        }

                        let durationSpan = acc.duration ? `<span class="duration-text">(${acc.duration})</span>` : '';

                        tr.innerHTML = `
                            <td style="font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; word-break: break-all;">${acc.email}</td>
                            <td><span class="badge-status ${badgeClass}">${acc.status}</span>${durationSpan}</td>
                            <td style="text-align: right;">${actionHtml}</td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            } catch(e) {}
        }
        setInterval(fetchStatus, 1200);

        let currentOffer = '5seat';

        function selectOffer(type) {
            currentOffer = type;
            const input = document.getElementById('selectedOfferInput');
            if (input) input.value = type;

            const btn5 = document.getElementById('opt-5seat');
            const btnInd = document.getElementById('opt-individual');

            if (type === '5seat') {
                if (btn5) {
                    btn5.classList.add('active');
                    const badge = btn5.querySelector('.offer-btn-badge');
                    if (badge) badge.innerText = '✓ Terpilih';
                }
                if (btnInd) {
                    btnInd.classList.remove('active');
                    const badge = btnInd.querySelector('.offer-btn-badge');
                    if (badge) badge.innerText = 'Pilih';
                }
            } else if (type === 'individual' || type === '30d') {
                if (btnInd) {
                    btnInd.classList.add('active');
                    const badge = btnInd.querySelector('.offer-btn-badge');
                    if (badge) badge.innerText = '✓ Terpilih';
                }
                if (btn5) {
                    btn5.classList.remove('active');
                    const badge = btn5.querySelector('.offer-btn-badge');
                    if (badge) badge.innerText = 'Pilih';
                }
            }
        }

        function showAlertModal() {
            document.getElementById('modalAlert').style.display = 'flex';
        }

        function closeAlertModal() {
            document.getElementById('modalAlert').style.display = 'none';
        }

        function toggleProxyState() {
            const toggle = document.getElementById('useProxyToggle');
            const label = document.getElementById('proxyStatusLabel');
            if (toggle && label) {
                if (toggle.checked) {
                    label.innerText = 'Proxy Aktif (Pengujian Kecepatan & Rotating IP)';
                    label.style.color = '#38bdf8';
                } else {
                    label.innerText = 'Proxy Nonaktif (Direct Connection / IP Lokal)';
                    label.style.color = '#94a3b8';
                }
            }
        }

        async function startBot() {
            const rawAccounts = document.getElementById('accountsInput').value.trim();
            if (!rawAccounts) {
                alert('Silakan masukkan setidaknya satu akun (format: email|password)');
                return;
            }

            const input = document.getElementById('selectedOfferInput');
            const selectedOffer = currentOffer || (input ? input.value : '');

            // Mandatory Trial Offer Selection Validation
            if (!selectedOffer) {
                showAlertModal();
                return;
            }

            const toggleEl = document.getElementById('useProxyToggle');
            const useProxy = toggleEl ? toggleEl.checked : true;

            document.getElementById('btnStartText').innerText = 'Memproses Multi-Thread...';

            const res = await fetch('/api/start', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    accounts: rawAccounts,
                    claim_type: selectedOffer,
                    use_proxy: useProxy
                })
            });
            const data = await res.json();
            if (data.status === 'error') {
                alert(data.message || 'Gagal memulai proses!');
                document.getElementById('btnStartText').innerText = '🚀 Jalankan Multi-Thread';
                return;
            }
            const offerLabel = selectedOffer === '5seat' ? '5-Seat Team' : 'Individual (30D Pro)';
            const proxyLabel = useProxy ? 'Proxy Aktif' : 'Direct IP';
            addLog(`[*] Memulai proses untuk ${data.total} akun dengan ${data.active_threads} browser paralel (Offer: ${offerLabel}, ${proxyLabel})...`);
        }

        async function stopGlobalBot() {
            await fetch('/api/stop', {method: 'POST'});
            addLog('[!] Perintah STOP dikirim ke seluruh worker.');
            document.getElementById('btnStartText').innerText = '🚀 Jalankan Multi-Thread';
        }

        async function cleanData() {
            if (confirm('Apakah Anda ingin membersihkan seluruh cache, logs, dan temporary profile?')) {
                const res = await fetch('/api/clean-data', {method: 'POST'});
                const data = await res.json();
                clearLogs();
                addLog('[🧹] Seluruh cache, temporary browser profile, dan logs berhasil dibersihkan dari disk!');
                alert('Cache dan profile berhasil dibersihkan!');
            }
        }
    </script>

    <!-- Mandatory Offer Selection Popup Modal -->
    <div id="modalAlert" class="modal-backdrop" style="display: none;">
        <div class="modal-box">
            <div style="font-size: 2.5rem; margin-bottom: 6px;">⚠️</div>
            <div class="modal-title">Wajib Memilih Trial Offer!</div>
            <div class="modal-desc">
                Anda belum memilih jenis <b>Trial Offer</b>.<br>
                Silakan pilih salah satu opsi offer terlebih dahulu sebelum melanjutkan proses:
                <div style="margin-top: 12px; padding: 12px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; border: 1px dashed rgba(59, 130, 246, 0.35); font-size: 0.8rem; color: #93c5fd; text-align: left; line-height: 1.6;">
                    • <b>5-Seat</b>: Offer 5-Seat Team<br>
                    • <b>Individual</b>: Offer 30D Pro
                </div>
            </div>
            <button class="btn btn-primary" style="width: 100%; margin-top: 14px;" onclick="closeAlertModal()">
                <span>Saya Mengerti & Pilih Opsi</span>
            </button>
        </div>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    return HTMLResponse(content=HTML_CONTENT)


@app.get("/api/logs")
async def sse_logs(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                msg = await asyncio.wait_for(log_queue.get(), timeout=1.0)
                yield f"data: {json.dumps({'log': msg, 'url': latest_url})}\n\n"
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'ping': True, 'url': latest_url})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/stream")
async def live_stream(request: Request):
    async def frame_generator():
        blank = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        while True:
            if await request.is_disconnected():
                break
            frame = latest_frame if latest_frame else blank
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            await asyncio.sleep(0.3)

    return StreamingResponse(frame_generator(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/status")
async def get_status():
    return {"accounts": account_statuses, "is_running": is_running}


async def background_bot_task(accounts: List[tuple], claim_type: str, use_proxy: bool = True):
    global is_running, should_stop_global, active_workers_map, cancelled_emails, account_statuses
    is_running = True
    should_stop_global = False
    active_workers_map.clear()

    max_limit = get_max_threads()
    max_workers = min(len(accounts), max_limit)
    semaphore = asyncio.Semaphore(max_workers)
    proxy_mode_str = "AKTIF (proxy.txt)" if use_proxy else "NONAKTIF (Direct IP)"
    on_new_log(f"[*] Meluncurkan {len(accounts)} akun dengan {max_workers} browser paralel aktif (MAX_THREADS={max_limit}, Proxy: {proxy_mode_str})...")

    async def process_account_task(email: str, pwd: str):
        if should_stop_global or email in cancelled_emails:
            for s in account_statuses:
                if s["email"] == email and s["status"] == "MENUNGGU":
                    s["status"] = "DIBATALKAN"
            return

        async with semaphore:
            if should_stop_global or email in cancelled_emails:
                for s in account_statuses:
                    if s["email"] == email and s["status"] == "MENUNGGU":
                        s["status"] = "DIBATALKAN"
                return

            t_start = time.time()
            for s in account_statuses:
                if s["email"] == email:
                    s["status"] = "DIPROSES"
                    break

            worker = CapcutWorker(log_callback=on_new_log, frame_callback=on_new_frame)
            active_workers_map[email] = worker

            try:
                res = await worker.process_single_account(email, pwd, claim_type, use_proxy=use_proxy)
                elapsed = time.time() - t_start
                mins, secs = divmod(elapsed, 60)
                dur_str = f"{int(mins)}m {secs:.1f}s" if mins > 0 else f"{secs:.1f}s"

                for s in account_statuses:
                    if s["email"] == email:
                        s["status"] = res["status"]
                        s["link"] = res.get("link")
                        s["duration"] = dur_str
                        break
            except Exception as err:
                for s in account_statuses:
                    if s["email"] == email:
                        s["status"] = "GAGAL"
                        break
            finally:
                active_workers_map.pop(email, None)
                # Cooling delay before next account slot is taken
                cooling_secs = get_cooling_delay()
                if cooling_secs > 0 and not should_stop_global and email != accounts[-1][0]:
                    on_new_log(f"⏳ [Cooling Process] Jeda {cooling_secs} detik sebelum memproses akun berikutnya...")
                    await asyncio.sleep(cooling_secs)

    tasks = [process_account_task(email, pwd) for email, pwd in accounts]
    await asyncio.gather(*tasks)

    is_running = False
    clean_info = cleanup_project_data()
    on_new_log(f"[+] Selesai memproses seluruh antrean akun. Seluruh cache & profile otomatis dibersihkan (Profiles cleaned: {clean_info.get('cleaned_profiles', 0)}).")


@app.post("/api/clean-data")
async def clean_all_data():
    res = cleanup_project_data()
    on_new_log(f"[🧹] Pembersihan manual berhasil: {res.get('cleaned_profiles', 0)} profile & {res.get('cleaned_pycache', 0)} pycache dibersihkan.")
    return {"status": "success", "detail": res}


@app.post("/api/start")
async def start_job(request: Request):
    global is_running, account_statuses, cancelled_emails
    data = await request.json()
    raw = data.get("accounts", "")
    claim_type = (data.get("claim_type") or "").strip().lower()
    use_proxy = bool(data.get("use_proxy", True))

    # Mandatory Trial Offer validation
    if not claim_type or claim_type not in ["5seat", "individual", "30d"]:
        return JSONResponse(
            status_code=400,
            content={"status": "error", "message": "Opsi Trial Offer ('5seat' atau 'individual') wajib dipilih sebelum memulai proses!"}
        )

    # Normalize 'individual' to '30d'
    if claim_type == "individual":
        claim_type = "30d"

    parsed_accounts = []
    account_statuses = []
    cancelled_emails.clear()

    for line in raw.strip().split("\n"):
        line = line.strip()
        if line and "|" in line:
            parts = line.split("|")
            email, pwd = parts[0].strip(), parts[1].strip()
            parsed_accounts.append((email, pwd))
            account_statuses.append({"email": email, "status": "MENUNGGU", "link": None, "duration": None})

    max_limit = get_max_threads()
    active_threads = min(len(parsed_accounts), max_limit) if parsed_accounts else 0
    if parsed_accounts:
        asyncio.create_task(background_bot_task(parsed_accounts, claim_type, use_proxy=use_proxy))

    return {"status": "started", "total": len(parsed_accounts), "active_threads": active_threads}


@app.post("/api/stop")
async def stop_all_job():
    global should_stop_global, active_workers_map
    should_stop_global = True
    for w in active_workers_map.values():
        w.should_stop = True
    for s in account_statuses:
        if s["status"] in ["MENUNGGU", "DIPROSES"]:
            s["status"] = "DIHENTIKAN"
    return {"status": "stopping_all"}


@app.post("/api/cancel-single")
async def cancel_single_job(request: Request):
    global cancelled_emails, account_statuses
    data = await request.json()
    email = data.get("email")
    if email:
        cancelled_emails.add(email)
        for s in account_statuses:
            if s["email"] == email:
                s["status"] = "DIBATALKAN"
    return {"status": "cancelled", "email": email}


@app.post("/api/stop-single")
async def stop_single_job(request: Request):
    global active_workers_map, account_statuses
    data = await request.json()
    email = data.get("email")
    if email and email in active_workers_map:
        worker = active_workers_map[email]
        worker.should_stop = True
        for s in account_statuses:
            if s["email"] == email:
                s["status"] = "DIHENTIKAN"
    return {"status": "stopped_single", "email": email}


if __name__ == "__main__":
    print("=================================================================")
    print("  CapCut Web Dashboard running on http://localhost:5000 ")
    print("=================================================================")
    uvicorn.run(app, host="0.0.0.0", port=5000, log_level="warning")
