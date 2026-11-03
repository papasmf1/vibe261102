"use client";

import { useEffect, useRef, useState } from "react";
import { Eye } from "lucide-react";

import { recordViewAction } from "@/lib/actions";

// 상세 페이지를 열 때 한 번만 조회수를 올린다. (개발 모드의 StrictMode 이중 실행도 ref로 막는다)
export function ViewCounter({ postId, initialViews }: { postId: number; initialViews: number }) {
  const [views, setViews] = useState(initialViews);
  const recorded = useRef(false);

  useEffect(() => {
    if (recorded.current) return;
    recorded.current = true;
    recordViewAction(postId).then((next) => {
      if (next !== null) setViews(next);
    });
  }, [postId]);

  return (
    <span className="inline-flex items-center gap-1">
      <Eye className="size-4" />
      조회 {Math.max(views, initialViews).toLocaleString("ko-KR")}
    </span>
  );
}
