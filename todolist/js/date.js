const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

const pad = (n) => String(n).padStart(2, '0');

// 로컬 시간 기준 'YYYY-MM-DD' (toISOString은 UTC라 자정 부근에 날짜가 어긋난다)
export function todayKey(date = new Date()) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function parseKey(key) {
  const [y, m, d] = key.split('-').map(Number);
  return { y, m, d, date: new Date(y, m - 1, d) };
}

// '2026년 11월 2일 (월)'
export function formatLong(key) {
  const { y, m, d, date } = parseKey(key);
  return `${y}년 ${m}월 ${d}일 (${WEEKDAYS[date.getDay()]})`;
}

// '11/2'
export function formatShort(key) {
  const { m, d } = parseKey(key);
  return `${m}/${d}`;
}
