# x-algorithm 学习教程

> 深入理解 X (Twitter) For You Feed 推荐算法 — 20 节课程 + 10 套面试题

## 项目结构

```
docs/          20 篇 Markdown 课程（L01-L20）
interview/     10 套面试题集
scripts/       build_site.py — 生成静态站点
site/          生成的 HTML 站点（33 页）
web/           Next.js 源码（备用，需 npm install）
CLAUDE.md      项目蓝图
```

## 快速开始

```bash
# 生成静态站点
pip3 install markdown
python3 scripts/build_site.py

# 本地预览
cd site && python3 -m http.server 8080
# 浏览器打开 http://localhost:8080
```

## 课程大纲

| 阶段 | 课程 | 主题 |
|------|------|------|
| 🟢 基础入门 | L01-L04 | 推荐系统概览、Transformer、Rust/Python、项目导览 |
| 🔵 核心组件 | L05-L10 | CandidatePipeline、Thunder、Phoenix Grok模型、双塔检索 |
| 🟣 流程串联 | L11-L15 | HomeMixer编排、Hydration、Scoring、Selection |
| 🟠 高级面试 | L16-L20 | 系统设计、性能优化、部署架构、简历与STAR面试法 |

## 面试题库

10 套面试题集覆盖：项目介绍话术、推荐系统、Transformer、系统设计、Rust工程、综合追问等，共 300+ 道题。

## 源项目

基于 [xai-org/x-algorithm](https://github.com/xai-org/x-algorithm) 开源推荐算法。
