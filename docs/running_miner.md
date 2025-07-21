# TAOHash Mining Guide

This guide will walk you through setting up and running a TaoHash miner on the Bittensor network.

TaoHash enables Bitcoin miners to contribute hashpower to a collective mining pool. All miners direct their hashpower to a single subnet pool, where validators evaluate and rank miners based on the share value they generate.

Miners are rewarded in TAOHash's subnet-specific (alpha) token on the Bittensor blockchain, which represents *stake* in the subnet. This alpha stake can be exited from the subnet by unstaking it to TAO (Bittensor's primary currency).

**Share value** is the difficulty at which the miner solved a blockhash. The higher the difficulty solved, the more incentive a miner gets during *emissions*, the process by which Bittensor periodically distributes tokens to participants based on the Yuma Consensus algorithm. In general, the higher the hashpower, the higher the share value submitted.

See also:

- [Introduction to TAOHash](../README.md)
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

Once entering the pool information, the Subnet's proxy will automatically register your contributions against your hotkey and you will start accumulating alpha. 

### Monitor Performance

Track your mining performance at: **https://taohash.com/leaderboard**

The leaderboard shows:
- Current hashrate contribution
- Share value generated
- Ranking among all miners
- Historical performance

## Setting Minimum Difficulty

High-performance ASICs may require minimum difficulty settings. Append the minimum difficulty to your password:

```
x;md=100000;
```
Note: It is important to follow the format of setting the difficulty. 

![Minimum Difficulty Settings](./images/miner_difficulties.png)

## Legacy Mining Script

The `miner_with_proxy.py` script is still supported and automatically mines to the subnet pool:

```bash
python taohash/miner/miner_with_proxy.py \
    --wallet.name <YOUR_WALLET> \
    --wallet.hotkey <YOUR_HOTKEY> \
    --subtensor.network finney \
    --btc_address <YOUR_BTC_ADDRESS>
```

## Troubleshooting

**Cannot connect to pool**
- Verify pool information using `miner.py`
<!-- how? -->
- Check firewall settings
- Ensure wallet is registered on subnet 14
**High rejection rate**
- Check network latency
- Update miner firmware

**Not showing on leaderboard**
- Use exact worker name from pool info
- Allow 30 minutes for statistics
- Verify shares are being accepted

## Advanced: Proxy Setup

You can use the miner proxy in-cases where you want all the hashpower from your miners to be directed at one point.
From that point, it can communicate with the subnet's proxy. 
This approach works well and has been in the works at the subnet level in the past. 

### Benefits:

- Real-time dashboard with statistics
- No manual worker configuration

### Installation:

1. **Start the proxy service:**
```bash
cd taohash/miner/proxy/taohash_proxy
docker compose up -d
```
Make sure the correct ports are configured and update the `config.toml` to contain the subnet's proxy information. 

2. **Configure miners to connect to proxy:**
- Stratum URL: `<your_local_ip>:3331`
- Worker: Any name
- Password: x

3. **Access dashboard:**
Visit `http://<your_local_ip>:8100` for real-time statistics.

4. **Run the miner script**
- Next you need to run the miner script so it can hot-load the configuration for you. 
- You can choose to skip this step and update the config.toml yourself (it will stay static anyway).

---

For support: https://github.com/latent-to/taohash/issues

Happy TaoHashing!