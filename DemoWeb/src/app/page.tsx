import Link from "next/link";
import { Eye } from "lucide-react";

import { BoardPagination } from "@/components/board-pagination";
import { SearchForm } from "@/components/search-form";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { listPosts } from "@/lib/db";
import type { SearchField } from "@/lib/types";
import { formatDate } from "@/lib/utils";

export const dynamic = "force-dynamic";

type SearchParams = Promise<{ q?: string; field?: string; page?: string }>;

function toField(value?: string): SearchField {
  return value === "title" || value === "content" ? value : "all";
}

export default async function HomePage({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const query = params.q?.trim() ?? "";
  const field = toField(params.field);
  const requestedPage = Number.parseInt(params.page ?? "1", 10) || 1;

  const { posts, total, page, totalPages, startIndex } = await listPosts({ query, field, page: requestedPage });

  return (
    <Card className="gap-4">
      <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="grid gap-1.5">
          <CardTitle className="text-xl">자유게시판</CardTitle>
          <CardDescription>
            {query ? `“${query}” 검색 결과 ${total}건` : `전체 ${total}개의 글`}
          </CardDescription>
        </div>
        <SearchForm query={query} field={field} />
      </CardHeader>
      <CardContent className="flex flex-col gap-6 px-0 sm:px-6">
        {posts.length === 0 ? (
          <p className="text-muted-foreground py-16 text-center text-sm">
            {query ? "검색 결과가 없습니다." : "아직 게시글이 없습니다. 첫 글을 작성해 보세요!"}
          </p>
        ) : (
          <>
            {/* 넓은 화면: 표 */}
            <Table className="hidden table-fixed md:table">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-16 text-center">번호</TableHead>
                  <TableHead>제목</TableHead>
                  <TableHead className="w-28">작성자</TableHead>
                  <TableHead className="w-28">작성일</TableHead>
                  <TableHead className="w-20 text-right">조회수</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {posts.map((post, i) => (
                  <TableRow key={post.id}>
                    <TableCell className="text-muted-foreground text-center">{total - startIndex - i}</TableCell>
                    <TableCell className="truncate">
                      <Link href={`/posts/${post.id}`} className="font-medium hover:underline">
                        {post.title}
                      </Link>
                      {post.commentCount > 0 && (
                        <Badge variant="secondary" className="ml-2 align-middle">
                          {post.commentCount}
                        </Badge>
                      )}
                    </TableCell>
                    <TableCell className="truncate">{post.author}</TableCell>
                    <TableCell className="text-muted-foreground">{formatDate(post.createdAt)}</TableCell>
                    <TableCell className="text-muted-foreground text-right">{post.views.toLocaleString("ko-KR")}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>

            {/* 좁은 화면: 목록 */}
            <ul className="divide-y border-y md:hidden">
              {posts.map((post) => (
                <li key={post.id}>
                  <Link href={`/posts/${post.id}`} className="hover:bg-muted/50 block px-6 py-3">
                    <div className="flex items-center gap-2">
                      <span className="truncate font-medium">{post.title}</span>
                      {post.commentCount > 0 && <Badge variant="secondary">{post.commentCount}</Badge>}
                    </div>
                    <div className="text-muted-foreground mt-1 flex items-center gap-2 text-xs">
                      <span>{post.author}</span>
                      <span>·</span>
                      <span>{formatDate(post.createdAt)}</span>
                      <span>·</span>
                      <span className="inline-flex items-center gap-1">
                        <Eye className="size-3" />
                        {post.views.toLocaleString("ko-KR")}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          </>
        )}
        <BoardPagination page={page} totalPages={totalPages} query={query} field={field} />
      </CardContent>
    </Card>
  );
}
