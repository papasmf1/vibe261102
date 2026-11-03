"use client";

import { useActionState } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { FormState } from "@/lib/actions";

type Props = {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  defaultValues?: { title: string; author: string; content: string };
  submitLabel: string;
  cancelHref: string;
};

export function PostForm({ action, defaultValues, submitLabel, cancelHref }: Props) {
  const [state, formAction, pending] = useActionState(action, {});
  // 검증 실패 시 서버가 돌려준 값으로 입력란을 다시 채운다.
  const values = { ...defaultValues, ...state.values };

  return (
    <form action={formAction} className="flex flex-col gap-5">
      {state.message && <p className="text-destructive text-sm">{state.message}</p>}
      <div className="grid gap-2">
        <Label htmlFor="title">제목</Label>
        <Input
          id="title"
          name="title"
          defaultValue={values.title}
          maxLength={100}
          placeholder="제목을 입력하세요"
          aria-invalid={!!state.errors?.title}
        />
        {state.errors?.title && <p className="text-destructive text-sm">{state.errors.title}</p>}
      </div>
      <div className="grid gap-2">
        <Label htmlFor="author">작성자</Label>
        <Input
          id="author"
          name="author"
          defaultValue={values.author}
          maxLength={20}
          placeholder="이름"
          className="sm:max-w-xs"
          aria-invalid={!!state.errors?.author}
        />
        {state.errors?.author && <p className="text-destructive text-sm">{state.errors.author}</p>}
      </div>
      <div className="grid gap-2">
        <Label htmlFor="content">내용</Label>
        <Textarea
          id="content"
          name="content"
          defaultValue={values.content}
          maxLength={5000}
          placeholder="내용을 입력하세요"
          className="min-h-60"
          aria-invalid={!!state.errors?.content}
        />
        {state.errors?.content && <p className="text-destructive text-sm">{state.errors.content}</p>}
      </div>
      <div className="flex justify-end gap-2">
        <Button asChild variant="outline">
          <Link href={cancelHref}>취소</Link>
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? "저장 중..." : submitLabel}
        </Button>
      </div>
    </form>
  );
}
