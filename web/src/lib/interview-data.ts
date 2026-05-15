export interface InterviewMeta {
  slug: string;
  title: string;
  category: "basic" | "deep";
  questionCount: string;
}

export const INTERVIEWS: InterviewMeta[] = [
  { slug: "01", title: "项目介绍话术", category: "basic", questionCount: "3 版本" },
  { slug: "02", title: "推荐系统基础面试题", category: "basic", questionCount: "15 题" },
  { slug: "03", title: "Transformer与深度学习面试题", category: "basic", questionCount: "20 题" },
  { slug: "04", title: "系统设计与Rust工程面试题", category: "basic", questionCount: "20 题" },
  { slug: "05", title: "综合追问与深挖题", category: "basic", questionCount: "15 题" },
  { slug: "06", title: "Transformer注意力机制深度拷问30题", category: "deep", questionCount: "30 题" },
  { slug: "07", title: "推荐系统排序模型面试50题", category: "deep", questionCount: "50 题" },
  { slug: "08", title: "双塔检索模型面试30题", category: "deep", questionCount: "30 题" },
  { slug: "09", title: "Rust并发与系统工程面试30题", category: "deep", questionCount: "30 题" },
  { slug: "10", title: "x-algorithm专属面试50题", category: "deep", questionCount: "50 题" },
];

export const INTERVIEW_FILES: Record<string, string> = {
  "01": "01-项目介绍话术.md",
  "02": "02-推荐系统基础面试题.md",
  "03": "03-Transformer与深度学习面试题.md",
  "04": "04-系统设计与Rust工程面试题.md",
  "05": "05-综合追问与深挖题.md",
  "06": "06-Transformer注意力机制深度拷问30题.md",
  "07": "07-推荐系统排序模型面试50题.md",
  "08": "08-双塔检索模型面试30题.md",
  "09": "09-Rust并发与系统工程面试30题.md",
  "10": "10-x-algorithm专属面试50题.md",
};
