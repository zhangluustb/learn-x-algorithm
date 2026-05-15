# L03 - Rust & Python 技术栈快速上手

> **"工欲善其事，必先利其器——读懂 x-algorithm 需要两把钥匙：Rust 和 JAX。"**

---

## 📌 本节目标

1. 掌握 Rust trait 系统与异步编程的核心概念
2. 了解 Python JAX/Haiku 框架的基本用法
3. 理解 gRPC 服务通信的工作方式
4. 认识 Kafka 消息队列在系统中的角色

---

## 📚 前置知识

- 任意一门编程语言的基础（变量、函数、控制流）
- 不需要 Rust 或 JAX 经验（我们从零讲起关键概念）

---

## 正文讲解

### 1. Rust Trait 系统——x-algorithm 的骨架

> **类比**：Trait 就像"职业资格证"。一个类型实现了 `Filter` trait，就像一个人考了"过滤师"证书——系统知道它能执行过滤操作，但不关心它具体怎么过滤。

在 x-algorithm 的 `candidate-pipeline` 中，整个管道框架都建立在 trait 之上：

```rust
// 定义 trait：规定"能做什么"
#[async_trait]
pub trait Filter<Q, C>: Send + Sync {
    fn name(&self) -> &str;
    fn enable(&self, query: &Q) -> bool { true }
    async fn filter(&self, query: &Q, candidates: Vec<C>) 
        -> FilterResult<C>;
}

// 实现 trait：规定"具体怎么做"
pub struct AgeFilter { max_age_seconds: u64 }

#[async_trait]
impl Filter<ScoredPostsQuery, PostCandidate> for AgeFilter {
    fn name(&self) -> &str { "AgeFilter" }
    async fn filter(&self, query: &_, candidates: Vec<_>) 
        -> FilterResult<_> {
        // 移除超过 max_age_seconds 的帖子
    }
}
```

**x-algorithm 中的六大 Trait：**

| Trait | 输入 | 输出 | 用途 |
|-------|------|------|------|
| `Source<Q,C>` | Query | Vec\<Candidate\> | 生成候选 |
| `Hydrator<Q,C>` | Query + Candidates | enriched Candidates | 补全数据 |
| `Filter<Q,C>` | Query + Candidates | keep / remove 分区 | 过滤 |
| `Scorer<Q,C>` | Query + Candidates | scored Candidates | 打分 |
| `Selector<Q,C>` | Query + Candidates | top-K Candidates | 选择 |
| `SideEffect<Q,C>` | Query + Candidates | () | 副作用 |

#### 1.2 异步编程基础

Rust 的 `async/await` 让 I/O 密集型操作不阻塞线程：

```rust
// 同步：线程等待网络响应
let posts = thunder_client.get_posts(user_id);  // 阻塞

// 异步：线程可以去做别的事
let posts = thunder_client.get_posts(user_id).await;  // 不阻塞
```

x-algorithm 大量使用异步操作：gRPC 调用、Kafka 消费、并行数据获取都是 async 的。

#### 1.3 常用 Rust 类型

```rust
Arc<T>          // 线程安全的引用计数智能指针
DashMap<K, V>   // 并发安全的 HashMap（Thunder 用来存帖子）
VecDeque<T>     // 双端队列（帖子按时间排列）
Box<dyn Trait>  // Trait 对象，运行时多态
Option<T>       // 可能有值也可能没有（替代 null）
```

### 2. Python JAX/Haiku——Phoenix 的基石

> **类比**：如果 PyTorch 是"自动挡汽车"，JAX 就是"手动挡跑车"——更底层、更快、更可控，但需要对底层原理有更好的理解。

#### 2.1 JAX 核心概念

```python
import jax
import jax.numpy as jnp

# JAX 数组（不可变！）
x = jnp.array([1.0, 2.0, 3.0])

# 自动微分
grad_fn = jax.grad(lambda x: jnp.sum(x ** 2))
gradients = grad_fn(x)  # [2.0, 4.0, 6.0]

# JIT 编译加速
@jax.jit
def fast_matmul(a, b):
    return a @ b

# 批量化
batched_fn = jax.vmap(single_example_fn)
```

**JAX 三大利器：**

| 功能 | API | 用途 |
|------|-----|------|
| 自动微分 | `jax.grad` | 计算梯度（训练） |
| JIT 编译 | `jax.jit` | 编译为 XLA 高性能代码 |
| 批量化 | `jax.vmap` | 单样本函数自动变批量 |

#### 2.2 Haiku：DeepMind 的神经网络库

Haiku 是 JAX 上的神经网络构建工具，风格类似 Sonnet：

```python
import haiku as hk

class MyLinear(hk.Module):
    def __init__(self, output_size, name=None):
        super().__init__(name=name)
        self.output_size = output_size
    
    def __call__(self, x):
        # hk.get_parameter 自动管理参数
        w = hk.get_parameter("w", 
            shape=[x.shape[-1], self.output_size],
            init=hk.initializers.RandomNormal())
        return x @ w

# 转换为纯函数（JAX 要求）
def forward(x):
    return MyLinear(64)(x)

model = hk.transform(forward)
params = model.init(rng_key, sample_input)
output = model.apply(params, rng_key, real_input)
```

在 Phoenix 的 `grok.py` 中，所有组件都是 `hk.Module` 的子类：

```python
class RMSNorm(hk.Module): ...
class Linear(hk.Module): ...
class RotaryEmbedding(hk.Module): ...
class MultiHeadAttention(hk.Module): ...
class DecoderLayer(hk.Module): ...
class Transformer(hk.Module): ...
```

### 3. gRPC 服务通信

> **类比**：gRPC 就像一份"合同模板"——服务端和客户端都签了同一份合同（.proto 文件），双方都知道该发什么格式的数据、期望收到什么格式的回复。

x-algorithm 中的 gRPC 服务：

| 服务 | 端点 | 功能 |
|------|------|------|
| **Thunder** | `GetInNetworkPosts` | 获取关注用户的帖子 |
| **Home Mixer** | `GetScoredPosts` | 获取排好序的信息流 |
| **Phoenix** | 模型推理 API | 检索/排序预测 |

```
客户端（Home Mixer）                   服务端（Thunder）
    │                                      │
    │──── GetInNetworkPosts(user_id) ─────►│
    │     [Protobuf 序列化, Zstd 压缩]      │
    │                                      │── 查询 PostStore
    │◄──── Vec<LightPost> ────────────────│
    │     [Protobuf 反序列化]               │
```

**gRPC 的优势：**
- 基于 HTTP/2，支持多路复用
- Protobuf 序列化比 JSON 小 3-10 倍
- 强类型，编译时检查接口一致性
- 支持流式传输

### 4. Kafka 消息队列

> **类比**：Kafka 就像一个"公告栏"——发帖的人把消息钉上去，看板的人随时来取。消息不会因为取了就消失，可以反复读取。

在 Thunder 中，Kafka 负责实时推送帖子事件：

```
帖子服务 ──► Kafka Topic ──► Thunder Consumer
                │
                ├── 创建帖子事件 → insert_posts()
                └── 删除帖子事件 → mark_as_deleted()
```

**关键概念：**

| 概念 | 说明 |
|------|------|
| Topic | 消息分类（如 "tweet-events"） |
| Partition | Topic 内的并行分片 |
| Consumer Group | 多个消费者协同处理 |
| Offset | 消费位置指针 |

---

## 💡 本节小结

| 技术 | x-algorithm 中的角色 |
|------|---------------------|
| Rust Trait | 定义管道框架的六大抽象（Source/Filter/Scorer...） |
| async/await | 所有网络 I/O 和并行操作的基础 |
| JAX/Haiku | Phoenix ML 模型的实现框架 |
| gRPC | 模块间高效通信 |
| Kafka | Thunder 实时接收帖子事件流 |

---

## 📝 习题集3

**概念理解：**
1. Rust 的 `Box<dyn Filter>` 和泛型 `T: Filter` 有什么区别？x-algorithm 为什么选择 trait 对象？
2. JAX 的 `jax.jit` 做了什么？为什么能加速计算？

**代码实践：**
3. 用 Rust 写一个简单的 `Filter` trait 实现，过滤掉长度超过 280 字符的帖子。
4. 用 JAX/Haiku 实现一个简单的两层 MLP。

**设计思考：**
5. x-algorithm 为什么选择 gRPC 而不是 REST API 进行模块间通信？
6. 如果 Kafka 发生延迟，Thunder 中的帖子会出现什么问题？如何应对？

---

> 下一课我们将学习 **L04 - x-algorithm 项目导览**，深入源码目录结构和数据流。
