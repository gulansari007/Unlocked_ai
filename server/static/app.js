/* ============================================================
   UNLOCKED AI — Material 3 Dashboard JavaScript
   ============================================================ */

'use strict';

// ── WebSocket ────────────────────────────────────────────────
let ws;
const WS_URL = `ws://${window.location.host}/ws`;

// ── DOM References ───────────────────────────────────────────
const $ = id => document.getElementById(id);

// Status
const statusBadge = $('status-badge');
const agentBadge  = $('agent-badge');

// Console
const chatStream = $('chat-stream');
const promptInput = $('prompt-input');
const runBtn      = $('run-btn');

// Terminal
const terminalView  = $('terminal-view');
const terminalInput = $('terminal-input');
const terminalCwd   = $('terminal-cwd');
const terminalCwdLabel = $('terminal-cwd-label');
const clearTerminalBtn = $('clear-terminal-btn');

// Approval dialog
const approvalScrim   = $('approval-scrim');
const approvalAgent   = $('approval-agent');
const approvalTool    = $('approval-tool');
const approvalArgs    = $('approval-args');
const approvalFeedback = $('approval-feedback');
const approveBtn  = $('approve-btn');
const rejectBtn   = $('reject-btn');

// File dialog
const fileScrim     = $('file-scrim');
const fileDialogTitle = $('file-dialog-title');
const fileContent   = $('file-content');
const closeFileBtn  = $('close-file-btn');
const closeFileBtn2 = $('close-file-btn2');

// Settings dialog
const settingsScrim   = $('settings-scrim');
const settingsBtn     = $('settings-btn');
const cancelSettingsBtn = $('cancel-settings-btn');
const saveSettingsBtn = $('save-settings-btn');

const sGemini     = $('s-gemini');
const sGroq       = $('s-groq');
const sOpenrouter = $('s-openrouter');
const sOllama     = $('s-ollama');
const sOpenai     = $('s-openai');
const sOpenaiUrl  = $('s-openai-url');
const sAnthropic  = $('s-anthropic');
const sAnthropicUrl = $('s-anthropic-url');
const sTelegram   = $('s-telegram');
const sOpencode   = $('s-opencode');
const sOpencodeUrl = $('s-opencode-url');



// Reminders UI
const remindersContainer = $('reminders-container');
const addReminderBtn     = $('add-reminder-btn');
const reminderScrim      = $('reminder-scrim');
const rMessage           = $('r-message');
const rInterval          = $('r-interval');
const rRecurring         = $('r-recurring');
const cancelReminderBtn  = $('cancel-reminder-btn');
const saveReminderBtn    = $('save-reminder-btn');

// Productivity Hub UI
const tabPomoBtn = $('tab-pomo-btn');
const tabTodoBtn = $('tab-todo-btn');
const panelPomo  = $('panel-pomo');
const panelTodo  = $('panel-todo');

const pomoTimerText = $('pomo-timer-text');
const pomoLabel     = $('pomo-label');
const pomo25Btn     = $('pomo-25-btn');
const pomo5Btn      = $('pomo-5-btn');
const pomoStopBtn   = $('pomo-stop-btn');

const todoListContainer = $('todo-list-container');
const todoInput         = $('todo-input');
const todoAddBtn        = $('todo-add-btn');

// Misc
const refreshFilesBtn = $('refresh-files-btn');

let activePromptId = null;

// ── WebSocket connection ─────────────────────────────────────
function connect() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setStatusChip(statusBadge, 'connected', 'Connected');
    loadProviders();
    loadFiles();
    loadReminders();
    loadTodos();
    checkPomodoroStatus();

    // Request notification permission if default
    if (typeof Notification !== 'undefined' && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  };

  ws.onclose = () => {
    setStatusChip(statusBadge, 'disconnected', 'Offline');
    setTimeout(connect, 3000);
  };

  ws.onmessage = evt => handleMessage(JSON.parse(evt.data));
}

function wsSend(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
}

// ── Status chip helpers ─────────────────────────────────────
function setStatusChip(el, state, label) {
  el.className = 'status-chip ' + state;
  el.querySelector('span').textContent = label;
}

// ── Message router ───────────────────────────────────────────
function handleMessage(msg) {
  switch (msg.type) {

    case 'init':
      if (msg.cwd) updateCwd(msg.cwd);
      break;

    case 'status':
      if (msg.running) {
        setStatusChip(agentBadge, 'running', 'Agent Working…');
        runBtn.disabled = true;
        runBtn.style.opacity = '0.5';
      } else {
        setStatusChip(agentBadge, '', 'Agent Idle');
        runBtn.disabled = false;
        runBtn.style.opacity = '1';
      }
      break;

    case 'thought':
      appendThought(msg.data.agent, msg.data.content);
      break;

    case 'log':
      appendLog(msg.data.level, msg.data.message);
      break;

    case 'tool_start':
      appendToolStart(msg.data.agent, msg.data.tool, msg.data.arguments);
      break;

    case 'tool_end':
      appendToolEnd(msg.data.agent, msg.data.tool, msg.data.output);
      break;

    case 'terminal_output':
      appendTerminalOutput(msg.data.content);
      break;

    case 'agent_response':
      appendFinalResponse(msg.content);
      break;

    case 'approval_request':
      showApproval(msg.prompt_id, msg.agent, msg.tool, msg.arguments);
      break;

    case 'provider_updated':
    case 'config_updated':
      loadProviders();
      break;

    case 'reminder':
      handleReminderTrigger(msg.data);
      break;

    case 'reminders_updated':
      renderRemindersList(msg.data);
      break;

    case 'todos_updated':
      renderTodosList(msg.data);
      break;

    case 'pomodoro_tick':
      updatePomodoroUI(msg.data);
      break;

    case 'pomodoro_complete':
      handlePomodoroComplete(msg.data);
      break;

    default:
      console.log('[ws]', msg);
  }
}

// ── Console helpers ───────────────────────────────────────────
function removeEmptyState() {
  const el = $('console-empty');
  if (el) el.remove();
}

function appendThought(agent, text) {
  removeEmptyState();
  const card = el('div', 'thought-card');
  const lbl  = el('div', 'thought-label');
  lbl.innerHTML = `<span class="thought-agent-chip">${esc(agent.toUpperCase())}</span>
                   <span class="thought-type-label">Thought</span>`;
  const body = el('div', 'thought-body');
  body.textContent = text;
  card.append(lbl, body);
  pushToStream(card);
}

function appendLog(level, text) {
  if (/\/ws|WebSocket|endpoint/i.test(text)) return;
  removeEmptyState();
  const entry = el('div', `log-entry ${(level || 'info').toLowerCase()}`);
  const time  = el('span', 'log-time');
  time.textContent = new Date().toLocaleTimeString();
  const body  = el('span', 'log-text');
  body.textContent = text;
  entry.append(time, body);
  pushToStream(entry);
}

let _lastToolCard = null;

function appendToolStart(agent, tool, args) {
  removeEmptyState();
  const card   = el('div', 'tool-card');
  const header = el('div', 'tool-card-header');
  header.innerHTML = `<span class="tool-card-icon">🛠️</span>
    <span class="tool-card-title">${esc(agent)} → ${esc(tool)}</span>
    <span class="tool-card-status">running</span>`;
  const body  = el('div', 'tool-card-body');
  const args_block = el('div', 'tool-output');
  args_block.textContent = JSON.stringify(args, null, 2);
  body.append(args_block);
  card.append(header, body);
  _lastToolCard = { card, statusEl: header.querySelector('.tool-card-status'), body };
  pushToStream(card);
}

function appendToolEnd(agent, tool, output) {
  if (_lastToolCard) {
    _lastToolCard.statusEl.textContent = 'done';
    _lastToolCard.statusEl.style.background = 'rgba(169,220,189,0.18)';
    _lastToolCard.statusEl.style.color = '#A9DCBD';
    const out = el('div', 'tool-output');
    out.style.marginTop = '10px';
    out.textContent = output;
    _lastToolCard.body.appendChild(out);
    _lastToolCard = null;
  }
}

function appendFinalResponse(text) {
  removeEmptyState();
  const card = el('div', 'response-card');
  const hdr  = el('div', 'response-header');
  hdr.innerHTML = '🔮 Final Coordinator Response';
  const body = el('div', 'response-body');
  body.textContent = text;
  card.append(hdr, body);
  pushToStream(card);
}

function pushToStream(node) {
  chatStream.appendChild(node);
  chatStream.scrollTop = chatStream.scrollHeight;
}

// ── Terminal helpers ─────────────────────────────────────────
function appendTerminalOutput(content) {
  const span = document.createElement('span');
  span.textContent = content;
  terminalView.appendChild(span);
  terminalView.scrollTop = terminalView.scrollHeight;
}

function updateCwd(path) {
  const short = path.length > 36 ? '…' + path.slice(-34) : path;
  terminalCwd.textContent = short + ' $';
  terminalCwdLabel.textContent = path;
}

// ── Agent run ────────────────────────────────────────────────
function runAgent() {
  const text = promptInput.value.trim();
  if (!text || runBtn.disabled) return;
  appendLog('info', `[You] ${text}`);
  wsSend({ type: 'run_agent', content: text });
  promptInput.value = '';
  promptInput.style.height = 'auto';
}

// ── Terminal execute ─────────────────────────────────────────
function runTerminalCmd() {
  const cmd = terminalInput.value.trim();
  if (!cmd) return;
  appendTerminalOutput(`\n$ ${cmd}\n`);
  wsSend({ type: 'terminal_input', command: cmd });
  terminalInput.value = '';
}

// ── Approval dialog ──────────────────────────────────────────
function showApproval(promptId, agent, tool, args) {
  activePromptId = promptId;
  approvalAgent.textContent = agent;
  approvalTool.textContent  = tool;
  approvalArgs.textContent  = JSON.stringify(args, null, 2);
  approvalFeedback.value = '';
  openDialog(approvalScrim);
}

function sendApproval(approved) {
  wsSend({
    type: 'approval_response',
    prompt_id: activePromptId,
    approved,
    feedback: approvalFeedback.value.trim()
  });
  closeDialog(approvalScrim);
  activePromptId = null;
}

// ── Dialog helpers ───────────────────────────────────────────
function openDialog(scrim)  { scrim.classList.add('open'); }
function closeDialog(scrim) { scrim.classList.remove('open'); }

// ── Settings dialog ──────────────────────────────────────────
async function openSettings() {
  try {
    const data = await fetch('/api/config').then(r => r.json());
    sGemini.value      = data.gemini_api_key      || '';
    sGroq.value        = data.groq_api_key         || '';
    sOpenrouter.value  = data.openrouter_api_key   || '';
    sOllama.value      = data.ollama_base_url       || '';
    sOpenai.value      = data.openai_api_key       || '';
    sOpenaiUrl.value   = data.openai_base_url      || '';
    sAnthropic.value   = data.anthropic_api_key    || '';
    sAnthropicUrl.value = data.anthropic_base_url   || '';
    sTelegram.value    = data.telegram_bot_token   || '';
    sOpencode.value    = data.opencode_api_key      || '';
    sOpencodeUrl.value = data.opencode_base_url     || '';
  } catch { /* ignore - open anyway */ }
  openDialog(settingsScrim);
}

async function saveSettings() {
  try {
    const res = await fetch('/api/config/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        gemini_api_key:    sGemini.value.trim(),
        groq_api_key:      sGroq.value.trim(),
        openrouter_api_key: sOpenrouter.value.trim(),
        ollama_base_url:   sOllama.value.trim(),
        openai_api_key:    sOpenai.value.trim(),
        openai_base_url:   sOpenaiUrl.value.trim(),
        anthropic_api_key:  sAnthropic.value.trim(),
        anthropic_base_url: sAnthropicUrl.value.trim(),
        telegram_bot_token: sTelegram.value.trim(),
        opencode_api_key:  sOpencode.value.trim(),
        opencode_base_url: sOpencodeUrl.value.trim()
      })
    });


    if (res.ok) {
      appendLog('info', '✓ API settings saved successfully');
      closeDialog(settingsScrim);
      loadProviders();
    } else {
      const err = await res.json();
      alert(`Save failed: ${err.detail}`);
    }
  } catch (e) {
    alert(`Network error: ${e.message}`);
  }
}

// ── File viewer ──────────────────────────────────────────────
async function viewFile(path) {
  try {
    const data = await fetch(`/api/file/read?path=${encodeURIComponent(path)}`).then(r => r.json());
    fileDialogTitle.textContent = path;
    fileContent.textContent = data.content;
    openDialog(fileScrim);
  } catch (e) {
    alert(`Cannot read file: ${e.message}`);
  }
}

// ── Providers ────────────────────────────────────────────────
async function loadProviders() {
  const res  = await fetch('/api/providers').then(r => r.json());
  const list = $('providers-container');
  list.innerHTML = '';

  const ICONS = {
    gemini:      '✨',
    groq:        '⚡',
    openrouter:  '🌐',
    ollama:      '🦙',
    openai:      '🧠',
    anthropic:   '🦉',
    opencode:    '💡'
  };


  res.providers.forEach(p => {
    const active = res.current_provider.startsWith(p.id);
    const ok     = p.configured || p.id === 'ollama';

    const item = el('div', `provider-item${active ? ' active' : ''}${!ok ? ' disabled' : ''}`);
    item.dataset.providerId = p.id;

    const badge = el('div', 'provider-badge');
    badge.textContent = ICONS[p.id] || '🤖';

    const text = el('div', 'provider-text');
    const name = el('div', 'provider-name');
    name.textContent = p.name;
    text.append(name);

    // Determine currently selected model
    let selectedModel = p.default_model;
    if (active) {
      const parts = res.current_provider.split('/', 2);
      if (parts.length > 1) {
        selectedModel = parts[1];
      }
    }

    if (ok) {
      const selectContainer = el('div', 'model-select-container');
      selectContainer.style.marginTop = '4px';
      selectContainer.style.display = 'flex';
      selectContainer.style.flexDirection = 'column';
      selectContainer.style.gap = '4px';
      selectContainer.style.width = '100%';

      const select = el('select', 'model-dropdown');
      select.style.width = '100%';
      select.style.background = 'var(--md-surface-container-highest)';
      select.style.color = 'var(--md-on-surface)';
      select.style.border = '1px solid var(--md-outline-variant)';
      select.style.borderRadius = 'var(--md-shape-extra-small)';
      select.style.padding = '4px 8px';
      select.style.fontSize = '12px';
      select.style.fontFamily = 'Roboto, sans-serif';
      select.style.outline = 'none';

      let isCustom = !p.available_models.includes(selectedModel);

      p.available_models.forEach(m => {
        const opt = el('option');
        opt.value = m;
        opt.textContent = m;
        if (m === selectedModel && !isCustom) {
          opt.selected = true;
        }
        select.appendChild(opt);
      });

      const customOpt = el('option');
      customOpt.value = 'custom';
      customOpt.textContent = 'Custom Model...';
      if (isCustom) {
        customOpt.selected = true;
      }
      select.appendChild(customOpt);

      const customInput = el('input', 'model-custom-input');
      customInput.type = 'text';
      customInput.placeholder = 'Type model name...';
      customInput.value = isCustom ? selectedModel : '';
      customInput.style.display = isCustom ? 'block' : 'none';
      customInput.style.width = '100%';
      customInput.style.background = 'var(--md-surface-container-highest)';
      customInput.style.color = 'var(--md-on-surface)';
      customInput.style.border = '1px solid var(--md-outline-variant)';
      customInput.style.borderRadius = 'var(--md-shape-extra-small)';
      customInput.style.padding = '4px 8px';
      customInput.style.fontSize = '12px';
      customInput.style.fontFamily = 'Roboto Mono, monospace';
      customInput.style.outline = 'none';

      select.addEventListener('click', e => e.stopPropagation());
      customInput.addEventListener('click', e => e.stopPropagation());

      select.addEventListener('change', async (e) => {
        e.stopPropagation();
        if (select.value === 'custom') {
          customInput.style.display = 'block';
          customInput.focus();
        } else {
          customInput.style.display = 'none';
          await selectProvider(p.id, select.value);
        }
      });

      customInput.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
          e.stopPropagation();
          const val = customInput.value.trim();
          if (val) {
            await selectProvider(p.id, val);
          }
        }
      });

      customInput.addEventListener('blur', async (e) => {
        const val = customInput.value.trim();
        if (val && select.value === 'custom') {
          await selectProvider(p.id, val);
        }
      });

      selectContainer.append(select, customInput);
      text.append(selectContainer);
    } else {
      const model = el('div', 'provider-model');
      model.textContent = p.default_model;
      text.append(model);
    }

    const check = el('div', 'provider-check');
    item.append(badge, text, check);

    if (ok) {
      item.addEventListener('click', () => {
        const selectEl = item.querySelector('.model-dropdown');
        const customEl = item.querySelector('.model-custom-input');
        const modelVal = (selectEl && selectEl.value === 'custom' && customEl.value.trim())
          ? customEl.value.trim()
          : (selectEl ? selectEl.value : p.default_model);
        selectProvider(p.id, modelVal);
      });
    }

    list.appendChild(item);
  });

}

async function selectProvider(id, model) {
  await fetch('/api/providers/select', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider_model: `${id}/${model}` })
  });
}

// ── File tree ────────────────────────────────────────────────
async function loadFiles() {
  const tree = await fetch('/api/files').then(r => r.json());
  const el2  = $('file-tree');
  el2.innerHTML = '';
  renderTree(tree, el2);
}

function renderTree(nodes, parent) {
  nodes.forEach(node => {
    const wrapper = el('div', 'tree-node');
    const row     = el('div', 'tree-row');
    row.setAttribute('role', node.type === 'directory' ? 'group' : 'treeitem');

    const icon = el('span', 'tree-icon');
    icon.textContent = node.type === 'directory' ? '📂' : getFileIcon(node.name);

    const name = el('span', 'tree-name');
    name.textContent = node.name;
    row.append(icon, name);
    wrapper.appendChild(row);

    if (node.type === 'directory') {
      const children = el('div', 'tree-children');
      if (node.children?.length) renderTree(node.children, children);
      wrapper.appendChild(children);
      row.addEventListener('click', e => {
        e.stopPropagation();
        const hidden = children.style.display === 'none';
        children.style.display = hidden ? '' : 'none';
        icon.textContent = hidden ? '📂' : '📁';
      });
    } else {
      row.addEventListener('click', e => { e.stopPropagation(); viewFile(node.path); });
    }

    parent.appendChild(wrapper);
  });
}

function getFileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  const map = { py:'🐍', js:'🟨', ts:'🔷', html:'🌐', css:'🎨', json:'📋', md:'📝', txt:'📄', sh:'⚙️', env:'🔑', toml:'⚙️', yml:'⚙️', yaml:'⚙️' };
  return map[ext] || '📄';
}

// ── Utility ───────────────────────────────────────────────────
function el(tag, cls) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
}

function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ── Reminders logic ───────────────────────────────────────────
function playReminderSound() {
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const playBeep = (freq, time, duration) => {
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, time);
      gain.gain.setValueAtTime(0.2, time);
      gain.gain.exponentialRampToValueAtTime(0.01, time + duration);
      osc.start(time);
      osc.stop(time + duration);
    };

    const now = audioCtx.currentTime;
    playBeep(880, now, 0.2);
    playBeep(1109, now + 0.15, 0.4);
  } catch (e) {
    console.error("Audio error:", e);
  }
}

function handleReminderTrigger(data) {
  playReminderSound();
  appendLog('warning', `⏰ REMINDER ALERT: ${data.message}`);

  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    new Notification("Unlocked AI Reminder ⏰", {
      body: data.message,
      icon: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>⏰</text></svg>"
    });
  }
  loadReminders();
}

async function loadReminders() {
  try {
    const reminders = await fetch('/api/reminders').then(r => r.json());
    renderRemindersList(reminders);
  } catch (e) {
    console.error("Error loading reminders:", e);
  }
}

function renderRemindersList(reminders) {
  remindersContainer.innerHTML = '';
  
  if (reminders.length === 0) {
    remindersContainer.innerHTML = '<div class="loading-text" style="color: var(--md-on-surface-variant); font-size: var(--md-body-small); text-align: center; padding: 12px;">No active reminders</div>';
    return;
  }
  
  reminders.forEach(r => {
    const item = el('div', 'reminder-item');
    item.style.display = 'flex';
    item.style.alignItems = 'center';
    item.style.justifyContent = 'space-between';
    item.style.gap = '8px';
    item.style.padding = '8px 12px';
    item.style.borderRadius = 'var(--md-shape-medium)';
    item.style.background = 'var(--md-surface-container-high)';
    item.style.marginBottom = '6px';
    
    const details = el('div');
    details.style.flex = '1';
    details.style.minWidth = '0';
    
    const msgText = el('div');
    msgText.style.fontSize = 'var(--md-body-medium)';
    msgText.style.color = 'var(--md-on-surface)';
    msgText.style.fontWeight = '500';
    msgText.style.textOverflow = 'ellipsis';
    msgText.style.overflow = 'hidden';
    msgText.style.whiteSpace = 'nowrap';
    msgText.textContent = r.message;
    
    const intervalText = el('div');
    intervalText.style.fontSize = 'var(--md-label-small)';
    intervalText.style.color = 'var(--md-on-surface-variant)';
    const recurStr = r.is_recurring ? 'recurring' : 'one-off';
    intervalText.textContent = `every ${r.interval_minutes}m (${recurStr})`;
    
    details.append(msgText, intervalText);
    
    const cancelBtn = el('button', 'icon-btn');
    cancelBtn.style.width = '28px';
    cancelBtn.style.height = '28px';
    cancelBtn.style.fontSize = '12px';
    cancelBtn.style.color = 'var(--md-error)';
    cancelBtn.style.border = 'none';
    cancelBtn.style.background = 'transparent';
    cancelBtn.style.cursor = 'pointer';
    cancelBtn.textContent = '✕';
    cancelBtn.title = 'Cancel reminder';
    
    cancelBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await cancelReminder(r.id);
    });
    
    item.append(details, cancelBtn);
    remindersContainer.appendChild(item);
  });
}

async function cancelReminder(id) {
  try {
    const res = await fetch('/api/reminders/cancel', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reminder_id: id })
    });
    if (res.ok) {
      appendLog('info', '✓ Reminder cancelled');
      loadReminders();
    }
  } catch (e) {
    console.error("Error cancelling reminder:", e);
  }
}

async function addReminder() {
  const message = rMessage.value.trim();
  const interval = parseFloat(rInterval.value);
  const isRecurring = rRecurring.checked;
  
  if (!message) {
    alert("Please enter a reminder message.");
    return;
  }
  if (isNaN(interval) || interval <= 0) {
    alert("Please enter a valid positive interval in minutes.");
    return;
  }
  
  try {
    const res = await fetch('/api/reminders/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        interval_minutes: interval,
        is_recurring: isRecurring
      })
    });
    
    if (res.ok) {
      appendLog('info', `✓ Scheduled reminder: "${message}"`);
      closeDialog(reminderScrim);
      rMessage.value = '';
      rInterval.value = '1';
      loadReminders();
    } else {
      const err = await res.json();
      alert(`Failed to add reminder: ${err.detail}`);
    }
  } catch (e) {
    alert(`Network error: ${e.message}`);
  }
}

// ── Productivity Hub logic ───────────────────────────────────────
// Tab switches
function switchTab(tab) {
  if (tab === 'pomo') {
    tabPomoBtn.classList.add('active');
    tabTodoBtn.classList.remove('active');
    tabPomoBtn.style.background = 'var(--md-secondary-container)';
    tabPomoBtn.style.color = 'var(--md-on-secondary-container)';
    tabTodoBtn.style.background = 'transparent';
    tabTodoBtn.style.color = 'var(--md-on-surface-variant)';
    panelPomo.style.display = 'flex';
    panelTodo.style.display = 'none';
  } else {
    tabTodoBtn.classList.add('active');
    tabPomoBtn.classList.remove('active');
    tabTodoBtn.style.background = 'var(--md-secondary-container)';
    tabTodoBtn.style.color = 'var(--md-on-secondary-container)';
    tabPomoBtn.style.background = 'transparent';
    tabPomoBtn.style.color = 'var(--md-on-surface-variant)';
    panelTodo.style.display = 'flex';
    panelPomo.style.display = 'none';
  }
}

// Pomodoro Timer
async function checkPomodoroStatus() {
  try {
    const status = await fetch('/api/pomodoro').then(r => r.json());
    updatePomodoroUI(status);
  } catch (e) {
    console.error("Error checking Pomodoro status:", e);
  }
}

async function startPomodoro(minutes, type) {
  try {
    const res = await fetch('/api/pomodoro/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ duration_minutes: minutes, session_type: type })
    });
    if (res.ok) {
      appendLog('info', `🍅 Started Pomodoro ${type} timer (${minutes}m)`);
      const status = await res.json();
      updatePomodoroUI(status);
    }
  } catch (e) {
    console.error("Error starting Pomodoro:", e);
  }
}

async function stopPomodoro() {
  try {
    const res = await fetch('/api/pomodoro/stop', { method: 'POST' });
    if (res.ok) {
      appendLog('info', '🍅 Stopped Pomodoro timer');
      checkPomodoroStatus();
    }
  } catch (e) {
    console.error("Error stopping Pomodoro:", e);
  }
}

function updatePomodoroUI(status) {
  if (status.active) {
    const mins = Math.floor(status.remaining_seconds / 60);
    const secs = status.remaining_seconds % 60;
    pomoTimerText.textContent = `${mins}:${secs < 10 ? '0' : ''}${secs}`;
    pomoLabel.textContent = status.session_type;
    pomoLabel.style.color = status.session_type === 'focus' ? 'var(--md-primary)' : 'var(--md-tertiary)';
    pomoTimerText.style.color = status.session_type === 'focus' ? 'var(--md-primary)' : 'var(--md-tertiary)';
    
    // Show stop button, hide presets
    pomoStopBtn.style.display = 'inline-block';
    pomo25Btn.style.display = 'none';
    pomo5Btn.style.display = 'none';
  } else {
    pomoTimerText.textContent = '25:00';
    pomoLabel.textContent = 'Ready';
    pomoLabel.style.color = 'var(--md-on-surface-variant)';
    pomoTimerText.style.color = 'var(--md-on-surface-variant)';
    
    // Hide stop button, show presets
    pomoStopBtn.style.display = 'none';
    pomo25Btn.style.display = 'inline-block';
    pomo5Btn.style.display = 'inline-block';
  }
}

function handlePomodoroComplete(data) {
  playReminderSound();
  appendLog('warning', `🍅 POMODORO COMPLETE: Your ${data.session_type} session is finished.`);
  
  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    new Notification("Pomodoro Complete! 🍅", {
      body: `Your ${data.session_type} session has finished.`,
      icon: "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>🍅</text></svg>"
    });
  }
  checkPomodoroStatus();
}

// Todos (Tasks)
async function loadTodos() {
  try {
    const todos = await fetch('/api/todos').then(r => r.json());
    renderTodosList(todos);
  } catch (e) {
    console.error("Error loading todos:", e);
  }
}

function renderTodosList(todos) {
  todoListContainer.innerHTML = '';
  
  if (todos.length === 0) {
    todoListContainer.innerHTML = '<div class="loading-text" style="color: var(--md-on-surface-variant); font-size: var(--md-body-small); text-align: center; padding: 12px;">No active tasks</div>';
    return;
  }
  
  todos.forEach(t => {
    const item = el('div', 'todo-item');
    item.style.display = 'flex';
    item.style.alignItems = 'center';
    item.style.justifyContent = 'space-between';
    item.style.gap = '8px';
    item.style.padding = '6px 8px';
    item.style.borderRadius = 'var(--md-shape-small)';
    item.style.background = 'var(--md-surface-container-high)';
    
    const details = el('div');
    details.style.display = 'flex';
    details.style.alignItems = 'center';
    details.style.gap = '8px';
    details.style.flex = '1';
    details.style.minWidth = '0';
    
    const checkbox = el('input');
    checkbox.type = 'checkbox';
    checkbox.checked = t.completed;
    checkbox.style.cursor = 'pointer';
    checkbox.style.accentColor = 'var(--md-primary)';
    checkbox.addEventListener('change', async (e) => {
      e.stopPropagation();
      await toggleTodo(t.id);
    });
    
    const text = el('span');
    text.style.fontSize = '12px';
    text.style.color = t.completed ? 'var(--md-on-surface-variant)' : 'var(--md-on-surface)';
    text.style.textDecoration = t.completed ? 'line-through' : 'none';
    text.style.textOverflow = 'ellipsis';
    text.style.overflow = 'hidden';
    text.style.whiteSpace = 'nowrap';
    text.textContent = t.text;
    
    details.append(checkbox, text);
    
    const delBtn = el('button');
    delBtn.style.border = 'none';
    delBtn.style.background = 'transparent';
    delBtn.style.color = 'var(--md-error)';
    delBtn.style.cursor = 'pointer';
    delBtn.style.fontSize = '11px';
    delBtn.textContent = '🗑';
    delBtn.title = 'Delete task';
    
    delBtn.addEventListener('click', async (e) => {
      e.stopPropagation();
      await deleteTodo(t.id);
    });
    
    item.append(details, delBtn);
    todoListContainer.appendChild(item);
  });
}

async function addTodo() {
  const text = todoInput.value.trim();
  if (!text) return;
  
  try {
    const res = await fetch('/api/todos/add', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    if (res.ok) {
      todoInput.value = '';
      loadTodos();
    }
  } catch (e) {
    console.error("Error adding todo:", e);
  }
}

async function toggleTodo(id) {
  try {
    const res = await fetch('/api/todos/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ todo_id: id })
    });
    if (res.ok) {
      loadTodos();
    }
  } catch (e) {
    console.error("Error toggling todo:", e);
  }
}

async function deleteTodo(id) {
  try {
    const res = await fetch('/api/todos/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ todo_id: id })
    });
    if (res.ok) {
      loadTodos();
    }
  } catch (e) {
    console.error("Error deleting todo:", e);
  }
}

// ── Auto-resize textarea ─────────────────────────────────────
promptInput.addEventListener('input', () => {
  promptInput.style.height = 'auto';
  promptInput.style.height = Math.min(promptInput.scrollHeight, 120) + 'px';
});

// ── Event bindings ────────────────────────────────────────────

// Prompt
runBtn.onclick = runAgent;
promptInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runAgent(); }
});

// Terminal
terminalInput.addEventListener('keydown', e => {
  if (e.key === 'Enter') runTerminalCmd();
});
clearTerminalBtn.onclick = () => {
  while (terminalView.firstChild) terminalView.removeChild(terminalView.firstChild);
  const welcome = el('div', 'terminal-welcome-text');
  welcome.textContent = 'Terminal cleared.';
  terminalView.appendChild(welcome);
};

// Approval
approveBtn.onclick = () => sendApproval(true);
rejectBtn.onclick  = () => sendApproval(false);

// File dialog
[closeFileBtn, closeFileBtn2].forEach(b => b.onclick = () => closeDialog(fileScrim));
fileScrim.addEventListener('click', e => { if (e.target === fileScrim) closeDialog(fileScrim); });

// Settings dialog
settingsBtn.onclick      = openSettings;
cancelSettingsBtn.onclick = () => closeDialog(settingsScrim);
saveSettingsBtn.onclick  = saveSettings;
settingsScrim.addEventListener('click', e => { if (e.target === settingsScrim) closeDialog(settingsScrim); });

// File refresh
refreshFilesBtn.onclick = loadFiles;

// Reminders
addReminderBtn.onclick = () => openDialog(reminderScrim);
cancelReminderBtn.onclick = () => { closeDialog(reminderScrim); rMessage.value = ''; rInterval.value = '1'; };
saveReminderBtn.onclick = addReminder;
reminderScrim.addEventListener('click', e => { if (e.target === reminderScrim) closeDialog(reminderScrim); });

// Productivity Hub (Pomodoro + Todos)
tabPomoBtn.onclick = () => switchTab('pomo');
tabTodoBtn.onclick = () => switchTab('todo');
pomo25Btn.onclick  = () => startPomodoro(25, 'focus');
pomo5Btn.onclick   = () => startPomodoro(5, 'break');
pomoStopBtn.onclick = stopPomodoro;

todoAddBtn.onclick = addTodo;
todoInput.addEventListener('keydown', e => { if (e.key === 'Enter') { e.stopPropagation(); addTodo(); } });

// Scrim backdrop closes on click
approvalScrim.addEventListener('click', e => {
  if (e.target === approvalScrim) closeDialog(approvalScrim);
});

// ── Bootstrap ─────────────────────────────────────────────────
connect();
