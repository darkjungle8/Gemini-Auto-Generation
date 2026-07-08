const socket = io();

const els = {
    // Inputs
    profileDir: document.getElementById('profileDir'),
    outputDir: document.getElementById('outputDir'),
    excelFile: document.getElementById('excelFile'),
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
    tasksList: document.getElementById('tasksList'),
    cooldownTime: document.getElementById('cooldownTime')
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
        alert("请完整填写账号目录和输出目录！");
        return false;
    }

    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(data)
        });
        
        // Show success status briefly
        els.saveStatus.textContent = "配置已保存";
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
    appendLog("[前台] 发送启动请求 (打开窗口准备登录)...", "info");
    
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
    appendLog("[前台] 发送确认跑图指令...", "info");
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

async function addTask() {
    const prompt = els.newTaskPrompt.value.trim();
    const count = parseInt(els.newTaskCount.value, 10) || 1;
    if (!prompt) return;
    
    els.addTaskBtn.disabled = true;
    try {
        await fetch('/api/tasks', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ prompt: prompt, target_count: count })
        });
        els.newTaskPrompt.value = '';
    } catch (e) {
        alert("添加失败: " + e);
    } finally {
        els.addTaskBtn.disabled = false;
    }
}

async function deleteTask(taskId) {
    if (!confirm("确定要删除这个任务吗？")) return;
    try {
        await fetch(`/api/tasks/${taskId}`, { method: 'DELETE' });
    } catch (e) {
        console.error("Failed to delete task", e);
    }
}

function renderTasks(tasks) {
    els.tasksList.innerHTML = '';
    if (!tasks || tasks.length === 0) {
        els.tasksList.innerHTML = '<li class="empty-hint">暂无提示词任务，请在上方添加</li>';
        return;
    }
    
    tasks.forEach(task => {
        const li = document.createElement('li');
        
        const promptDiv = document.createElement('div');
        promptDiv.className = 'task-prompt';
        promptDiv.textContent = task.prompt;
        promptDiv.title = task.prompt;
        
        let statusClass = '';
        let statusText = `${task.current_count}/${task.target_count} 张`;
        
        if (task.status === 'completed') {
            statusClass = 'completed';
            statusText = '✅ 已完成';
        } else if (task.status === 'failed') {
            statusClass = 'failed';
            statusText = '❌ 失败';
        } else if (task.status === 'running') {
            statusText = `🚀 跑图中 (${task.current_count}/${task.target_count})`;
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
els.startBtn.onclick = startRun;
els.confirmBtn.onclick = confirmRun;
els.stopBtn.onclick = stopRun;
els.addTaskBtn.onclick = addTask;

// --- Socket IO ---
socket.on('log_event', (data) => {
    appendLog(data.message, data.level);
    
    // Auto-update workflow based on log messages
    if (data.message.includes("等待手动确认")) {
        updateWorkflow(2);
    } else if (data.message.includes("收到确认信号")) {
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
        els.statusIndicator.textContent = '运行中 🚀';
        els.statusIndicator.style.color = 'var(--warning)';
    } else if (data.status === 'waiting') {
        els.startBtn.disabled = true;
        els.confirmBtn.disabled = false;
        els.stopBtn.disabled = false;
        els.statusIndicator.textContent = '等待确认 ⏳';
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
