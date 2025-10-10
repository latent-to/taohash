# 🌀 TIDES FAQ – Frequently Asked Questions

## What is TIDES?

**TIDES (Time-based Incentivized Distribution of Earnings System)** is TAOHash's Bitcoin reward distribution protocol.  
It’s inspired by OCEAN’s Transparent Index of Distinct Extended Shares — a provably fair, variance-smoothing reward system that tracks every submitted share in order, calculates its value within a moving reward *window*, and distributes BTC accordingly.  

TIDES ensures that:
- Every miner receives **direct Bitcoin payouts** proportional to their verified share contributions.
- The system is **transparent and auditable**, meaning rewards can be verified from public share logs.
- Consistent miners earn **stable, predictable payouts** over time — no “pool hopping” or luck bias.

Registering your wallet on **Bittensor Subnet 14** unlocks an **additional 5% Alpha Token reward** based on your hashrate contribution.

---

## Do I need to join Bittensor to earn TIDES rewards?

**No!**  
TIDES BTC rewards are open to all miners connected to TAOHash — no Bittensor registration is required.  
Simply point your miner to the TAOHash Stratum endpoint, configure your payout address, and start earning.

---

## How does the reward system work?

TAOHash operates with **two parallel incentive systems**:

1. **TIDES BTC Rewards (All Miners)**  
   - Paid directly in Bitcoin.  
   - Based on your share contributions within the active TIDES window.  
   - Transparent and non-custodial — rewards are tied directly to block discovery.  

2. **Alpha Token Rewards (Bittensor Registered Miners)**  
   - +5% additional value relative to your hashrate.  
   - Denominated in Alpha Tokens (convertible to TAO).  
   - Encourages participation in Bittensor’s decentralized compute network.

---

## How are BTC rewards calculated?

TIDES follows a **share-weighted proportional system** with a sliding window that smooths variance and eliminates manipulation.

### 🔹 Core Concepts

| Term | Description |
|------|--------------|
| **Share** | A proof of work submitted by your miner. Each share represents measurable computational effort (hashrate × difficulty). |
| **Share Log** | Every valid share is appended to a global, ordered log. Nothing is discarded or overwritten. |
| **TIDES Window** | A moving range of shares whose total difficulty ≈ `network_difficulty × 8`. This window defines which shares are currently “eligible” for the next block’s reward. |
| **Proportional Split** | When a block is found, the BTC reward is split according to each miner’s share value inside the window:  
  `Your Reward = (Your Total Shares in Window / Total Window Shares) × Block Reward`. |

### 🔹 Window Mechanics

- The **window constantly slides forward**, always containing the newest shares and trimming the oldest to maintain total difficulty ≤ 8× network difficulty.  
- This means roughly *eight blocks worth* of shares are considered each time — a balance between fairness and stability.  
- When network difficulty changes, the window automatically resizes to maintain consistency.  
- Because the log is **never deleted**, all rewards remain verifiable and auditable.

### 🔹 Why It Matters

- **Smooth Payouts:** You don’t depend on lucky rounds — steady miners always average fair returns.  
- **No Pool Hopping Advantage:** Shares stay valid across windows, so timing your mining offers no exploit.  
- **Full Transparency:** The window composition and each miner’s contribution are visible in the dashboard.

---

## Example

Let’s simplify with an example:

- Network difficulty = `1,000,000`
- Window size = `8 × 1,000,000 = 8,000,000`
- Miner A contributed shares totaling `800,000` difficulty
- Miner B contributed `1,200,000`
- Miner C contributed `6,000,000`

If the pool finds a 6.25 BTC block:

- Miner A → (800,000 / 8,000,000) × 6.25 = **0.625 BTC**  
- Miner B → (1,200,000 / 8,000,000) × 6.25 = **0.9375 BTC**  
- Miner C → (6,000,000 / 8,000,000) × 6.25 = **4.6875 BTC**

This payout occurs after each block — no manual claiming or extra fees.

---

## When are BTC rewards distributed?

- **Lightning payouts:** Sent instantly — no minimum balance required.  
- **BTC on-chain payouts:** Require a minimum balance of $5 USD before being processed.  
- **Block discovery frequency:** TAOHash currently finds ~1–4 blocks per day depending on pool hashrate.  

---

## How can I check my BTC earnings?

- [TAOHash Leaderboard](https://taohash.com/leaderboard) – real-time rankings and share percentages.  
- **Dashboard:** Displays your contribution, current % in the TIDES window, and historical shares.  
- **Blockchain:** All BTC and Lightning payments are traceable via your configured address.

---

## What's the difference between TIDES and Alpha Tokens?

| Aspect | TIDES BTC Rewards | Alpha Tokens |
|--------|-------------------|--------------|
| **Eligibility** | All miners | Bittensor-registered miners only |
| **Payment Type** | Direct Bitcoin | Alpha Token (convertible to TAO) |
| **Distribution Basis** | Share value in active window | Hashprice × exchange rate |
| **Frequency** | Per block | Periodic (based on hashrate reporting) |
| **Purpose** | Fair BTC payouts | Ecosystem participation bonus |
| **Bonus Value** | — | +5% of hashrate value |

---

## How do I maximize my rewards?

### For All Miners (TIDES BTC)
1. **Mine Consistently** – Continuous hashing keeps your shares in the top of the window.  
2. **Avoid Pool Switching** – Leaving resets your share streak and removes you from the current window tail.  
3. **Use Efficient Hardware** – Higher hashrate = higher share difficulty = greater window weight.  
4. **Minimize Downtime** – Every missed share reduces your proportional weight.  

### For Bittensor Miners (+5% Alpha Tokens)
1. Register your hotkey on **Subnet 14**.  
2. Keep your registration active and bonded.  
3. Enjoy TIDES BTC + 5% Alpha incentive combined returns.

---

## Do I need special setup for BTC rewards?

No special configuration required.  
Just ensure:
1. Your BTC address or Lightning address is correctly set in your Stratum username.  
2. You’re connected to the TAOHash pool URL.  
3. Rewards are automatically distributed once thresholds are met.

---

## Can I track historical BTC payouts?

Yes — via:
- **[taohash.com/blocks](https://taohash.com/blocks)** – block-level reward transparency.  
- **Pool logs:** Each block shows which miners were within the TIDES window and their exact BTC share.  
- **Public explorers:** Verify every payout transaction to your wallet.

---

## Why TIDES Matters

TIDES represents the next generation of transparent Bitcoin mining reward systems.

| Problem (Old Pools) | TIDES Solution |
|----------------------|----------------|
| Pool-hopping exploits | Immutable share log + sliding window fairness |
| High payout variance | Extended 8-block smoothing window |
| Opaque reward accounting | Fully auditable share distribution |
| Operator risk or custodial funds | Non-custodial, on-block payments |
| Unfair luck weighting | Every share counts equally by work done |

---

## Ecosystem Impact

- **Open Access:** Anyone can mine and earn BTC instantly.  
- **Ecosystem Growth:** Bittensor miners receive Alpha bonuses for participation.  
- **Transparent Incentives:** Verifiable fairness builds miner trust.  
- **Sustainable Model:** BTC rewards + Alpha yield ensures long-term economic health.  

---

## Support

Need help?  
- **GitHub Issues:** [latent-to/taohash/issues](https://github.com/latent-to/taohash/issues)  
- **Discord:** TAOHash channel in the Bittensor Discord  
- **Docs:** [taohash.com/docs](https://taohash.com/docs)

---
