from typing import Tuple

import os
import time
import argparse
import traceback
import bittensor as bt
from bittensor_wallet import Wallet

import utils

from .proxy import ProxyAPI, PoolInfo

MAX_POOL_WEIGHT = 2**16 - 1 # TODO: assume u16

class Miner:
    metagraph: bt.metagraph
    subtensor: bt.subtensor
    proxy: ProxyAPI
    wallet: Wallet

    def __init__(self):
        self.config = self.get_config()
        self.setup_logging()
        self.setup_bittensor_objects()

    def get_config(self):
        # Set up the configuration parser
        parser = argparse.ArgumentParser()
        # TODO: Add your custom miner arguments to the parser.
        parser.add_argument(
            "--custom",
            default="my_custom_value",
            help="Adds a custom value to the parser.",
        )
        # Adds override arguments for network and netuid.
        parser.add_argument(
            "--netuid", type=int, default=1, help="The chain subnet uid."
        )

        ProxyAPI.add_args(parser)

        # Adds subtensor specific arguments.
        bt.subtensor.add_args(parser)
        # Adds logging specific arguments.
        bt.logging.add_args(parser)
        # Adds wallet specific arguments.
        bt.wallet.add_args(parser)
        # Parse the arguments.
        config = bt.config(parser)
        # Set up logging directory
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey_str,
                config.netuid,
                "miner",
            )
        )
        # Ensure the directory for logging exists.
        os.makedirs(config.full_path, exist_ok=True)
        return config

    def setup_logging(self):
        # Activate Bittensor's logging with the set configurations.
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(
            f"Running miner for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:"
        )
        bt.logging.info(self.config)

    def setup_bittensor_objects(self):
        # Initialize Bittensor miner objects
        bt.logging.info("Setting up Bittensor objects.")

        # Initialize wallet.
        self.wallet = bt.wallet(config=self.config)
        bt.logging.info(f"Wallet: {self.wallet}")

        # Initialize subtensor.
        self.subtensor = bt.subtensor(config=self.config)
        bt.logging.info(f"Subtensor: {self.subtensor}")

        # Initialize metagraph.
        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        bt.logging.info(f"Metagraph: {self.metagraph}")

        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            bt.logging.error(
                f"\nYour miner: {self.wallet} is not registered to chain connection: {self.subtensor} \nRun 'btcli register' and try again."
            )
            exit()
        else:
            # Each miner gets a unique identity (UID) in the network.
            self.my_subnet_uid = self.metagraph.hotkeys.index(
                self.wallet.hotkey.ss58_address
            )
            bt.logging.info(f"Running miner on uid: {self.my_subnet_uid}")

    def run(self):
        # Keep the miner alive.
        bt.logging.info(f"Starting main loop")
        step = 0
        while True:
            try:
                max_validators = self.subtensor.query_map("SubtensorModule", "MaxAllowedValidators", params=[self.config.netuid]).value
                # Update pools and hashrate distribution based on validator stake
                ## Get all validators and their axons
                sorted_by_stake = sorted([(n.uid, n.stake) for n in self.metagraph.neurons], key=lambda x: x[1])
                validators = sorted_by_stake[:max_validators]

                validator_axons = {uid: self.metagraph.axons[uid] for uid, _ in validators if self.metagraph.axons[uid] is not None}
                validator_certs = {uid: utils.get_neuron_certificate(axon.hotkey) for uid, axon in validator_axons.items()}

                ## Get hashrate weight distribution based on stake
                stake_sum = sum([ self.metgraph.neurons[axon[1]].stake for axon in validator_axons.values() ])
                pool_weights = { uid: int(self.metgraph.neurons[axon[1]].stake / stake_sum * MAX_POOL_WEIGHT) for uid, axon in validator_axons.items() }

                ## Add pools based on axons
                pools = { uid: utils.get_pool_from_axon(axon) for uid, axon in validator_axons.items() }
                pool_users = { uid: utils.get_pool_user_from_certificate(cert) for uid, cert in validator_certs.items() }

                ## (Optional) Get split to personal pool based on coin price
                # TODO:
                ### Add personal pool
                
                new_pools = { pool: (uid, pool_user) for uid, (pool, pool_user) in pools.items() }
                ## Run update pools
                self.proxy = ProxyAPI() # default url
                existing_pools = self.proxy.get_pools()
                for pool in existing_pools:
                    if pool.host in pools.values():
                        if pool.weight != pool_weights[pool.host]:
                            pool.weight = pool_weights[pool.host]
                            self.proxy.update_pool(pool)
                        else:
                            continue
                        new_pools.remove(pool.host)
                        
                    else:
                        # Delete pool
                        self.proxy.remove_pool(pool.name)

                for pool_url, (uid, pool_user) in new_pools.items():
                    pool_info = PoolInfo(
                        username=f"{pool_user}.{self.wallet.hotkey.ss58_address}",
                        appendWorkerNames=False,
                        weight=pool_weights[uid],
                        useWorkerPassword=False,
                        workerNamesSeparator="",
                        isExtranonceSubscribeEnabled=False,
                        host=pool_url,
                        name=f"validator-{uid}",
                        priority=ranks[uid],
                        password="x"
                    )
                    self.proxy.add_pool(pool_info)
                        

                # Periodically update our knowledge of the network graph.
                if step % 60 == 0:
                    self.metagraph.sync()
                    log = (
                        f"Block: {self.metagraph.block.item()} | "
                        f"Incentive: {self.metagraph.I[self.my_subnet_uid]} | "
                    )
                    bt.logging.info(log)
                step += 1
                time.sleep(1)

            except KeyboardInterrupt:
                bt.logging.success("Miner killed by keyboard interrupt.")
                break
            except Exception as e:
                bt.logging.error(traceback.format_exc())
                continue


# Run the miner.
if __name__ == "__main__":
    miner = Miner()
    miner.run()
