import { todayKey } from './date.js';
import { load, save } from './storage.js';
import { createStore, newId } from './store.js';
import { els, render, renderTheme, renderNotice } from './view.js';

const TOAST_MS = 5000;
const LEAVE_MS = 160;

const NOTICES = {
  unavailable: '브라우저 저장소를 사용할 수 없어, 새로고침하면 할 일이 사라집니다.',
  corrupt: '저장된 데이터를 읽을 수 없어 새 목록으로 시작합니다. (이전 데이터는 백업해 두었습니다)',
};

const loaded = load();
let storageError = loaded.error;
let today = todayKey();

// 저장하지 않는 화면 상태
const ui = {
  editingId: null,
  enteringId: null,
  focusAfter: null, // { id, cls } | { input: true }
};

const store = createStore(loaded.data, (state) => {
  if (!save(state)) storageError = 'unavailable';
  update();
});
const dispatch = (action) => store.dispatch({ ...action, today });

const darkQuery = matchMedia('(prefers-color-scheme: dark)');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

function isDark(theme) {
  return theme === 'dark' || (theme === 'system' && darkQuery.matches);
}

function applyTheme(theme) {
  if (theme === 'system') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  renderTheme(isDark(theme));
}

// 다시 그리면 목록 DOM이 새로 만들어지므로, 포커스 위치를 기억했다가 되돌린다.
function captureFocus() {
  const active = document.activeElement;
  const li = active?.closest?.('li.todo');
  if (!li) return null;
  return { id: li.dataset.id, cls: active === li ? null : active.classList[0] };
}

function restoreFocus(focus) {
  if (!focus) return;
  if (focus.input) {
    els.input.focus();
    return;
  }
  const li = els.list.querySelector(`li[data-id="${CSS.escape(focus.id)}"]`);
  if (!li) return;
  const target = focus.cls ? li.querySelector(`.${focus.cls}`) : null;
  (target ?? li).focus();
}

function update() {
  const state = store.getState();
  const focus = ui.focusAfter ?? captureFocus();
  ui.focusAfter = null;

  render(state, { today, editingId: ui.editingId, enteringId: ui.enteringId });
  ui.enteringId = null;
  applyTheme(state.settings.theme);
  renderNotice(storageError ? NOTICES[storageError] : null);
  restoreFocus(focus);
}

// 토스트
let toastTimer = null;
function showToast() {
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(hideToast, TOAST_MS);
}
function hideToast() {
  clearTimeout(toastTimer);
  els.toast.hidden = true;
}

// 동작
function findTodo(id) {
  return store.getState().todos.find((t) => t.id === id);
}

function removeTodo(id) {
  const li = els.list.querySelector(`li[data-id="${CSS.escape(id)}"]`);
  if (li?.classList.contains('leaving')) return;

  // 삭제 후 포커스를 옆 항목으로 옮긴다
  let focusAfter = null;
  if (li && li.contains(document.activeElement)) {
    const sibling = li.nextElementSibling ?? li.previousElementSibling;
    focusAfter = sibling ? { id: sibling.dataset.id, cls: null } : { input: true };
  }

  const finish = () => {
    ui.focusAfter = focusAfter;
    if (ui.editingId === id) ui.editingId = null;
    dispatch({ type: 'DELETE_TODO', id });
    showToast();
  };

  if (li && !reducedMotion.matches) {
    li.classList.add('leaving');
    setTimeout(finish, LEAVE_MS);
  } else {
    finish();
  }
}

function startEdit(id) {
  ui.editingId = id;
  update();
  const input = els.list.querySelector('.edit');
  input?.focus();
  input?.select();
}

function commitEdit(id, value) {
  if (ui.editingId !== id) return; // Enter 후 blur로 한 번 더 들어오는 경우
  ui.editingId = null;
  if (!value.trim()) {
    removeTodo(id);
    return;
  }
  const before = store.getState();
  dispatch({ type: 'EDIT_TODO', id, text: value });
  if (store.getState() === before) update();
}

function cancelEdit(id) {
  ui.editingId = null;
  ui.focusAfter = { id, cls: null };
  update();
}

// 이벤트 바인딩
els.addForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const id = newId();
  ui.enteringId = id;
  const before = store.getState();
  dispatch({ type: 'ADD_TODO', id, text: els.input.value });
  if (store.getState() !== before) els.input.value = '';
  ui.enteringId = null;
  els.input.focus();
});

els.list.addEventListener('click', (e) => {
  const li = e.target.closest('li.todo');
  if (!li) return;
  if (e.target.closest('.delete')) removeTodo(li.dataset.id);
  else if (e.target.closest('.star')) dispatch({ type: 'TOGGLE_IMPORTANT', id: li.dataset.id });
});

els.list.addEventListener('change', (e) => {
  if (!e.target.matches('.check')) return;
  dispatch({ type: 'TOGGLE_TODO', id: e.target.closest('li.todo').dataset.id });
});

els.list.addEventListener('dblclick', (e) => {
  if (!e.target.matches('.text')) return;
  startEdit(e.target.closest('li.todo').dataset.id);
});

els.list.addEventListener('keydown', (e) => {
  const li = e.target.closest('li.todo');
  if (!li) return;
  const { id } = li.dataset;

  if (e.target.matches('.edit')) {
    if (e.isComposing) return; // 한글 조합 중 Enter 무시
    if (e.key === 'Enter') {
      e.preventDefault();
      ui.focusAfter = { id, cls: null };
      commitEdit(id, e.target.value);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      cancelEdit(id);
    }
    return;
  }

  if (e.target !== li) return;
  if (e.key === ' ') {
    e.preventDefault();
    dispatch({ type: 'TOGGLE_TODO', id });
  } else if (e.key === 'Enter') {
    e.preventDefault();
    startEdit(id);
  } else if (e.key === 'Delete') {
    e.preventDefault();
    removeTodo(id);
  }
});

els.list.addEventListener('focusout', (e) => {
  if (!e.target.matches('.edit')) return;
  commitEdit(e.target.closest('li.todo').dataset.id, e.target.value);
});

els.filters.addEventListener('click', (e) => {
  const button = e.target.closest('button[data-filter]');
  if (button) dispatch({ type: 'SET_FILTER', filter: button.dataset.filter });
});

els.clearDone.addEventListener('click', () => dispatch({ type: 'CLEAR_DONE' }));
els.carryAccept.addEventListener('click', () => dispatch({ type: 'CARRY_OVER' }));
els.carryDismiss.addEventListener('click', () => dispatch({ type: 'DISMISS_CARRY' }));

els.undo.addEventListener('click', () => {
  hideToast();
  dispatch({ type: 'UNDO_DELETE' });
});

els.themeToggle.addEventListener('click', () => {
  const dark = isDark(store.getState().settings.theme);
  dispatch({ type: 'SET_THEME', theme: dark ? 'light' : 'dark' });
});
darkQuery.addEventListener('change', update);

// 전역 단축키: '/' 또는 'N' → 입력창 포커스
document.addEventListener('keydown', (e) => {
  if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return;
  const target = e.target;
  if (target.matches?.('input, textarea, select') || target.isContentEditable) return;
  if (e.key === '/' || e.code === 'KeyN') {
    e.preventDefault();
    els.input.focus();
  }
});

// 페이지를 켜 둔 채 자정이 지나면 날짜를 갱신한다
function checkDate() {
  const key = todayKey();
  if (key === today) return;
  today = key;
  ui.editingId = null;
  update();
}
setInterval(checkDate, 60_000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) checkDate();
});

update();
