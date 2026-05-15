（交流可以用英文，本文档中文，保留这句）

# X For You Feed Algorithm 学习教程项目说明

## 项目目标
编写一份 X For You Feed Algorithm (x-algorithm) 的由浅入深学习教程，包含 20 节课程、面试八股文、
STAR 面试稿、简历模板和哆啦A梦漫画图解。

## 工具说明
当需要时，可以通过深度研究得到想要的答案

## 源项目信息
- 项目名：X For You Feed Algorithm (x-algorithm)
- 地址：https://github.com/xai-org/x-algorithm
- 技术栈：Rust (Home Mixer / Thunder / Candidate Pipeline) + Python / JAX / Haiku (Phoenix ML模型)
- 核心功能：驱动 X (Twitter) "For You" 信息流推荐系统，结合关注用户内容(In-Network)和算法发现内容(Out-of-Network)，通过 Grok-based Transformer 模型预测用户参与度进行排序

## 教程大纲

### 第一部分：基础入门（L01-L04）🟢
1. **推荐系统简介与 For You 信息流概览**
   - 1.1 什么是推荐系统
   - 1.2 协同过滤 vs 内容过滤 vs 深度学习推荐
   - 1.3 X (Twitter) For You 信息流的定位
   - 1.4 x-algorithm 项目架构全景图
   - 习题集1

2. **Transformer 基础与注意力机制**
   - 2.1 从 RNN 到 Attention 的演进
   - 2.2 Self-Attention 的数学原理
   - 2.3 Multi-Head Attention 与 Grouped Query Attention
   - 2.4 RoPE 旋转位置编码
   - 2.5 RMSNorm 与残差连接
   - 习题集2

3. **Rust & Python 技术栈快速上手**
   - 3.1 Rust trait 系统与异步编程基础
   - 3.2 Python JAX/Haiku 框架入门
   - 3.3 gRPC 服务通信基础
   - 3.4 Kafka 消息队列基础
   - 习题集3

4. **x-algorithm 项目导览**
   - 4.1 仓库目录结构解读
   - 4.2 四大模块关系图：Home Mixer → Candidate Pipeline / Thunder / Phoenix
   - 4.3 环境搭建与首次运行（run_ranker.py / run_retrieval.py）
   - 4.4 数据流全链路追踪
   - 习题集4

### 第二部分：核心组件拆解（L05-L10）🔵
5. **Candidate Pipeline 框架设计**
   - 5.1 Pipeline Stage 枚举与执行顺序
   - 5.2 六大 Trait：Source / Hydrator / Filter / Scorer / Selector / SideEffect
   - 5.3 并行 vs 顺序执行策略
   - 5.4 PipelineResult 结构与错误处理
   - 习题集5

6. **Thunder：实时帖子存储引擎**
   - 6.1 PostStore 数据结构：DashMap + VecDeque
   - 6.2 Kafka 事件消费：帖子创建/删除
   - 6.3 按用户分桶：原创/转发回复/视频
   - 6.4 TTL 过期与自动裁剪
   - 6.5 gRPC 服务与并发控制（Semaphore）
   - 习题集6

7. **Phoenix Grok 模型架构（上）：Transformer 核心**
   - 7.1 从 Grok-1 到推荐系统的适配
   - 7.2 TransformerConfig 配置解读
   - 7.3 DecoderLayer：MHA → FFN 残差结构
   - 7.4 GQA (Grouped Query Attention) 实现
   - 7.5 SiLU 门控 FFN（DenseBlock）
   - 习题集7

8. **Phoenix Grok 模型架构（下）：嵌入与注意力掩码**
   - 8.1 Multi-Hash Embedding 策略（HashConfig）
   - 8.2 三层 Embedding Reduction：User / History / Candidate
   - 8.3 Candidate Isolation 注意力掩码（关键创新）
   - 8.4 混合精度：fp32 参数 + bfloat16 计算
   - 8.5 RecsysBatch 数据容器
   - 习题集8

9. **Phoenix 排序模型：多行为预测**
   - 9.1 PhoenixModel 前向传播流程
   - 9.2 19 种用户行为预测（favorite/reply/repost/click...）
   - 9.3 RecsysModelOutput 输出解读
   - 9.4 runners.py 模型初始化与推理
   - 习题集9

10. **Phoenix 检索模型：双塔架构**
    - 10.1 Two-Tower 模型原理
    - 10.2 User Tower：用户特征编码
    - 10.3 Candidate Tower：帖子嵌入与 L2 归一化
    - 10.4 Dot Product 相似度搜索
    - 10.5 Top-K 检索流程（run_retrieval.py）
    - 习题集10

### 第三部分：完整流程串联（L11-L15）🟣
11. **Home Mixer 编排层总览**
    - 11.1 ScoredPostsService gRPC 端点
    - 11.2 PhoenixCandidatePipeline 组装
    - 11.3 Query 与 PostCandidate 数据结构
    - 11.4 请求生命周期完整追踪
    - 习题集11

12. **Query Hydration 与 Candidate Sources**
    - 12.1 UserActionSeqQueryHydrator：用户行为序列获取
    - 12.2 UserFeaturesQueryHydrator：关注列表获取
    - 12.3 ThunderSource：In-Network 候选获取
    - 12.4 PhoenixSource：Out-of-Network 候选获取
    - 12.5 候选合并策略
    - 习题集12

13. **Hydration 与 Filtering 详解**
    - 13.1 五大 Hydrator：CoreData / Gizmoduck / InNetwork / Subscription / VideoDuration
    - 13.2 十大 Pre-Selection Filter 逐一解析
    - 13.3 过滤顺序的工程考量
    - 13.4 FilterResult 与候选追踪
    - 习题集13

14. **Scoring 全链路：从 ML 预测到最终排分**
    - 14.1 PhoenixScorer：调用 Transformer 获取 19 维预测
    - 14.2 WeightedScorer：加权组合公式
    - 14.3 AuthorDiversityScorer：作者多样性衰减
    - 14.4 OONScorer：Out-of-Network 调整
    - 14.5 PhoenixScores 结构体详解
    - 习题集14

15. **Selection 与 Post-Processing**
    - 15.1 TopKScoreSelector：排序与截断
    - 15.2 VFFilter：安全/合规可见性过滤
    - 15.3 DedupConversationFilter：对话去重
    - 15.4 CacheRequestInfoSideEffect：预测结果缓存
    - 15.5 ScoredPostsResponse 最终响应构建
    - 习题集15

### 第四部分：高级特性与面试（L16-L20）🟠
16. **系统设计深度分析**
    - 16.1 零手工特征工程的设计哲学
    - 16.2 Candidate Isolation 的可缓存性
    - 16.3 Hash-Based Embeddings 的工程优势
    - 16.4 多行为预测 vs 单一相关性分数
    - 16.5 可组合管道架构的扩展性
    - 习题集16

17. **性能优化与工程实践**
    - 17.1 混合精度推理（bfloat16）
    - 17.2 DashMap 无锁并发读写
    - 17.3 Semaphore 背压与流量控制
    - 17.4 Kafka 消费与内存管理
    - 17.5 gRPC + Zstd 压缩传输
    - 习题集17

18. **部署架构与监控**
    - 18.1 微服务部署拓扑
    - 18.2 关键监控指标：延迟/吞吐/新鲜度/多样性
    - 18.3 A/B 测试与灰度发布
    - 18.4 模型更新与热加载
    - 习题集18

19. **简历撰写指南**
    - 19.1 STAR 法则在简历中的应用
    - 19.2 四个详略等级的简历描述
    - 19.3 量化数据对照表
    - 19.4 普通写法 vs 优化写法对比
    - 19.5 不同岗位方向调整

20. **STAR 面试法完整稿**
    - 20.1 STAR 面试法介绍
    - 20.2 自我介绍模板（30秒/1分钟/3分钟）
    - 20.3 技术难点 STAR 应对（7个场景）
    - 20.4 模拟面试（12轮）

## 面试材料大纲

### 基础面试（interview/01-05）
- 01-项目介绍话术.md（30秒/1分钟/3分钟）
- 02-推荐系统基础面试题.md
- 03-Transformer与深度学习面试题.md
- 04-系统设计与Rust工程面试题.md
- 05-综合追问与深挖题.md

### 深度八股文（interview/06-10）
- 06-Transformer注意力机制深度拷问30题.md
- 07-推荐系统排序模型面试50题.md
- 08-双塔检索模型面试30题.md
- 09-Rust并发与系统工程面试30题.md
- 10-x-algorithm专属面试50题.md

## 哆啦A梦漫画规划

| 编号 | 文件名 | 对应课程 | 漫画主题 |
|------|--------|---------|---------|
| 01 | 01-recsys-overview.png | L01 | 推荐系统全景概览图 |
| 02 | 02-transformer-attention.png | L02 | 注意力机制工作原理 |
| 03 | 03-project-architecture.png | L04 | 四大模块关系图 |
| 04 | 04-candidate-pipeline.png | L05 | Pipeline框架执行流程 |
| 05 | 05-thunder-poststore.png | L06 | Thunder实时存储引擎 |
| 06 | 06-grok-transformer.png | L07 | Grok Transformer结构 |
| 07 | 07-candidate-isolation.png | L08 | Candidate Isolation掩码 |
| 08 | 08-two-tower.png | L10 | 双塔检索模型 |
| 09 | 09-home-mixer-flow.png | L11 | Home Mixer完整流程 |
| 10 | 10-scoring-pipeline.png | L14 | 四级评分链路 |
| 11 | 11-filtering-funnel.png | L13 | 十大过滤器漏斗 |
| 12 | 12-multi-action.png | L16 | 19种行为预测 |

## 教程特色
- 每章节包含理论讲解、源码分析、架构图解
- 大量习题覆盖概念理解、设计实践、问题解决
- 渐进式学习路径，从基础到高级
- 面试八股文 190+ 题，覆盖项目所有知识点
- STAR 面试稿 + 简历模板，直接用于求职
- 哆啦A梦漫画图解，降低学习门槛

## 任务清单 (Todo List)

### Phase 1: 基础设施 🏗️
- [x] 创建项目目录结构
- [x] 创建 CLAUDE.md（本文件）
- [ ] 创建 README.md

### Phase 2: 课程内容 📚
- [ ] 编写 L01-推荐系统简介与ForYou信息流概览.md
- [ ] 编写 L02-Transformer基础与注意力机制.md
- [ ] 编写 L03-Rust与Python技术栈快速上手.md
- [ ] 编写 L04-x-algorithm项目导览.md
- [ ] 编写 L05-CandidatePipeline框架设计.md
- [ ] 编写 L06-Thunder实时帖子存储引擎.md
- [ ] 编写 L07-PhoenixGrok模型架构上.md
- [ ] 编写 L08-PhoenixGrok模型架构下.md
- [ ] 编写 L09-Phoenix排序模型多行为预测.md
- [ ] 编写 L10-Phoenix检索模型双塔架构.md
- [ ] 编写 L11-HomeMixer编排层总览.md
- [ ] 编写 L12-QueryHydration与CandidateSources.md
- [ ] 编写 L13-Hydration与Filtering详解.md
- [ ] 编写 L14-Scoring全链路.md
- [ ] 编写 L15-Selection与PostProcessing.md
- [ ] 编写 L16-系统设计深度分析.md
- [ ] 编写 L17-性能优化与工程实践.md
- [ ] 编写 L18-部署架构与监控.md
- [ ] 编写 L19-简历撰写指南.md
- [ ] 编写 L20-STAR面试法完整稿.md

### Phase 3: 面试材料 🎯
- [ ] 编写 interview/01-项目介绍话术.md
- [ ] 编写 interview/02-推荐系统基础面试题.md
- [ ] 编写 interview/03-Transformer与深度学习面试题.md
- [ ] 编写 interview/04-系统设计与Rust工程面试题.md
- [ ] 编写 interview/05-综合追问与深挖题.md
- [ ] 编写 interview/06-Transformer注意力机制深度拷问30题.md
- [ ] 编写 interview/07-推荐系统排序模型面试50题.md
- [ ] 编写 interview/08-双塔检索模型面试30题.md
- [ ] 编写 interview/09-Rust并发与系统工程面试30题.md
- [ ] 编写 interview/10-x-algorithm专属面试50题.md

### Phase 4: 哆啦A梦漫画 🎨
- [ ] 生成漫画 01-12（12张）

### Phase 5: Web 应用 🌐
- [ ] 初始化 Next.js 项目
- [ ] 创建 lib/lessons-data.ts
- [ ] 创建 lib/interview-data.ts
- [ ] 创建首页 + Hero 组件
- [ ] 创建课程列表页与详情页
- [ ] 创建面试列表页与详情页
- [ ] 验证 npm run build

### Phase 6: 构建脚本 🔧
- [ ] 创建 scripts/build_html.py
- [ ] 创建 scripts/build_pdf.py

### Phase 7: 收尾 ✅
- [ ] 质量检查
- [ ] git init && commit
