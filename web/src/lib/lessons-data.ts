export interface LessonMeta {
  slug: string;
  title: string;
  phase: number;
  color: string;
  emoji: string;
}

export const LESSONS: LessonMeta[] = [
  { slug: "L01", title: "推荐系统简介与ForYou信息流概览", phase: 1, color: "#10b981", emoji: "🟢" },
  { slug: "L02", title: "Transformer基础与注意力机制", phase: 1, color: "#10b981", emoji: "🟢" },
  { slug: "L03", title: "Rust与Python技术栈快速上手", phase: 1, color: "#10b981", emoji: "🟢" },
  { slug: "L04", title: "x-algorithm项目导览", phase: 1, color: "#10b981", emoji: "🟢" },
  { slug: "L05", title: "CandidatePipeline框架设计", phase: 2, color: "#3b82f6", emoji: "🔵" },
  { slug: "L06", title: "Thunder实时帖子存储引擎", phase: 2, color: "#3b82f6", emoji: "🔵" },
  { slug: "L07", title: "PhoenixGrok模型架构上", phase: 2, color: "#3b82f6", emoji: "🔵" },
  { slug: "L08", title: "PhoenixGrok模型架构下", phase: 2, color: "#3b82f6", emoji: "🔵" },
  { slug: "L09", title: "Phoenix排序模型多行为预测", phase: 2, color: "#3b82f6", emoji: "🔵" },
  { slug: "L10", title: "Phoenix检索模型双塔架构", phase: 2, color: "#3b82f6", emoji: "🔵" },
  { slug: "L11", title: "HomeMixer编排层总览", phase: 3, color: "#8b5cf6", emoji: "🟣" },
  { slug: "L12", title: "QueryHydration与CandidateSources", phase: 3, color: "#8b5cf6", emoji: "🟣" },
  { slug: "L13", title: "Hydration与Filtering详解", phase: 3, color: "#8b5cf6", emoji: "🟣" },
  { slug: "L14", title: "Scoring全链路", phase: 3, color: "#8b5cf6", emoji: "🟣" },
  { slug: "L15", title: "Selection与PostProcessing", phase: 3, color: "#8b5cf6", emoji: "🟣" },
  { slug: "L16", title: "系统设计深度分析", phase: 4, color: "#f59e0b", emoji: "🟠" },
  { slug: "L17", title: "性能优化与工程实践", phase: 4, color: "#f59e0b", emoji: "🟠" },
  { slug: "L18", title: "部署架构与监控", phase: 4, color: "#f59e0b", emoji: "🟠" },
  { slug: "L19", title: "简历撰写指南", phase: 4, color: "#f59e0b", emoji: "🟠" },
  { slug: "L20", title: "STAR面试法完整稿", phase: 4, color: "#f59e0b", emoji: "🟠" },
];

export const PHASES = [
  { id: 1, name: "基础入门", color: "#10b981", range: "L01-L04" },
  { id: 2, name: "核心组件拆解", color: "#3b82f6", range: "L05-L10" },
  { id: 3, name: "完整流程串联", color: "#8b5cf6", range: "L11-L15" },
  { id: 4, name: "高级特性与面试", color: "#f59e0b", range: "L16-L20" },
];

export const LESSON_FILES: Record<string, string> = {
  L01: "L01-推荐系统简介与ForYou信息流概览.md",
  L02: "L02-Transformer基础与注意力机制.md",
  L03: "L03-Rust与Python技术栈快速上手.md",
  L04: "L04-x-algorithm项目导览.md",
  L05: "L05-CandidatePipeline框架设计.md",
  L06: "L06-Thunder实时帖子存储引擎.md",
  L07: "L07-PhoenixGrok模型架构上.md",
  L08: "L08-PhoenixGrok模型架构下.md",
  L09: "L09-Phoenix排序模型多行为预测.md",
  L10: "L10-Phoenix检索模型双塔架构.md",
  L11: "L11-HomeMixer编排层总览.md",
  L12: "L12-QueryHydration与CandidateSources.md",
  L13: "L13-Hydration与Filtering详解.md",
  L14: "L14-Scoring全链路.md",
  L15: "L15-Selection与PostProcessing.md",
  L16: "L16-系统设计深度分析.md",
  L17: "L17-性能优化与工程实践.md",
  L18: "L18-部署架构与监控.md",
  L19: "L19-简历撰写指南.md",
  L20: "L20-STAR面试法完整稿.md",
};
