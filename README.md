<div align="center">

# **TAOHash** ![Subnet 14](https://img.shields.io/badge/Subnet-14_%CE%BE-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/latent-to/taohash)

</div>

## Introduction

Bittensor is a decentralized platform that incentivizes production of best-in-class digital commodities. TAOHash is a Bittensor subnet designed around production of proof-of-work (PoW) BTC mining hashrate.

The long-term vision for TAOHash includes developing into a public marketplace for hashrate, backed by smart contracts.

You can learn more about our roadmap and future plans at [taohash.com/roadmap](https://taohash.com/roadmap).

It is possible to contribute as a **miner** or a **validator**.

**Miners** contribute BTC mining hashrate, and earn rewards through two independent systems:
1. **TIDES**: Direct BTC earnings for all miners (no Bittensor registration required). Rewards are based on the proportion of work done inside the TIDES window when a block is found. On average, max blocks are found ~4 times a day with a minimum of 1.
2. **Alpha tokens**: Subnet-specific tokens for Bittensor-registered miners, worth 5% of the hashpower value they provide. 

**Validators** evaluate miners, ranking (weighting) them by the share-value they've produced over each period of time. This creates a pool where miners can earn immediate BTC rewards while miners who are also Bittensor participants also accumulate alpha tokens representing additional value.

By design, this architecture is extensible to other mining projects where miner performance can be precisely and efficiently verified.

**Related Bittensor Documentation**:

- [Introduction to Bittensor](https://docs.learnbittensor.org/learn/introduction)
- [TAOHash Subnet Information](https://learnbittensor.org/subnets/14)
- [Mining in Bittensor](https://docs.learnbittensor.org/miners/)
- [Frequently asked questions (FAQ)](https://docs-git-permissions-list-bittensor.vercel.app/questions-and-answers)

**TAOHash Resources**:
- [About TAOHash](https://taohash.com/about)
- [TAOHash Roadmap](https://taohash.com/roadmap)
- [TIDES FAQ - BTC Rewards System](docs/tides_faq.md)

**Page Contents**:
- [Incentive Design](#incentive-design)
- [Reward System](#reward-system)
- [Requirements](#requirements)
  - [Miner Requirements](#miner-requirements)
  - [Validator Requirements](#validator-requirements)
- [Installation](#installation)
  - [Common Setup](#common-setup)
  - [Miner Specific Setup](#miner-specific-setup)
  - [Validator Specific Setup](#validator-specific-setup)
- [Get Involved](#get-involved)
---

# Incentive Design

TAOhash's incentive mechanism aligns the collective interests of a pool of miners.  All miners are rewarded fairly for the hashrate they contribute, validators are rewarded for checking the miners' work, and all participants (both miners and validators) benefit from the contributions of more total hashrate to the subnet's unified pool.

![TAOHash Diagram](docs/images/incentive-design.png)

# Reward System

TAOHash operates two distinct reward mechanisms:

## 1. TIDES Protocol (All Miners)
TIDES (Time-based Incentivized Distribution of Earnings System) is a reward protocol that distributes BTC to miners contributing hashpower:
- **No Registration Required**: Any miner can earn TIDES rewards without joining Bittensor. You just have to enter a valid BTC/Lightning address in your username
- **Direct BTC Earnings**: Rewards paid directly in Bitcoin to your configured address
- **Fair Distribution**: BTC distributed proportionally based on share value contributions in the TIDES window
- **Window size**: Uses `network difficulty × 8` for creating the TIDES window. 
- **Performance-Based**: Higher hashrate = high difficulty shares = larger BTC rewards

## 2. Alpha Token Rewards (Bittensor Participants)
Subnet 14 incentivizes miners with additional alpha token rewards:
- **5% Value Back**: Alpha tokens worth 5% of the hashpower value you provide
- **Value Calculation**: Based on hashprice index and current exchange rates
- **Requires Registration**: Only available to miners registered on Bittensor subnet 14
- **Subnet Stake**: Alpha tokens represent stake in the TAOHash subnet
- **Convertible to TAO**: Can be unstaked to TAO (Bittensor's primary currency)


# Requirements

## Miner Requirements

To run a miner with TAOHash rewards, you will need:

- A Bittensor wallet with coldkey and hotkey
- Bitcoin mining hardware (ASICs, GPUs, etc.) OR access to remote hashrate (NiceHash, MiningRigRentals)
- Python 3.9 or higher
- The most recent release of [Bittensor SDK](https://pypi.org/project/bittensor/)
- (Optional, for miner proxy usage): Docker & Docker Compose

See: [TAOHash miner guide](/docs/running_miner.md)

**Related Bittensor Documentation**:

- [Wallets, Coldkeys and Hotkeys in Bittensor](https://docs.learnbittensor.org/getting-started/wallets)
- [Miner registration](./miners/index.md#miner-registration)

## Validator Requirements

To run a TAOHash validator, you will need:

- A Bittensor wallet with coldkey and hotkey
- Subnet proxy credentials (provided by subnet maintainers)
- Python 3.9 or higher environment
- The most recent release of [Bittensor SDK](https://pypi.org/project/bittensor/)

See: [TAOHash validator guide](/docs/running_validator.md)

**Related Bittensor Documentation**:
- [Wallets, Coldkeys and Hotkeys in Bittensor](https://docs.learnbittensor.org/getting-started/wallets)
- [Validator registration](./validators/index.md#validator-registration)

# Installation

## Common Setup
These steps apply to both miners and validators:

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/latent-to/taohash.git
    cd taohash
    ```

2.  **Set up and activate a Python virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Upgrade pip:**
    ```bash
    pip install --upgrade pip
    ```

4.  **Install the TAOHash package:**
    ```bash
    pip install -e .
    ```

## Miner Specific Setup
After completing the common setup, the easiest way to start mining is:

### Quick Start (Direct Mining)
1. **Get Mining Pool Credentials**: Run the [`miner.py`](taohash/miner/miner.py) script to fetch your pool information:
   ```bash
   python taohash/miner/miner.py --subtensor.network finney --wallet.name WALLET_NAME --wallet.hotkey WALLET_HOTKEY --btc_address YOUR_BTC_ADDRESS
   ```
   This script will display your unique worker credentials and pool connection details. The username format will be `YOUR_BTC_ADDRESS.WORKER_SUFFIX`.

2. **Configure Your Miners**: Point your mining hardware directly to the subnet pool using the credentials from step 1.

3. **Monitor Your Performance**: Check your statistics at [https://taohash.com/leaderboard](https://taohash.com/leaderboard)

For complete details, see the [TAOHash Miner Setup Guide](docs/running_miner.md).

## Validator Specific Setup
After completing the common setup, follow the detailed steps in the Validator Guide:

* [Get subnet proxy credentials from the subnet staff](docs/running_validator.md#1-get-subnet-proxy-credentials)
* [Configure your validator (`.env` file)](docs/running_validator.md#4-configuration)
* [Run the validator (using PM2 recommended)](docs/running_validator.md#5-running-the-validator)

For the complete, step-by-step instructions for setting up and running your validator, please refer to the [TAOHash Validator Setup](docs/running_validator.md).

# Get Involved

- Join the discussion on the [Bittensor Discord](https://discord.com/invite/bittensor) in the Subnet 14 channels.
- Check out the [Bittensor Documentation](https://docs.bittensor.com/) for general information about running subnets and nodes.
- Contributions are welcome! See the repository's contribution guidelines for details.

---
**Full Guides:**
- [TAOHash Miner Setup Guide](docs/running_miner.md)
- [TaoHash Validator Setup](docs/running_validator.md) 
