import { formatLong, formatShort } from './date.js';
import { MAX_LENGTH, todayTodos, pendingPast, visibleTodos } from './store.js';

const $ = (selector) => document.querySelector(selector);

export const els = {
  date: $('#today-date'),
  themeToggle: $('#theme-toggle'),
  notice: $('#storage-notice'),
  carryBanner: $('#carry-banner'),
  carryText: $('#carry-text'),
  carryAccept: $('#carry-accept'),
  carryDismiss: $('#carry-dismiss'),
  addForm: $('#add-form'),
  input: $('#new-todo'),
  progressCount: $('#progress-count'),
  progressPercent: $('#progress-percent'),
  progressBar: $('#progress-bar'),
  progressFill: $('#progress-fill'),
  filters: $('#filters'),
  celebrate: $('#celebrate'),
  list: $('#todo-list'),
  empty: $('#empty'),
  clearDone: $('#clear-done'),
  toast: $('#toast'),
  undo: $('#undo'),
};

const EMPTY_TEXT = {
  all: '오늘 할 일을 추가해 보세요',
  active: '진행 중인 할 일이 없어요',
  done: '아직 완료한 할 일이 없어요',
};

function el(tag, props = {}) {
  return Object.assign(document.createElement(tag), props);
}

// 사용자 입력은 항상 textContent/value로만 넣는다 (XSS 방지)
function renderItem(todo, ctx) {
  const li = el('li', { className: 'todo', tabIndex: 0 });
  li.dataset.id = todo.id;
  li.classList.toggle('done', todo.done);
  li.classList.toggle('important', todo.important);
  li.classList.toggle('enter', ctx.enteringId === todo.id);

  const check = el('input', { type: 'checkbox', className: 'check', checked: todo.done });
  check.setAttribute('aria-label', `${todo.text} 완료`);

  const star = el('button', { type: 'button', className: 'star', textContent: '★', title: '중요 표시' });
  star.setAttribute('aria-label', '중요 표시');
  star.setAttribute('aria-pressed', String(todo.important));

  const body =
    ctx.editingId === todo.id
      ? el('input', { type: 'text', className: 'edit', value: todo.text, maxLength: MAX_LENGTH })
      : el('span', { className: 'text', textContent: todo.text, title: '더블클릭하여 수정' });
  if (ctx.editingId === todo.id) body.setAttribute('aria-label', '할 일 수정');

  li.append(check, star, body);

  if (todo.carriedFrom) {
    li.append(el('span', { className: 'tag', textContent: `${formatShort(todo.carriedFrom)}에서 이월` }));
  }

  const del = el('button', { type: 'button', className: 'delete', textContent: '×', title: '삭제' });
  del.setAttribute('aria-label', `${todo.text} 삭제`);
  li.append(del);

  return li;
}

export function render(state, ctx) {
  const { today } = ctx;
  const { filter } = state.settings;

  els.date.textContent = formatLong(today);

  // 진행률
  const todays = todayTodos(state, today);
  const total = todays.length;
  const doneCount = todays.filter((t) => t.done).length;
  const percent = total ? Math.round((doneCount / total) * 100) : 0;
  els.progressCount.textContent = `${doneCount} / ${total} 완료`;
  els.progressPercent.textContent = `${percent}%`;
  els.progressFill.style.width = `${percent}%`;
  els.progressBar.setAttribute('aria-valuenow', String(percent));
  els.celebrate.hidden = !(total > 0 && doneCount === total);

  // 필터 탭
  for (const button of els.filters.querySelectorAll('button')) {
    button.setAttribute('aria-pressed', String(button.dataset.filter === filter));
  }

  // 목록 · 빈 상태
  const items = visibleTodos(state, today);
  els.list.replaceChildren(...items.map((todo) => renderItem(todo, ctx)));
  els.empty.hidden = items.length > 0;
  els.empty.textContent = total === 0 ? EMPTY_TEXT.all : EMPTY_TEXT[filter];
  els.clearDone.hidden = doneCount === 0;

  // 미완료 이월 배너
  const past = pendingPast(state, today);
  els.carryBanner.hidden = past.length === 0 || state.carryDismissedDate === today;
  els.carryText.textContent = `지난 날 끝내지 못한 일 ${past.length}개가 있어요`;
}

export function renderTheme(isDark) {
  els.themeToggle.textContent = isDark ? '☀️' : '🌙';
  els.themeToggle.setAttribute('aria-label', isDark ? '라이트 모드로 전환' : '다크 모드로 전환');
}

export function renderNotice(message) {
  els.notice.hidden = !message;
  els.notice.textContent = message ?? '';
}
