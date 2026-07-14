const socket = io();

const els = {
    // Inputs
    profileDir: document.getElementById('profileDir'),
    outputDir: document.getElementById('outputDir'),
    imgPrefix: document.getElementById('imgPrefix'),
    parallelWindows: document.getElementById('parallelWindows'),
    accountsPerWindow: document.getElementById('accountsPerWindow'),
    
    // Buttons & Status
    startBtn: document.getElementById('startBtn'),
    confirmBtn: document.getElementById('confirmBtn'),
    stopBtn: document.getElementById('stopBtn'),
    saveStatus: document.getElementById('saveStatus'),
    statusIndicator: document.getElementById('statusIndicator'),
    
    // Logs & Workflow
    logContainer: document.getElementById('logContainer'),
    step1: document.getElementById('stepIndicator1'),
    step2: document.getElementById('stepIndicator2'),
    step3: document.getElementById('stepIndicator3'),
    
    // Tasks
    newTaskPrompt: document.getElementById('newTaskPrompt'),
    newTaskCount: document.getElementById('newTaskCount'),
    addTaskBtn: document.getElementById('addTaskBtn'),
    clearTasksBtn: document.getElementById('clearTasksBtn'),
    excelFileInput: document.getElementById('excelFileInput'),
    importExcelBtn: document.getElementById('importExcelBtn'),
    tasksList: document.getElementById('tasksList'),
    taskBadge: document.getElementById('taskBadge'),
    cooldownTime: document.getElementById('cooldownTime'),

    // Miner UI
    minerKeyword: document.getElementById('minerKeyword'),
    minerLimit: document.getElementById('minerLimit'),
    minerTargetCount: document.getElementById('minerTargetCount'),
    mineBtn: document.getElementById('mineBtn')
};

// --- Config Management ---
async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        
        els.profileDir.value = data.chrome_profile_base_dir || '';
        els.outputDir.value = data.output_dir || '';
        els.cooldownTime.value = data.cooldown_time || 15;
        els.imgPrefix.value = data.image_name_prefix || 'gemini_img';
        els.parallelWindows.value = data.parallel_windows || 1;
        els.accountsPerWindow.value = data.accounts_per_window || 10;
        
    } catch (e) {
        console.error("Failed to load config", e);
    }
}

async function saveConfig() {
    const data = {
        chrome_profile_base_dir: els.profileDir.value.trim(),
        output_dir: els.outputDir.value.trim(),
        cooldown_time: parseInt(els.cooldownTime.value, 10),
        image_name_prefix: els.imgPrefix.value.trim(),
        parallel_windows: parseInt(els.parallelWindows.value, 10),
        accounts_per_window: parseInt(els.accountsPerWindow.value, 10)
    };
    
    if (!data.chrome_profile_base_dir || !data.output_dir) {
        alert("请完整填写 Chrome 账号目录和图片输出目录！");
        return false;
    }

    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        
        els.saveStatus.textContent = "✓ 已保存";
        els.saveStatus.classList.add('show');
        setTimeout(() => els.saveStatus.classList.remove('show'), 2000);
        return true;
    } catch (e) {
        alert("保存失败: " + e);
        return false;
    }
}

// --- Run Control ---
async function startRun() {
    const saved = await saveConfig();
    if (!saved) return;
    
    els.logContainer.innerHTML = '';
    appendLog("[系统] 正在打开 Gemini 浏览器窗口，请在弹出的窗口中手动登录 Google...", "info");
    
    try {
        const res = await fetch('/api/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({wait_for_confirm: true})
        });
        const data = await res.json();
        if (data.error) {
            alert(data.error);
            appendLog(`[系统] 启动失败: ${data.error}`, "error");
        }
    } catch (e) {
        alert("请求失败: " + e);
    }
}

async function confirmRun() {
    appendLog("[系统] ✅ 登录确认！Gemini 跑图机器人已就位，等待任务...", "success");
    appendLog("[系统] 现在请去下方「亚马逊爆款挖掘」区域点击挖掘，或手动添加任务。", "info");
    try {
        await fetch('/api/confirm', {method: 'POST'});
    } catch (e) {
        alert("请求失败: " + e);
    }
}

async function stopRun() {
    try {
        await fetch('/api/stop', {method: 'POST'});
    } catch (e) {
        alert("请求失败: " + e);
    }
}

function appendLog(msg, level) {
    const div = document.createElement('div');
    div.className = `log-${level}`;
    div.textContent = msg;
    els.logContainer.appendChild(div);
    els.logContainer.scrollTop = els.logContainer.scrollHeight;
}

// --- UI Helpers ---
function updateWorkflow(step) {
    els.step1.classList.toggle('done', step > 1);
    els.step1.classList.toggle('active', step === 1);
    
    els.step2.classList.toggle('done', step > 2);
    els.step2.classList.toggle('active', step === 2);
    
    els.step3.classList.toggle('active', step === 3);
}

// --- Task Management ---
async function fetchTasks() {
    try {
        const res = await fetch('/api/tasks');
        const tasks = await res.json();
        renderTasks(tasks);
    } catch (e) {
        console.error("Failed to fetch tasks", e);
    }
}

let pendingImages = [];

function renderImagePreviews() {
    const container = document.getElementById('imagePreviewContainer');
    if (!container) return;
    container.innerHTML = '';
    
    pendingImages.forEach((file, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.style.cssText = "display: flex; align-items: center; background: rgba(0,0,0,0.05); padding: 2px 6px; border-radius: 4px; font-size: 0.75rem;";
        
        const nameSpan = document.createElement('span');
        nameSpan.textContent = file.name;
        nameSpan.style.marginRight = "6px";
        nameSpan.style.maxWidth = "100px";
        nameSpan.style.overflow = "hidden";
        nameSpan.style.textOverflow = "ellipsis";
        nameSpan.style.whiteSpace = "nowrap";
        
        const rmBtn = document.createElement('button');
        rmBtn.textContent = '✖';
        rmBtn.style.cssText = "background: none; border: none; color: red; cursor: pointer; padding: 0; font-size: 0.8rem;";
        rmBtn.onclick = () => {
            pendingImages.splice(index, 1);
            renderImagePreviews();
        };
        
        itemDiv.appendChild(nameSpan);
        itemDiv.appendChild(rmBtn);
        container.appendChild(itemDiv);
    });
}

const fileInput = document.getElementById('newTaskImages');
if (fileInput) {
    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files.length > 0) {
            for (let i = 0; i < e.target.files.length; i++) {
                pendingImages.push(e.target.files[i]);
            }
            renderImagePreviews();
        }
        // clear the input so the same files can be selected again
        e.target.value = '';
    });
}

async function addTask() {
    const prompt = els.newTaskPrompt.value.trim();
    const count = parseInt(els.newTaskCount.value, 10) || 1;
    if (!prompt) return;
    
    els.addTaskBtn.disabled = true;
    try {
        const formData = new FormData();
        formData.append('prompt', prompt);
        formData.append('target_count', count);
        
        if (pendingImages.length > 0) {
            for (let i = 0; i < pendingImages.length; i++) {
                formData.append('images', pendingImages[i]);
            }
        }

        await fetch('/api/tasks', {
            method: 'POST',
            body: formData
        });
        
        els.newTaskPrompt.value = '';
        pendingImages = [];
        renderImagePreviews();
    } catch (e) {
        alert("添加失败: " + e);
    } finally {
        els.addTaskBtn.disabled = false;
    }
}

async function deleteTask(taskId) {
    if (!confirm("确定删除？")) return;
    try {
        await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
    } catch (e) {
        console.error("Failed to delete task", e);
    }
}

function renderTasks(tasks) {
    els.tasksList.innerHTML = '';
    if (!tasks || tasks.length === 0) {
        els.tasksList.innerHTML = '<li class="empty-hint">暂无任务 — 请先挖掘亚马逊或手动添加</li>';
        els.taskBadge.textContent = '';
        return;
    }
    
    const pending = tasks.filter(t => t.status === 'pending' || t.status === 'running').length;
    els.taskBadge.textContent = pending > 0 ? `(${pending} 个待执行)` : `(${tasks.length} 个)`;
    
    tasks.forEach(task => {
        const li = document.createElement('li');
        
        const promptDiv = document.createElement('div');
        promptDiv.className = 'task-prompt';
        promptDiv.textContent = task.prompt;
        promptDiv.title = task.prompt;
        
        let statusClass = '';
        let statusText = `${task.current_count}/${task.target_count}`;
        
        if (task.status === 'completed') {
            statusClass = 'completed';
            statusText = '✅';
        } else if (task.status === 'failed') {
            statusClass = 'failed';
            statusText = '❌';
        } else if (task.status === 'running') {
            statusText = `🚀 ${task.current_count}/${task.target_count}`;
        }
        
        // Show reference image indicator
        if (task.reference_image_path) {
            statusText = '📷' + statusText;
        }
        
        const statusDiv = document.createElement('div');
        statusDiv.className = `task-progress ${statusClass}`;
        statusDiv.textContent = statusText;
        
        const btn = document.createElement('button');
        btn.className = 'delete-btn';
        btn.innerHTML = '✖';
        btn.onclick = () => deleteTask(task.id);
        
        li.appendChild(promptDiv);
        li.appendChild(statusDiv);
        li.appendChild(btn);
        
        els.tasksList.appendChild(li);
    });
}

// --- Event Listeners ---
async function clearTasks() {
    if (!confirm("确定清空所有排队任务吗？")) return;
    try {
        await fetch('/api/tasks/clear', { method: 'POST' });
    } catch (e) {
        console.error("Failed to clear tasks", e);
    }
}

els.startBtn.onclick = startRun;
els.confirmBtn.onclick = confirmRun;
els.stopBtn.onclick = stopRun;
els.addTaskBtn.onclick = addTask;
els.clearTasksBtn.onclick = clearTasks;

if (els.importExcelBtn) {
    els.importExcelBtn.addEventListener('click', async () => {
        const file = els.excelFileInput.files[0];
        if (!file) {
            alert("请选择一个 .xlsx 文件！");
            return;
        }
        els.importExcelBtn.disabled = true;
        els.importExcelBtn.textContent = "导入中...";
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/tasks/excel', {
                method: 'POST',
                body: formData
            });
            const data = await response.json();
            
            if (response.ok) {
                alert(`成功导入 ${data.imported_count} 个生图任务！`);
                els.excelFileInput.value = '';
            } else {
                alert(`导入失败: ${data.error}`);
            }
        } catch (e) {
            alert("请求失败: " + e);
        } finally {
            els.importExcelBtn.disabled = false;
            els.importExcelBtn.textContent = "导入 Excel";
        }
    });
}

// --- Socket IO ---
socket.on('log_event', (data) => {
    appendLog(data.message, data.level);
    
    if (data.message.includes("等待手动确认")) {
        updateWorkflow(2);
    } else if (data.message.includes("收到确认信号") || data.message.includes("登录确认")) {
        updateWorkflow(2);
    } else if (data.message.includes("执行生成") || data.message.includes("开始处理任务")) {
        updateWorkflow(3);
    }
});

socket.on('task_update', (data) => {
    renderTasks(data.tasks);
});

socket.on('status_update', (data) => {
    if (data.status === 'running') {
        els.startBtn.disabled = true;
        els.confirmBtn.disabled = true;
        els.stopBtn.disabled = false;
        els.statusIndicator.textContent = '跑图中 🚀';
        els.statusIndicator.style.color = 'var(--warning)';
    } else if (data.status === 'waiting') {
        els.startBtn.disabled = true;
        els.confirmBtn.disabled = false;
        els.stopBtn.disabled = false;
        els.statusIndicator.textContent = '等待登录 ⏳';
        els.statusIndicator.style.color = 'var(--accent)';
    } else {
        els.startBtn.disabled = false;
        els.confirmBtn.disabled = true;
        els.stopBtn.disabled = true;
        els.statusIndicator.textContent = '就绪 ✅';
        els.statusIndicator.style.color = 'var(--success)';
        updateWorkflow(1);
    }
});

// Init
loadConfig();
fetchTasks();

// ==========================================
// Miner Logic
// ==========================================
if(els.mineBtn) {
    els.mineBtn.addEventListener('click', async () => {
        const keyword = els.minerKeyword.value.trim();
        const limit = parseInt(els.minerLimit.value);
        const target_count = parseInt(els.minerTargetCount.value) || 4;

        if (!keyword) {
            alert("请输入关键词！");
            return;
        }

        els.mineBtn.disabled = true;
        els.mineBtn.textContent = "⛏️ 搜索亚马逊中...请勿关闭弹出的浏览器窗口";
        appendLog(`[挖掘机] 开始搜索亚马逊: "${keyword}"，目标 ${limit} 个商品...`, "info");
        appendLog(`[挖掘机] 会弹出一个 Chrome 窗口访问亚马逊，请不要手动关闭它！`, "warning");

        try {
            const response = await fetch('/api/mine_trends', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ keyword, limit, target_count })
            });
            
            if (response.ok) {
                appendLog(`[挖掘机] 挖掘任务已启动，正在后台进行：搜索 → 过滤 → 进入详情页 → 下载原图 → 生成提示词...`, "info");
                // Reset button after a delay
                setTimeout(() => {
                    els.mineBtn.disabled = false;
                    els.mineBtn.textContent = "⛏️ 一键挖掘 → 下载原图 → 生成提示词";
                }, 60000); // 1 minute cooldown
            } else {
                alert('挖掘任务启动失败');
                els.mineBtn.disabled = false;
                els.mineBtn.textContent = "⛏️ 一键挖掘 → 下载原图 → 生成提示词";
            }
        } catch (error) {
            console.error('Miner Error:', error);
            alert('请求失败');
            els.mineBtn.disabled = false;
            els.mineBtn.textContent = "⛏️ 一键挖掘 → 下载原图 → 生成提示词";
        }
    });
}
