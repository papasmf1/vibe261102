export type Comment = {
  id: number;
  author: string;
  content: string;
  createdAt: string;
};

export type Post = {
  id: number;
  title: string;
  author: string;
  content: string;
  views: number;
  createdAt: string;
  updatedAt: string;
  comments: Comment[];
};

export type BoardData = {
  nextPostId: number;
  nextCommentId: number;
  posts: Post[];
};

export type SearchField = "all" | "title" | "content";
