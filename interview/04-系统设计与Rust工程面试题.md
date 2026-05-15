# 04 - 系统设计与 Rust 工程面试题

> 覆盖系统架构、Rust 并发、微服务设计，结合 x-algorithm 工程实践。

---

## Q1: 设计一个推荐系统的候选管道框架 ⭐⭐⭐

**标准答案：**

定义核心 Trait：Source / Hydrator / Filter / Scorer / Selector / SideEffect

关键设计决策：
- Source 和 Hydrator 并行（无依赖）
- Filter 和 Scorer 顺序（有依赖）
- 使用 Builder 模式组装管道
- 每个组件 `enable()` 支持条件执行

**x-algorithm 实现：** `candidate-pipeline` crate，6 大 Trait + Pipeline 执行引擎。

---

## Q2: DashMap vs HashMap + Mutex 的使用场景？⭐⭐

| 方案 | 锁粒度 | 适用场景 |
|------|--------|---------|
| HashMap + Mutex | 全表锁 | 写少读多，简单场景 |
| HashMap + RwLock | 读共享/写独占 | 读远多于写 |
| **DashMap** | **分片锁** | **读写都频繁**（Thunder 场景） |

DashMap 将数据分为 N 个 shard，不同 shard 读写完全并行。

---

## Q3: 为什么 Thunder 选择内存存储而不是 Redis/数据库？⭐⭐

- 延迟：内存 <1ms vs Redis ~1-5ms vs DB ~10-50ms
- 数据模型：按用户分桶 + 三分类，自定义比通用数据库更高效
- 无持久化需求：帖子数据有权威来源（Kafka），Thunder 是缓存角色

---

## Q4: Rust 的 Arc<T> 和 Box<T> 什么时候用？⭐⭐

| 类型 | 堆/栈 | 共享 | x-algorithm 用途 |
|------|-------|------|-----------------|
| `Box<T>` | 堆分配 | 独占所有权 | Filter/Scorer trait 对象 |
| `Arc<T>` | 堆分配 | 多线程共享 | PostStore, Client 共享引用 |

---

## Q5: gRPC vs REST 在微服务通信中的对比？⭐⭐

| 维度 | gRPC | REST |
|------|------|------|
| 序列化 | Protobuf（二进制） | JSON（文本） |
| 大小 | 小 3-10x | 大 |
| 类型安全 | 编译时检查 | 运行时 |
| 流式 | 原生支持 | 不便 |

x-algorithm 选 gRPC：推荐系统内部通信量大，需要高效序列化。

---

## Q6: 如何设计 Semaphore 的 permits 数？⭐⭐

考虑因素：
- 单请求内存和 CPU 消耗
- 可接受的最大排队延迟
- 下游服务承受能力
- 一般设为：`min(下游承载 × 安全系数, 本机内存 / 单请求内存)`

---

## Q7: Kafka 消费者 Offset 管理策略？⭐⭐

- **自动提交**：定时提交，可能重复消费
- **手动提交**：处理完再提交，保证 at-least-once
- x-algorithm 用 at-least-once + 幂等插入（重复帖子自动覆盖）

---

## Q8: 如何实现服务的优雅降级？⭐⭐⭐

**x-algorithm 场景：** Phoenix GPU 集群故障时
1. PhoenixSource `enable()` 返回 false → 只用 Thunder（In-Network）
2. PhoenixScorer 降级为简单的启发式评分
3. 返回纯 In-Network 内容，质量降低但可用

---

## Q9: Builder 模式在 x-algorithm 中的应用？⭐

```rust
CandidatePipeline::builder()
    .source(Box::new(ThunderSource::new()))
    .filter(Box::new(AgeFilter::new(30 * 86400)))
    .scorer(Box::new(PhoenixScorer::new()))
    .build()
```

优势：声明式配置、编译时类型检查、易于 A/B 测试。

---

## Q10: 如何设计推荐系统的 A/B 测试框架？⭐⭐⭐

1. 用户分桶（hash(user_id) % 100）
2. 每个桶指定实验版本
3. 核心指标：CTR、停留时长、负面反馈率
4. 统计显著性检验（P值 < 0.05）
5. 自动回滚机制（负面指标恶化 >5%）

---

## Q11-Q20: （简略标题）

**Q11:** async/await 在 Rust 中的调度原理 ⭐⭐
**Q12:** 如何设计帖子的 TTL 过期策略？⭐
**Q13:** 微服务间的断路器模式 ⭐⭐
**Q14:** 如何对推荐管道进行端到端测试？⭐⭐
**Q15:** Protobuf 和 Thrift 序列化对比 ⭐
**Q16:** 如何监控推荐系统的健康状态？⭐⭐
**Q17:** 设计推荐系统的日志和追踪 ⭐⭐
**Q18:** VecDeque vs Vec 的选择依据 ⭐
**Q19:** 如何实现推荐结果的增量更新？⭐⭐⭐
**Q20:** 推荐系统的安全性考虑（注入攻击等）⭐⭐
