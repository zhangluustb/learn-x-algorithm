# 10 - x-algorithm 专属面试 50 题

> 专门针对 x-algorithm 项目的深度面试题，覆盖所有模块和设计决策。

---

## 架构总览（Q1-Q10）

**Q1:** 画出 x-algorithm 的完整架构图，标注四大模块的通信方式。⭐⭐
**Q2:** 为什么 x-algorithm 不用单体架构而用微服务？⭐⭐
**Q3:** Home Mixer、Thunder、Phoenix 各用什么语言？为什么选择不同语言？⭐⭐
**Q4:** 一次 For You 请求的端到端数据流？⭐⭐⭐
**Q5:** Candidate Pipeline 框架的六大 Trait 分别是什么？⭐⭐
**Q6:** 为什么 Source 并行而 Filter 顺序？⭐⭐
**Q7:** PipelineResult 包含哪些字段？⭐
**Q8:** Pipeline 的错误处理策略？⭐⭐
**Q9:** 如何新增一个候选源（如广告）？需要改几行代码？⭐⭐
**Q10:** Builder 模式在管道组装中的优势？⭐

## Thunder 模块（Q11-Q20）

**Q11:** PostStore 的数据结构设计？为什么用三个 DashMap？⭐⭐
**Q12:** TinyPost vs LightPost 的区别？为什么需要两种？⭐⭐
**Q13:** VecDeque 在帖子存储中的作用？⭐
**Q14:** Kafka 事件的消费和反序列化流程？⭐⭐
**Q15:** TTL 的懒过期和主动裁剪如何配合？⭐⭐
**Q16:** Semaphore 的 permits 数如何确定？⭐⭐
**Q17:** Thunder 的 gRPC 服务暴露了什么接口？⭐
**Q18:** get_posts_by_users 的实现逻辑？⭐⭐
**Q19:** 如果一个用户关注了 10 万人，Thunder 查询会怎样？⭐⭐
**Q20:** Thunder 的监控指标有哪些？⭐⭐

## Phoenix 模型（Q21-Q35）

**Q21:** TransformerConfig 的关键参数和它们的关系？⭐⭐
**Q22:** Grok-1 适配推荐系统做了哪些改动？⭐⭐⭐
**Q23:** HashConfig 的设计考量？⭐⭐
**Q24:** 三层 Embedding Reduction 的完整流程？⭐⭐⭐
**Q25:** Candidate Isolation 掩码的构建方法和数学证明？⭐⭐⭐
**Q26:** PhoenixModel 的前向传播 6 个步骤？⭐⭐
**Q27:** 19 种行为预测的具体列表和分类？⭐⭐
**Q28:** WeightedScorer 的权重设计原则？⭐⭐⭐
**Q29:** 负面行为权重为什么是 -74？改为 -10 会怎样？⭐⭐
**Q30:** PhoenixRetrievalModel 和 PhoenixModel 的区别？⭐⭐
**Q31:** CandidateTower 为什么要 L2 归一化？⭐⭐
**Q32:** User Tower 为什么取最后一个位置作为表示？⭐⭐
**Q33:** bfloat16 混合精度的实现细节？⭐⭐
**Q34:** RecsysBatch 包含哪些字段？为什么用 NamedTuple？⭐
**Q35:** runners.py 的 Haiku transform 流程？⭐⭐

## Home Mixer 编排（Q36-Q45）

**Q36:** Query Hydration 阶段获取了什么数据？⭐⭐
**Q37:** ThunderSource 和 PhoenixSource 的实现和区别？⭐⭐
**Q38:** 五大 Hydrator 各自补全什么字段？⭐⭐
**Q39:** 十大 Filter 的顺序为什么这样排列？⭐⭐⭐
**Q40:** RetweetDeduplicationFilter 的去重逻辑？⭐⭐
**Q41:** PhoenixScorer 是如何调用 Transformer 模型的？⭐⭐
**Q42:** AuthorDiversityScorer 的 1/N 衰减原理？⭐⭐
**Q43:** VFFilter 为什么放在 Post-Selection？⭐⭐
**Q44:** DedupConversationFilter 的对话根 ID 如何确定？⭐⭐
**Q45:** ScoredPostsResponse 包含哪些字段？⭐

## 设计决策与优化（Q46-Q50）

**Q46:** 零手工特征的优缺点？在哪些场景下会失效？⭐⭐⭐
**Q47:** Hash 嵌入从 512GB 降到 3GB，质量损失多少？如何验证？⭐⭐⭐
**Q48:** 可组合管道架构如何支持 A/B 测试？⭐⭐
**Q49:** 如果要增加"Grok 对话推荐"作为新 Source，需要改什么？⭐⭐
**Q50:** 对比 x-algorithm 和 Twitter 2023 开源的推荐算法，主要区别是什么？⭐⭐⭐
