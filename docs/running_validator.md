# TaoHash Validator Setup

This guide will walk you through setting up and running a TaoHash validator on the Bittensor network.

## Prerequisites

1. A Bittensor wallet
2. Subnet proxy credentials (provided by subnet owner)
3. Python 3.9 or higher

## Setup Steps

### 1. Get Subnet Proxy Credentials

Contact the subnet owner to receive:
- **Proxy API URL**: The endpoint for retrieving miner statistics
- **API Token**: Authentication token for the proxy API

These credentials allow your validator to evaluate miners based on their mining contributions.

### 2. Bittensor Wallet Setup

Ensure you have created a Bittensor wallet:
```bash
pip install bittensor-cli
btcli wallet create
```

### 3. Clone Repository and Install

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

### 4. Configuration

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

### 5. Running the Validator

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
- Verify the SUBNET_PROXY_API_URL is correct
- Check that your API token is valid
- Ensure network connectivity to the proxy

**No miner data received**
- Confirm miners are actively mining
- Check proxy logs for any issues
- Verify time synchronization

**Wallet issues**
- Ensure wallet is properly created and registered
- Check that wallet path is correct
- Verify you're using the correct network

## Support

- GitHub Issues: https://github.com/latent-to/taohash/issues
- Bittensor Discord: Subnet 14 channel

Happy validating!