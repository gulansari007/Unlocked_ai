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

// Scrim backdrop closes on click
approvalScrim.addEventListener('click', e => {
  if (e.target === approvalScrim) closeDialog(approvalScrim);
});

// ── Bootstrap ─────────────────────────────────────────────────
connect();
