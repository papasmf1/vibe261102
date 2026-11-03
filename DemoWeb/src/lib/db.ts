import "server-only";

import { promises as fs } from "fs";
import path from "path";

import { createSeedData } from "./seed";
import type { BoardData, Comment, Post, SearchField } from "./types";

const DATA_DIR = path.join(process.cwd(), "data");
const DATA_FILE = path.join(DATA_DIR, "board.json");

export const PAGE_SIZE = 10;

// 동시 요청이 파일을 동시에 덮어쓰지 않도록 쓰기 작업을 순서대로 실행한다.
let queue: Promise<unknown> = Promise.resolve();

function serialize<T>(task: () => Promise<T>): Promise<T> {
  const run = queue.then(task, task);
  queue = run.catch(() => undefined);
  return run;
}

async function readData(): Promise<BoardData> {
  try {
    const raw = await fs.readFile(DATA_FILE, "utf8");
    return JSON.parse(raw) as BoardData;
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    const seed = createSeedData();
    await writeData(seed);
    return seed;
  }
}

async function writeData(data: BoardData) {
  await fs.mkdir(DATA_DIR, { recursive: true });
  const tmp = `${DATA_FILE}.${process.pid}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(data, null, 2), "utf8");
  await fs.rename(tmp, DATA_FILE);
}

function mutate<T>(fn: (data: BoardData) => T): Promise<T> {
  return serialize(async () => {
    const data = await readData();
    const result = fn(data);
    await writeData(data);
    return result;
  });
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
  const data = await serialize(readData);
  const q = query.trim().toLowerCase();

  const filtered = q
    ? data.posts.filter((post) => {
        const inTitle = post.title.toLowerCase().includes(q);
        const inContent = post.content.toLowerCase().includes(q);
        if (field === "title") return inTitle;
        if (field === "content") return inContent;
        return inTitle || inContent;
      })
    : data.posts;

  const total = filtered.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const current = Math.min(Math.max(1, page), totalPages);
  const start = (current - 1) * PAGE_SIZE;

  const posts: PostSummary[] = filtered.slice(start, start + PAGE_SIZE).map((post) => ({
    id: post.id,
    title: post.title,
    author: post.author,
    views: post.views,
    createdAt: post.createdAt,
    updatedAt: post.updatedAt,
    commentCount: post.comments.length,
  }));

  return { posts, total, page: current, totalPages, startIndex: start };
}

export async function getPost(id: number): Promise<Post | null> {
  const data = await serialize(readData);
  return data.posts.find((post) => post.id === id) ?? null;
}

export function incrementViews(id: number): Promise<number | null> {
  return mutate((data) => {
    const post = data.posts.find((p) => p.id === id);
    if (!post) return null;
    post.views += 1;
    return post.views;
  });
}

export function createPost(input: Pick<Post, "title" | "author" | "content">): Promise<Post> {
  return mutate((data) => {
    const now = new Date().toISOString();
    const post: Post = {
      id: data.nextPostId++,
      ...input,
      views: 0,
      createdAt: now,
      updatedAt: now,
      comments: [],
    };
    data.posts.unshift(post);
    return post;
  });
}

export function updatePost(id: number, input: Pick<Post, "title" | "author" | "content">): Promise<boolean> {
  return mutate((data) => {
    const post = data.posts.find((p) => p.id === id);
    if (!post) return false;
    Object.assign(post, input, { updatedAt: new Date().toISOString() });
    return true;
  });
}

export function deletePost(id: number): Promise<boolean> {
  return mutate((data) => {
    const before = data.posts.length;
    data.posts = data.posts.filter((p) => p.id !== id);
    return data.posts.length !== before;
  });
}

export function addComment(postId: number, input: Pick<Comment, "author" | "content">): Promise<Comment | null> {
  return mutate((data) => {
    const post = data.posts.find((p) => p.id === postId);
    if (!post) return null;
    const comment: Comment = { id: data.nextCommentId++, ...input, createdAt: new Date().toISOString() };
    post.comments.push(comment);
    return comment;
  });
}

export function deleteComment(postId: number, commentId: number): Promise<boolean> {
  return mutate((data) => {
    const post = data.posts.find((p) => p.id === postId);
    if (!post) return false;
    const before = post.comments.length;
    post.comments = post.comments.filter((c) => c.id !== commentId);
    return post.comments.length !== before;
  });
}
