from typing import List

import os
import random
import argparse
import traceback
import bittensor as bt

from node import Node
from pool import Pool, PoolIndex
import utils
from pool.metrics import get_metrics_for_miners, MiningMetrics
from ..pricing import CoinPriceAPI


class Validator:
    def __init__(self):
        self.config = self.get_config()
        self.setup_logging()
        self.setup_bittensor_objects()
        self.last_update = 0
        self.my_uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
        self.scores = [1.0] * len(self.metagraph.S)
        self.last_update = 0
        self.current_block = 0
        self.tempo = self.node_query("SubtensorModule", "Tempo", [self.config.netuid])
        self.moving_avg_scores = [1.0] * len(self.metagraph.S)
        self.alpha = 0.1
        self.node = Node(url=self.config.subtensor.chain_endpoint)
        self.pool = Pool(pool=self.config.pool.pool, api_key=self.config.pool.api_key)
        self.price_api = CoinPriceAPI(
            method=self.config.price.method, api_key=self.config.price.api_key
        )

    def get_config(self):
        # Set up the configuration parser.
        parser = argparse.ArgumentParser()
        # TODO: Add your custom validator arguments to the parser.
        parser.add_argument(
            "--custom",
            default="my_custom_value",
            help="Adds a custom value to the parser.",
        )
        # Adds override arguments for network and netuid.
        parser.add_argument(
            "--netuid", type=int, default=1, help="The chain subnet uid."
        )

        parser.add_argument(
            "--coins",
            type=str,
            nargs='+',
            default=['bitcoin'],
            help="The coins you wish to reward miners for. Use CoinGecko token naming"
        )
        # Adds subtensor specific arguments.
        bt.subtensor.add_args(parser)
        # Adds logging specific arguments.
        bt.logging.add_args(parser)
        # Adds wallet specific arguments.
        bt.wallet.add_args(parser)

        Pool.add_args(parser)
        CoinPriceAPI.add_args(parser)

        # Parse the config.
        config = bt.config(parser)
        # Set up logging directory.
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey_str,
                config.netuid,
                "validator",
            )
        )
        # Ensure the logging directory exists.
        os.makedirs(config.full_path, exist_ok=True)
        return config

    def setup_logging(self):
        # Set up logging.
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(
            f"Running validator for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:"
        )
        bt.logging.info(self.config)

    def setup_bittensor_objects(self):
        # Build Bittensor validator objects.
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

        # Connect the validator to the network.
        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            bt.logging.error(
                f"\nYour validator: {self.wallet} is not registered to chain connection: {self.subtensor} \nRun 'btcli register' and try again."
            )
            exit()
        else:
            # Each validator gets a unique identity (UID) in the network.
            self.my_subnet_uid = self.metagraph.hotkeys.index(
                self.wallet.hotkey.ss58_address
            )
            bt.logging.info(f"Running validator on uid: {self.my_subnet_uid}")

        # Set up initial scoring weights for validation.
        bt.logging.info("Building validation weights.")
        self.scores = [1.0] * len(self.metagraph.S)
        bt.logging.info(f"Weights: {self.scores}")

        # Set an axon of the pool address
        self._serve_axon(self.wallet, port=self.pool.port, ip=self.pool.ip, pool_index=self.pool.index)
       
    def _serve_axon(self, wallet: bt.wallet, ip: str, port: int, pool_index: PoolIndex) -> None:
        wallet.hotkey
        params = {
            "version": bt.__version_as_int__,
            "ip": utils.ip_to_int(ip),
            "port": port,
            "ip_type": utils.ip_version(ip),
            "netuid": self.config.netuid,
            "hotkey": wallet.hotkey.ss58_address,
            "coldkey": wallet.coldkeypub.ss58_address,
            "protocol": pool_index.value, # Use protocol for setting the pool
            "placeholder1": 0,
            "placeholder2": 0,
        }
        uid = self.metagraph.hotkeys.index(wallet.hotkey.ss58_address)
        current_axon = self.metagraph.axons[uid]
        if current_axon.protocol == params["protocol"]:
            return # same pool, don't serve twice

        axon_call = self.node.compose_call(
            call_module="SubtensorModule",
            call_function="serve_axon",
            call_params=params,
        )
        extrinsic = self.node.create_signed_extrinsic(
            call=axon_call, keypair=wallet.hotkey
        )
        response = self.node.submit_extrinsic(
            extrinsic,
            wait_for_inclusion=True,
            wait_for_finalization=True,
    )
        response.process_events()
        if not response.is_success:
            raise RuntimeError("Pool address could not be served")

    def node_query(self, module, method, params):
        result = self.node.query(module, method, params).value

        return result

    def run(self):
        # The Main Validation Loop.
        bt.logging.info("Starting validator loop.")
        while True:
            try:
                current_scores = [0.0] * len(self.metagraph.S)
                hotkey_to_uid = {n.hotkey: n.uid for n in self.metagraph.neurons}

                for coin in self.config.coins:
                    miner_metrics: List[MiningMetrics] = [
                        get_metrics_for_miners(self.pool, self.metagraph.neurons)
                    ]
                    coin_price: float = self.price_api.get_price(coin)
                    fpps: float = self.pool.get_fpps(coin)

                    for metric in miner_metrics:
                        uid = hotkey_to_uid[metric.hotkey]

                        shares_value: float = MiningMetrics.get_shares_value(fpps)
                        in_usd: float = shares_value * coin_price

                        current_scores[uid] += hash_value
                
                for i, current_score in enumerate(current_scores):
                    self.moving_avg_scores[i] = (
                        1 - self.alpha
                    ) * self.moving_avg_scores[i] + self.alpha * current_score

                bt.logging.info(f"Moving Average Scores: {self.moving_avg_scores}")

                self.current_block = self.node_query("System", "Number", [])
                self.last_update = (
                    self.current_block
                    - self.node_query(
                        "SubtensorModule", "LastUpdate", [self.config.netuid]
                    )[self.my_uid]
                )

                # set weights once every tempo + 1
                if self.last_update > self.tempo + 1:
                    total = sum(self.moving_avg_scores)
                    weights = [score / total for score in self.moving_avg_scores]
                    bt.logging.info(f"Setting weights: {weights}")
                    # Update the incentive mechanism on the Bittensor blockchain.
                    result = self.subtensor.set_weights(
                        netuid=self.config.netuid,
                        wallet=self.wallet,
                        uids=self.metagraph.uids,
                        weights=weights,
                        wait_for_inclusion=True,
                    )
                    self.metagraph.sync()

            except RuntimeError as e:
                bt.logging.error(e)
                traceback.print_exc()

            except KeyboardInterrupt:
                bt.logging.success("Keyboard interrupt detected. Exiting validator.")
                exit()


# Run the validator.
if __name__ == "__main__":
    validator = Validator()
    validator.run()
