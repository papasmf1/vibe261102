export const MAX_LENGTH = 100;

export function newId() {
  if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

const normalize = (text) => String(text ?? '').trim().slice(0, MAX_LENGTH);

const nextOrder = (todos) => todos.reduce((max, t) => Math.max(max, t.order), 0) + 1;

function mapTodo(state, id, fn) {
  return { ...state, todos: state.todos.map((t) => (t.id === id ? fn(t) : t)) };
}

// 순수 함수: (state, action) → 새 state. 변경이 없으면 같은 state를 그대로 반환한다.
export function reducer(state, action) {
  switch (action.type) {
    case 'ADD_TODO': {
      const text = normalize(action.text);
      if (!text) return state;
      const todo = {
        id: action.id,
        text,
        done: false,
        important: false,
        date: action.today,
        createdAt: Date.now(),
        order: nextOrder(state.todos),
      };
      return { ...state, todos: [...state.todos, todo] };
    }

    case 'TOGGLE_TODO':
      return mapTodo(state, action.id, (t) => {
        if (t.done) {
          const { completedAt, ...rest } = t;
          return { ...rest, done: false };
        }
        return { ...t, done: true, completedAt: Date.now() };
      });

    case 'EDIT_TODO': {
      const text = normalize(action.text);
      const current = state.todos.find((t) => t.id === action.id);
      if (!text || !current || current.text === text) return state;
      return mapTodo(state, action.id, (t) => ({ ...t, text }));
    }

    case 'DELETE_TODO':
      if (!state.todos.some((t) => t.id === action.id)) return state;
      return { ...state, todos: state.todos.filter((t) => t.id !== action.id) };

    case 'RESTORE_TODO':
      if (state.todos.some((t) => t.id === action.todo.id)) return state;
      return { ...state, todos: [...state.todos, action.todo] };

    case 'CLEAR_DONE': {
      const todos = state.todos.filter((t) => !(t.done && t.date === action.today));
      return todos.length === state.todos.length ? state : { ...state, todos };
    }

    case 'TOGGLE_IMPORTANT':
      return mapTodo(state, action.id, (t) => ({ ...t, important: !t.important }));

    case 'CARRY_OVER': {
      if (pendingPast(state, action.today).length === 0) return state;
      return {
        ...state,
        todos: state.todos.map((t) =>
          !t.done && t.date < action.today
            ? { ...t, date: action.today, carriedFrom: t.carriedFrom ?? t.date }
            : t,
        ),
      };
    }

    case 'DISMISS_CARRY':
      return { ...state, carryDismissedDate: action.today };

    case 'SET_FILTER':
      if (state.settings.filter === action.filter) return state;
      return { ...state, settings: { ...state.settings, filter: action.filter } };

    case 'SET_THEME':
      if (state.settings.theme === action.theme) return state;
      return { ...state, settings: { ...state.settings, theme: action.theme } };

    default:
      return state;
  }
}

// 선택자
export const todayTodos = (state, today) => state.todos.filter((t) => t.date === today);

export const pendingPast = (state, today) => state.todos.filter((t) => !t.done && t.date < today);

// 중요(★) 우선 → 미완료 우선 → order 오름차순
export function sortTodos(todos) {
  return [...todos].sort(
    (a, b) =>
      Number(b.important) - Number(a.important) ||
      Number(a.done) - Number(b.done) ||
      a.order - b.order,
  );
}

export function visibleTodos(state, today) {
  const { filter } = state.settings;
  const todos = todayTodos(state, today).filter((t) =>
    filter === 'active' ? !t.done : filter === 'done' ? t.done : true,
  );
  return sortTodos(todos);
}

// 마지막으로 삭제한 항목 하나를 기억해 UNDO_DELETE로 복원할 수 있게 한다.
export function createStore(initial, listener) {
  let state = initial;
  let lastDeleted = null;

  function dispatch(action) {
    if (action.type === 'DELETE_TODO') {
      lastDeleted = state.todos.find((t) => t.id === action.id) ?? null;
    } else if (action.type === 'UNDO_DELETE') {
      if (!lastDeleted) return;
      action = { type: 'RESTORE_TODO', todo: lastDeleted };
      lastDeleted = null;
    }
    const next = reducer(state, action);
    if (next !== state) {
      state = next;
      listener(state);
    }
  }

  return { getState: () => state, dispatch };
}
