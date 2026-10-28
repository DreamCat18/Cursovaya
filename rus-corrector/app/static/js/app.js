const state = { errors: [], originalText: '', correctedText: '', filter: 'all', checking: false };

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

btnClear.addEventListener('click', () => {
  editor.innerHTML = '';
  state.errors = [];
  state.originalText = '';
  state.correctedText = '';
  renderErrors();
  renderCorrected();
  updateCharCount();
  setStatus('Готово к проверке');
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
    
    state.originalText = text;
    state.errors = data.errors || [];
    state.correctedText = data.corrected_text || text;

    // Подсветка строится по координатам, а не по поиску первого совпадения.
    highlightErrors(state.errors, state.originalText);

    renderErrors();
    renderCorrected();
    
    setStatus(state.errors.length ? `Найдено ошибок: ${state.errors.length}` : 'Ошибок не найдено');
    
  } catch (err) {
    setStatus('Ошибка проверки', true);
  } finally {
    state.checking = false;
    btnCheck.disabled = false;
  }
});

function highlightErrors(errors, originalText) {
  const ranges = errors
    .map((err, idx) => ({ ...err, idx, start: Number(err.start), end: Number(err.end) }))
    .filter(err => Number.isInteger(err.start) && Number.isInteger(err.end)
      && err.start >= 0 && err.end >= err.start && err.end <= originalText.length)
    .sort((a, b) => a.start - b.start || a.end - b.end);

  let cursor = 0;
  let html = '';
  for (const err of ranges) {
    if (err.start < cursor) continue;
    html += escapeHtml(originalText.slice(cursor, err.start));
    if (err.end === err.start) {
      // Вставленная запятая не существует в исходнике: ставим кликабельный маркер
      // точно в позицию вставки, чтобы карточка всё равно имела связь с текстом.
      html += `<span class="err-marker err-marker--${escapeHtml(err.type)}" data-idx="${err.idx}" title="Пунктуационное исправление">│</span>`;
    } else {
      html += `<span class="err err--${escapeHtml(err.type)}" data-idx="${err.idx}" title="Нажмите, чтобы увидеть исправление">${escapeHtml(originalText.slice(err.start, err.end))}</span>`;
    }
    cursor = err.end;
  }
  html += escapeHtml(originalText.slice(cursor));
  editor.innerHTML = html;
}

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
}

function labelFor(type) {
  const map = { grammar: 'Грамматика', syntax: 'Синтаксис', lexis: 'Лексика', punct: 'Пунктуация' };
  return map[type] || type;
}

document.querySelectorAll('.result-tab').forEach(tab => tab.addEventListener('click', () => switchResultTab(tab.dataset.result)));
function switchResultTab(name) {
  document.querySelectorAll('.result-tab').forEach(t => t.classList.toggle('result-tab--active', t.dataset.result === name));
  document.getElementById('pane-errors').hidden = name !== 'errors';
  document.getElementById('pane-corrected').hidden = name !== 'corrected';
}

function renderCorrected() {
  if (!state.correctedText) {
    correctedText.textContent = 'Исправленный текст появится здесь после проверки.';
    btnCopyCorrected.disabled = true;
    return;
  }

  const ranges = state.errors
    .map((err, idx) => ({
      ...err, idx,
      start: Number(err.corrected_start),
      end: Number(err.corrected_end)
    }))
    .filter(err => Number.isInteger(err.start) && Number.isInteger(err.end)
      && err.start >= 0 && err.end >= err.start && err.end <= state.correctedText.length)
    .sort((a, b) => a.start - b.start || a.end - b.end);

  let cursor = 0;
  let html = '';
  for (const err of ranges) {
    if (err.start < cursor) continue;
    html += escapeHtml(state.correctedText.slice(cursor, err.start));
    if (err.end === err.start) {
      // Если в чистовике позиция нулевая (например, удаление), оставляем маркер связи.
      html += `<span class="corrected-marker" data-idx="${err.idx}" title="Показать объяснение">│</span>`;
    } else {
      html += `<span class="corrected-change" data-idx="${err.idx}" title="Нажмите, чтобы увидеть объяснение">${escapeHtml(state.correctedText.slice(err.start, err.end))}</span>`;
    }
    cursor = err.end;
  }
  html += escapeHtml(state.correctedText.slice(cursor));
  correctedText.innerHTML = html;
  btnCopyCorrected.disabled = false;
}

btnCopyCorrected.addEventListener('click', async () => {
  if (!state.correctedText) return;
  try {
    await navigator.clipboard.writeText(state.correctedText);
    setStatus('Скопировано');
    btnCopyCorrected.textContent = 'Скопировано';
    setTimeout(() => btnCopyCorrected.textContent = 'Скопировать чистовик', 1500);
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

// Вкладки шапки (без изменений)
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

// Чат (без изменений)
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


function focusError(idx, source = true) {
  switchResultTab('errors');
  const card = errorsList.querySelector(`.error-item[data-idx="${idx}"]`);
  if (card) {
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.classList.add('error-item--active');
    window.setTimeout(() => card.classList.remove('error-item--active'), 1300);
  }
  const selector = source ? `.err[data-idx="${idx}"], .err-marker[data-idx="${idx}"]`
                          : `.corrected-change[data-idx="${idx}"], .corrected-marker[data-idx="${idx}"]`;
  const target = (source ? editor : correctedText).querySelector(selector);
  if (target) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.classList.add('err--active');
    window.setTimeout(() => target.classList.remove('err--active'), 1300);
  }
}

editor.addEventListener('click', (event) => {
  const target = event.target.closest('[data-idx]');
  if (target) focusError(Number(target.dataset.idx), true);
});
correctedText.addEventListener('click', (event) => {
  const target = event.target.closest('[data-idx]');
  if (target) focusError(Number(target.dataset.idx), false);
});
errorsList.addEventListener('click', (event) => {
  const card = event.target.closest('.error-item[data-idx]');
  if (card) {
    const idx = Number(card.dataset.idx);
    const target = editor.querySelector(`.err[data-idx="${idx}"], .err-marker[data-idx="${idx}"]`);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      target.classList.add('err--active');
      window.setTimeout(() => target.classList.remove('err--active'), 1300);
    }
  }
});

updateCharCount();