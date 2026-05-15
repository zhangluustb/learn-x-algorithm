# L13 - Hydration 与 Filtering 详解

> **"推荐系统的质量，取决于你丢掉了什么——好的过滤器让用户永远看不到不该看到的内容。"**

---

## 📌 本节目标

1. 理解五大 Hydrator 各自的职责
2. 逐一解析十大 Pre-Selection Filter
3. 理解过滤顺序的工程考量
4. 掌握 FilterResult 与候选追踪

---

## 📚 前置知识

- L05 中的 Hydrator/Filter trait
- L11-L12 中的管道组装

---

## 正文讲解

### 1. 五大 Hydrator——给候选"填履历"

候选从 Source 出来时只有 `tweet_id` 和 `author_id`——就像只知道名字的陌生人。Hydrator 负责"调查背景"：

| Hydrator | 数据源 | 填充的字段 |
|----------|--------|-----------|
| **InNetworkCandidateHydrator** | following list | `in_network: bool` |
| **CoreDataCandidateHydrator** | TweetyPie 服务 | `tweet_text, created_at, in_reply_to, retweeted_*, media` |
| **GizmoduckCandidateHydrator** | Gizmoduck 服务 | `author_followers_count, author_screen_name` |
| **VideoDurationCandidateHydrator** | Media 服务 | `video_duration_ms` |
| **SubscriptionHydrator** | 订阅服务 | `subscription_author_id` |

#### InNetworkCandidateHydrator

```rust
async fn hydrate(&self, query: &Q, candidates: Vec<PostCandidate>) 
    -> Vec<PostCandidate> 
{
    let following_set: HashSet<u64> = 
        query.user_features.following_ids.iter().copied().collect();
    
    candidates.into_iter()
        .map(|mut c| {
            c.in_network = Some(following_set.contains(&c.author_id));
            c
        })
        .collect()
}
```

#### CoreDataCandidateHydrator

```rust
async fn hydrate(&self, _query: &Q, candidates: Vec<PostCandidate>) 
    -> Vec<PostCandidate> 
{
    // 批量获取帖子元数据（一次 RPC 调用）
    let tweet_ids: Vec<i64> = candidates.iter()
        .map(|c| c.tweet_id)
        .collect();
    
    let tweet_data = self.tweetypie_client
        .get_tweets(&tweet_ids)
        .await;
    
    // 填充数据
    candidates.into_iter()
        .map(|mut c| {
            if let Some(data) = tweet_data.get(&c.tweet_id) {
                c.tweet_text = data.text.clone();
                c.in_reply_to_tweet_id = data.in_reply_to;
                c.retweeted_tweet_id = data.retweeted_id;
                // ... 更多字段
            }
            c  // 即使获取失败也保留候选（后续 Filter 会处理）
        })
        .collect()
}
```

### 2. 十大 Pre-Selection Filter

过滤器按**从粗到细**的顺序排列，每一层筛掉一类问题：

```
380 条合并候选
    │
    ├── ① DropDuplicatesFilter    → 去除重复帖子 ID
    ├── ② CoreDataHydrationFilter → 去除数据获取失败的帖子
    ├── ③ AgeFilter               → 去除超过 30 天的帖子
    ├── ④ SelfTweetFilter         → 去除用户自己发的帖子
    ├── ⑤ RetweetDeduplicationFilter → 同一原帖的转发只保留一条
    ├── ⑥ IneligibleSubscriptionFilter → 去除付费内容(用户未订阅)
    ├── ⑦ PreviouslySeenPostsFilter → 去除已浏览过的帖子
    ├── ⑧ PreviouslyServedPostsFilter → 去除本次会话已推送过的
    ├── ⑨ MutedKeywordFilter       → 去除含静音关键词的帖子
    └── ⑩ AuthorSocialgraphFilter  → 去除屏蔽/静音作者的帖子
    │
    ▼
约 250 条候选进入评分
```

#### ① DropDuplicatesFilter

```rust
async fn filter(&self, _query: &Q, candidates: Vec<PostCandidate>) 
    -> FilterResult<PostCandidate> 
{
    let mut seen = HashSet::new();
    let (kept, removed): (Vec<_>, Vec<_>) = candidates
        .into_iter()
        .partition(|c| seen.insert(c.tweet_id));
    
    FilterResult { kept, removed }
}
```

> Thunder 和 Phoenix 可能返回同一条帖子（一条热门帖子既是关注用户发的，又被推荐算法选中），需要去重。

#### ③ AgeFilter

```rust
async fn filter(&self, _query: &Q, candidates: Vec<PostCandidate>) 
    -> FilterResult<PostCandidate> 
{
    let now = SystemTime::now();
    candidates.into_iter()
        .partition(|c| {
            c.created_at
                .map(|t| now.duration_since(t).unwrap().as_secs() 
                     < self.max_age_seconds)
                .unwrap_or(false)  // 没有创建时间的也过滤
        })
}
```

#### ⑤ RetweetDeduplicationFilter

```rust
async fn filter(&self, _query: &Q, candidates: Vec<PostCandidate>) 
    -> FilterResult<PostCandidate> 
{
    let mut seen_originals = HashSet::new();
    candidates.into_iter()
        .partition(|c| {
            match c.retweeted_tweet_id {
                Some(original_id) => seen_originals.insert(original_id),
                None => true,  // 非转发，保留
            }
        })
}
```

> 如果 10 个人都转发了同一条帖子，只保留第一条转发——避免信息流刷屏。

#### ⑨ MutedKeywordFilter

```rust
async fn filter(&self, query: &Q, candidates: Vec<PostCandidate>) 
    -> FilterResult<PostCandidate> 
{
    let muted_keywords = &query.user_features.muted_keywords;
    candidates.into_iter()
        .partition(|c| {
            let text = c.tweet_text.to_lowercase();
            !muted_keywords.iter().any(|kw| text.contains(kw))
        })
}
```

#### ⑩ AuthorSocialgraphFilter

```rust
async fn filter(&self, query: &Q, candidates: Vec<PostCandidate>) 
    -> FilterResult<PostCandidate> 
{
    let blocked = &query.user_features.blocked_ids;
    let muted = &query.user_features.muted_ids;
    
    candidates.into_iter()
        .partition(|c| {
            !blocked.contains(&c.author_id) 
            && !muted.contains(&c.author_id)
        })
}
```

### 3. 过滤顺序的工程考量

为什么按这个顺序排列？

| 原则 | 说明 | 示例 |
|------|------|------|
| **快→慢** | 计算简单的先执行 | DropDuplicates（O(1) HashSet）在前 |
| **多→少** | 过滤比例大的先执行 | 去重可能过滤 5-10% |
| **依赖顺序** | 依赖数据的 Filter 排在 Hydrator 之后 | CoreDataHydrationFilter 需要先 Hydrate |
| **安全优先** | 安全相关的不能遗漏 | AuthorSocialgraph 必须执行 |

### 4. Post-Selection Filter

选择 Top-50 后，还有两道"安全防线"：

#### VFFilter（Visibility Filtering）

```rust
// 检查帖子是否因以下原因被标记不可见：
// - 已删除
// - 被判定为垃圾信息
// - 包含暴力/血腥内容
// - 违反平台政策
// - 法律原因不可显示
async fn filter(&self, _query: &Q, candidates: Vec<PostCandidate>) 
    -> FilterResult<PostCandidate> 
{
    candidates.into_iter()
        .partition(|c| c.visibility_reason.is_none())
}
```

#### DedupConversationFilter

```rust
// 同一个对话线程只保留一条帖子
// 防止信息流被同一话题的多条回复占据
async fn filter(&self, _query: &Q, candidates: Vec<PostCandidate>) 
    -> FilterResult<PostCandidate> 
{
    let mut seen_conversations = HashSet::new();
    candidates.into_iter()
        .partition(|c| {
            let conversation_id = c.in_reply_to_tweet_id
                .unwrap_or(c.tweet_id as u64);
            seen_conversations.insert(conversation_id)
        })
}
```

---

## 💡 本节小结

| 阶段 | 数量 | 执行方式 | 核心职责 |
|------|------|---------|---------|
| Hydration | 5 个 | 并行 | 补全帖子元数据 |
| Pre-Selection Filters | 10 个 | 顺序 | 去重、去旧、去违规 |
| Post-Selection Filters | 2 个 | 顺序 | 安全兜底、对话去重 |

---

## 📝 习题集13

**代码阅读：**
1. `CoreDataHydrationFilter` 是如何判断一个候选"数据获取失败"的？
2. `RetweetDeduplicationFilter` 保留的是"第一条转发"——这个"第一条"是按什么顺序的？

**设计思考：**
3. 如果要新增一个 Filter 过滤"没有图片或视频的纯文字帖子"，应该插在哪个位置？为什么？
4. Pre-Selection 和 Post-Selection 为什么要分开？VFFilter 为什么不放在 Pre-Selection？

---

> 下一课我们将学习 **L14 - Scoring 全链路：从 ML 预测到最终排分**。
