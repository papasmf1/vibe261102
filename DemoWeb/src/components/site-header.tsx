import Link from "next/link";
import { MessagesSquare, PenSquare } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ModeToggle } from "@/components/mode-toggle";

export function SiteHeader() {
  return (
    <header className="bg-background/80 sticky top-0 z-40 border-b backdrop-blur">
      <div className="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <MessagesSquare className="size-5" />
          <span>DemoWeb 게시판</span>
        </Link>
        <div className="flex items-center gap-2">
          <Button asChild size="sm">
            <Link href="/posts/new">
              <PenSquare />
              <span className="hidden sm:inline">글쓰기</span>
            </Link>
          </Button>
          <ModeToggle />
        </div>
      </div>
    </header>
  );
}
