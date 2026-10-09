let tasksState = {};
let ws = null;
let currentPreviewText = "";

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  initWebSocket();
  fetchTasks();
});

function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws`;
  
  ws = new WebSocket(wsUrl);

  ws.onopen = () => {
    document.getElementById("wsStatus").innerHTML = `
      <span class="w-2 h-2 rounded-full bg-emerald-500 mr-1.5 animate-pulse"></span> 实时同步中
    `;
    document.getElementById("wsStatus").className = "inline-flex items-center text-xs text-emerald-600 font-medium";
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.type === "init") {
        tasksState = {};
        msg.data.forEach(t => tasksState[t.id] = t);
        renderTaskList();
      } else if (msg.type === "task_added" || msg.type === "task_updated") {
        tasksState[msg.data.id] = msg.data;
        renderTaskList();
      } else if (msg.type === "task_deleted") {
        delete tasksState[msg.data.id];
        renderTaskList();
      } else if (msg.type === "queue_cleared") {
        fetchTasks();
      }
    } catch (e) {
      console.error("WS error:", e);
    }
  };

  ws.onclose = () => {
    document.getElementById("wsStatus").innerHTML = `
      <span class="w-2 h-2 rounded-full bg-amber-500 mr-1.5"></span> 连接断开，重连中...
    `;
    document.getElementById("wsStatus").className = "inline-flex items-center text-xs text-amber-600 font-medium";
    setTimeout(initWebSocket, 2000);
  };
}

async function fetchTasks() {
  try {
    const res = await fetch("/api/tasks");
    const data = await res.json();
    tasksState = {};
    data.forEach(t => tasksState[t.id] = t);
    renderTaskList();
  } catch (e) {
    console.error("Fetch tasks failed:", e);
  }
}

async function submitTasks() {
  const inputEl = document.getElementById("sourceInput");
  const text = inputEl.value.trim();
  if (!text) {
    alert("请先输入视频链接或本地路径！");
    return;
  }

  const lines = text.split("\n").map(l => l.trim()).filter(l => l.length > 0);
  if (lines.length === 0) return;

  const btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin mr-2"></i> 提交中...`;

  try {
    const res = await fetch("/api/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sources: lines })
    });
    if (res.ok) {
      inputEl.value = "";
      fetchTasks();
    } else {
      const err = await res.json();
      alert("添加失败: " + (err.detail || "未知错误"));
    }
  } catch (e) {
    alert("网络异常: " + e.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-paper-plane mr-2"></i> 加入任务队列`;
  }
}

async function deleteTask(taskId) {
  try {
    await fetch(`/api/tasks/${taskId}`, { method: "DELETE" });
    delete tasksState[taskId];
    renderTaskList();
  } catch (e) {
    console.error(e);
  }
}

async function clearCompletedTasks() {
  try {
    await fetch("/api/tasks/clear", { method: "POST" });
    fetchTasks();
  } catch (e) {
    console.error(e);
  }
}

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  toast.className = `pointer-events-auto flex items-start space-x-3 max-w-md p-4 rounded-xl shadow-xl border transition-all duration-300 transform translate-y-2 opacity-0 ${
    type === "error"
      ? "bg-red-50 text-red-800 border-red-200"
      : type === "success"
      ? "bg-emerald-50 text-emerald-800 border-emerald-200"
      : "bg-white text-slate-800 border-slate-200"
  }`;

  const iconMap = {
    error: '<i class="fa-solid fa-circle-exclamation text-red-500 mt-0.5"></i>',
    success: '<i class="fa-solid fa-circle-check text-emerald-500 mt-0.5"></i>',
    info: '<i class="fa-solid fa-circle-info text-indigo-500 mt-0.5"></i>'
  };

  toast.innerHTML = `
    <div class="text-base">${iconMap[type] || iconMap.info}</div>
    <div class="flex-1 text-xs leading-relaxed font-sans whitespace-pre-wrap">${message}</div>
  `;

  container.appendChild(toast);

  requestAnimationFrame(() => {
    toast.classList.remove("translate-y-2", "opacity-0");
  });

  setTimeout(() => {
    toast.classList.add("translate-y-2", "opacity-0");
    setTimeout(() => toast.remove(), 300);
  }, 4500);
}

async function openOutputFolder() {
  const btn = document.getElementById("openFolderBtn");
  const originalHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin text-amber-500 mr-2 text-sm"></i> 打开中...`;
  }

  try {
    const res = await fetch("/api/open-folder", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (res.ok) {
      if (data.path) {
        navigator.clipboard.writeText(data.path).catch(() => {});
        showToast(`📁 已呼叫 Windows 打开文件夹：\n${data.path}\n（如窗口在后台，路径已同步复制到剪贴板，可直接粘贴）`, "success");
      } else {
        showToast("📁 已呼叫 Windows 打开输出文件夹", "success");
      }
      if (btn) {
        btn.innerHTML = `<i class="fa-solid fa-check text-emerald-500 mr-2 text-sm"></i> 已打开`;
      }
    } else {
      showToast("无法打开文件夹: " + (data.detail || "未知错误"), "error");
    }
  } catch (e) {
    showToast("网络请求失败: " + e.message, "error");
  } finally {
    setTimeout(() => {
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalHtml;
      }
    }, 2000);
  }
}

function formatDuration(sec) {
  if (!sec || sec <= 0) return "--:--";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? '0' : ''}${s}`;
}

function getSourceBadge(type) {
  if (type === "bilibili") {
    return `<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-pink-50 text-pink-600 border border-pink-200"><i class="fa-brands fa-bilibili mr-1"></i>B站</span>`;
  } else if (type === "youtube") {
    return `<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-red-50 text-red-600 border border-red-200"><i class="fa-brands fa-youtube mr-1"></i>YouTube</span>`;
  } else if (type === "local") {
    return `<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-300"><i class="fa-regular fa-file-video mr-1"></i>本地文件</span>`;
  }
  return `<span class="px-2 py-0.5 rounded text-[11px] font-semibold bg-blue-50 text-blue-600 border border-blue-200"><i class="fa-solid fa-globe mr-1"></i>网络视频</span>`;
}

function getStatusBadge(status) {
  const map = {
    queued: `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">排队中</span>`,
    parsing: `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 animate-pulse">解析中</span>`,
    extracting_sub: `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-700 animate-pulse">拉取字幕</span>`,
    transcribing_asr: `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-indigo-100 text-indigo-700 animate-pulse">ASR听写中</span>`,
    formatting: `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 animate-pulse">分段排版</span>`,
    completed: `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800"><i class="fa-solid fa-check mr-1"></i>已完成</span>`,
    error: `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-700"><i class="fa-solid fa-triangle-exclamation mr-1"></i>失败</span>`
  };
  return map[status] || `<span class="px-2 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600">${status}</span>`;
}

function renderTaskList() {
  const container = document.getElementById("taskListContainer");
  const tasks = Object.values(tasksState);
  document.getElementById("taskCountBadge").innerText = tasks.length;

  if (tasks.length === 0) {
    container.innerHTML = `
      <div class="py-16 text-center">
        <div class="w-12 h-12 rounded-full bg-slate-100 text-slate-400 flex items-center justify-center mx-auto mb-3">
          <i class="fa-solid fa-inbox text-xl"></i>
        </div>
        <p class="text-sm font-medium text-slate-600">暂无处理任务</p>
        <p class="text-xs text-slate-400 mt-1">在上方粘贴 B站/YouTube 视频链接或本地路径，点击“加入任务队列”开始批量转录</p>
      </div>
    `;
    return;
  }

  let html = "";
  tasks.forEach((t, idx) => {
    const isCompleted = t.status === "completed";
    const isError = t.status === "error";

    html += `
      <div class="p-5 hover:bg-slate-50/80 transition flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        
        <!-- Left info -->
        <div class="flex-1 min-w-0 space-y-1.5">
          <div class="flex items-center space-x-2">
            ${getSourceBadge(t.source_type)}
            <h4 class="text-sm font-bold text-slate-900 truncate" title="${t.title}">${t.title}</h4>
          </div>

          <div class="flex flex-wrap items-center gap-3 text-xs text-slate-500">
            <span class="truncate max-w-xs font-mono text-[11px] text-slate-400">${t.source}</span>
            <span>·</span>
            <span><i class="fa-regular fa-clock mr-1"></i>时长: ${formatDuration(t.duration)}</span>
            <span>·</span>
            ${getStatusBadge(t.status)}
            <span class="text-slate-600 font-medium">${t.step_desc || ""}</span>
          </div>

          <!-- Progress Bar -->
          <div class="w-full bg-slate-100 rounded-full h-2 overflow-hidden mt-2">
            <div class="h-full rounded-full transition-all duration-300 ${
              isError ? 'bg-red-500' : (isCompleted ? 'bg-emerald-500' : 'bg-indigo-600')
            }" style="width: ${t.progress || 0}%"></div>
          </div>
        </div>

        <!-- Right actions -->
        <div class="flex items-center space-x-2 shrink-0">
          ${isCompleted ? `
            <button onclick="openPreviewModal('${t.id}')" class="inline-flex items-center px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition shadow-sm">
              <i class="fa-regular fa-eye mr-1.5"></i> 预览
            </button>
            <a href="/api/download/${t.id}/md" download class="inline-flex items-center px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100 transition" title="下载 Markdown 文本">
              .MD
            </a>
            <a href="/api/download/${t.id}/txt" download class="inline-flex items-center px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100 transition" title="下载纯文本 TXT">
              .TXT
            </a>
            <a href="/api/download/${t.id}/srt" download class="inline-flex items-center px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-slate-200 text-slate-700 hover:bg-slate-100 transition" title="下载时间轴 SRT 字幕">
              .SRT
            </a>
            ${t.output_files && t.output_files.timeline ? `
            <a href="/api/download/${t.id}/timeline" download class="inline-flex items-center px-2.5 py-1.5 text-xs font-semibold rounded-lg border border-indigo-200 text-indigo-700 bg-indigo-50 hover:bg-indigo-100 transition" title="下载带时间轴逐句稿">
              逐句稿
            </a>` : ''}
          ` : ''}

          <button onclick="deleteTask('${t.id}')" class="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition" title="移除任务">
            <i class="fa-regular fa-trash-can"></i>
          </button>
        </div>

      </div>
    `;
  });

  container.innerHTML = html;
}

// Modal handling
function openPreviewModal(taskId) {
  const task = tasksState[taskId];
  if (!task || !task.markdown_content) {
    alert("该任务暂无转录内容");
    return;
  }
  document.getElementById("previewTitle").innerText = `${task.title} - 预览`;
  document.getElementById("previewContent").innerText = task.markdown_content;
  currentPreviewText = task.markdown_content;
  document.getElementById("previewModal").classList.remove("hidden");
}

function closePreviewModal() {
  document.getElementById("previewModal").classList.add("hidden");
}

function copyPreviewContent() {
  if (currentPreviewText) {
    navigator.clipboard.writeText(currentPreviewText).then(() => {
      showToast("已成功复制转录全文到剪贴板！", "success");
    }).catch(err => {
      showToast("复制失败: " + err, "error");
    });
  }
}

async function openSettingsModal() {
  try {
    const res = await fetch("/api/config");
    const data = await res.json();
    const cfg = data.config;
    const resolved = data.resolved_paths;

    document.getElementById("cfgOutputDir").value = cfg.output_dir;
    document.getElementById("resolvedOutputDir").innerText = `实际路径: ${resolved.output_dir}`;

    document.getElementById("cfgCacheDir").value = cfg.cache_dir;
    document.getElementById("resolvedCacheDir").innerText = `实际路径: ${resolved.cache_dir}`;

    document.getElementById("cfgModelDir").value = cfg.model_dir;
    document.getElementById("resolvedModelDir").innerText = `实际路径: ${resolved.model_dir}`;

    document.getElementById("cfgModelSize").value = cfg.model_size;
    document.getElementById("cfgDevice").value = cfg.device;
    document.getElementById("cfgTimelineTranscript").checked = !!cfg.export_timeline_transcript;

    document.getElementById("settingsModal").classList.remove("hidden");
  } catch (e) {
    alert("无法获取设置: " + e.message);
  }
}

function closeSettingsModal() {
  document.getElementById("settingsModal").classList.add("hidden");
}

async function saveSettings() {
  const req = {
    output_dir: document.getElementById("cfgOutputDir").value.trim(),
    cache_dir: document.getElementById("cfgCacheDir").value.trim(),
    model_dir: document.getElementById("cfgModelDir").value.trim(),
    model_size: document.getElementById("cfgModelSize").value,
    device: document.getElementById("cfgDevice").value,
    compute_type: document.getElementById("cfgDevice").value === "cuda" ? "float16" : "int8",
    export_timeline_transcript: document.getElementById("cfgTimelineTranscript").checked
  };

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req)
    });
    if (res.ok) {
      closeSettingsModal();
      showToast("设置已保存！路径与模型已生效。", "success");
    } else {
      showToast("设置保存失败", "error");
    }
  } catch (e) {
    showToast("保存失败: " + e.message, "error");
  }
}
