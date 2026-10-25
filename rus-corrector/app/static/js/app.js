const state = { errors: [], correctedText: '', filter: 'all', checking: false };

const editor = document.getElementById('editor');
const charCount = document.getElementById('char-count');
const statusText = document.getElementById('status-text');
const btnCheck = document.getElementById('btn-check');
const btnClear = document.getElementById('btn-clear');
const btnCopyCorrected = document.getElementById('btn-copy-corrected');
const correctedText = document.getElementById('corrected-text');
const errorsList = document.getElementById('errors-list');
const errorsCount = document.getElementById('errors-count');

const escapeHtml = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
const setStatus = (text, isError = false) => {
  statusText.textContent = text;
  statusText.style.color = isError ? 'var(--red-500)' : 'var(--blue-600)';
};
const getPlainText = () => editor.innerText.replace(/\u00a0/g, ' ');
const updateCharCount = () => { charCount.textContent = `${getPlainText().length} знаков`; };

editor.addEventListener('input', updateCharCount);
editor.addEventListener('paste', (e) => {
  e.preventDefault();
  const text = (e.clipboardData || window.clipboardData).getData('text/plain');
  document.execCommand('insertText', false, text);
});

btnClear.addEventListener('click', () => {
  editor.innerHTML = '';
  state.errors = [];
  state.correctedText = '';
  renderErrors();
  renderCorrected();
  updateCharCount();
  setStatus('Готово к проверке');
  switchResultTab('errors');
});

btnCheck.addEventListener('click', async () => {
  const text = getPlainText().trim();
  if (!text) { setStatus('Введите текст', true); return; }

  state.checking = true;
  btnCheck.disabled = true;
  setStatus('Проверяем текст…');

  try {
    const response = await fetch('/api/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });
    if (!response.ok) throw new Error('Ошибка');
    const data = await response.json();
    state.errors = data.errors || [];
    state.correctedText = data.corrected_text || text;

    highlightErrors(state.errors);
    renderErrors();
    renderCorrected();
    
    setStatus(state.errors.length ? `Найдено ошибок: ${state.errors.length}` : 'Ошибок не найдено');
    
    // Если ошибки есть, показываем вкладку "Ошибки", иначе "Исправленный текст"
    switchResultTab(state.errors.length > 0 ? 'errors' : 'corrected');
    
  } catch (err) {
    setStatus('Ошибка проверки', true);
  } finally {
    state.checking = false;
    btnCheck.disabled = false;
  }
});

function highlightErrors(errors) {
  const plain = editor.innerText.replace(/\u00a0/g, ' ');
  if (!errors.length) { editor.textContent = plain; return; }

  const sortedErrors = [...errors].filter(e => e.fragment).sort((a, b) => b.fragment.length - a.fragment.length);
  let html = escapeHtml(plain);

  sortedErrors.forEach((err) => {
    const safeFrag = escapeHtml(err.fragment);
    const safeSugg = escapeHtml(err.suggestion || '');
    const pos = html.indexOf(safeFrag);
    
    if (pos !== -1) {
      const openTagPos = html.lastIndexOf('<span', pos);
      const closeTagPos = html.lastIndexOf('</span>', pos);
      if (openTagPos > closeTagPos) return;

      const idx = errors.indexOf(err);
      const replacement = `<span class="err err--${err.type}" data-idx="${idx}" data-suggestion="${safeSugg}">${safeFrag}</span>`;
      html = html.substring(0, pos) + replacement + html.substring(pos + safeFrag.length);
    }
  });

  editor.innerHTML = html;
  editor.querySelectorAll('.err').forEach(span => {
    span.addEventListener('click', (e) => {
      e.preventDefault();
      const idx = Number(span.dataset.idx);
      switchResultTab('errors');
      highlightItemInList(idx);
      scrollToErrorInList(idx);
    });
  });
}

function highlightItemInList(idx) {
  document.querySelectorAll('.error-item').forEach(item => item.classList.toggle('error-item--active', Number(item.dataset.idx) === idx));
  document.querySelectorAll('.err').forEach(span => span.classList.toggle('err--active', Number(span.dataset.idx) === idx));
}
function scrollToErrorInList(idx) {
  const item = document.querySelector(`.error-item[data-idx="${idx}"]`);
  if (item) item.scrollIntoView({ behavior: 'smooth', block: 'center' });
}
function scrollToErrorInEditor(idx) {
  const span = editor.querySelector(`.err[data-idx="${idx}"]`);
  if (span) span.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

document.querySelectorAll('.result-tab').forEach(tab => tab.addEventListener('click', () => switchResultTab(tab.dataset.result)));
function switchResultTab(name) {
  document.querySelectorAll('.result-tab').forEach(t => t.classList.toggle('result-tab--active', t.dataset.result === name));
  document.getElementById('pane-errors').hidden = name !== 'errors';
  document.getElementById('pane-corrected').hidden = name !== 'corrected';
}

function renderCorrected() {
  const text = state.correctedText || '';
  if (!text) {
    correctedText.textContent = 'Исправленный текст появится здесь после проверки.';
    btnCopyCorrected.disabled = true; return;
  }
  correctedText.textContent = text;
  btnCopyCorrected.disabled = false;
}

btnCopyCorrected.addEventListener('click', async () => {
  if (!state.correctedText) return;
  try {
    await navigator.clipboard.writeText(state.correctedText);
    setStatus('Скопировано');
    btnCopyCorrected.textContent = 'Скопировано';
    setTimeout(() => btnCopyCorrected.textContent = 'Скопировать исправленный текст', 1500);
  } catch { setStatus('Ошибка копирования', true); }
});

document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('chip--active'));
    chip.classList.add('chip--active');
    state.filter = chip.dataset.filter;
    renderErrors();
  });
});

function renderErrors() {
  const filtered = state.filter === 'all' ? state.errors : state.errors.filter(e => e.type === state.filter);
  errorsCount.textContent = state.errors.length;
  if (!filtered.length) {
    errorsList.innerHTML = `<li class="errors__empty"><div class="empty__icon">✓</div><p>Ошибок нет.</p></li>`;
    return;
  }
  errorsList.innerHTML = filtered.map((err) => {
    const idx = state.errors.indexOf(err);
    const frag = escapeHtml(err.fragment || '');
    const sugg = escapeHtml(err.suggestion || '');
    const reason = err.reason ? escapeHtml(err.reason) : '';
    return `<li class="error-item" data-idx="${idx}">
      <div class="error-item__top"><span class="error-item__type type--${err.type}">${labelFor(err.type)}</span></div>
      <div class="error-item__frag">${frag}</div>
      <div class="error-item__fix">→ ${sugg || 'удалить'}</div>
      ${reason ? `<div class="error-item__why">${reason}</div>` : ''}
    </li>`;
  }).join('');
  errorsList.querySelectorAll('.error-item').forEach(item => {
    item.addEventListener('click', () => {
      const idx = Number(item.dataset.idx);
      highlightItemInList(idx);
      scrollToErrorInEditor(idx);
    });
  });
}

function labelFor(type) {
  const map = { grammar: 'Грамматика', syntax: 'Синтаксис', lexis: 'Лексика', punct: 'Пунктуация' };
  return map[type] || type;
}

// Вкладки и модалки
document.querySelectorAll('.nav__btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.nav__btn').forEach(b => b.classList.remove('nav__btn--active'));
    btn.classList.add('nav__btn--active');
    if (tab === 'chat') openModal('modal-chat');
    if (tab === 'help') openModal('modal-help');
    if (tab === 'editor') document.querySelectorAll('.modal').forEach(m => m.hidden = true);
  });
});
function openModal(id) { document.getElementById(id).hidden = false; }
function closeModal(id) {
  document.getElementById(id).hidden = true;
  if (id === 'modal-chat') {
    document.querySelectorAll('.nav__btn').forEach(b => b.classList.remove('nav__btn--active'));
    document.querySelector('[data-tab="editor"]').classList.add('nav__btn--active');
  }
}
document.querySelectorAll('[data-close]').forEach(el => el.addEventListener('click', () => {
  const modal = el.closest('.modal'); if (modal) closeModal(modal.id);
}));
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') document.querySelectorAll('.modal:not([hidden])').forEach(m => closeModal(m.id)); });

// Чат
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatLog = document.getElementById('chat-log');
chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;
  appendMessage('user', question);
  chatInput.value = '';
  const thinking = appendMessage('bot', 'Думаю…');
  try {
    const response = await fetch('/api/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, text: getPlainText() })
    });
    const data = await response.json();
    thinking.textContent = data.answer || 'Не удалось получить ответ.';
  } catch { thinking.textContent = 'Ошибка связи.'; }
});
function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `chat__msg chat__msg--${role}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

updateCharCount();
renderCorrected();