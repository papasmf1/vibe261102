import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PostForm } from "@/components/post-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { updatePostAction } from "@/lib/actions";
import { getPost } from "@/lib/db";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "글 수정" };

export default async function EditPostPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const postId = Number(id);
  const post = Number.isInteger(postId) ? await getPost(postId) : null;
  if (!post) notFound();

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">글 수정</CardTitle>
      </CardHeader>
      <CardContent>
        <PostForm
          action={updatePostAction.bind(null, post.id)}
          defaultValues={{ title: post.title, author: post.author, content: post.content }}
          submitLabel="수정 완료"
          cancelHref={`/posts/${post.id}`}
        />
      </CardContent>
    </Card>
  );
}
