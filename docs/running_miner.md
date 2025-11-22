# TAOHash Mining Guide

This guide will walk you through setting up and running a TaoHash miner on the Bittensor network.

As of now, TAOHash support Bitcoin and Bitcoin Cash mining protocols.

TaoHash enables miners to contribute hashpower to collective mining pools. All miners direct their hashpower to a single subnet pool for that specific coin, where validators evaluate and rank miners based on the share value they generate.

TAOHash miners earn from **two independent reward systems**, both designed to fairly and transparently compensate you for your computational contributions.

### 1. TIDES BTC/BCH Rewards (All Miners)

The **TIDES protocol** provides direct mining payouts to **all** miners connected to TAOHash — no Bittensor registration required.

- **Open Access:** Anyone can mine and earn BTC/BCH instantly.  
- **Calculation:** Rewards are determined using a *sliding window* equal to `network_difficulty × 8`, roughly covering the last eight blocks of work.  
- **Proportional Distribution:** Your share of the window determines your share of BTC/BCH rewards.  
- **Direct Payment:** BTC/BCH is automatically sent to your configured address (on-chain or Lightning).  
- **Regular Disbursements:** Based on real pool block discoveries — typically multiple per day.  

#### How It Works
TIDES tracks every valid share in a global log.  
When a block is found:
1. The window is filled with the most recent shares until the total difficulty ≈ 8× the network difficulty.  
2. Each miner’s proportional share difficulty in that window determines their cut of the BTC/BCH reward.  
3. The window slides forward, and the process repeats for the next block.  

This ensures fairness, smooths variance, and prevents “pool-hopping” — your consistent hashrate always earns consistent rewards.

---

### 2. Alpha Token Rewards (Bittensor Registered Miners)

Bittensor’s **Subnet 14** adds a second layer of incentives for miners who register their wallet and hotkey.

- **+5% Value Back:** Earn Alpha tokens worth 5% of your contributed hashpower’s value.  
- **Value Basis:** Calculated using real-time **hashprice index** and BTC/TAO or BCH/TAO exchange rates.  
- **Eligibility:** Requires registration on **Bittensor Subnet 14**.  
- **Continuous Accumulation:** Tokens accrue automatically as you mine.  
- **Convertibility:** Alpha tokens can be unstaked or swapped to TAO for liquidity.  

This mechanism ties your physical mining to the decentralized compute economy of Bittensor — rewarding both immediate work (BTC/BCH) and long-term network participation (Alpha).
Alpha rewards are disbursed through Bittensor's incentive mechanism every tempo (~72 minutes). These rewards are irrespective whether the pool found a block or not. 

---

See also:

- [Introduction to TAOHash](../README.md)
- [TIDES FAQ - Understanding BTC Rewards](./tides_faq.md)
- [Introduction to Bittensor](https://docs.learnbittensor.org/learn/introduction)
- [Yuma Consensus](https://docs.learnbittensor.org/yuma-consensus/)
- [Emissions](https://docs.learnbittensor.org/emissions/)


## Prerequisites

To run a TaoHash miner, you will need:

- A Bittensor wallet with coldkey and hotkey
- Bitcoin mining hardware (ASICs, GPUs, etc.) OR access to remote hashrate (NiceHash, MiningRigRentals)
- Python 3.9 or higher
- The most recent release of [Bittensor SDK](https://pypi.org/project/bittensor/)
- (Optional, for miner proxy usage): Docker & Docker Compose

Bittensor Docs:

- [Wallets, Coldkeys and Hotkeys in Bittensor](https://docs.learnbittensor.org/getting-started/wallets)
- [Miner registration](./miners/index.md#miner-registration)

## Quick Start

### Wallet Setup

Check your wallet, or create one if you have not already.

Bittensor Documentation: [Creating/Importing a Bittensor Wallet
](https://docs.learnbittensor.org/working-with-keys)

```bash
btcli wallet list
```
```console
Wallets
├── Coldkey YourColdkey  ss58_address 5F...
│   ├── Hotkey YourHotkey  ss58_address
│   │   5E...
```

```bash
btcli wallet balance \
--wallet.name <your wallet name> \
--network finney
```

```console
                             Wallet Coldkey Balance
                                  Network: finney

    Walle…   Coldkey Address                             Free…   Stake…   Total…
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    realm…   5DvSxCaMW9tCPBS4TURmw4hDzXx5Bif51jq4baC6…   …       …        …



    Total…                                               …       …        …
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Register on subnet 14 (mainnet)

#### Check registration status

```bash
btcli wallet overview btcli wallet overview --netuid 14
```

#### Register

```bash
btcli subnet register --netuid 14 --wallet.name <YOUR_WALLET> --wallet.hotkey <YOUR_HOTKEY> --network finney
```

### Step 2: Get Pool Information
Fetch your mining pool configuration:

```bash
# Clone the repository
git clone https://github.com/latent-to/taohash.git
cd taohash

# Install dependencies
pip install -e .

# Get your mining configuration
python taohash/miner/miner.py \
    --wallet.name <YOUR_WALLET> \
    --wallet.hotkey <YOUR_HOTKEY> \
    --subtensor.network finney \
    --btc_address <YOUR_BTC_ADDRESS>
```

This outputs your pool configuration:
```
=== SUBNET POOL CONFIGURATION ===

Normal Pool:
  URL: 178.156.163.146:3331
  Worker: <YOUR_BTC_ADDRESS>.5EX7d4Eu
  Password: x

High Difficulty Pool:
  URL: 178.156.163.146:3332
  Worker: <YOUR_BTC_ADDRESS>.5EX7d4Eu
  Password: x
```

### Configure Your Miners
Use the pool information to configure your ASIC miners:
- **Stratum URL**: Use the pool URL from Step 2
- **Worker Name**: Use the exact worker name provided
- **Password**: x

Once entering the pool information, the pool will automatically register your contributions. You'll immediately start earning TIDES BTC rewards. If you're registered on Bittensor, you'll also accumulate alpha tokens worth 5% of your hashpower value. 

### Monitor Performance

Track your mining performance at: **https://taohash.com/leaderboard**

The leaderboard shows:
- Current hashrate contribution
- Share value generated
- Ranking among all miners
- Historical performance

### Maximizing Your Rewards

#### For TIDES
1. **Maintain a Consistent Hashrate:** The longer you stay active, the more of the TIDES window you occupy.  
2. **Submit High-Difficulty Shares:** Stronger hardware or higher target difficulty increases share value.  
3. **Keep Downtime Minimal:** Every valid share counts toward your share-weighted BTC portion.  
4. **Monitor Share Acceptance:** Check your miner’s logs and the TAOHash dashboard to confirm accepted shares.  

#### For Bittensor Participants (+5% Alpha Tokens)
1. **Register on Subnet 14:** Required for Alpha rewards eligibility.  
2. **Keep Your Hotkey Active:** Inactive or unregistered hotkeys won’t earn Alpha emissions.  
3. **Monitor Accumulation:** Track token balances via your wallet or the Bittensor explorer.  
4. **Think Long-Term:** Alpha represents network stake — its value compounds as the subnet grows.  

---

### Total Value Proposition

| Miner Type | BTC Rewards | Alpha Tokens | Total Return |
|-------------|--------------|---------------|---------------|
| **Non-Bittensor Miner** | ✅ TIDES BTC rewards proportional to hashpower | ❌ Not available | Fair BTC payouts |
| **Bittensor-Registered Miner** | ✅ TIDES BTC rewards | ✅ +5% Alpha Token value | BTC + Alpha yield |
| **Key Benefit** | Fair, variance-smoothed BTC income | Long-term ecosystem stake | Up to **5% higher total returns** |

---
## Setting Minimum Difficulty

High-performance ASICs may require minimum difficulty settings. 
Even though the pool's minimum difficulty is around 150K, you have an option to enforce a even higher number. 
Append the minimum difficulty to your password:

```
x;md=100000;
```
Note: It is important to follow the format of setting the difficulty. 
