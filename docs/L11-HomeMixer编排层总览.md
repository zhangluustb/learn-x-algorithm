# L11 - Home Mixer 编排层总览

> **"如果 Thunder 是食材供应商，Phoenix 是大厨，那 Home Mixer 就是餐厅经理——协调一切，确保每道菜按时上桌。"**

---

## 📌 本节目标

1. 理解 ScoredPostsService gRPC 端点
2. 掌握 PhoenixCandidatePipeline 的组装方式
3. 熟悉 Query 与 PostCandidate 数据结构
4. 追踪一次请求的完整生命周期

---

## 📚 前置知识

- L05 中的 Candidate Pipeline 框架
- L06 Thunder / L09-L10 Phoenix 的基本概念

---

## 正文讲解

### 1. ScoredPostsService——对外接口

Home Mixer 通过 gRPC 暴露一个简洁的接口：

```rust
// server.rs
pub struct ScoredPostsServiceImpl {
    pipeline: PhoenixCandidatePipeline,
}

impl ScoredPostsService for ScoredPostsServiceImpl {
    async fn get_scored_posts(
        &self, 
        request: ScoredPostsRequest
    ) -> ScoredPostsResponse {
        // 1. 构造 Query
        let query = ScoredPostsQuery::from(request);
        
        // 2. 执行管道
        let result = self.pipeline.execute(query).await;
        
        // 3. 转换为响应
        ScoredPostsResponse {
            scored_posts: result.selected_candidates
                .into_iter()
                .map(|c| to_scored_post(c))
                .collect(),
        }
    }
}
```

**响应结构：**

```rust
pub struct ScoredPost {
    tweet_id: i64,
    author_id: u64,
    score: f64,                         // 最终加权分数
    in_network: bool,                   // 是否来自关注用户
    served_type: ServedType,            // ForYouPhoenixRetrieval | ForYouInNetwork
    screen_names: HashMap<u64, String>, // 作者昵称映射
    retweeted_tweet_id: Option<u64>,    // 如果是转发
}
```

### 2. PhoenixCandidatePipeline——管道组装

```rust
pub fn build_phoenix_candidate_pipeline() -> CandidatePipeline<
    ScoredPostsQuery, PostCandidate
> {
    CandidatePipeline::builder()
        // === Query Hydrators（并行）===
        .query_hydrator(Box::new(UserActionSeqQueryHydrator::new()))
        .query_hydrator(Box::new(UserFeaturesQueryHydrator::new()))
        
        // === Sources（并行）===
        .source(Box::new(ThunderSource::new()))
        .source(Box::new(PhoenixSource::new()))
        
        // === Hydrators（并行）===
        .hydrator(Box::new(InNetworkCandidateHydrator::new()))
        .hydrator(Box::new(CoreDataCandidateHydrator::new()))
        .hydrator(Box::new(VideoDurationCandidateHydrator::new()))
        .hydrator(Box::new(SubscriptionHydrator::new()))
        .hydrator(Box::new(GizmoduckCandidateHydrator::new()))
        
        // === Filters（顺序）===
        .filter(Box::new(DropDuplicatesFilter::new()))
        .filter(Box::new(CoreDataHydrationFilter::new()))
        .filter(Box::new(AgeFilter::new(30 * 24 * 3600))) // 30 天
        .filter(Box::new(SelfTweetFilter::new()))
        .filter(Box::new(RetweetDeduplicationFilter::new()))
        .filter(Box::new(IneligibleSubscriptionFilter::new()))
        .filter(Box::new(PreviouslySeenPostsFilter::new()))
        .filter(Box::new(PreviouslyServedPostsFilter::new()))
        .filter(Box::new(MutedKeywordFilter::new()))
        .filter(Box::new(AuthorSocialgraphFilter::new()))
        
        // === Scorers（顺序）===
        .scorer(Box::new(PhoenixScorer::new()))
        .scorer(Box::new(WeightedScorer::new()))
        .scorer(Box::new(AuthorDiversityScorer::new()))
        .scorer(Box::new(OONScorer::new()))
        
        // === Selector ===
        .selector(Box::new(TopKScoreSelector::new(50)))
        
        // === Post-Selection ===
        .post_selection_hydrator(Box::new(VFCandidateHydrator::new()))
        .post_selection_filter(Box::new(VFFilter::new()))
        .post_selection_filter(Box::new(DedupConversationFilter::new()))
        
        // === Side Effects ===
        .side_effect(Box::new(CacheRequestInfoSideEffect::new()))
        
        .build()
}
```

这就是整个 For You 信息流的"配方"——所有组件以声明式方式挂载。

### 3. ScoredPostsQuery——请求上下文

```rust
pub struct ScoredPostsQuery {
    // === 原始请求字段 ===
    pub viewer_id: u64,            // 请求用户 ID
    pub client_app_id: i32,        // 客户端应用 ID
    pub country_code: String,      // 国家代码
    pub language_code: String,     // 语言代码
    pub seen_ids: Vec<u64>,        // 已看过的帖子 ID
    pub served_ids: Vec<u64>,      // 已推送过的帖子 ID
    pub in_network_only: bool,     // 是否只要关注用户内容
    pub is_bottom_request: bool,   // 是否是上拉加载
    pub bloom_filter_entries: Vec<u64>,  // 布隆过滤器
    
    // === Hydrator 填充的字段 ===
    pub user_action_sequence: Option<UserActionSequence>,
    pub user_features: UserFeatures,
}
```

### 4. PostCandidate——候选帖子

```rust
pub struct PostCandidate {
    // === 基础信息 ===
    pub tweet_id: i64,
    pub author_id: u64,
    pub tweet_text: String,
    
    // === 社交关系 ===
    pub in_reply_to_tweet_id: Option<u64>,
    pub retweeted_tweet_id: Option<u64>,
    pub retweeted_user_id: Option<u64>,
    pub in_network: Option<bool>,
    
    // === ML 评分 ===
    pub phoenix_scores: PhoenixScores,   // 19 维预测
    pub weighted_score: Option<f64>,      // 加权综合分
    pub score: Option<f64>,               // 最终分数
    
    // === 元数据 ===
    pub author_followers_count: Option<i32>,
    pub author_screen_name: Option<String>,
    pub video_duration_ms: Option<i32>,
    pub visibility_reason: Option<FilteredReason>,
    pub ancestors: Vec<u64>,              // 对话线索
}
```

**候选的"成长历程"：**

| 阶段 | 填充的字段 |
|------|-----------|
| Source | tweet_id, author_id |
| CoreDataHydrator | tweet_text, in_reply_to, retweeted_* |
| InNetworkHydrator | in_network |
| GizmoduckHydrator | author_followers_count, screen_name |
| PhoenixScorer | phoenix_scores |
| WeightedScorer | weighted_score |
| AuthorDiversityScorer | score (调整后) |
| VFHydrator | visibility_reason |

### 5. 请求生命周期完整追踪

```
T=0ms    客户端发起 GetScoredPosts RPC
         │
T=1ms    ├── Query Hydration（并行 ~50ms）
         │   ├── UAS 服务 → user_action_sequence
         │   └── Strato → user_features (following list)
         │
T=50ms   ├── Candidate Sources（并行 ~30ms）
         │   ├── Thunder gRPC → 80 条 In-Network
         │   └── Phoenix Retrieval → 300 条 Out-of-Network
         │
T=80ms   ├── Hydration（并行 ~40ms）
         │   ├── CoreData → 帖子元数据
         │   ├── Gizmoduck → 作者信息
         │   ├── InNetwork → 标记
         │   ├── Subscription → 付费状态
         │   └── VideoDuration → 视频时长
         │
T=120ms  ├── Filtering（顺序 ~10ms）
         │   380 → 250 条
         │
T=130ms  ├── Scoring（顺序 ~100ms）
         │   ├── PhoenixScorer (~80ms，主要延迟)
         │   ├── WeightedScorer (~1ms)
         │   ├── AuthorDiversityScorer (~1ms)
         │   └── OONScorer (~1ms)
         │
T=230ms  ├── Selection: Top-50
         │
T=231ms  ├── Post-Selection（~20ms）
         │   ├── VF Hydration + Filter
         │   └── DedupConversation
         │   50 → ~45 条
         │
T=250ms  ├── Side Effects（异步，不阻塞）
         │   └── CacheRequestInfo
         │
T=250ms  └── 返回 ScoredPostsResponse
```

**端到端延迟约 250ms**，其中 PhoenixScorer 的 Transformer 推理是主要瓶颈（~80ms）。

---

## 💡 本节小结

| 概念 | 一句话总结 |
|------|-----------|
| ScoredPostsService | 单一 gRPC 端点，封装整个推荐管道 |
| Pipeline 组装 | Builder 模式声明式挂载所有组件 |
| PostCandidate | 随管道推进逐步被各组件"充实"的数据结构 |
| 端到端延迟 | ~250ms，PhoenixScorer 是瓶颈 |

---

## 📝 习题集11

**代码阅读：**
1. 在 `phoenix_candidate_pipeline.rs` 中，Filter 的添加顺序为什么是这样的？如果把 `AgeFilter` 放在最后会怎样？
2. `PostCandidate` 的哪些字段在 Source 阶段就有值？哪些是后续 Hydrator 填充的？

**设计思考：**
3. 为什么 PhoenixScorer 是延迟瓶颈？有哪些可能的优化方案？
4. Builder 模式相比直接在 `execute()` 里写所有逻辑有什么优势？

---

> 下一课我们将深入 **L12 - Query Hydration 与 Candidate Sources**。
