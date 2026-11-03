import type { Metadata } from "next";

import { PostForm } from "@/components/post-form";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { createPostAction } from "@/lib/actions";

export const metadata: Metadata = { title: "글쓰기" };

export default function NewPostPage() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-xl">글쓰기</CardTitle>
      </CardHeader>
      <CardContent>
        <PostForm action={createPostAction} submitLabel="등록" cancelHref="/" />
      </CardContent>
    </Card>
  );
}
