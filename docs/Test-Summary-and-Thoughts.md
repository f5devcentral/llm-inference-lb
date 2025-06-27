## Test Summary and Thoughts

### Heterogeneous Scenario: Two Nodes (one 1-GPU, one 4-GPU)

> **Test Dataset:** `ShareGPT_V3_unfiltered_cleaned_split.json`
>
> **Tokenization:** Standard tokenizer from the `transformer` library.
>
> **Environment:** Two GPU servers, one with a single GPU and the other with four GPUs using tensor parallelism. The performance difference between the two machines is not substantial. The 4-GPU machine's TTFT (Time To First Token) starts to increase significantly above 40-50 concurrent requests.
>
> - **1-GPU Machine:** Waiting requests increase after 160 concurrent requests.
> - **4-GPU Machine:** Waiting requests increase after 250 concurrent requests.

---

### 1. Low Concurrency Range (Under 40 Concurrent Requests)

In this range, both machines are under low load, below their TTFT and waiting request inflection points. Using a scheduler can reduce TTFT latency.

> The `s1_enhanced` algorithm performs best with `waiting` weight at 0.1 and `cache` weight at 0.9. (A 0.2/0.8 split for waiting/cache was found to be less effective).

![performance_comparison_s1_enhanced_tblb_vs_notblb](%E6%B5%8B%E8%AF%95%E6%80%BB%E7%BB%93%E4%B8%8E%E6%80%9D%E8%80%83.assets/performance_comparison_s1_enhanced_tblb_vs_notblb.png)

#### TBLB vs. No TBLB: Speed Improvement (%) with `s1_enhanced`

| Concurrency | Mean TTFT Speedup | Median TTFT Speedup | P99 TTFT Speedup | Mean TPOT Speedup | Median TPOT Speedup | P99 TPOT Speedup |
| :---------- | :---------------- | :------------------ | :--------------- | :---------------- | :------------------ | :--------------- |
| 10          | -16.48% ⬆️         | -28.05% ⬆️          | -19.11% ⬆️        | -16.88% ⬆️         | -2.85% ⬆️           | -4.90% ⬆️         |
| 20          | -7.02% ⬆️          | -7.64% ⬆️           | -9.24% ⬆️         | -13.75% ⬆️         | +5.01% ⬇️           | -11.41% ⬆️        |
| 30          | -3.98% ⬆️          | +5.51% ⬇️           | -1.46% ⬆️         | -11.54% ⬆️         | +10.91% ⬇️          | -15.89% ⬆️        |
| 40          | +0.24% ⬇️          | +15.41% ⬇️          | +18.37% ⬇️        | -5.47% ⬆️          | +23.93% ⬇️          | -13.10% ⬆️        |
| 50          | +0.44% ⬇️          | +13.38% ⬇️          | +5.97% ⬇️         | -2.36% ⬆️          | +27.25% ⬇️          | -21.29% ⬆️        |

#### 🚀 Speedup Trends

-   **TTFT (Time To First Token):**
    -   **Low Concurrency (10-20):** TBLB is significantly faster (7%-28% latency reduction).
    -   **Mid Concurrency (30):** TBLB is slightly faster (1.5%-4% latency reduction).
    -   **High Concurrency (40-50):** TBLB becomes slower (0.2%-18% latency increase). This is due to both machines hitting their performance inflection points.

-   **TPOT (Time Per Output Token):**
    -   **Mean TPOT:** TBLB is faster across all concurrencies (2.4%-16.9% latency reduction).
    -   **Median TPOT:** Faster at low concurrency but slower at high concurrency.
    -   **P99 TPOT:** TBLB is faster across all concurrencies (4.9%-21.3% latency reduction).

#### 🎯 Optimal Performance Scenarios

-   **10-20 Concurrency:** TBLB excels across almost all metrics.
-   The greatest TTFT improvement is at 10 concurrency (Median TTFT is 28% faster).
-   Mean TPOT improvement is most significant at low concurrency.

#### ⚠️ Performance Trade-offs

-   **High Concurrency (40-50):** TBLB underperforms `no-tblb` on TTFT as both machines become stressed.
-   **Median TPOT:** TBLB slows down at high concurrency, possibly due to resource contention.
-   **P99 Metrics:** TBLB consistently shows an advantage, indicating effective load balancing under extreme conditions.

---

### 2. High Concurrency Range 1 (100-300 Concurrent Requests)

Using the `s1_enhanced` algorithm (with various `waiting`/`cache` weights like 0.1/0.9, 0.2/0.8, 0.5/0.5), performance is roughly equivalent to having no TBLB.

![image-20250622232533043](%E6%B5%8B%E8%AF%95%E6%80%BB%E7%BB%93%E4%B8%8E%E6%80%9D%E8%80%83.assets/image-20250622232533043.png)

---

### 3. High Concurrency Range 2 (Over 300 Concurrent Requests)

Using the `s2_enhanced` algorithm with `waiting` and `cache` weights both at 0.5.

![s2_enhanced_performance_analysis](%E6%B5%8B%E8%AF%95%E6%80%BB%E7%BB%93%E4%B8%8E%E6%80%9D%E8%80%83.assets/s2_enhanced_performance_analysis.png)

#### 📊 Performance Analysis: TBLB vs. No TBLB (`s2_enhanced`)

##### 🎯 Key Findings

1.  **Excellent TTFT Performance:**
    -   Mean TTFT Improvement: **10.46%**
    -   Median TTFT Improvement: **12.27%**
    -   P99 TTFT Improvement: **11.40%**
    -   Max Improvement: **49.39%** (at 500 concurrency)
2.  **TPOT Performance Gains:**
    -   Mean TPOT Improvement: **3.10%**
    -   P99 TPOT Improvement: **5.48%**

##### 📈 Key Performance Patterns

1.  **Effective at High Concurrency:**
    -   At ≥400 concurrency, TBLB improves average TTFT by **21.24%**.
    -   At max concurrency (500), TTFT improvements range from **49%-61%**.
2.  **Stepped Improvement Curve:**
    -   Low Concurrency (100-150): 1%-3% improvement.
    -   Mid Concurrency (200-350): Stable 5%-8% improvement.
    -   High Concurrency (450-500): Significant 18%-49% improvement.
3.  **Significant Long-Tail Latency (P99) Reduction:**
    -   P99 TTFT improved in 7 out of 9 concurrency levels.
    -   The most significant P99 improvements occur at very high concurrency.

##### 🚀 Core Technical Advantages

1.  TBLB excels in high-concurrency scenarios, with benefits scaling with the number of concurrent requests.
2.  **400 concurrency is the inflection point** where TBLB's advantages become prominent.
3.  Significantly optimizes first-token response time, leading to a better user experience.
4.  Excellent control over long-tail latency, especially under heavy load.

| Concurrency Range | No TBLB      | TBLB         |
| ----------------- | ------------ | ------------ |
| <50               |              | Better       |
| 50-90             | Close (Slightly Better) |              |
| 90-300            | Similar      | Similar      |
| >300              |              | Better       |

#### Why is the scheduler better under 50 concurrency but less effective afterward?

| Concurrency | 1-GPU Load Status                                  | 4-GPU Available Capacity     | Scheduler Advantage                | Overall Performance |
| ----------- | -------------------------------------------------- | ---------------------------- | ---------------------------------- | ------------------- |
| 10          | Far below capacity                                 | Mostly idle                  | Precisely avoids the slower node   | Optimal             |
| 20          | Approaching sweet spot                             | Still has ample capacity     | Diversion clearly speeds up requests | Good                |
| 30          | Slightly overloaded, 4-GPU starts to feel pressure | Scheduler still effective      | Improvement diminishes             | -                   |
| **50**      | Load reduced, but 4-GPU hits its performance cliff (near saturation) | Scheduler "overloads" the stronger node, slowing it down | **Degrades**        | -                   |

---

### Summary of Test Patterns in this Heterogeneous Environment

-   When all nodes operate below their TTFT inflection points (no waiting requests), scheduling based on `cache` is effective.
-   When nodes are at or above their TTFT inflection point but have no waiting requests, metric-based scheduling is often no better than `least_conn`.
-   At high concurrency with waiting requests, scheduling based on `waiting` + `cache` is necessary.
-   **Avoid using the `running` metric in highly heterogeneous environments.**

In our specific test setup, the TTFT of the 1-GPU machine at 10 concurrency is close to the 4-GPU machine at 20 concurrency. Pushing requests beyond these numbers causes a sharp increase in TTFT that outweighs any scheduling gains. This matches the test results, where scheduling benefits disappear after ~30 total concurrent requests.

This outcome is specific to our environment where the two machines have a small performance gap. If the performance difference were large, a scheduler should still be effective. (In this test, the 4-GPU machine's cache utilization stayed around 20-25%, possibly due to inefficient cache use from tensor parallelism with a 4-byte model).

When all machines are busy and have waiting requests, a `waiting` + `cache` strategy with higher weight on `waiting` (e.g., 0.5/0.5) works well:

```yaml
w_a: 0.5  # Weight for waiting queue metric
w_b: 0.5 # Weight for cache usage metric
```

For identical nodes, a `waiting` + `running` + `cache` strategy can be used, but a higher `cache` weight might still be preferable if `running` metrics don't vary much under pressure. Observing scheduler logs is crucial for fine-tuning.

### Algorithm Comparison

![performance_comparison_alg_ttft](%E6%B5%8B%E8%AF%95%E6%80%BB%E7%BB%93%E4%B8%8E%E6%80%9D%E8%80%83.assets/performance_comparison_alg_ttft.png)

---

## Homogeneous Scenario: Five 1-GPU Machines

**Environment:** Five identical single-GPU nodes.
> `SERVER_LIST=("10.0.20.128:8000" "10.0.20.133:8000" "10.0.20.133:8001" "10.0.20.133:8002" "10.0.20.133:8003")`

For each test run, a background traffic load is applied to two machines (`10.0.20.128:8000` and `10.0.20.133:8000`). The background concurrency (50 requests each) is set above the single-node TTFT inflection point (which is ~30-40 concurrency). This keeps two nodes in a relatively high-stress state.

The main test load starts at 40 total concurrent requests and steps up by 20.
```
MAX_START=40
MAX_END=220
STEP=20
```
This simulates a 5-node pool where 2 nodes are consistently under high TTFT pressure.

### Test Results

| Concurrency | Mean TTFT | Median TTFT | P99 TTFT | Mean TPOT | Median TPOT | P99 TPOT |
| ----------- | --------- | ----------- | -------- | --------- | ----------- | -------- |
| 40          | +9.74%    | +1.53%      | +5.12%   | +15.03%   | -1.43%      | +12.66%  |
| 60          | +7.92%    | -0.28%      | +8.94%   | +12.29%   | -5.66%      | +16.46%  |
| 80          | +3.90%    | -4.76%      | -11.40%  | +9.92%    | -8.90%      | +18.31%  |
| 100         | -0.08%    | -7.00%      | +7.15%   | +6.41%    | -12.48%     | +18.99%  |
| 120         | -6.89%    | -13.27%     | -20.85%  | +2.35%    | -18.43%     | +20.51%  |
| 140         | -7.40%    | -14.17%     | +0.39%   | +1.84%    | -17.34%     | +20.37%  |
| 160         | -8.48%    | -14.94%     | -5.55%   | +1.74%    | -17.00%     | +20.47%  |
| 180         | -15.16%  | -13.67%     | -2.73%   | +1.15%    | -14.61%     | +18.56%  |
| 200         | -22.61%  | -10.92%     | -117.26% | +1.50%    | -12.56%     | +13.34%  |

*Note: Positive percentages indicate improvement (faster), negative percentages indicate degradation (slower).*

### Analysis

![image-20250624162317895](%E6%B5%8B%E8%AF%95%E6%80%BB%E7%BB%93%E4%B8%8E%E6%80%9D%E8%80%83.assets/image-20250624162317895.png)

The Grafana chart shows that with a simple `least_conn` algorithm (before 13:57), the two nodes with background traffic consistently handle ~80 requests each (including the 50 background requests). The other three nodes handle ~20 requests each. This means three nodes are in a low-TTFT state.

After 13:57, the TBLB scheduler is enabled. It correctly routes more traffic to the three lightly-loaded nodes and less to the two heavily-loaded ones. The scheduler's mechanism works as expected. However, the overall average client TTFT shows no improvement and hits a tipping point. This is because the three nodes now receiving more traffic are pushed into their non-linear TTFT growth zone (~30 requests each). While the two high-stress nodes received fewer new requests, they remained in a high-TTFT state (>50 requests). The gains from unloading the busy nodes were offset by the performance degradation of the newly stressed nodes.

![image-20250624154651612](%E6%B5%8B%E8%AF%95%E6%80%BB%E7%BB%93%E4%B8%8E%E6%80%9D%E8%80%83.assets/image-20250624154651612.png)

If the three idle nodes could have handled the new load while remaining below their inflection point (e.g., < 20-30 requests each), an overall improvement would have been observed. This is what happens at a total concurrency below 100: the three idle machines can efficiently process almost all requests. This reduces the load on the busy nodes without pushing the idle nodes past their tipping point, resulting in a net positive effect compared to `least_conn`.

### Problems and Reflections

This metric-based scheduling approach ruthlessly distributes load based on the *relative* values between nodes, without considering the absolute "healthy" operating range of a given node. It treats the GPUs as workhorses to be loaded based on metric differences. **Even if a node is already very busy, if its metrics are slightly better than others, it will be flooded with new connections, causing its TTFT to skyrocket and degrading the overall client experience.**

In contrast, `least_conn`, while not "smart" about pressure, allows the system to find a stable equilibrium where all nodes are roughly equally busy. It doesn't suddenly overload one particular node.

Therefore, metric-based scheduling for an unevenly loaded pool performs well only in specific ranges: either when all machines are well below their TTFT inflection point, or when all machines are so far past it that they all have similarly high TTFTs, creating a new window for optimization.

### Appendix

Tests were also run with random background traffic patterns using `s1_enhanced` and `s2_dynamic_waiting` algorithms. The results were not favorable.

![performance_comparison_s2_dynamic_waiting_tblb_vs_notblb](%E6%B5%8B%E8%AF%95%E6%80%BB%E7%BB%93%E4%B8%8E%E6%80%9D%E8%80%83.assets/performance_comparison_s2_dynamic_waiting_tblb_vs_notblb.png)

![performance_comparison_s1_enhanced_tblb_vs_notblb](%E6%B5%8B%E8%AF%95%E6%80%BB%E7%BB%93%E4%B8%8E%E6%80%9D%E8%80%83.assets/performance_comparison_s1_enhanced_tblb_vs_notblb-0828428.png) 