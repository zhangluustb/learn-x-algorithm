# L12 - Query Hydration 与 Candidate Sources

> **"管道的前两步决定了信息流的'原材料'——用户画像越丰富，候选池越优质，最终推荐就越好。"**

---

## 📌 本节目标

1. 理解 UserActionSeqQueryHydrator 获取用户行为序列
2. 掌握 UserFeaturesQueryHydrator 获取关注列表
3. 了解 ThunderSource 的 In-Network 候选获取
4. 掌握 PhoenixSource 的 Out-of-Network 候选获取
5. 理解候选合并策略

---

## 📚 前置知识

- L06 Thunder / L10 Phoenix 检索
- L11 Home Mixer 架构

---

## 正文讲解

### 1. UserActionSeqQueryHydrator——"了解用户"

> **类比**：这就像面试官在见面前先翻阅候选人的简历——了解你过去做了什么，才能判断你未来想要什么。

```rust
pub struct UserActionSeqQueryHydrator {
    uas_client: Arc<UASClient>,  // User Action Sequence 服务
}

#[async_trait]
impl QueryHydrator<ScoredPostsQuery> for UserActionSeqQueryHydrator {
    async fn hydrate(&self, query: ScoredPostsQuery) -> ScoredPostsQuery {
        // 1. 调用 UAS 服务获取用户最近的行为序列
        let action_seq = self.uas_client
            .get_actions(query.viewer_id, limit=500)
            .await;
        
        // action_seq 包含:
        // - 用户最近交互的 500 条帖子 ID
        // - 每条帖子的交互类型（点赞/回复/转发/点击...）
        // - 交互时间戳
        // - 帖子作者 ID
        
        // 2. 填充到 query 中
        ScoredPostsQuery {
            user_action_sequence: Some(action_seq),
            ..query
        }
    }
}
```

**行为序列的结构：**

```
UserActionSequence {
    actions: [
        { post_id: 1001, author_id: 42, action: "favorite", ts: 1715... },
        { post_id: 1002, author_id: 55, action: "reply",    ts: 1715... },
        { post_id: 1003, author_id: 42, action: "retweet",  ts: 1715... },
        ... (最近 500 条)
    ]
}
```

这个序列直接喂给 Phoenix 排序模型作为 History，让 Transformer 学习用户的兴趣模式。

### 2. UserFeaturesQueryHydrator——"关注列表"

```rust
pub struct UserFeaturesQueryHydrator {
    strato_client: Arc<StratoClient>,
}

#[async_trait]
impl QueryHydrator<ScoredPostsQuery> for UserFeaturesQueryHydrator {
    async fn hydrate(&self, query: ScoredPostsQuery) -> ScoredPostsQuery {
        // 获取用户的关注列表
        let following_ids = self.strato_client
            .get_following(query.viewer_id)
            .await;
        
        // 获取用户的屏蔽/静音列表
        let blocked_ids = self.strato_client
            .get_blocked(query.viewer_id)
            .await;
        let muted_ids = self.strato_client
            .get_muted(query.viewer_id)
            .await;
        
        ScoredPostsQuery {
            user_features: UserFeatures {
                following_ids,
                blocked_ids,
                muted_ids,
                ..query.user_features
            },
            ..query
        }
    }
}
```

**关注列表用于两个地方：**
1. **ThunderSource**：告诉 Thunder "这个用户关注了谁"，Thunder 返回这些人的帖子
2. **AuthorSocialgraphFilter**：屏蔽/静音列表用于过滤

### 3. ThunderSource——In-Network 候选

```rust
pub struct ThunderSource {
    thunder_client: Arc<ThunderClient>,
}

#[async_trait]
impl Source<ScoredPostsQuery, PostCandidate> for ThunderSource {
    fn name(&self) -> &str { "ThunderSource" }
    
    async fn get(&self, query: &ScoredPostsQuery) -> Vec<PostCandidate> {
        // 1. 调用 Thunder 获取关注用户的帖子
        let posts = self.thunder_client
            .get_in_network_posts(
                query.viewer_id,
                &query.user_features.following_ids,
            )
            .await;
        
        // 2. 转换为 PostCandidate
        posts.into_iter()
            .map(|post| PostCandidate {
                tweet_id: post.id,
                author_id: post.author_id,
                in_network: Some(true),  // 标记为 In-Network
                ..Default::default()
            })
            .collect()
    }
}
```

**Thunder 返回的帖子特点：**
- 来源明确：全部来自用户关注的账号
- 时间范围：最近 7 天内
- 类型多样：原创、回复、转发、视频

### 4. PhoenixSource——Out-of-Network 候选

```rust
pub struct PhoenixSource {
    phoenix_client: Arc<PhoenixRetrievalClient>,
}

#[async_trait]
impl Source<ScoredPostsQuery, PostCandidate> for PhoenixSource {
    fn name(&self) -> &str { "PhoenixSource" }
    
    fn enable(&self, query: &ScoredPostsQuery) -> bool {
        // 如果请求只要 In-Network，则禁用
        !query.in_network_only
    }
    
    async fn get(&self, query: &ScoredPostsQuery) -> Vec<PostCandidate> {
        // 1. 调用 Phoenix 检索模型
        let retrieval_results = self.phoenix_client
            .retrieve(
                query.viewer_id,
                &query.user_action_sequence,
                top_k: 300,
            )
            .await;
        
        // 2. 转换为 PostCandidate
        retrieval_results.into_iter()
            .map(|result| PostCandidate {
                tweet_id: result.tweet_id,
                author_id: result.author_id,
                in_network: Some(false),  // 标记为 Out-of-Network
                ..Default::default()
            })
            .collect()
    }
}
```

**Phoenix 检索的过程：**
1. User Tower 编码用户行为序列 → 用户向量
2. 在预建的候选向量索引中 ANN 搜索
3. 返回 Top-300 最相似的帖子

### 5. 候选合并策略

两个 Source 并行执行，结果直接合并：

```
ThunderSource (并行)  ──→  80 条 In-Network
                                                ──→ 380 条合并候选
PhoenixSource (并行)  ──→ 300 条 Out-of-Network
```

合并后候选通过 `in_network` 字段区分来源。后续的评分器（如 OONScorer）会根据来源调整分数。

**In-Network vs Out-of-Network 的比例：**

在典型场景中，约 20-30% 是 In-Network（你关注的人发的内容），70-80% 是 Out-of-Network（算法推荐的内容）。但由于 In-Network 内容与用户的关联更强，最终信息流中两者的比例会更接近 50:50。

---

## 💡 本节小结

| 组件 | 数据源 | 获取内容 |
|------|--------|---------|
| UserActionSeqHydrator | UAS 服务 | 最近 500 条行为记录 |
| UserFeaturesHydrator | Strato | 关注/屏蔽/静音列表 |
| ThunderSource | Thunder gRPC | ~80 条关注用户帖子 |
| PhoenixSource | Phoenix Retrieval | ~300 条推荐帖子 |

---

## 📝 习题集12

**概念理解：**
1. 为什么 QueryHydrator 要并行执行？如果 UAS 服务响应慢，会发生什么？
2. `PhoenixSource` 的 `enable()` 方法根据 `in_network_only` 决定是否执行。这种设计的好处是什么？

**设计思考：**
3. 如果用户是新注册的（没有关注任何人，没有行为历史），这四个组件各自会返回什么？系统如何处理冷启动？
4. 为什么 Out-of-Network 候选数（300）远多于 In-Network（80）？

---

> 下一课我们将学习 **L13 - Hydration 与 Filtering 详解**。
