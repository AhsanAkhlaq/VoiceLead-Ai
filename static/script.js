// static/script.js
let mediaRecorder;
let audioChunks = [];
const ws = new WebSocket(`ws://${window.location.host}/ws/voice`);

ws.onopen = () => console.log("WebSocket connected");

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "response") {
        document.getElementById("transcript").innerHTML += 
            `<strong>You:</strong> ${data.user_text}<br>` +
            `<strong>AI:</strong> ${data.ai_text}<br><br>`;
        
        const audio = document.getElementById("aiAudio");
        audio.src = data.audio_base64;
        audio.play();
        
        document.getElementById("score").textContent = data.lead_score || "WARM";
        document.getElementById("status").textContent = "Ready to talk again";
    } else if (data.type === "error") {
        console.error("AI Error:", data.message);
        document.getElementById("status").textContent = "Error - try again";
    }
};

const recordBtn = document.getElementById("recordBtn");

recordBtn.addEventListener("mousedown", async () => {
    let stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // Use mp4 format - Groq Whisper accepts this much more reliably
    const options = { mimeType: "audio/mp4" };
    mediaRecorder = new MediaRecorder(stream, options);
    
    audioChunks = [];
    
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/mp4" });
        const reader = new FileReader();
        reader.onloadend = () => {
            ws.send(JSON.stringify({
                type: "audio",
                audio_base64: reader.result
            }));
        };
        reader.readAsDataURL(audioBlob);
    };
    
    mediaRecorder.start();
    recordBtn.textContent = "🔴 Recording... Release to send";
    document.getElementById("status").textContent = "Listening...";
});

recordBtn.addEventListener("mouseup", () => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
        recordBtn.textContent = "🎙️ Hold to Speak";
    }
});