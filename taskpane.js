/* =============================================================
 * taskpane.js - SpeechFunc Word Add-in
 * Logic: Mic -> PCM16 -> WebSocket -> Office.js insertText
 * ============================================================= */

// ============================================================
// STATE
// ============================================================
var isListening = false;
var ws = null;
var audioContext = null;
var mediaStream = null;
var scriptProcessor = null;
var sourceNode = null;
var manualStop = false;

var committedText = "";
var currentPreview = "";

// ============================================================
// OFFICE INIT
// ============================================================
Office.onReady(function (info) {
  if (info.host === Office.HostType.Word) {
    setStatus("Sẵn sàng. Nhấn bắt đầu nói!", "idle");
  } else {
    setStatus("Plugin chỉ hoạt động trong Word", "error");
  }
});

// ============================================================
// UI HELPERS
// ============================================================
function setStatus(text, type) {
  var bar = document.getElementById("statusBar");
  var textEl = document.getElementById("statusText");
  bar.className = "status-bar status-" + (type || "idle");
  textEl.textContent = text;
}

function setPreview(text) {
  var box = document.getElementById("previewBox");
  var indicator = document.getElementById("liveIndicator");
  currentPreview = text;
  if (text) {
    box.innerHTML = "<em>" + escapeHtml(text) + "</em>";
    box.classList.add("active");
    indicator.classList.remove("hidden");
  } else {
    box.innerHTML =
      "<span class='preview-placeholder'>Văn bản tự động hiện ở đây khi nói...</span>";
    box.classList.remove("active");
    indicator.classList.add("hidden");
  }
}

function appendCommitted(text) {
  var box = document.getElementById("committedBox");
  if (committedText) committedText += " ";
  committedText += text;
  box.textContent = committedText;
  box.scrollTop = box.scrollHeight;
}

function clearCommitted() {
  committedText = "";
  document.getElementById("committedBox").textContent = "";
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setMicState(listening) {
  isListening = listening;
  var btn = document.getElementById("micBtn");
  var label = document.getElementById("micLabel");
  if (listening) {
    btn.classList.add("listening");
    label.textContent = "Dừng lại";
  } else {
    btn.classList.remove("listening");
    label.textContent = "Bắt đầu nói";
  }
}

// ============================================================
// TOGGLE MIC
// ============================================================
function toggleMic() {
  if (isListening) {
    stopListening();
  } else {
    startListening();
  }
}

// ============================================================
// FLOAT32 -> INT16 PCM
// ============================================================
function floatTo16BitPCM(float32Array) {
  var int16 = new Int16Array(float32Array.length);
  for (var i = 0; i < float32Array.length; i++) {
    var s = Math.max(-1, Math.min(1, float32Array[i]));
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return int16.buffer;
}

// ============================================================
// START LISTENING
// ============================================================
function startListening() {
  manualStop = false;
  var serverEl = document.getElementById("serverUrl");
  var serverUrl = serverEl ? serverEl.value.trim() : "ws://localhost:8009/ws/speech";
  if (!serverUrl) {
    setStatus("Vui lòng nhập WebSocket URL", "error");
    return;
  }

  setStatus("Đang kết nối server...", "connecting");

  // Open WebSocket first
  try {
    ws = new WebSocket(serverUrl);
    ws.binaryType = "arraybuffer";
  } catch (e) {
    setStatus("URL WebSocket không hợp lệ: " + serverUrl, "error");
    return;
  }

  ws.onopen = function () {
    setStatus("Đã kết nối! Cho phép Microphone...", "connecting");
    ws.send(JSON.stringify({ type: "config", codeMode: false }));
    openMicrophone();
  };

  ws.onmessage = function (event) {
    try {
      var data = JSON.parse(event.data);
      handleServerMessage(data);
    } catch (e) {
      // ignore parse errors
    }
  };

  ws.onerror = function () {
    if (!manualStop) {
      setStatus("Lỗi kết nối WebSocket. Server đã chạy chưa?", "error");
      stopListening();
    }
  };

  ws.onclose = function () {
    if (!manualStop) {
      setStatus("Đã ngắt kết nối WebSocket", "error");
      setMicState(false);
    }
  };
}

// ============================================================
// OPEN MICROPHONE
// ============================================================
function openMicrophone() {
  navigator.mediaDevices
    .getUserMedia({
      audio: {
        channelCount: 1,
        sampleRate: 16000,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    })
    .then(function (stream) {
      if (manualStop) {
        stream.getTracks().forEach(function (t) {
          t.stop();
        });
        return;
      }

      mediaStream = stream;
      audioContext = new AudioContext({ sampleRate: 16000 });
      sourceNode = audioContext.createMediaStreamSource(stream);
      scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);

      scriptProcessor.onaudioprocess = function (e) {
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        var pcm = floatTo16BitPCM(e.inputBuffer.getChannelData(0));
        ws.send(pcm);
      };

      sourceNode.connect(scriptProcessor);
      scriptProcessor.connect(audioContext.destination);

      setMicState(true);
      setStatus("Đang nghe... nói gì đi!", "listening");
    })
    .catch(function (err) {
      setStatus("Không thể mở Microphone: " + (err.message || err), "error");
      stopListening();
    });
}

// ============================================================
// STOP LISTENING
// ============================================================
function stopListening() {
  manualStop = true;
  setMicState(false);
  setPreview("");
  setStatus("Đã dừng thu âm", "idle");

  if (scriptProcessor) {
    scriptProcessor.disconnect();
    scriptProcessor = null;
  }
  if (sourceNode) {
    sourceNode.disconnect();
    sourceNode = null;
  }
  if (audioContext) {
    audioContext.close().catch(function () {});
    audioContext = null;
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach(function (t) {
      t.stop();
    });
    mediaStream = null;
  }
  if (ws) {
    var _ws = ws;
    ws = null;
    if (
      _ws.readyState === WebSocket.OPEN ||
      _ws.readyState === WebSocket.CONNECTING
    ) {
      _ws.close();
    }
  }
}

// ============================================================
// HANDLE SERVER MESSAGES
// ============================================================
function handleServerMessage(data) {
  switch (data.type) {
    case "voice":
      // mic detecting voice - indicator already handles this
      break;

    case "partial":
    case "replace":
      // Realtime preview - do NOT insert to Word yet
      setPreview(data.text || "");
      break;

    case "append":
      var text = (data.text || "").trim();
      if (!text) break;

      setPreview("");
      appendCommitted(text);
      insertTextToWord(text);
      break;

    case "commit":
      // Server gui ca commit lan append cho cung text.
      // Chi xu ly append de tranh chen 2 lan vao Word.
      setPreview("");
      break;

    case "status":
      if (isListening) {
        setStatus(data.text || "", "listening");
      }
      break;

    case "error":
      setStatus(data.text || "Loi server STT", "error");
      stopListening();
      break;
  }
}

// ============================================================
// INSERT TEXT INTO WORD
// ============================================================
function insertTextToWord(text) {
  var insertSpace = document.getElementById("insertSpace").checked;
  var insertNewline = document.getElementById("insertNewline").checked;

  Word.run(function (context) {
    var selection = context.document.getSelection();
    selection.load("text");

    return context.sync().then(function () {
      var toInsert = text;

      if (insertNewline) {
        selection.insertText(toInsert, Word.InsertLocation.end);
        selection.insertBreak(Word.BreakType.line, Word.InsertLocation.end);
      } else {
        // Insert with space before if needed
        if (insertSpace) {
          // Check if there is existing text - add a space prefix
          var existingText = selection.text || "";
          if (existingText.length > 0 && !existingText.endsWith(" ")) {
            toInsert = " " + toInsert;
          }
        }
        selection.insertText(toInsert + " ", Word.InsertLocation.end);
      }

      // Move cursor to end of inserted text
      selection.select(Word.SelectionMode.end);

      return context.sync();
    });
  }).catch(function (err) {
    console.error("Lỗi chèn text vào Word:", err);
    setStatus("Lỗi chèn text vào Word: " + (err.message || err), "error");
  });
}
