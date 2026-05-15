# L06 - Thunder 实时帖子存储引擎

> **"在推荐系统中，'快'不是优势，而是生命线——Thunder 用纯内存实现亚毫秒级帖子查询。"**

---

## 📌 本节目标

1. 理解 PostStore 的数据结构设计
2. 掌握 Kafka 事件消费流程
3. 了解按用户分桶的存储策略
4. 理解 TTL 过期与并发控制机制

---

## 📚 前置知识

- L03 中的 Rust 并发基础
- L05 中的 Source trait

---

## 正文讲解

### 1. PostStore——纯内存帖子仓库

> **类比**：PostStore 就像一个巨大的"快递柜"——每个用户有自己的柜子，柜子里按时间排列着最近的帖子。超过 7 天的帖子自动清理，腾出空间。

```rust
pub struct PostStore {
    // 全量帖子索引：帖子ID → 帖子详情
    posts: Arc<DashMap<i64, LightPost>>,
    
    // 按用户分桶（3 个独立队列）
    original_posts_by_user: Arc<DashMap<i64, VecDeque<TinyPost>>>,
    secondary_posts_by_user: Arc<DashMap<i64, VecDeque<TinyPost>>>,  // 回复+转发
    video_posts_by_user: Arc<DashMap<i64, VecDeque<TinyPost>>>,
    
    // 删除标记
    deleted_posts: Arc<DashMap<i64, bool>>,
    
    // 配置
    retention_seconds: u64,  // 默认 604800（7天）
    request_timeout: Duration,
}
```

**为什么用 `DashMap` 而不是 `HashMap + Mutex`？**

| 方案 | 读写 | 适用场景 |
|------|------|---------|
| `HashMap + Mutex` | 全局锁，读写互斥 | 写多读少 |
| `HashMap + RwLock` | 读共享，写独占 | 读多写少 |
| **`DashMap`** | 分片锁，细粒度并发 | **读写都多**（Thunder 的场景） |

`DashMap` 内部将数据分为多个 shard，不同 shard 的读写可以完全并行。对于 Thunder 这种同时接收大量写入（Kafka 事件）和大量读取（gRPC 查询）的场景，`DashMap` 是最佳选择。

### 2. Kafka 事件消费

Thunder 通过 Kafka 实时接收两种事件：

```
Kafka 帖子主题
    │
    ├── 帖子创建事件 → PostStore::insert_posts()
    │   包含：帖子ID、作者ID、文本、创建时间、
    │         是否是回复、是否是转发、是否有视频
    │
    └── 帖子删除事件 → PostStore::mark_as_deleted()
        包含：帖子ID
```

**消费流程：**

```rust
// 简化的 Kafka 消费循环
loop {
    let events = kafka_consumer.poll().await;
    for event in events {
        match event {
            TweetCreateEvent(post) => {
                // 检查是否在保留期内
                if post.age() < retention_seconds {
                    post_store.insert_posts(vec![post]);
                }
            }
            TweetDeleteEvent(id) => {
                post_store.mark_as_deleted(vec![id]);
            }
        }
    }
}
```

### 3. 按用户三桶分类

为什么要把帖子分成三个队列？因为不同类型的帖子在推荐中的权重不同：

| 队列 | 内容 | 推荐意义 |
|------|------|---------|
| `original_posts_by_user` | 用户的原创帖子 | 最高优先级，核心创作内容 |
| `secondary_posts_by_user` | 回复 + 转发 | 社交互动信号 |
| `video_posts_by_user` | 视频帖子 | 单独追踪，视频有特殊排序逻辑 |

**数据结构选择——VecDeque：**

```rust
#[derive(Clone)]
pub struct TinyPost {
    post_id: i64,
    created_at: i64,  // Unix 秒时间戳
}
```

> **类比**：`VecDeque` 就像一条"传送带"——新帖子从一端放入，过期帖子从另一端移除。始终保持按时间排序。

```
新帖子 →  [最新] [较新] [较旧] [最旧]  → 过期移除
           push_front()          pop_back()
```

### 4. 插入与查询

#### 4.1 插入帖子

```rust
impl PostStore {
    pub fn insert_posts(&self, posts: Vec<LightPost>) {
        for post in posts {
            // 1. 检查保留期
            if post.age_seconds() > self.retention_seconds {
                continue;
            }
            
            // 2. 存入全量索引
            self.posts.insert(post.id, post.clone());
            
            // 3. 按类型存入对应用户队列
            let tiny = TinyPost { 
                post_id: post.id, 
                created_at: post.created_at 
            };
            
            if post.has_video {
                self.video_posts_by_user
                    .entry(post.author_id)
                    .or_default()
                    .push_front(tiny.clone());
            }
            
            if post.is_reply || post.is_retweet {
                self.secondary_posts_by_user
                    .entry(post.author_id)
                    .or_default()
                    .push_front(tiny);
            } else {
                self.original_posts_by_user
                    .entry(post.author_id)
                    .or_default()
                    .push_front(tiny);
            }
        }
    }
}
```

#### 4.2 查询用户帖子

```rust
pub fn get_posts_by_users(&self, user_ids: &[i64]) -> Vec<LightPost> {
    let mut results = Vec::new();
    
    for &user_id in user_ids {
        // 从三个队列中收集
        for store in [
            &self.original_posts_by_user,
            &self.secondary_posts_by_user,
            &self.video_posts_by_user,
        ] {
            if let Some(posts) = store.get(&user_id) {
                for tiny in posts.iter() {
                    // 跳过已删除的
                    if self.deleted_posts.contains_key(&tiny.post_id) {
                        continue;
                    }
                    // 跳过过期的
                    if tiny.is_expired(self.retention_seconds) {
                        continue;
                    }
                    if let Some(post) = self.posts.get(&tiny.post_id) {
                        results.push(post.clone());
                    }
                }
            }
        }
    }
    results
}
```

### 5. TTL 过期与自动裁剪

Thunder 有两层过期机制：

**懒过期（查询时）**：查询时跳过过期帖子，不立即删除。

**主动裁剪（定时任务）**：

```rust
pub fn start_auto_trim(&self, interval: Duration) {
    // 每隔 interval 扫描所有用户队列
    // 从尾部（最旧）开始移除过期帖子
    loop {
        sleep(interval).await;
        
        for store in [original, secondary, video] {
            for mut entry in store.iter_mut() {
                let deque = entry.value_mut();
                while let Some(back) = deque.back() {
                    if back.is_expired(self.retention_seconds) {
                        deque.pop_back();
                        self.posts.remove(&back.post_id);
                    } else {
                        break;  // VecDeque 有序，后面都没过期
                    }
                }
            }
        }
    }
}
```

### 6. gRPC 服务与并发控制

```rust
struct ThunderServiceImpl {
    post_store: Arc<PostStore>,
    strato_client: Arc<StratoClient>,
    request_semaphore: Arc<Semaphore>,  // 限制并发请求数
}
```

**Semaphore 的作用：**

> **类比**：Semaphore 就像餐厅的等位系统——最多同时服务 N 桌客人。新客人来时，如果已满，就排队等待。

```rust
async fn get_in_network_posts(&self, request: Request) -> Response {
    // 获取许可（如果已满则等待）
    let _permit = self.request_semaphore.acquire().await;
    
    // 执行查询
    let posts = self.post_store
        .get_posts_by_users(&request.following_list);
    
    // 返回（permit 自动释放）
    Response::new(posts)
}
```

**关键监控指标：**

| 指标 | 含义 |
|------|------|
| `FOUND_FRESHNESS_SECONDS` | 最新帖子的年龄 |
| `FOUND_TIME_RANGE_SECONDS` | 最新到最旧帖子的时间跨度 |
| `FOUND_UNIQUE_AUTHORS` | 结果中的不同作者数 |
| `FOUND_REPLY_RATIO` | 回复帖占比 |

---

## 💡 本节小结

| 概念 | 一句话总结 |
|------|-----------|
| PostStore | 基于 DashMap 的线程安全内存帖子存储 |
| 三桶分类 | 原创/转发回复/视频分别存储，支持差异化推荐 |
| Kafka 消费 | 实时接收帖子创建/删除事件 |
| TTL 裁剪 | 懒过期 + 定时主动清理双重机制 |
| Semaphore | 限制并发请求数，防止过载 |

---

## 📝 习题集6

**代码阅读：**
1. 在 `post_store.rs` 中，`insert_posts` 为什么要先检查帖子年龄？
2. `DashMap` 的 `entry().or_default()` 是什么模式？它解决了什么问题？

**设计思考：**
3. 如果关注用户有 10 万个，每人平均 50 条帖子，Thunder 需要多少内存？怎么估算？
4. 懒过期和主动裁剪各有什么优缺点？为什么 Thunder 两者都用？
5. 如果 Kafka 短暂宕机 5 分钟，Thunder 的数据会有什么问题？恢复后如何处理？

---

> 下一课我们将进入 Phoenix 模型的核心——**L07 - Phoenix Grok 模型架构（上）：Transformer 核心**。
