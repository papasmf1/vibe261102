# DemoWeb 게시판

Next.js(App Router) + TypeScript + shadcn/ui(Tailwind CSS v4)로 만든 기본 게시판 데모입니다.

## 기능

- 게시글 목록: 번호, 제목(댓글 수), 작성자, 작성일, 조회수 / 페이지당 10개 페이지네이션
- 검색: 제목+내용, 제목, 내용 중 선택해서 검색 (`/?q=검색어&field=all|title|content`)
- 게시글 상세 보기: 열 때마다 조회수 1 증가
- 글쓰기 / 수정 / 삭제 (삭제 전 확인 대화상자)
- 댓글 작성·목록·삭제 (삭제 전 확인 대화상자)
- 반응형 레이아웃 (넓은 화면은 표, 좁은 화면은 카드형 목록)
- 라이트 / 다크 / 시스템 테마 (`next-themes`)

로그인 기능은 없으므로 누구나 글을 수정·삭제할 수 있습니다. (데모 용도)

## 실행

```bash
npm install
npm run dev      # http://localhost:3100
```

프로덕션 빌드:

```bash
npm run build
npm start        # http://localhost:3100
```

저장소 루트의 `.claude/launch.json`에 `demoweb` 설정(3100 포트)이 들어 있습니다.

## 데이터 저장 방식

별도 DB 없이 **로컬 JSON 파일**(`data/board.json`)에 저장합니다.

- 읽기: 서버 컴포넌트에서 `src/lib/db.ts`의 함수로 파일을 직접 읽습니다.
- 쓰기: 글쓰기·수정·삭제·댓글·조회수 증가는 모두 **Server Actions**(`src/lib/actions.ts`)로 처리하고, 끝나면 `revalidatePath`로 화면을 갱신합니다.
- 동시 요청이 파일을 동시에 덮어쓰지 않도록 쓰기 작업을 한 줄로 세워 실행하고, 임시 파일에 쓴 뒤 이름을 바꾸는 방식으로 저장합니다.
- `data/board.json`이 없으면 첫 요청 때 `src/lib/seed.ts`의 데모 게시글 25개(댓글 포함)로 자동 생성됩니다. **초기 상태로 되돌리려면 이 파일을 지우면 됩니다.**
- `data/board.json`은 `.gitignore`에 포함되어 커밋되지 않습니다.

> 파일 시스템에 쓰기 때문에 단일 서버(로컬 실행)용입니다. Vercel 같은 서버리스 환경에서는 저장이 유지되지 않습니다.

## 폴더 구조

```
src/
  app/
    page.tsx                 # 목록 + 검색 + 페이지네이션
    posts/new/page.tsx       # 글쓰기
    posts/[id]/page.tsx      # 상세 + 댓글
    posts/[id]/edit/page.tsx # 수정
  components/
    ui/                      # shadcn/ui 컴포넌트 (Button, Card, Input, Textarea, Table, Dialog, AlertDialog, Pagination 등)
    post-form.tsx, comment-section.tsx, delete-post-button.tsx, view-counter.tsx ...
  lib/
    db.ts                    # JSON 파일 저장소
    actions.ts               # Server Actions
    seed.ts                  # 시드 데이터
```
