/* ===== Состояние ===== */
const state = {
  errors: [],
  filter: 'all',
  checking: false
};

/* ===== Элементы ===== */
const editor      = document.getElementById('editor');
const charCount   = document.getElementById('char-count');
const statusText  = document.getElementById('status-text');
const btnCheck    = document.getElementById('btn-check');
const btnClear    = document.getElementById('btn-clear');
const btnCopy     = document.getElementById('btn-copy');
const errorsList  = document.getElementById('errors-list');
const errorsCount = document.getElementById('errors-count');

/* ===== Утилиты ===== */
const escapeHtml = (s) => String(s)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

const setStatus = (text, isError = false) => {
  statusText.textContent = text;
  statusText.style.color = isError ? 'var(--red-500)' : 'var(--blue-600)';
};

const getPlainText = () => editor.innerText.replace(/\u00a0/g, ' ');

const updateCharCount = () => {
  charCount.textContent = `${getPlainText().length} знаков`;
};

/* ===== Ввод текста ===== */
editor.addEventListener('input', () => {
  updateCharCount();
  btnCopy.disabled = !getPlainText().trim();
});

/* ===== Вставка только текста ===== */
editor.addEventListener('paste', (e) => {
  e.preventDefault();
  const text = (e.clipboardData || window.clipboardData).getData('text/plain');
  document.execCommand('insertText', false, text);
});

/* ===== Очистка ===== */
btnClear.addEventListener('click', () => {
  editor.innerHTML = '';
  state.errors = [];
  renderErrors();
  updateCharCount();
  btnCopy.disabled = true;
  setStatus('Готово к проверке');
});

/* ===== Копирование исправленного текста ===== */
btnCopy.addEventListener('click', async () => {
  // Собираем текст из DOM, убирая служебные span
  const clone = editor.cloneNode(true);

  clone.querySelectorAll('.err').forEach(span => {
    const fix = span.dataset.suggestion;
    const original = span.textContent;

    // Если suggestion пустой или равен "(удалить)" — удаляем фрагмент
    if (fix === '' || fix === undefined || fix === '(удалить)') {
      span.remove();
      return;
    }

    // Иначе заменяем на исправление
    span.replaceWith(document.createTextNode(fix));
  });

  const cleanText = clone.innerText.replace(/\u00a0/g, ' ');

  try {
    await navigator.clipboard.writeText(cleanText);
    setStatus('Исправленный текст скопирован');
    btnCopy.textContent = 'Скопировано';
    setTimeout(() => { btnCopy.textContent = 'Скопировать'; }, 1500);
  } catch {
    setStatus('Не удалось скопировать. Выделите текст вручную.', true);
  }
});

/* ===== Проверка текста ===== */
btnCheck.addEventListener('click', async () => {
  const text = getPlainText().trim();
  if (!text) {
    setStatus('Введите текст для проверки', true);
    return;
  }

  state.checking = true;
  btnCheck.disabled = true;
  setStatus('Проверяем текст…');

  try {
    const response = await fetch('/api/check', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text })
    });

    if (!response.ok) throw new Error('Ошибка сервера');

    const data = await response.json();
    state.errors = data.errors || [];

    highlightErrors(state.errors);
    renderErrors();

    setStatus(
      state.errors.length
        ? `Найдено ошибок: ${state.errors.length}`
        : 'Ошибок не найдено — текст выглядит корректно'
    );
    btnCopy.disabled = false;
  } catch (err) {
    setStatus('Не удалось проверить текст. Попробуйте ещё раз.', true);
    console.error(err);
  } finally {
    state.checking = false;
    btnCheck.disabled = false;
  }
});

/* ===== Подсветка ошибок в тексте ===== */
function highlightErrors(errors) {
  // 1. Получаем чистый текст без предыдущих подсветок
  const plain = editor.innerText.replace(/\u00a0/g, ' ');

  // 2. Разбиваем текст на токены (слова, знаки препинания, пробелы)
  const tokens = plain.match(/\w+|[^\w\s]|\s+/g) || [];

  // 3. Индексируем ошибки по фрагментам
  const errByFragment = new Map();
  errors.forEach((err, idx) => {
    const key = (err.fragment || '').toLowerCase().trim();
    if (key) errByFragment.set(key, { ...err, idx });
  });

  // 4. Собираем HTML, оборачивая подходящие токены в span
  let html = '';
  const usedIdx = new Set();

  tokens.forEach((token) => {
    const key = token.toLowerCase().trim();
    const err = errByFragment.get(key);

    if (err && !usedIdx.has(err.idx)) {
      usedIdx.add(err.idx);
      const safe = escapeHtml(token);
      const suggestion = escapeHtml(err.suggestion || '');
      html += `<span class="err err--${err.type}" data-idx="${err.idx}" data-suggestion="${suggestion}">${safe}</span>`;
    } else {
      html += escapeHtml(token);
    }
  });

  editor.innerHTML = html;

  // 5. Навешиваем обработчики на подсвеченные фрагменты
  editor.querySelectorAll('.err').forEach(span => {
    span.addEventListener('click', (e) => {
      e.preventDefault();
      const idx = Number(span.dataset.idx);
      highlightItemInList(idx);
      scrollToErrorInList(idx);
    });
  });
}

/* ===== Синхронизация: клик по ошибке в списке ===== */
function highlightItemInList(idx) {
  document.querySelectorAll('.error-item').forEach(item => {
    item.classList.toggle('error-item--active', Number(item.dataset.idx) === idx);
  });
  document.querySelectorAll('.err').forEach(span => {
    span.classList.toggle('err--active', Number(span.dataset.idx) === idx);
  });
}

function scrollToErrorInList(idx) {
  const item = document.querySelector(`.error-item[data-idx="${idx}"]`);
  if (item) {
    item.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}

/* ===== Фильтр ===== */
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('chip--active'));
    chip.classList.add('chip--active');
    state.filter = chip.dataset.filter;
    renderErrors();
  });
});

/* ===== Отрисовка списка ошибок ===== */
function renderErrors() {
  const filtered = state.filter === 'all'
    ? state.errors
    : state.errors.filter(e => e.type === state.filter);

  errorsCount.textContent = state.errors.length;

  if (!filtered.length) {
    errorsList.innerHTML = `
      <li class="errors__empty">
        <div class="empty__icon">✓</div>
        <p>${state.errors.length
          ? 'В этой категории ошибок нет.'
          : 'Ошибок пока нет. Введите текст и нажмите «Проверить».'}</p>
      </li>`;
    return;
  }

  errorsList.innerHTML = filtered.map((err) => {
    const idx = state.errors.indexOf(err);
    const frag = escapeHtml(err.fragment || '');
    const sugg = escapeHtml(err.suggestion || '');
    const reason = err.reason ? escapeHtml(err.reason) : '';

    const suggestionHtml = sugg
      ? `<div class="error-item__fix">→ ${sugg}</div>`
      : `<div class="error-item__fix">→ удалить</div>`;

    return `
      <li class="error-item" data-idx="${idx}">
        <div class="error-item__top">
          <span class="error-item__type type--${err.type}">${labelFor(err.type)}</span>
        </div>
        <div class="error-item__frag">${frag}</div>
        ${suggestionHtml}
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

function scrollToErrorInEditor(idx) {
  const span = editor.querySelector(`.err[data-idx="${idx}"]`);
  if (span) span.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function labelFor(type) {
  const map = {
    grammar: 'Грамматика',
    syntax: 'Синтаксис',
    lexis: 'Лексика',
    punct: 'Пунктуация'
  };
  return map[type] || type;
}

/* ===== Вкладки и модальные окна ===== */
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

document.querySelectorAll('[data-close]').forEach(el => {
  el.addEventListener('click', () => {
    const modal = el.closest('.modal');
    if (modal) closeModal(modal.id);
  });
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal:not([hidden])').forEach(m => closeModal(m.id));
  }
});

/* ===== Чат ===== */
const chatForm  = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatLog   = document.getElementById('chat-log');

chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;

  appendMessage('user', question);
  chatInput.value = '';

  const thinking = appendMessage('bot', 'Думаю…');

  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, text: getPlainText() })
    });
    const data = await response.json();
    thinking.textContent = data.answer || 'Не удалось получить ответ.';
  } catch {
    thinking.textContent = 'Ошибка связи с моделью. Попробуйте позже.';
  }
});

function appendMessage(role, text) {
  const div = document.createElement('div');
  div.className = `chat__msg chat__msg--${role}`;
  div.textContent = text;
  chatLog.appendChild(div);
  chatLog.scrollTop = chatLog.scrollHeight;
  return div;
}

/* ===== Инициализация ===== */
updateCharCount();
btnCopy.disabled = true;