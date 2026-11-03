import "server-only";

import { neon } from "@neondatabase/serverless";

import { createSeedData } from "./seed";
import type { Comment, Post, SearchField } from "./types";

// 배포 환경 변수에 .env 형식 그대로 따옴표까지 붙여 넣는 경우가 있어 앞뒤 공백과 따옴표를 걷어 낸다.
const databaseUrl = process.env.DATABASE_URL?.trim().replace(/^(["'])(.*)\1$/, "$2");

if (!databaseUrl) {
  throw new Error("DATABASE_URL 환경 변수가 없습니다. .env.local에 Neon 접속 문자열을 넣어 주세요.");
}

const sql = neon(databaseUrl);

export const PAGE_SIZE = 10;

type PostRow = {
  id: number;
  title: string;
  author: string;
  content: string;
  views: number;
  created_at: Date | string;
  updated_at: Date | string;
};

type CommentRow = {
  id: number;
  post_id: number;
  author: string;
  content: string;
  created_at: Date | string;
};

const toIso = (value: Date | string) => new Date(value).toISOString();

const toComment = (row: CommentRow): Comment => ({
  id: row.id,
  author: row.author,
  content: row.content,
  createdAt: toIso(row.created_at),
});

// 첫 요청 때 테이블을 만들고, 비어 있으면 시드 데이터를 넣는다. 프로세스당 한 번만 실행된다.
let ready: Promise<void> | null = null;

function ensureSchema() {
  ready ??= initSchema().catch((error) => {
    ready = null;
    throw error;
  });
  return ready;
}

async function initSchema() {
  await sql.transaction([
    sql`CREATE TABLE IF NOT EXISTS posts (
      id SERIAL PRIMARY KEY,
      title VARCHAR(100) NOT NULL,
      author VARCHAR(20) NOT NULL,
      content TEXT NOT NULL,
      views INTEGER NOT NULL DEFAULT 0,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
      updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )`,
    sql`CREATE TABLE IF NOT EXISTS comments (
      id SERIAL PRIMARY KEY,
      post_id INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
      author VARCHAR(20) NOT NULL,
      content TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )`,
    sql`CREATE INDEX IF NOT EXISTS comments_post_id_idx ON comments(post_id)`,
  ]);

  const [{ count }] = (await sql`SELECT count(*)::int AS count FROM posts`) as Array<{ count: number }>;
  if (count === 0) await seed();
}

async function seed() {
  const data = createSeedData();
  const posts = data.posts;
  const comments = posts.flatMap((post) => post.comments.map((c) => ({ ...c, postId: post.id })));

  // id를 직접 넣으므로 ON CONFLICT로 동시에 시드가 실행돼도 중복되지 않게 하고, 끝나면 시퀀스를 맞춘다.
  await sql.transaction([
    sql`INSERT INTO posts (id, title, author, content, views, created_at, updated_at)
      SELECT * FROM jsonb_to_recordset(${JSON.stringify(posts)}::jsonb)
        AS p(id int, title text, author text, content text, views int, "createdAt" timestamptz, "updatedAt" timestamptz)
      ON CONFLICT (id) DO NOTHING`,
    sql`INSERT INTO comments (id, post_id, author, content, created_at)
      SELECT * FROM jsonb_to_recordset(${JSON.stringify(comments)}::jsonb)
        AS c(id int, "postId" int, author text, content text, "createdAt" timestamptz)
      ON CONFLICT (id) DO NOTHING`,
    sql`SELECT setval(pg_get_serial_sequence('posts', 'id'), (SELECT max(id) FROM posts))`,
    sql`SELECT setval(pg_get_serial_sequence('comments', 'id'), (SELECT max(id) FROM comments))`,
  ]);
}

export type PostSummary = Omit<Post, "content" | "comments"> & { commentCount: number };

export async function listPosts({
  query = "",
  field = "all",
  page = 1,
}: {
  query?: string;
  field?: SearchField;
  page?: number;
}) {
  await ensureSchema();
  const q = query.trim();
  // LIKE 특수문자(%, _, \)는 글자 그대로 검색되도록 이스케이프한다.
  const pattern = `%${q.replace(/[\\%_]/g, "\\$&")}%`;
  const where = `
    $1 = ''
    OR ($2 IN ('all', 'title') AND title ILIKE $3)
    OR ($2 IN ('all', 'content') AND content ILIKE $3)`;

  const [{ total }] = (await sql.query(`SELECT count(*)::int AS total FROM posts WHERE ${where}`, [
    q,
    field,
    pattern,
  ])) as Array<{ total: number }>;

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.min(Math.max(1, page), totalPages);
  const start = (current - 1) * PAGE_SIZE;

  const rows = (await sql.query(
    `SELECT p.id, p.title, p.author, p.views, p.created_at, p.updated_at,
       (SELECT count(*)::int FROM comments c WHERE c.post_id = p.id) AS comment_count
     FROM posts p
     WHERE ${where}
     ORDER BY p.id DESC
     LIMIT $4 OFFSET $5`,
    [q, field, pattern, PAGE_SIZE, start]
  )) as Array<Omit<PostRow, "content"> & { comment_count: number }>;

  const posts: PostSummary[] = rows.map((row) => ({
    id: row.id,
    title: row.title,
    author: row.author,
    views: row.views,
    createdAt: toIso(row.created_at),
    updatedAt: toIso(row.updated_at),
    commentCount: row.comment_count,
  }));

  return { posts, total, page: current, totalPages, startIndex: start };
}

export async function getPost(id: number): Promise<Post | null> {
  await ensureSchema();
  const [postRows, commentRows] = await sql.transaction([
    sql`SELECT * FROM posts WHERE id = ${id}`,
    sql`SELECT * FROM comments WHERE post_id = ${id} ORDER BY id`,
  ]);
  const row = (postRows as PostRow[])[0];
  if (!row) return null;
  return {
    id: row.id,
    title: row.title,
    author: row.author,
    content: row.content,
    views: row.views,
    createdAt: toIso(row.created_at),
    updatedAt: toIso(row.updated_at),
    comments: (commentRows as CommentRow[]).map(toComment),
  };
}

export async function incrementViews(id: number): Promise<number | null> {
  await ensureSchema();
  const rows = (await sql`UPDATE posts SET views = views + 1 WHERE id = ${id} RETURNING views`) as Array<{
    views: number;
  }>;
  return rows[0]?.views ?? null;
}

export async function createPost(input: Pick<Post, "title" | "author" | "content">): Promise<Post> {
  await ensureSchema();
  const [row] = (await sql`
    INSERT INTO posts (title, author, content)
    VALUES (${input.title}, ${input.author}, ${input.content})
    RETURNING *`) as PostRow[];
  return {
    id: row.id,
    title: row.title,
    author: row.author,
    content: row.content,
    views: row.views,
    createdAt: toIso(row.created_at),
    updatedAt: toIso(row.updated_at),
    comments: [],
  };
}

export async function updatePost(id: number, input: Pick<Post, "title" | "author" | "content">): Promise<boolean> {
  await ensureSchema();
  const rows = await sql`
    UPDATE posts
    SET title = ${input.title}, author = ${input.author}, content = ${input.content}, updated_at = now()
    WHERE id = ${id}
    RETURNING id`;
  return rows.length > 0;
}

export async function deletePost(id: number): Promise<boolean> {
  await ensureSchema();
  const rows = await sql`DELETE FROM posts WHERE id = ${id} RETURNING id`;
  return rows.length > 0;
}

export async function addComment(postId: number, input: Pick<Comment, "author" | "content">): Promise<Comment | null> {
  await ensureSchema();
  const rows = (await sql`
    INSERT INTO comments (post_id, author, content)
    SELECT id, ${input.author}, ${input.content} FROM posts WHERE id = ${postId}
    RETURNING *`) as CommentRow[];
  return rows[0] ? toComment(rows[0]) : null;
}

export async function deleteComment(postId: number, commentId: number): Promise<boolean> {
  await ensureSchema();
  const rows = await sql`DELETE FROM comments WHERE id = ${commentId} AND post_id = ${postId} RETURNING id`;
  return rows.length > 0;
}
