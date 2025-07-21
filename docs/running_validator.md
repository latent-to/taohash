# TaoHash Validator Setup

This guide will walk you through setting up and running a TaoHash validator on the Bittensor network.

TaoHash enables Bitcoin miners to contribute hashpower to a collective mining pool. All miners direct their hashpower to a single subnet pool, where validators evaluate and rank miners based on the share value they generate.

Validators are rewarded in TAOHash's subnet-specific (alpha) token on the Bittensor blockchain, which represents *stake* in the subnet. This alpha stake can be exited from the subnet by unstaking it to TAO (Bittensor's primary currency).
<!-- Is the above true? Or do they also get BTC or what? -->

**Share value** is the difficulty at which the miner solved a blockhash. The higher the difficulty solved, the more incentive a miner gets during *emissions*, the process by which Bittensor periodically distributes tokens to participants based on the Yuma Consensus algorithm. In general, the higher the hashpower, the higher the share value submitted.

See also:

- [Introduction to TAOHash](../README.md)
- [Introduction to Bittensor](https://docs.learnbittensor.org/learn/introduction)
- [Yuma Consensus](https://docs.learnbittensor.org/yuma-consensus/)
- [Emissions](https://docs.learnbittensor.org/emissions/)

## Prerequisites

- A Bittensor wallet with coldkey and hotkey, registered on TAOHash, with sufficient stake weight.
- Subnet proxy credentials (provided by subnet maintainers)
- Python 3.9 or higher environment
- The most recent release of [Bittensor SDK](https://pypi.org/project/bittensor/) and the Bittensor CLI, [BTCLI](https://pypi.org/project/bittensor-cli/)

Bittensor Docs:

- [Requirements for Validation](https://docs.learnbittensor.org/validators/#requirements-for-validation)
- [Validator registration](./validators/index.md#validator-registration)
- [Wallets, Coldkeys and Hotkeys in Bittensor](https://docs.learnbittensor.org/getting-started/wallets)

## Setup Steps

### Get Subnet Proxy Credentials

<!-- How do they contact the subnet owner? Email? Discord? -->
Contact the subnet owner to receive:

- **Proxy API URL**: The endpoint for retrieving miner statistics
- **API Token**: Authentication token for the proxy API

These credentials allow your validator to evaluate miners based on their mining contributions.

### Bittensor Wallet Setup

Check your wallet, or create one if you have not already.

Bittensor Documentation: [Creating/Importing a Bittensor Wallet
](https://docs.learnbittensor.org/working-with-keys)

### List wallet
```bash
btcli wallet list
```
```console
Wallets
├── Coldkey YourColdkey  ss58_address 5F...
│   ├── Hotkey YourHotkey  ss58_address
│   │   5E...
```

### Check your wallet's balance

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

### Register on TAOHash, subnet 14 on Bittensor mainnet ("finney")

```bash
btcli subnet register --netuid 14 --wallet.name YOUR_WALLET --wallet.hotkey YOUR_HOTKEY --network finney
```

### Clone Repository and Install

```bash
# Clone the repository
git clone https://github.com/latent-to/taohash.git
cd taohash

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the package
pip install -e .
```

### Configuration

Create a `.env` file in the validator directory:

```bash
cd taohash/validator
cp .env.validator.example .env
nano .env
```

Update the `.env` file with your credentials:
```env
# Bittensor Configuration
NETUID=14
SUBTENSOR_NETWORK=finney
BT_WALLET_NAME="your_wallet_name"
BT_WALLET_HOTKEY="your_hotkey_name"

# Subnet Proxy Configuration (from subnet owner)
SUBNET_PROXY_API_URL="http://proxy.example.com:8888"
SUBNET_PROXY_API_TOKEN="your-api-token-here"

# Recovery Configuration
RECOVERY_FILE_PATH=~/.bittensor/data/taohash/validator
RECOVERY_FILE_NAME=validator_state.json
```

### Running the Validator

#### Using PM2 (Recommended)

1. Install PM2:
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install nodejs npm -y
sudo npm install pm2@latest -g

# macOS
brew install node
npm install pm2@latest -g
```

2. Start the validator:
```bash
pm2 start python3 --name "taohash-validator" -- taohash/validator/validator.py run \
    --subtensor.network finney \
    --logging.info

# Save PM2 configuration
pm2 save
pm2 startup
```

#### Direct Execution

```bash
python3 taohash/validator/validator.py run \
    --subtensor.network finney \
    --logging.info
```

## Important Parameters

- `netuid`: Set to 14 for TaoHash subnet
- `subtensor.network`: Set to `finney` for mainnet
- `wallet.name`: Your Bittensor wallet name
- `wallet.hotkey`: Your wallet's hotkey

## Validator Evaluation Process

1. Validators fetch miner statistics from the subnet proxy every 5 minutes (25 blocks)
2. They calculate share values based on miner contributions
3. Weights are set every `tempo` blocks (every epoch) based on moving averages
4. All validators use the same proxy endpoint for consistent evaluation

## PM2 Management

```bash
# View processes
pm2 list

# Monitor in real-time
pm2 monit

# View logs
pm2 logs taohash-validator
pm2 logs taohash-validator --lines 100

# Control validator
pm2 stop taohash-validator
pm2 restart taohash-validator
pm2 delete taohash-validator

# Log rotation
pm2 install pm2-logrotate
pm2 set pm2-logrotate:max_size 10M
pm2 set pm2-logrotate:retain 7
```

## Troubleshooting

**Cannot connect to subnet proxy**
- Verify the `SUBNET_PROXY_API_URL` is correct
- Check that your API token is valid
- Ensure network connectivity to the proxy

**No miner data received**
- Confirm miners are actively mining
<!-- How? What are the various links in the chain? -->
- Check proxy logs for any issues
<!-- What do I look for? What do I do if I see it? -->
- Verify time synchronization
<!-- What do I look for? What do I do if I see it? -->

**Wallet issues**
- Ensure wallet is properly created and registered
<!--  -->
- Check that wallet path is correct
- Verify you're using the correct network

## Support

- GitHub Issues: https://github.com/latent-to/taohash/issues
- Bittensor Discord: Subnet 14 channel

Happy validating!