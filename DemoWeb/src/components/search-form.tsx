import Link from "next/link";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { SearchField } from "@/lib/types";

export function SearchForm({ query, field }: { query: string; field: SearchField }) {
  return (
    <form action="/" className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row" role="search">
      <select
        name="field"
        defaultValue={field}
        aria-label="검색 대상"
        className="border-input dark:bg-input/30 focus-visible:border-ring focus-visible:ring-ring/50 h-9 rounded-md border bg-transparent px-3 text-sm shadow-xs outline-none focus-visible:ring-[3px]"
      >
        <option value="all">제목+내용</option>
        <option value="title">제목</option>
        <option value="content">내용</option>
      </select>
      <div className="flex gap-2">
        <Input name="q" defaultValue={query} placeholder="검색어를 입력하세요" className="sm:w-56" aria-label="검색어" />
        <Button type="submit" variant="secondary">
          <Search />
          검색
        </Button>
        {query && (
          <Button asChild variant="ghost">
            <Link href="/">초기화</Link>
          </Button>
        )}
      </div>
    </form>
  );
}
