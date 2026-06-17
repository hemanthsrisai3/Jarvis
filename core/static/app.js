// J.A.R.V.I.S. Frontend Orchestration

// State Variables
let sessionId = localStorage.getItem("jarvis_session_id");
if (!sessionId) {
    sessionId = "session_" + Date.now();
    localStorage.setItem("jarvis_session_id", sessionId);
}

let speechEnabled = localStorage.getItem("jarvis_speech_enabled") !== "false";
let isSpeaking = false;
let currentAudio = null;
let audioCtx = null;
let analyser = null;
let source = null;
let animationFrameId = null;

// UI Elements
const sphere = document.getElementById("jarvis-core-sphere");
const stateLabel = document.getElementById("core-state-label");
const voiceToggle = document.getElementById("voice-toggle");
const messagesLog = document.getElementById("messages-log");
const userPrompt = document.getElementById("user-prompt");
const sendBtn = document.getElementById("send-btn");
const toolLog = document.getElementById("tool-log");
const sessionsContainer = document.getElementById("sessions-container");
const clearSessionBtn = document.getElementById("clear-session-btn");

// Initialize UI States
updateVoiceButtonUI();
loadSessions();
loadChatHistory(sessionId);
startSystemStatsPolling();

// 1. System Stats Background Polling
function startSystemStatsPolling() {
    updateSystemStats();
    setInterval(updateSystemStats, 3000);
}

async function updateSystemStats() {
    try {
        const res = await fetch("/api/system-stats");
        if (res.ok) {
            const data = await res.json();
            document.getElementById("cpu-bar").style.width = `${data.cpu}%`;
            document.getElementById("cpu-val").innerText = `${Math.round(data.cpu)}%`;
            
            document.getElementById("ram-bar").style.width = `${data.ram}%`;
            document.getElementById("ram-val").innerText = `${Math.round(data.ram)}%`;
            
            document.getElementById("disk-bar").style.width = `${data.disk}%`;
            document.getElementById("disk-val").innerText = `${Math.round(data.disk)}%`;

            // Process any fired alarms or timers
            if (data.alerts && data.alerts.length > 0) {
                data.alerts.forEach(alert => {
                    // Create visual alert card in tool log panel
                    const alertId = `alert-fired-${alert.id}`;
                    const alertEl = document.createElement("div");
                    alertEl.id = alertId;
                    alertEl.className = "tool-alert success";
                    alertEl.innerHTML = `
                        <div><strong>[${alert.type.toUpperCase()} TRIGGERED]</strong></div>
                        <div>Label: <span>${alert.label}</span></div>
                        <div style="font-size: 10px; opacity: 0.8; margin-top: 3px;">Scheduled target reached.</div>
                    `;
                    toolLog.appendChild(alertEl);
                    setTimeout(() => {
                        alertEl.style.opacity = "0";
                        setTimeout(() => alertEl.remove(), 500);
                    }, 8000);

                    // Play sci-fi alert sound and speak
                    playAlertSound();
                    speak(`Sir, your ${alert.type.toLowerCase()} for "${alert.label}" has completed.`);
                });
            }

            // Render active alarms and timers in the sidebar
            renderActiveAlerts(data.active_alerts);
        }
    } catch (err) {
        console.warn("Failed to update system metrics", err);
    }
}

function renderActiveAlerts(activeAlerts) {
    const container = document.getElementById("alerts-container");
    if (!container) return;

    if (!activeAlerts || activeAlerts.length === 0) {
        container.innerHTML = `<div style="font-size: 11px; color: var(--text-secondary); text-align: center; padding: 10px; opacity: 0.6; font-style: italic;">NO PENDING PROTOCOLS</div>`;
        return;
    }

    container.innerHTML = "";
    activeAlerts.forEach(alert => {
        const item = document.createElement("div");
        item.className = "alert-item";
        
        let timeLabel = "";
        if (alert.type === "Timer") {
            const mins = Math.floor(alert.remaining / 60);
            const secs = alert.remaining % 60;
            const minsStr = mins.toString().padStart(2, '0');
            const secsStr = secs.toString().padStart(2, '0');
            timeLabel = `${minsStr}:${secsStr} remaining`;
        } else {
            // Alarm
            const date = new Date(alert.target_time * 1000);
            const hours = date.getHours();
            const mins = date.getMinutes().toString().padStart(2, '0');
            const ampm = hours >= 12 ? 'PM' : 'AM';
            const displayHours = (hours % 12 || 12).toString().padStart(2, '0');
            timeLabel = `Target: ${displayHours}:${mins} ${ampm}`;
        }

        item.innerHTML = `
            <div class="alert-info">
                <div class="alert-label" title="${alert.label}">${alert.type.toUpperCase()}: ${alert.label}</div>
                <div class="alert-time">${timeLabel}</div>
            </div>
            <button class="alert-abort-btn" onclick="abortAlert('${alert.id}', '${alert.type}', '${alert.label}')">ABORT</button>
        `;
        container.appendChild(item);
    });
}

async function abortAlert(id, type, label) {
    try {
        const res = await fetch("/api/cancel-alert", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ id: id })
        });
        if (res.ok) {
            playAbortSound();
            speak(`Aborted ${type.toLowerCase()} for "${label}".`);
            updateSystemStats();
        } else {
            console.error("Failed to cancel alert on backend.");
        }
    } catch (err) {
        console.error("Error canceling alert:", err);
    }
}

function playAbortSound() {
    try {
        const synthCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = synthCtx.createOscillator();
        const gain = synthCtx.createGain();
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(220, synthCtx.currentTime); // Warning buzz
        gain.gain.setValueAtTime(0.08, synthCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, synthCtx.currentTime + 0.25);
        osc.connect(gain);
        gain.connect(synthCtx.destination);
        osc.start();
        osc.stop(synthCtx.currentTime + 0.3);
    } catch (e) {
        console.warn("Failed to play abort sound:", e);
    }
}

// Expose abort function to window object so it can be called from inline onclick handlers
window.abortAlert = abortAlert;

function playAlertSound() {
    try {
        const synthCtx = new (window.AudioContext || window.webkitAudioContext)();
        
        // Futurist triple beep
        const playBeep = (time, freq) => {
            const osc = synthCtx.createOscillator();
            const gain = synthCtx.createGain();
            
            osc.type = "sine";
            osc.frequency.setValueAtTime(freq, time);
            
            gain.gain.setValueAtTime(0.12, time);
            gain.gain.exponentialRampToValueAtTime(0.001, time + 0.25);
            
            osc.connect(gain);
            gain.connect(synthCtx.destination);
            
            osc.start(time);
            osc.stop(time + 0.3);
        };
        
        const now = synthCtx.currentTime;
        playBeep(now, 880);       // High A note
        playBeep(now + 0.12, 880);  // Second beep
        playBeep(now + 0.24, 1174.66); // Higher D note (clean sci-fi chime)
    } catch (e) {
        console.warn("Failed to play alert synth sound:", e);
    }
}

// 2. Active Session Management
async function loadSessions() {
    try {
        const res = await fetch("/api/sessions");
        if (res.ok) {
            const data = await res.json();
            sessionsContainer.innerHTML = "";
            
            if (data.sessions && data.sessions.length > 0) {
                data.sessions.forEach(sess => {
                    const item = document.createElement("div");
                    item.className = `session-item ${sess.session_id === sessionId ? "active" : ""}`;
                    item.innerText = sess.session_id.substring(0, 18);
                    item.title = sess.session_id;
                    item.addEventListener("click", () => switchSession(sess.session_id));
                    sessionsContainer.appendChild(item);
                });
            } else {
                // Add current session if none exist
                const item = document.createElement("div");
                item.className = "session-item active";
                item.innerText = sessionId.substring(0, 18);
                sessionsContainer.appendChild(item);
            }
        }
    } catch (err) {
        console.error("Failed to load sessions", err);
    }
}

async function switchSession(id) {
    if (isSpeaking) {
        stopSpeaking();
    }
    sessionId = id;
    localStorage.setItem("jarvis_session_id", sessionId);
    
    // Highlight active session
    document.querySelectorAll(".session-item").forEach(item => {
        if (item.title === id) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });

    loadChatHistory(sessionId);
}

async function loadChatHistory(id) {
    messagesLog.innerHTML = "";
    try {
        const res = await fetch(`/api/history?session_id=${id}`);
        if (res.ok) {
            const data = await res.json();
            if (data.history && data.history.length > 0) {
                data.history.forEach(msg => {
                    // Skip system or tool messages in history render, only show user and assistant
                    if (msg.role === "user" || msg.role === "assistant") {
                        appendMessage(msg.role, msg.content);
                    }
                });
                scrollToBottom();
            } else {
                renderWelcomeMessage();
            }
        }
    } catch (err) {
        console.error("Failed to load history", err);
        renderWelcomeMessage();
    }
}

function renderWelcomeMessage() {
    messagesLog.innerHTML = `
        <div class="system-welcome">
            <div class="welcome-title">INITIALIZATION COMPLETE</div>
            <p>Welcome back, sir. Neural link established. The local core engine is fully loaded and ready to assist you. Voice feedback is active.</p>
        </div>
    `;
}

// 3. Web Speech API (Pulsing Sphere Sync)
voiceToggle.addEventListener("click", () => {
    speechEnabled = !speechEnabled;
    localStorage.setItem("jarvis_speech_enabled", speechEnabled);
    updateVoiceButtonUI();
    if (!speechEnabled && isSpeaking) {
        stopSpeaking();
    }
});

function updateVoiceButtonUI() {
    if (speechEnabled) {
        voiceToggle.classList.add("active");
        voiceToggle.innerText = "SPEECH: ENABLED";
    } else {
        voiceToggle.classList.remove("active");
        voiceToggle.innerText = "SPEECH: MUTED";
    }
}

function stopSpeaking() {
    if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
    }
    if (animationFrameId) {
        cancelAnimationFrame(animationFrameId);
        animationFrameId = null;
    }
    isSpeaking = false;
    sphere.classList.remove("speaking");
    sphere.style.transform = "";
    stateLabel.innerText = "CORE IDLE";
}

function cleanTextForSpeech(text) {
    // Strip markdown code blocks to prevent spelling out raw code lines
    let clean = text.replace(/```[\s\S]*?```/g, " [File block contents omitted] ");
    // Strip inline code symbols
    clean = clean.replace(/`([^`]+)`/g, "$1");
    // Strip common markdown elements
    clean = clean.replace(/[\#\*\_\[\]\-\+\>]/g, " ");
    return clean.trim();
}

function speak(text) {
    if (!speechEnabled) return;

    // Stop active speech
    stopSpeaking();

    const textToSpeak = cleanTextForSpeech(text);
    if (!textToSpeak) return;

    isSpeaking = true;
    
    // Create new audio element
    const encodedText = encodeURIComponent(textToSpeak);
    currentAudio = new Audio(`/api/tts?text=${encodedText}`);
    
    // We want to analyze the audio to pulse the sphere
    currentAudio.crossOrigin = "anonymous";
    
    currentAudio.onplay = () => {
        sphere.classList.add("speaking");
        stateLabel.innerText = "CORE TRANSMITTING";
        
        try {
            // Setup Web Audio context to capture volume fluctuations
            if (!audioCtx) {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (!analyser) {
                analyser = audioCtx.createAnalyser();
                analyser.fftSize = 256;
            }
            
            // Disconnect old source if exists
            if (source) {
                source.disconnect();
            }
            
            source = audioCtx.createMediaElementSource(currentAudio);
            source.connect(analyser);
            analyser.connect(audioCtx.destination);
            
            const bufferLength = analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            
            function animateSphere() {
                if (!isSpeaking) return;
                
                analyser.getByteFrequencyData(dataArray);
                
                // Calculate average volume
                let total = 0;
                for (let i = 0; i < bufferLength; i++) {
                    total += dataArray[i];
                }
                const average = total / bufferLength;
                
                // Map volume to scale (1.0 to 1.35)
                const scale = 1.0 + (average / 128.0) * 0.35;
                sphere.style.transform = `scale(${scale})`;
                
                animationFrameId = requestAnimationFrame(animateSphere);
            }
            
            // Resume context if suspended (browser security fallback)
            if (audioCtx.state === 'suspended') {
                audioCtx.resume();
            }
            
            animateSphere();
        } catch (e) {
            console.warn("Web Audio API not fully allowed/initialized:", e);
            // Fallback micro-pulse animation if Web Audio API fails
            let pulseInterval = setInterval(() => {
                if (!isSpeaking) {
                    clearInterval(pulseInterval);
                    return;
                }
                sphere.style.transform = "scale(1.18)";
                setTimeout(() => {
                    if (isSpeaking) sphere.style.transform = "scale(1.05)";
                }, 150);
            }, 400);
        }
    };

    currentAudio.onended = () => {
        stopSpeaking();
    };

    currentAudio.onerror = (e) => {
        console.error("Audio playback error", e);
        stopSpeaking();
    };

    currentAudio.play().catch(err => {
        console.error("TTS play catch", err);
        stopSpeaking();
    });
}

// 4. Custom Terminal Alerts for Tool Executions
function triggerToolAlert(toolName, isStart, details = "") {
    const alertId = `alert-${toolName}`;
    let alertEl = document.getElementById(alertId);

    if (isStart) {
        // Create alert
        alertEl = document.createElement("div");
        alertEl.id = alertId;
        alertEl.className = "tool-alert";
        alertEl.innerHTML = `
            <div><strong>[RUNNING PROTOCOL]</strong></div>
            <div>Executing tool: <span>${toolName}</span></div>
            <div style="font-size: 10px; color: var(--text-secondary); margin-top: 3px;">Arguments: ${JSON.stringify(details)}</div>
        `;
        toolLog.appendChild(alertEl);
        
        // Change core status
        stateLabel.innerText = "CORE COMPUTING";
        sphere.style.transform = "scale(1.15)";
    } else {
        // Finish alert
        if (alertEl) {
            alertEl.classList.add("success");
            alertEl.innerHTML = `
                <div><strong>[PROTOCOL COMPLETE]</strong></div>
                <div>Executed tool: <span>${toolName}</span></div>
                <div style="font-size: 10px; opacity: 0.8; margin-top: 3px; max-height: 40px; overflow: hidden; text-overflow: ellipsis;">Output logged to context.</div>
            `;
            // Remove after 3.5 seconds
            setTimeout(() => {
                alertEl.style.opacity = "0";
                setTimeout(() => alertEl.remove(), 500);
            }, 3500);
        }
        
        stateLabel.innerText = "CORE IDLE";
        sphere.style.transform = "";
    }
}

// 5. Chat Transmission (SSE Reader)
async function sendCommand() {
    const prompt = userPrompt.value.trim();
    if (!prompt) return;

    if (isSpeaking) {
        stopSpeaking();
    }

    userPrompt.value = "";
    appendMessage("user", prompt);
    scrollToBottom();

    // Show assistant typing skeleton
    const assistantBubble = appendMessage("assistant", "");
    const textSpan = assistantBubble.querySelector(".msg-text");
    textSpan.innerHTML = "<span class='pulse-dot' style='display:inline-block'></span> Generating response...";
    scrollToBottom();

    stateLabel.innerText = "CORE PROCESSOR";
    sphere.classList.add("speaking");

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                session_id: sessionId,
                message: prompt
            })
        });

        if (!response.ok) {
            throw new Error(`Server returned error status ${response.status}`);
        }

        // Clear generating text indicator
        textSpan.innerHTML = "";
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let accumulatedResponse = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            // Split chunks by Server-Sent Events separator
            const lines = chunk.split("\n\n");
            
            for (let line of lines) {
                if (line.startsWith("data: ")) {
                    try {
                        const event = JSON.parse(line.substring(6));
                        
                        if (event.type === "text") {
                            accumulatedResponse += event.content;
                            textSpan.innerHTML = formatMarkdown(accumulatedResponse);
                            scrollToBottom();
                        } else if (event.type === "tool_start") {
                            triggerToolAlert(event.tool_name, true, event.arguments);
                        } else if (event.type === "tool_end") {
                            triggerToolAlert(event.tool_name, false);
                        } else if (event.type === "error") {
                            textSpan.innerHTML += `<div style="color:#ff3366">Error: ${event.content}</div>`;
                            scrollToBottom();
                        }
                    } catch (parseErr) {
                        // Incomplete JSON buffer or keepalive
                        console.debug("SSE Parse skip line:", line);
                    }
                }
            }
        }

        stateLabel.innerText = "CORE IDLE";
        sphere.classList.remove("speaking");

        // Trigger TTS read out
        speak(accumulatedResponse);
        
        // Reload sessions list to capture new session
        loadSessions();

    } catch (err) {
        console.error("Chat communication failure", err);
        textSpan.innerHTML = `<span style="color:#ff3366">Failed connection to core: ${err.message}</span>`;
        stateLabel.innerText = "CORE ERROR";
        sphere.classList.remove("speaking");
    }
}

// Message Rendering Helpers
function appendMessage(role, content) {
    const bubble = document.createElement("div");
    bubble.className = `message-bubble ${role}`;
    
    const sender = document.createElement("div");
    sender.className = "msg-sender";
    sender.innerText = role === "user" ? "USER CONSOLE" : "J.A.R.V.I.S.";
    
    const text = document.createElement("div");
    text.className = "msg-text";
    text.innerHTML = formatMarkdown(content);
    
    bubble.appendChild(sender);
    bubble.appendChild(text);
    messagesLog.appendChild(bubble);
    return bubble;
}

function scrollToBottom() {
    messagesLog.scrollTop = messagesLog.scrollHeight;
}

// Basic markdown formatter to handle bold and code blocks
function formatMarkdown(text) {
    if (!text) return "";
    
    let html = text;
    // Replace HTML entity symbols
    html = html.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    
    // Replace multi-line code blocks: ```python ... ```
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
        return `<pre><code class="language-${lang}">${code.trim()}</code></pre>`;
    });
    
    // Replace inline code ticks: `foo`
    html = html.replace(/`([^`\n]+)`/g, "<code>$1</code>");
    
    // Replace bold formatting: **foo**
    html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    
    return html;
}

// 6. PURGE active history
clearSessionBtn.addEventListener("click", async () => {
    if (confirm("Are you sure you want to purge cognitive records for the current session?")) {
        try {
            const res = await fetch("/api/clear", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: sessionId })
            });
            if (res.ok) {
                stopSpeaking();
                messagesLog.innerHTML = "";
                renderWelcomeMessage();
                triggerToolAlert("memory_purge", true, { session: sessionId });
                setTimeout(() => triggerToolAlert("memory_purge", false), 1000);
            }
        } catch (err) {
            alert("Protocol error: Unable to purge database records.");
        }
    }
});

// Event Bindings
sendBtn.addEventListener("click", sendCommand);
userPrompt.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        sendCommand();
    }
});

// Intercept Ctrl+Shift+R or Ctrl+F5 to force reload bypassing cache
window.addEventListener("keydown", (e) => {
    // e.code 'KeyR' matches R key regardless of layout or shift state; e.code 'F5' matches function key F5.
    if ((e.ctrlKey && e.shiftKey && e.code === "KeyR") || (e.ctrlKey && e.code === "F5")) {
        e.preventDefault();
        const url = new URL(window.location.href);
        url.searchParams.set("t", Date.now().toString());
        window.location.href = url.toString();
    }
});

// Explicit user gesture listeners to authorize audio playback on first interaction
const authorizeAudio = () => {
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume().then(() => {
            console.log("AudioContext resumed successfully via user gesture.");
        }).catch(err => {
            console.warn("Failed to resume AudioContext:", err);
        });
    }
    // Remove listeners once gesture is captured
    window.removeEventListener("click", authorizeAudio);
    window.removeEventListener("keydown", authorizeAudio);
};
window.addEventListener("click", authorizeAudio);
window.addEventListener("keydown", authorizeAudio);
