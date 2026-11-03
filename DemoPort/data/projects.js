// 프로젝트 목록 — 항목을 추가/수정하면 Projects 섹션에 자동 반영됩니다.
// category: "python" | "web" | "ios"
// file://로 열어도 동작하도록 JSON 대신 JS 전역 변수로 둡니다.
window.PROJECTS = [
  {
    title: "업무 자동화 봇",
    category: "python",
    icon: "🤖",
    description: "엑셀 리포트 생성, 메일 발송, 파일 정리를 자동화한 Python 스크립트 모음.",
    tags: ["Python", "pandas", "openpyxl"],
    links: { github: "https://github.com/" }
  },
  {
    title: "REST API 서버",
    category: "python",
    icon: "⚡",
    description: "FastAPI 기반 인증·CRUD API 서버. 자동 문서화와 테스트 코드 포함.",
    tags: ["FastAPI", "PostgreSQL", "Docker"],
    links: { github: "https://github.com/", demo: "#" }
  },
  {
    title: "반응형 랜딩 페이지",
    category: "web",
    icon: "🎨",
    description: "HTML5 시맨틱 마크업과 CSS Grid로 구현한 접근성 높은 반응형 랜딩 페이지.",
    tags: ["HTML5", "CSS3", "JavaScript"],
    links: { github: "https://github.com/", demo: "#" }
  },
  {
    title: "Canvas 미니 게임",
    category: "web",
    icon: "🕹️",
    description: "HTML5 Canvas API로 만든 브라우저 아케이드 게임. 모바일 터치 지원.",
    tags: ["HTML5 Canvas", "JavaScript"],
    links: { github: "https://github.com/", demo: "#" }
  },
  {
    title: "습관 트래커 앱",
    category: "ios",
    icon: "✅",
    description: "SwiftUI와 SwiftData로 만든 습관 기록 앱. 위젯과 알림 기능 제공.",
    tags: ["Swift", "SwiftUI", "WidgetKit"],
    links: { github: "https://github.com/", appstore: "#" }
  },
  {
    title: "날씨 iOS 앱",
    category: "ios",
    icon: "🌤️",
    description: "공공 API를 연동한 날씨 앱. MVVM 구조와 async/await 네트워킹 적용.",
    tags: ["Swift", "UIKit", "MVVM"],
    links: { github: "https://github.com/", appstore: "#" }
  }
];
