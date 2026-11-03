"use client";

import { useActionState, useState, useTransition } from "react";
import { MessageSquare, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import { addCommentAction, deleteCommentAction, type FormState } from "@/lib/actions";
import type { Comment } from "@/lib/types";
import { formatDateTime } from "@/lib/utils";

function DeleteCommentButton({ postId, commentId }: { postId: number; commentId: number }) {
  const [open, setOpen] = useState(false);
  const [pending, startTransition] = useTransition();

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className="text-muted-foreground size-8" aria-label="댓글 삭제">
          <Trash2 />
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>댓글을 삭제할까요?</DialogTitle>
          <DialogDescription>삭제한 댓글은 되돌릴 수 없습니다.</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">취소</Button>
          </DialogClose>
          <Button
            variant="destructive"
            disabled={pending}
            onClick={() =>
              startTransition(async () => {
                await deleteCommentAction(postId, commentId);
                setOpen(false);
              })
            }
          >
            {pending ? "삭제 중..." : "삭제"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export function CommentSection({ postId, comments }: { postId: number; comments: Comment[] }) {
  const [state, formAction, pending] = useActionState<FormState, FormData>(addCommentAction.bind(null, postId), {});

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <MessageSquare className="size-4" />
          댓글 {comments.length}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {comments.length === 0 ? (
          <p className="text-muted-foreground text-sm">첫 댓글을 남겨 보세요.</p>
        ) : (
          <ul className="flex flex-col">
            {comments.map((comment, index) => (
              <li key={comment.id}>
                {index > 0 && <Separator className="my-3" />}
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-baseline gap-x-2 text-sm">
                      <span className="font-medium">{comment.author}</span>
                      <span className="text-muted-foreground text-xs">{formatDateTime(comment.createdAt)}</span>
                    </div>
                    <p className="mt-1 text-sm break-words whitespace-pre-wrap">{comment.content}</p>
                  </div>
                  <DeleteCommentButton postId={postId} commentId={comment.id} />
                </div>
              </li>
            ))}
          </ul>
        )}

        <Separator />

        {/* 제출 후 React가 폼을 defaultValue로 되돌리므로 작성자는 유지되고 내용은 비워진다. */}
        <form action={formAction} className="flex flex-col gap-2">
          {state.message && <p className="text-destructive text-sm">{state.message}</p>}
          <Input
            name="author"
            placeholder="작성자"
            maxLength={20}
            defaultValue={state.values?.author}
            className="sm:max-w-xs"
            aria-label="댓글 작성자"
            aria-invalid={!!state.errors?.author}
          />
          {state.errors?.author && <p className="text-destructive text-sm">{state.errors.author}</p>}
          <Textarea
            name="content"
            placeholder="댓글을 입력하세요"
            maxLength={5000}
            defaultValue={state.errors ? state.values?.content : undefined}
            aria-label="댓글 내용"
            aria-invalid={!!state.errors?.content}
          />
          {state.errors?.content && <p className="text-destructive text-sm">{state.errors.content}</p>}
          <div className="flex justify-end">
            <Button type="submit" disabled={pending}>
              {pending ? "등록 중..." : "댓글 등록"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
