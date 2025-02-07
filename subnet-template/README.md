
# Bittensor Subnet Template

This repository provides a minimal template for setting up a simple Bittensor subnet with a miner and a validator. The miner and validator communicate using a custom protocol defined in `protocol.py`. This template serves as a starting point for developers interested in building on the Bittensor network.

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Setup Instructions](#setup-instructions)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Install Dependencies](#2-install-dependencies)
  - [3. Create Wallets](#3-create-wallets)
  - [4. Register Wallets](#4-register-wallets)
- [Running the Miner and Validator](#running-the-miner-and-validator)
  - [Running the Miner](#running-the-miner)
  - [Running the Validator](#running-the-validator)
- [Monitoring and Logging](#monitoring-and-logging)
- [Customization](#customization)
- [Notes and Considerations](#notes-and-considerations)
- [License](#license)

---

## Overview

This template demonstrates how to:

- Set up a basic miner that responds to queries from validators.
- Implement a validator that sends queries to miners and adjusts their scores based on responses.
- Use a custom protocol for communication between the miner and validator.
- Update weights on the Bittensor blockchain based on miner performance.

By following this guide, you'll have a functional miner and validator interacting on a Bittensor subnet.

## Project Structure

```
bittensor_subnet/
├── miner.py          # Miner node script
├── validator.py      # Validator node script
└── protocol.py       # Custom protocol definition
```

- **miner.py**: Implements a miner that listens for incoming requests and responds according to the protocol.
- **validator.py**: Implements a validator that sends requests to miners and updates their scores.
- **protocol.py**: Defines the custom protocol used for communication between the miner and validator.

## Prerequisites

Before you begin, ensure you have the following installed:

- Python 3.10 or higher
- [Git](https://git-scm.com/)
- [Bittensor SDK](https://github.com/opentensor/bittensor)

## Setup Instructions

### 1. Clone the Repository

Clone this repository to your local machine:

```bash
git clone https://github.com/yourusername/bittensor_subnet.git
cd bittensor_subnet
```

### 2. Install Dependencies

Install the required Python packages:

```bash
pip install bittensor
```

> **Note**: It's recommended to use a virtual environment to manage dependencies.

### 3. Create Wallets

You'll need to create wallets for both the miner and validator.

#### Using `btcli`

The `btcli` tool is used to manage wallets and keys.

1. **Create a Coldkey** (shared between miner and validator):

   ```bash
   btcli w new_coldkey --wallet.name mywallet
   ```

2. **Create Hotkeys**:

   - **Miner Hotkey**:

     ```bash
     btcli w new_hotkey --wallet.name mywallet --wallet.hotkey miner_hotkey
     ```

   - **Validator Hotkey**:

     ```bash
     btcli w new_hotkey --wallet.name mywallet --wallet.hotkey validator_hotkey
     ```

### 4. Register Wallets

Register both the miner and validator on the Bittensor network.

- **Register the Miner**:

  ```bash
  btcli s register --wallet.name mywallet --wallet.hotkey miner_hotkey --subtensor.network finney
  ```

- **Register the Validator**:

  ```bash
  btcli s register --wallet.name mywallet --wallet.hotkey validator_hotkey --subtensor.network finney
  ```

> **Note**: Replace `finney` with the name of the network you are connecting to if different.

---

## Running the Miner and Validator

### Running the Miner

In one terminal window, navigate to the project directory and run:

```bash
python miner.py --wallet.name mywallet --wallet.hotkey miner_hotkey --subtensor.network finney --axon.port 8901
```

**Arguments**:

- `--wallet.name`: The name of the wallet.
- `--wallet.hotkey`: The hotkey name for the miner.
- `--subtensor.network`: The Bittensor network to connect to.

### Running the Validator

In another terminal window, navigate to the project directory and run:

```bash
python validator.py --wallet.name mywallet --wallet.hotkey validator_hotkey --subtensor.network finney
```

**Arguments**:

- `--wallet.name`: The name of the wallet.
- `--wallet.hotkey`: The hotkey name for the validator.
- `--subtensor.network`: The Bittensor network to connect to.

---

## Monitoring and Logging

Both the miner and validator will output logs to the console and save logs to files in the following directory structure:

```
~/.bittensor/wallets/<wallet.name>/<wallet.hotkey>/netuid<netuid>/<miner or validator>/
```

- **Miner Logs**: Located in the `miner` directory.
- **Validator Logs**: Located in the `validator` directory.

You can monitor these logs to observe the interactions and performance metrics.

---

## Customization

### Modifying the Protocol

The communication protocol is defined in `protocol.py`. You can modify or extend the `Dummy` class to implement more complex interactions.

Example:

```python
class CustomProtocol(bt.Synapse):
    # Define your custom protocol attributes and methods
    ...
```

Update `miner.py` and `validator.py` to use your custom protocol.

### Adjusting Scoring Logic

In `validator.py`, the validator adjusts miner scores based on their responses. You can modify the scoring logic in the main loop to suit your needs.

Example:

```python
# Custom scoring logic
if resp_i == expected_value:
    score = 1
else:
    score = 0
```

### Changing Network Parameters

You can adjust network parameters like `netuid`, timeouts, and other settings via command-line arguments or by modifying the code.

---

## Notes and Considerations

- **Security**: This template is for educational purposes. In a production environment, ensure robust security measures are in place.
- **Error Handling**: The provided code includes basic error handling. Enhance it to handle edge cases and exceptions gracefully.
- **Network Compatibility**: Ensure that the `netuid` and `subtensor.network` values match the subnet you intend to connect to.
- **Bittensor Updates**: Bittensor is an evolving project. Keep your SDK updated and adjust the code as necessary to accommodate changes.

---

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

Feel free to contribute, raise issues, or suggest improvements to this template. Happy mining and validating on the Bittensor network!
