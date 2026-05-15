import fs from "fs";
import path from "path";

export function readMarkdown(dir: string, filename: string): string {
  const filePath = path.join(process.cwd(), "..", dir, filename);
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return `# 文件未找到\n\n无法读取 ${filename}`;
  }
}

export function extractTitle(content: string): string {
  const match = content.match(/^#\s+(.+)/m);
  return match ? match[1] : "无标题";
}
