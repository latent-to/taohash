# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2024 Cameron Fairchild

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from typing import Any, Dict, List, Optional, Tuple

import time
import asyncio

import bittensor as bt

NETUID: int = 99  # TOOD: Set the netuid based on testnet, etc.
UPDATE_INTERVAL: int = 60 * 5  # Update config every 5 minutes

AxonStr = Optional[str]  # Validators may not yet have axons
ProxyConfig = Any  # TODO: Define the proxy config


class Miner:
    config: Any
    subtensor: bt.subtensor

    def __init__(self, config=None):
        super(Miner, self).__init__(config=config)

    def __enter__(self):
        # init subtensor
        self.subtensor = bt.subtensor(
            self.config.subtensor.network,
        )
        return self

    def get_validators(
        self, netuid: int = NETUID
    ) -> Tuple[List[str], List[int], Dict[str, AxonStr]]:
        # TODO: async def get_validators(self, netuid: int = NETUID) -> Tuple[List[str], List[int], List[AxonStr]]:
        """
        Get the validators' UIDs, Hotkeys, and Axons on the subnet
        """
        validator_permits_result = self.subtensor.query_subtensor(
            name="ValidatorPermit", params=[netuid]
        )

        uids, hotkeys, axons = [], [], {}
        for uid, permit in enumerate(validator_permits_result):
            if not permit:
                continue
            uids.append(uid)

            hotkey = self.subtensor.query_subtensor(name="Keys", params=[uid])
            hotkeys.append(hotkey)

            axon = self.subtensor.query_subtensor(name="Axon", params=[netuid, hotkey])
            axons[hotkey] = axon

        return uids, hotkeys, axons

    def get_stakes(self, hotkeys: List[str]) -> Dict[str, float]:
        # TODO: async def get_stakes(self, hotkeys: List[str]) -> Dict[str, float]:
        """
        Get the total hotkey stakes of the hotkeys

        Returns a dictionary of hotkey -> stake
        """
        stakes = {}
        for hotkey in hotkeys:
            stake = self.subtensor.query_subtensor(
                name="TotalHotkeyStake", params=[hotkey]
            )
            stakes[hotkey] = stake

        return stakes

    @staticmethod
    def _is_valid_axon(axon: AxonStr) -> bool:
        # TODO: Implement a more robust check

        if axon is None:
            return False
        if len(axon) == 0:
            return False
        # TODO: Check if the axon is a valid stratum address

        return True

    def get_priority(
        self, stakes: Dict[str, float], axons: Dict[str, AxonStr]
    ) -> Dict[str, float]:
        """
        Get the priority of the validators based on their stakes

        The priority should sum to 1.0 and represent the fraction of the time
            the proxy server should be mining on behalf of the validator.
        """
        # TODO: Try other priority functions
        # Normalize the stakes

        total_stake = sum(
            [
                stake
                for hk, stake in stakes.items()
                if self._is_valid_axon(axons.get(hk))
            ]
        )
        priority = {hotkey: stake / total_stake for hotkey, stake in stakes.items()}

        return priority

    def get_mining_pools(self, validator_axons: Dict[str, str]) -> Dict[str, str]:
        # async def get_mining_pools(self, validator_axons: Dict[str, str]) -> Dict[str, str]:
        """
        Get the hotkey -> mining pool map

        This map can be grabbed by querying all the validators on the subnet
        """
        mining_pool_map = {}
        for hotkey, axon in validator_axons.items():
            mining_pool_map[hotkey] = axon

        return mining_pool_map

    def create_proxy_config(priority: List[int], mining_pools: List[str]) -> ProxyConfig:
        """
        Create a config for the proxy server based on the priority and mining pools
        """
        pass

    def should_restart(self, old_config: ProxyConfig, new_config: ProxyConfig) -> bool:
        """
        Check if the proxy server should be restarted
        """
        return old_config != new_config  # TODO: Allow for more complex checks
    
    def restart_proxy_server(self, config: ProxyConfig) -> None:
        """
        Restart the proxy server
        """
        # TODO: Load the config into the proxy server
        # TODO: Restart the proxy server
        pass


async def main():
    old_config = None
    with Miner() as miner:
        while True:
            bt.logging.info("Miner running...", time.time())

            # Setup a configuration for the proxy server
            ## Get the validators UIDs on the subnet
            validator_uids, validator_hotkeys, validator_axons = (
                await miner.get_validators()
            )
            ## Get the stakes of the validators
            validator_stakes: Dict[str, float] = await miner.get_stakes(
                validator_uids, validator_hotkeys
            )
            ## Get the priority of the validators based on their stakes
            priority: Dict[str, float] = miner.get_priority(validator_stakes)
            ## Get the mining pools for the validators
            mining_pool_map = await miner.get_mining_pools(validator_axons)
            ## Get the mining pools for the validators
            mining_pools = [
                mining_pool_map[hotkey]
                for hotkey in validator_hotkeys
                if hotkey in mining_pool_map
            ]
            ## Create a config for the proxy server based on the priority
            proxy_config = miner.create_proxy_config(priority, mining_pools)

            # Load the config into the proxy server
            if miner.should_restart(old_config, proxy_config):
                # Restart the proxy server
                miner.restart_proxy_server(proxy_config)

            old_config = proxy_config

            # Wait for a bit before checking again
            time.sleep(UPDATE_INTERVAL)


# This is the main function, which runs the miner.
if __name__ == "__main__":
    bt.logging.info("Starting Miner...")
    asyncio.run(main())
    bt.logging.info("Press Ctrl+C to stop the miner.")
    bt.logging.info("Running...")
    bt.logging.info("Miner running...", time.time())
