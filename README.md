<div align="center">

# **TAO Hash** <!-- omit in toc -->
</div>
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) 

TAO Hash is a Subnet for decentralizing mining hash rental. Validators set weights on miners based on the PoW mining hash rate they provide to the Validators pool. Although the initial implementation will only support Bitcoin mining, this can be extended to other pooled-mining projects with the same ability to verify miner performance quickly.

Another extension might be weighting different mining contributions based on their perceived value, or reducing hashrate automatically based on the hash-value.

---
- [Incentive Design](#incentive-design)
- [Requirements](#requirements)
  - [Miner Requirements](#miner-requirements)
  - [Validator Requirements](#validator-requirements)
  - [Installation](#installation)
    - [Miner](#miner)
    - [Validator](#validator)
---

# Incentive Design
![Hash Tensor Diagram](docs/incentive-design.png)
# Requirements

<!-- TODO -->
## Miner Requirements
- git
- Docker
- Docker-Compose
- Ubuntu 20.04+
- [Braiins Proxy](https://github.com/braiins/farm-proxy?tab=readme-ov-file#quick-start) 
- Any BTC Miner (hardware and software) with the ability to mine to a pool address

## Validator Requirements

## Installation
### Miner
- [Install Docker](https://docs.docker.com/engine/install/ubuntu/)
- [Install Docker compose](https://docs.docker.com/compose/install/)
- [Install Braiins Proxy](https://github.com/braiins/farm-proxy?tab=readme-ov-file#quick-start)

### Validator


