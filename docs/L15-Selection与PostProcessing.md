# L15 - Selection 与 Post-Processing

> **"最后的 5% 工作决定了 50% 的用户体验——选择和后处理是推荐系统的收尾艺术。"**

---

## 📌 本节目标

1. 理解 TopKScoreSelector 的排序与截断
2. 掌握 VFFilter 安全可见性过滤
3. 了解 DedupConversationFilter 对话去重
4. 认识 CacheRequestInfoSideEffect 预测缓存
5. 理解 ScoredPostsResponse 最终响应构建

---

## 📚 前置知识

- L14 中的四级评分链路
- L05 中的 Selector/SideEffect trait

---

## 正文讲解

### 1. TopKScoreSelector——排序与截断

```rust
pub struct TopKScoreSelector {
    k: usize,  // 默认 50
}

#[async_trait]
impl Selector<ScoredPostsQuery, PostCandidate> for TopKScoreSelector {
    async fn select(&self, _query: &Q, mut candidates: Vec<PostCandidate>) 
        -> Vec<PostCandidate> 
    {
        // 按 score 降序排列
        candidates.sort_by(|a, b| {
            b.score.unwrap_or(f64::NEG_INFINITY)
                .partial_cmp(&a.score.unwrap_or(f64::NEG_INFINITY))
                .unwrap_or(std::cmp::Ordering::Equal)
        });
        
        // 截断到 Top-K
        candidates.truncate(self.k);
        
        candidates
    }
}
```

**从 250 条到 50 条**——这一步丢弃了 80% 的候选，只留下分数最高的精华。

> **类比**：这就像高考录取——不管你怎么报名（Source）、怎么答题（Score），最终只有 Top-K 被录取。

### 2. Post-Selection Hydration：VFCandidateHydrator

选择 Top-50 后，再做一轮数据补全——这次是**安全相关**的数据：

```rust
pub struct VFCandidateHydrator {
    vf_client: Arc<VisibilityFilterClient>,
}

#[async_trait]
impl Hydrator<ScoredPostsQuery, PostCandidate> for VFCandidateHydrator {
    async fn hydrate(&self, _query: &Q, candidates: Vec<PostCandidate>) 
        -> Vec<PostCandidate> 
    {
        let tweet_ids: Vec<i64> = candidates.iter()
            .map(|c| c.tweet_id)
            .collect();
        
        // 批量检查可见性
        let visibility = self.vf_client
            .check_visibility(&tweet_ids)
            .await;
        
        candidates.into_iter()
            .map(|mut c| {
                c.visibility_reason = visibility
                    .get(&c.tweet_id)
                    .and_then(|v| v.filtered_reason.clone());
                c
            })
            .collect()
    }
}
```

**为什么 VF 检查放在 Post-Selection？** 因为 VF 服务调用成本高（需要检查法律合规、内容安全等）。先选出 Top-50 再检查，比对 250 条都检查节省 80% 的 RPC 开销。

### 3. VFFilter——安全底线

```rust
pub struct VFFilter;

impl Filter<ScoredPostsQuery, PostCandidate> for VFFilter {
    async fn filter(&self, _query: &Q, candidates: Vec<PostCandidate>) 
        -> FilterResult<PostCandidate> 
    {
        candidates.into_iter()
            .partition(|c| c.visibility_reason.is_none())
    }
}
```

被 VF 过滤的原因包括：

| FilteredReason | 含义 |
|---------------|------|
| `Deleted` | 帖子已被删除 |
| `BounceDeleted` | 帖子被自动删除（违规） |
| `SpamFiltered` | 垃圾信息 |
| `SafetyFiltered` | 安全内容审核不通过 |
| `LegalDemand` | 法律要求移除 |
| `Interstitial` | 需要警告提示 |

### 4. DedupConversationFilter——对话去重

```rust
pub struct DedupConversationFilter;

impl Filter<ScoredPostsQuery, PostCandidate> for DedupConversationFilter {
    async fn filter(&self, _query: &Q, candidates: Vec<PostCandidate>) 
        -> FilterResult<PostCandidate> 
    {
        let mut seen_conversations: HashSet<u64> = HashSet::new();
        
        candidates.into_iter()
            .partition(|c| {
                // 对话根 ID = 最早的祖先帖子 ID（如果有的话）
                let conversation_root = c.ancestors
                    .first()
                    .copied()
                    .or(c.in_reply_to_tweet_id)
                    .unwrap_or(c.tweet_id as u64);
                
                seen_conversations.insert(conversation_root)
            })
    }
}
```

> **场景**：一条热门帖子下面有 3 条高分回复都进了 Top-50。没有去重的话，信息流前 4 条可能全是同一个话题。DedupConversationFilter 保证每个对话最多出现一条。

### 5. CacheRequestInfoSideEffect——预测缓存

```rust
pub struct CacheRequestInfoSideEffect {
    cache_client: Arc<PredictionCacheClient>,
}

#[async_trait]
impl SideEffect<ScoredPostsQuery, PostCandidate> 
    for CacheRequestInfoSideEffect 
{
    async fn apply(&self, query: &Q, candidates: &[PostCandidate]) {
        // 记录预测结果供后续分析
        let cache_entries: Vec<CacheEntry> = candidates.iter()
            .filter_map(|c| {
                Some(CacheEntry {
                    viewer_id: query.viewer_id,
                    tweet_id: c.tweet_id,
                    prediction_request_id: c.prediction_request_id?,
                    phoenix_scores: c.phoenix_scores.clone(),
                    weighted_score: c.weighted_score?,
                    final_score: c.score?,
                    in_network: c.in_network?,
                    served_at_ms: now_ms(),
                })
            })
            .collect();
        
        // Fire-and-forget：不等待结果
        let _ = self.cache_client.put_batch(cache_entries).await;
    }
}
```

**缓存的用途：**
1. **模型评估**：对比预测值与实际行为，计算模型准确率
2. **A/B 测试**：比较不同权重配置的效果
3. **调试**：排查"为什么某条帖子被推荐/未被推荐"
4. **重训练**：作为监督信号反馈给模型

### 6. ScoredPostsResponse——最终响应

```rust
pub struct ScoredPostsResponse {
    pub scored_posts: Vec<ScoredPost>,
}

pub struct ScoredPost {
    pub tweet_id: i64,
    pub author_id: u64,
    pub retweeted_tweet_id: Option<u64>,
    pub score: f64,
    pub in_network: bool,
    pub served_type: ServedType,  // ForYouPhoenixRetrieval | ForYouInNetwork
    pub screen_names: HashMap<u64, String>,
    pub visibility_reason: Option<FilteredReason>,
}
```

**构建响应的过程：**

```rust
fn build_response(result: PipelineResult<ScoredPostsQuery, PostCandidate>) 
    -> ScoredPostsResponse 
{
    let scored_posts = result.selected_candidates
        .into_iter()
        .map(|c| {
            let mut screen_names = HashMap::new();
            if let Some(name) = &c.author_screen_name {
                screen_names.insert(c.author_id, name.clone());
            }
            if let (Some(rt_id), Some(rt_name)) = 
                (c.retweeted_user_id, &c.retweeted_screen_name) 
            {
                screen_names.insert(rt_id, rt_name.clone());
            }
            
            ScoredPost {
                tweet_id: c.tweet_id,
                author_id: c.author_id,
                retweeted_tweet_id: c.retweeted_tweet_id.map(|id| id as i64),
                score: c.score.unwrap_or(0.0),
                in_network: c.in_network.unwrap_or(false),
                served_type: if c.in_network == Some(true) {
                    ServedType::ForYouInNetwork
                } else {
                    ServedType::ForYouPhoenixRetrieval
                },
                screen_names,
                visibility_reason: c.visibility_reason,
            }
        })
        .collect();
    
    ScoredPostsResponse { scored_posts }
}
```

---

## 💡 本节小结

| 阶段 | 输入 → 输出 | 核心作用 |
|------|------------|---------|
| TopKSelector | 250条 → 50条 | 按分数截断 |
| VFHydrator + VFFilter | 50条 → ~48条 | 安全合规过滤 |
| DedupConversation | ~48条 → ~45条 | 对话去重 |
| CacheRequestInfo | 不改变结果 | 记录预测供分析 |
| Response 构建 | PostCandidate → ScoredPost | 裁剪字段，返回客户端 |

---

## 📝 习题集15

**概念理解：**
1. 为什么 VF 检查放在 Post-Selection 而不是 Pre-Selection？如果有一条违规帖子分数很高，它会怎样被处理？
2. CacheRequestInfoSideEffect 为什么是"fire-and-forget"？如果缓存写入失败，会影响推荐结果吗？

**设计思考：**
3. DedupConversationFilter 只保留每个对话的第一条（按 Top-K 排序后的第一条，即分数最高的）。这个策略有什么潜在问题？
4. 如果用户快速下滑，在 1 秒内请求了 3 次 GetScoredPosts，served_ids 如何防止重复？

**综合题：**
5. 画出从 Source 产生 380 条候选到最终返回 45 条的完整漏斗图，标注每个阶段的数量变化和所用组件。

---

> 下一课我们将进入第四部分——**L16 - 系统设计深度分析**，从更高的维度审视整个系统。
