#!/usr/bin/env python3
"""Build static HTML site from markdown lesson and interview files."""

import os
import sys
import markdown
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
INTERVIEW = ROOT / "interview"
OUT = ROOT / "site"

LESSONS = [
    ("L01", "推荐系统简介与ForYou信息流概览", 1),
    ("L02", "Transformer基础与注意力机制", 1),
    ("L03", "Rust与Python技术栈快速上手", 1),
    ("L04", "x-algorithm项目导览", 1),
    ("L05", "CandidatePipeline框架设计", 2),
    ("L06", "Thunder实时帖子存储引擎", 2),
    ("L07", "PhoenixGrok模型架构上", 2),
    ("L08", "PhoenixGrok模型架构下", 2),
    ("L09", "Phoenix排序模型多行为预测", 2),
    ("L10", "Phoenix检索模型双塔架构", 2),
    ("L11", "HomeMixer编排层总览", 3),
    ("L12", "QueryHydration与CandidateSources", 3),
    ("L13", "Hydration与Filtering详解", 3),
    ("L14", "Scoring全链路", 3),
    ("L15", "Selection与PostProcessing", 3),
    ("L16", "系统设计深度分析", 4),
    ("L17", "性能优化与工程实践", 4),
    ("L18", "部署架构与监控", 4),
    ("L19", "简历撰写指南", 4),
    ("L20", "STAR面试法完整稿", 4),
]

PHASES = [
    (1, "基础入门", "#10b981"),
    (2, "核心组件拆解", "#3b82f6"),
    (3, "完整流程串联", "#8b5cf6"),
    (4, "高级特性与面试", "#f59e0b"),
]

PHASE_EMOJI = {1: "🟢", 2: "🔵", 3: "🟣", 4: "🟠"}

INTERVIEWS = [
    ("01", "项目介绍话术"),
    ("02", "推荐系统基础面试题"),
    ("03", "Transformer与深度学习面试题"),
    ("04", "系统设计与Rust工程面试题"),
    ("05", "综合追问与深挖题"),
    ("06", "Transformer注意力机制深度拷问30题"),
    ("07", "推荐系统排序模型面试50题"),
    ("08", "双塔检索模型面试30题"),
    ("09", "Rust并发与系统工程面试30题"),
    ("10", "x-algorithm专属面试50题"),
]

CSS = """
:root { --bg: #0f172a; --card: #1e293b; --text: #e2e8f0; --muted: #94a3b8; --accent: #38bdf8; }
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); line-height: 1.7; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.container { max-width: 900px; margin: 0 auto; padding: 0 1.5rem; }
nav { background: var(--card); border-bottom: 1px solid #334155; padding: 1rem 0; position: sticky; top: 0; z-index: 10; }
nav .container { display: flex; gap: 2rem; align-items: center; }
nav .logo { font-size: 1.25rem; font-weight: 700; color: var(--text); }
nav a { color: var(--muted); font-size: 0.9rem; }
nav a:hover { color: var(--text); text-decoration: none; }
.hero { text-align: center; padding: 4rem 0 3rem; }
.hero h1 { font-size: 2.5rem; margin-bottom: 0.75rem; background: linear-gradient(135deg, #38bdf8, #818cf8); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
.hero p { color: var(--muted); font-size: 1.1rem; max-width: 600px; margin: 0 auto; }
.phase { margin-bottom: 2.5rem; }
.phase-title { font-size: 1.1rem; font-weight: 600; margin-bottom: 0.75rem; padding-left: 0.5rem; border-left: 3px solid; }
.lessons-grid { display: grid; gap: 0.75rem; }
.lesson-card { background: var(--card); border-radius: 0.5rem; padding: 1rem 1.25rem; display: flex; align-items: center; gap: 1rem; transition: transform 0.15s, box-shadow 0.15s; }
.lesson-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); text-decoration: none; }
.lesson-card .num { font-size: 0.85rem; font-weight: 700; color: var(--muted); min-width: 2.5rem; }
.lesson-card .title { color: var(--text); }
.section-title { font-size: 1.5rem; font-weight: 700; margin: 3rem 0 1.5rem; }
article { background: var(--card); border-radius: 0.75rem; padding: 2.5rem; margin: 2rem 0 3rem; }
article h1 { font-size: 1.75rem; margin-bottom: 1.5rem; }
article h2 { font-size: 1.35rem; margin: 2rem 0 0.75rem; color: var(--accent); }
article h3 { font-size: 1.1rem; margin: 1.5rem 0 0.5rem; }
article p { margin-bottom: 1rem; }
article ul, article ol { margin: 0.5rem 0 1rem 1.5rem; }
article li { margin-bottom: 0.35rem; }
article code { background: #334155; padding: 0.15rem 0.4rem; border-radius: 0.25rem; font-size: 0.9em; }
article pre { background: #0f172a; border: 1px solid #334155; border-radius: 0.5rem; padding: 1rem; overflow-x: auto; margin: 1rem 0; }
article pre code { background: transparent; padding: 0; }
article blockquote { border-left: 3px solid var(--accent); padding-left: 1rem; color: var(--muted); margin: 1rem 0; }
article table { width: 100%; border-collapse: collapse; margin: 1rem 0; }
article th, article td { border: 1px solid #334155; padding: 0.5rem 0.75rem; text-align: left; }
article th { background: #334155; }
article strong { color: #f1f5f9; }
.breadcrumb { color: var(--muted); margin: 1.5rem 0 0; font-size: 0.9rem; }
.breadcrumb a { color: var(--muted); }
.nav-links { display: flex; justify-content: space-between; margin: 2rem 0 3rem; }
.nav-links a { background: var(--card); padding: 0.75rem 1.25rem; border-radius: 0.5rem; font-size: 0.9rem; }
footer { border-top: 1px solid #334155; padding: 2rem 0; text-align: center; color: var(--muted); font-size: 0.85rem; margin-top: auto; }
"""

def md_to_html(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "toc"],
        output_format="html",
    )

def page_wrap(title: str, body: str, breadcrumb: str = "") -> str:
    bc = f'<div class="breadcrumb">{breadcrumb}</div>' if breadcrumb else ""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — x-algorithm 学习教程</title>
<style>{CSS}</style>
</head>
<body>
<nav><div class="container">
<span class="logo">📘 x-algorithm 学习教程</span>
<a href="index.html">首页</a>
<a href="learn.html">课程</a>
<a href="interview.html">面试</a>
</div></nav>
<div class="container">{bc}{body}</div>
<footer><div class="container">x-algorithm 学习教程 · 基于 X (Twitter) For You Feed 开源算法</div></footer>
</body></html>"""

def find_md_file(directory: Path, prefix: str) -> Path | None:
    for f in sorted(directory.iterdir()):
        if f.name.startswith(prefix) and f.suffix == ".md":
            return f
    return None

def build_index() -> str:
    phases_html = ""
    for pid, pname, pcolor in PHASES:
        cards = ""
        for slug, title, phase in LESSONS:
            if phase != pid:
                continue
            cards += f'<a class="lesson-card" href="lesson-{slug}.html"><span class="num">{PHASE_EMOJI[pid]} {slug}</span><span class="title">{title}</span></a>\n'
        phases_html += f'<div class="phase"><div class="phase-title" style="border-color:{pcolor};color:{pcolor}">阶段{pid} · {pname}</div><div class="lessons-grid">{cards}</div></div>\n'

    interview_cards = ""
    for num, title in INTERVIEWS:
        interview_cards += f'<a class="lesson-card" href="interview-{num}.html"><span class="num">📝 {num}</span><span class="title">{title}</span></a>\n'

    body = f"""
<div class="hero">
<h1>x-algorithm 学习教程</h1>
<p>深入理解 X (Twitter) For You Feed 推荐算法 · 20节课程 + 10套面试题</p>
</div>
<div class="section-title">📚 学习路径</div>
{phases_html}
<div class="section-title">🎯 面试准备</div>
<div class="lessons-grid">{interview_cards}</div>
"""
    return page_wrap("首页", body)

def build_learn() -> str:
    phases_html = ""
    for pid, pname, pcolor in PHASES:
        cards = ""
        for slug, title, phase in LESSONS:
            if phase != pid:
                continue
            cards += f'<a class="lesson-card" href="lesson-{slug}.html"><span class="num">{PHASE_EMOJI[pid]} {slug}</span><span class="title">{title}</span></a>\n'
        phases_html += f'<div class="phase"><div class="phase-title" style="border-color:{pcolor};color:{pcolor}">阶段{pid} · {pname}</div><div class="lessons-grid">{cards}</div></div>\n'
    body = f'<div class="section-title">📚 全部课程</div>\n{phases_html}'
    return page_wrap("全部课程", body, '<a href="index.html">首页</a> / 课程')

def build_interview_list() -> str:
    cards = ""
    for num, title in INTERVIEWS:
        cards += f'<a class="lesson-card" href="interview-{num}.html"><span class="num">📝 {num}</span><span class="title">{title}</span></a>\n'
    body = f'<div class="section-title">🎯 面试题库</div>\n<div class="lessons-grid">{cards}</div>'
    return page_wrap("面试题库", body, '<a href="index.html">首页</a> / 面试')

def build_lesson_page(idx: int) -> str | None:
    slug, title, phase = LESSONS[idx]
    f = find_md_file(DOCS, slug)
    if not f:
        print(f"  ⚠️  {slug} markdown not found, skipping")
        return None
    content = md_to_html(f.read_text(encoding="utf-8"))
    nav = '<div class="nav-links">'
    if idx > 0:
        ps, pt, _ = LESSONS[idx - 1]
        nav += f'<a href="lesson-{ps}.html">← {ps} {pt}</a>'
    else:
        nav += "<span></span>"
    if idx < len(LESSONS) - 1:
        ns, nt, _ = LESSONS[idx + 1]
        nav += f'<a href="lesson-{ns}.html">{ns} {nt} →</a>'
    nav += "</div>"
    body = f"<article>{content}</article>{nav}"
    bc = f'<a href="index.html">首页</a> / <a href="learn.html">课程</a> / {slug}'
    return page_wrap(f"{slug} {title}", body, bc)

def build_interview_page(idx: int) -> str | None:
    num, title = INTERVIEWS[idx]
    f = find_md_file(INTERVIEW, num)
    if not f:
        print(f"  ⚠️  interview {num} not found, skipping")
        return None
    content = md_to_html(f.read_text(encoding="utf-8"))
    nav = '<div class="nav-links">'
    if idx > 0:
        pn, pt = INTERVIEWS[idx - 1]
        nav += f'<a href="interview-{pn}.html">← {pt}</a>'
    else:
        nav += "<span></span>"
    if idx < len(INTERVIEWS) - 1:
        nn, nt = INTERVIEWS[idx + 1]
        nav += f'<a href="interview-{nn}.html">{nt} →</a>'
    nav += "</div>"
    body = f"<article>{content}</article>{nav}"
    bc = f'<a href="index.html">首页</a> / <a href="interview.html">面试</a> / {title}'
    return page_wrap(title, body, bc)

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("Building site →", OUT)

    (OUT / "index.html").write_text(build_index(), encoding="utf-8")
    print("  ✅ index.html")

    (OUT / "learn.html").write_text(build_learn(), encoding="utf-8")
    print("  ✅ learn.html")

    (OUT / "interview.html").write_text(build_interview_list(), encoding="utf-8")
    print("  ✅ interview.html")

    for i in range(len(LESSONS)):
        html = build_lesson_page(i)
        if html:
            slug = LESSONS[i][0]
            (OUT / f"lesson-{slug}.html").write_text(html, encoding="utf-8")
            print(f"  ✅ lesson-{slug}.html")

    for i in range(len(INTERVIEWS)):
        html = build_interview_page(i)
        if html:
            num = INTERVIEWS[i][0]
            (OUT / f"interview-{num}.html").write_text(html, encoding="utf-8")
            print(f"  ✅ interview-{num}.html")

    total = len(list(OUT.glob("*.html")))
    print(f"\n🎉 Done! {total} pages generated in site/")

if __name__ == "__main__":
    main()
