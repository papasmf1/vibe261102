const KEY = 'todolist:v1';
const CORRUPT_KEY = `${KEY}:corrupt`;

export const THEMES = ['system', 'light', 'dark'];
export const FILTERS = ['all', 'active', 'done'];

export function createDefault() {
  return {
    version: 1,
    todos: [],
    settings: { theme: 'system', filter: 'all' },
    carryDismissedDate: null,
  };
}

const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

function isValidTodo(t) {
  return (
    t !== null &&
    typeof t === 'object' &&
    typeof t.id === 'string' &&
    typeof t.text === 'string' &&
    typeof t.done === 'boolean' &&
    typeof t.important === 'boolean' &&
    typeof t.date === 'string' && DATE_RE.test(t.date) &&
    typeof t.createdAt === 'number' &&
    typeof t.order === 'number' &&
    (t.completedAt === undefined || typeof t.completedAt === 'number') &&
    (t.carriedFrom === undefined || (typeof t.carriedFrom === 'string' && DATE_RE.test(t.carriedFrom)))
  );
}

function validate(parsed) {
  if (!parsed || parsed.version !== 1 || !Array.isArray(parsed.todos)) return null;
  if (!parsed.todos.every(isValidTodo)) return null;
  const settings = parsed.settings ?? {};
  return {
    version: 1,
    todos: parsed.todos,
    settings: {
      theme: THEMES.includes(settings.theme) ? settings.theme : 'system',
      filter: FILTERS.includes(settings.filter) ? settings.filter : 'all',
    },
    carryDismissedDate: typeof parsed.carryDismissedDate === 'string' ? parsed.carryDismissedDate : null,
  };
}

// error: null | 'unavailable' (저장소 접근 불가) | 'corrupt' (손상 데이터, 백업 후 초기화)
export function load() {
  let raw;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    return { data: createDefault(), error: 'unavailable' };
  }
  if (raw === null) return { data: createDefault(), error: null };

  try {
    const data = validate(JSON.parse(raw));
    if (data) return { data, error: null };
  } catch {
    // JSON 파싱 실패 → 아래에서 손상 데이터로 처리
  }

  try {
    localStorage.setItem(CORRUPT_KEY, raw);
    localStorage.removeItem(KEY);
  } catch {
    // 백업 실패는 무시하고 빈 상태로 시작
  }
  return { data: createDefault(), error: 'corrupt' };
}

export function save(data) {
  try {
    localStorage.setItem(KEY, JSON.stringify(data));
    return true;
  } catch {
    return false;
  }
}
