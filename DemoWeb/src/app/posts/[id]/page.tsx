import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Pencil } from "lucide-react";

import { CommentSection } from "@/components/comment-section";
import { DeletePostButton } from "@/components/delete-post-button";
import { ViewCounter } from "@/components/view-counter";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { getPost } from "@/lib/db";
import { formatDateTime } from "@/lib/utils";

export const dynamic = "force-dynamic";

type Params = Promise<{ id: string }>;

async function loadPost(params: Params) {
  const { id } = await params;
  const postId = Number(id);
  if (!Number.isInteger(postId)) notFound();
  const post = await getPost(postId);
  if (!post) notFound();
  return post;
}

export async function generateMetadata({ params }: { params: Params }): Promise<Metadata> {
  const post = await loadPost(params);
  return { title: post.title };
}

export default async function PostPage({ params }: { params: Params }) {
  const post = await loadPost(params);
  const edited = post.updatedAt !== post.createdAt;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader className="border-b">
          <CardTitle className="text-xl leading-snug break-words sm:text-2xl">{post.title}</CardTitle>
          <div className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="text-foreground font-medium">{post.author}</span>
            <span>{formatDateTime(post.createdAt)}</span>
            {edited && <span>(수정됨 {formatDateTime(post.updatedAt)})</span>}
            <ViewCounter postId={post.id} initialViews={post.views} />
          </div>
        </CardHeader>
        <CardContent>
          <div className="min-h-32 leading-7 break-words whitespace-pre-wrap">{post.content}</div>
        </CardContent>
        <CardFooter className="justify-between gap-2 border-t">
          <Button asChild variant="outline" size="sm">
            <Link href="/">
              <ArrowLeft />
              목록
            </Link>
          </Button>
          <div className="flex gap-2">
            <Button asChild variant="secondary" size="sm">
              <Link href={`/posts/${post.id}/edit`}>
                <Pencil />
                수정
              </Link>
            </Button>
            <DeletePostButton id={post.id} title={post.title} />
          </div>
        </CardFooter>
      </Card>

      <CommentSection postId={post.id} comments={post.comments} />
    </div>
  );
}
