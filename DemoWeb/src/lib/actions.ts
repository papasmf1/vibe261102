"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import * as db from "./db";

export type FormState = {
  errors?: Partial<Record<"title" | "author" | "content", string>>;
  message?: string;
  values?: { title?: string; author?: string; content?: string };
};

const LIMITS = { title: 100, author: 20, content: 5000 } as const;
// 조사(을/를, 은/는)까지 붙인 표기
const LABELS = {
  title: { object: "제목을", topic: "제목은" },
  author: { object: "작성자를", topic: "작성자는" },
  content: { object: "내용을", topic: "내용은" },
} as const;

function readFields(formData: FormData, keys: Array<keyof typeof LIMITS>) {
  const values: Record<string, string> = {};
  const errors: FormState["errors"] = {};
  for (const key of keys) {
    const value = String(formData.get(key) ?? "").trim();
    values[key] = value;
    if (!value) errors[key] = `${LABELS[key].object} 입력해 주세요.`;
    else if (value.length > LIMITS[key]) errors[key] = `${LABELS[key].topic} ${LIMITS[key]}자 이하로 입력해 주세요.`;
  }
  return { values, errors };
}

export async function createPostAction(_prev: FormState, formData: FormData): Promise<FormState> {
  const { values, errors } = readFields(formData, ["title", "author", "content"]);
  if (Object.keys(errors).length) return { errors, values };

  const post = await db.createPost({ title: values.title, author: values.author, content: values.content });
  revalidatePath("/");
  redirect(`/posts/${post.id}`);
}

export async function updatePostAction(id: number, _prev: FormState, formData: FormData): Promise<FormState> {
  const { values, errors } = readFields(formData, ["title", "author", "content"]);
  if (Object.keys(errors).length) return { errors, values };

  const ok = await db.updatePost(id, { title: values.title, author: values.author, content: values.content });
  if (!ok) return { message: "게시글을 찾을 수 없습니다.", values };
  revalidatePath("/");
  revalidatePath(`/posts/${id}`);
  redirect(`/posts/${id}`);
}

export async function deletePostAction(id: number) {
  await db.deletePost(id);
  revalidatePath("/");
  redirect("/");
}

export async function recordViewAction(id: number) {
  const views = await db.incrementViews(id);
  revalidatePath("/");
  return views;
}

export async function addCommentAction(postId: number, _prev: FormState, formData: FormData): Promise<FormState> {
  const { values, errors } = readFields(formData, ["author", "content"]);
  if (Object.keys(errors).length) return { errors, values };

  const comment = await db.addComment(postId, { author: values.author, content: values.content });
  if (!comment) return { message: "게시글을 찾을 수 없습니다.", values };
  revalidatePath(`/posts/${postId}`);
  revalidatePath("/");
  // 작성자 이름은 다음 댓글을 위해 남겨 둔다.
  return { values: { author: values.author } };
}

export async function deleteCommentAction(postId: number, commentId: number) {
  await db.deleteComment(postId, commentId);
  revalidatePath(`/posts/${postId}`);
  revalidatePath("/");
}
