import type { BoardData, Post } from "./types";

const featured: Array<Pick<Post, "title" | "author" | "content">> = [
  {
    title: "DemoWeb 게시판에 오신 것을 환영합니다",
    author: "관리자",
    content:
      "Next.js App Router와 shadcn/ui로 만든 데모 게시판입니다.\n\n글쓰기, 수정, 삭제, 댓글 기능을 자유롭게 사용해 보세요. 데이터는 data/board.json 파일에 저장됩니다.",
  },
  {
    title: "Server Actions로 폼 처리하기",
    author: "김개발",
    content:
      "이 게시판의 글쓰기와 댓글은 모두 Server Actions로 처리됩니다. 별도 API 라우트 없이 form의 action 속성에 서버 함수를 연결하면 됩니다.",
  },
  {
    title: "다크 모드 지원 방법",
    author: "이디자인",
    content: "상단 오른쪽의 테마 버튼으로 라이트/다크/시스템 모드를 바꿀 수 있습니다. next-themes를 사용했습니다.",
  },
  {
    title: "Tailwind CSS v4 사용 후기",
    author: "박프론트",
    content: "설정 파일 없이 CSS 안에서 @theme로 디자인 토큰을 정의할 수 있어서 편했습니다.",
  },
  {
    title: "검색 기능 테스트용 글",
    author: "최테스트",
    content: "목록 상단의 검색창에서 제목이나 내용으로 검색할 수 있습니다. 이 글은 '검색'이라는 단어로 찾아보세요.",
  },
];

const topics = ["React", "TypeScript", "CSS", "접근성", "성능 최적화", "배포", "테스트", "상태 관리"];
const authors = ["김개발", "이디자인", "박프론트", "최테스트", "정백엔드"];

export function createSeedData(): BoardData {
  const now = Date.now();
  const hour = 60 * 60 * 1000;
  const posts: Post[] = [];

  const generatedCount = 20;
  for (let i = 0; i < generatedCount; i++) {
    const topic = topics[i % topics.length];
    posts.push({
      id: 0,
      title: `${topic} 관련 질문 있습니다 #${i + 1}`,
      author: authors[i % authors.length],
      content: `${topic}에 대해 공부하다가 궁금한 점이 생겨서 글을 남깁니다.\n\n경험 있으신 분들의 조언 부탁드립니다.`,
      views: 0,
      createdAt: "",
      updatedAt: "",
      comments: [],
    });
  }

  for (const item of featured.slice().reverse()) {
    posts.push({ ...item, id: 0, views: 0, createdAt: "", updatedAt: "", comments: [] });
  }

  // 오래된 글부터 id와 작성 시각을 부여한다.
  posts.forEach((post, index) => {
    const created = new Date(now - (posts.length - index) * 7 * hour).toISOString();
    post.id = index + 1;
    post.createdAt = created;
    post.updatedAt = created;
    post.views = ((index * 37) % 120) + 3;
  });

  let commentId = 1;
  const welcome = posts[posts.length - 1];
  welcome.comments.push(
    { id: commentId++, author: "김개발", content: "깔끔하네요! 잘 쓰겠습니다.", createdAt: new Date(now - 2 * hour).toISOString() },
    { id: commentId++, author: "이디자인", content: "다크 모드도 예쁘네요 👍", createdAt: new Date(now - hour).toISOString() }
  );
  posts[posts.length - 2].comments.push({
    id: commentId++,
    author: "정백엔드",
    content: "revalidatePath로 캐시를 갱신하는 부분이 핵심이군요.",
    createdAt: new Date(now - 3 * hour).toISOString(),
  });

  return {
    nextPostId: posts.length + 1,
    nextCommentId: commentId,
    posts: posts.reverse(),
  };
}
