import argparse
import os
import socket
import traceback
import time
from typing import List, Optional

import bittensor as bt
from taohash.pool import Pool, BraiinsPool
from taohash.pool.metrics import MiningMetrics, get_metrics_for_miners
from taohash.pricing import CoinPriceAPI, PriceAPIMethod


class Validator:
    def __init__(self):
        self.config = self.get_config()
        self.setup_logging()
        self.pool = Pool(
            pool=self.config.pool.pool,
            api_key=self.config.pool.api_key,
            config=self.config,
        )
        self.price_api: PriceAPIMethod = CoinPriceAPI(
            method=self.config.price.method, api_key=self.config.price.api_key
        )
        self.setup_bittensor_objects()
        self._set_pool_commitment()
        self.last_update = 0
        self.my_uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
        self.scores = [1.0] * len(self.metagraph.S)
        self.last_update = 0
        self.current_block = 0
        self.tempo = self.subtensor.tempo(self.config.netuid)
        self.moving_avg_scores = [1.0] * len(self.metagraph.S)
        self.alpha = 0.1
        self.last_update = self.subtensor.blocks_since_last_update(
            self.config.netuid, self.my_uid
        )

    def get_config(self):
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "--custom",
            default="my_custom_value",
            help="Adds a custom value to the parser.",
        )
        parser.add_argument(
            "--netuid", type=int, default=1, help="The chain subnet uid."
        )
        parser.add_argument(
            "--coins",
            type=str,
            nargs="+",
            default=["bitcoin"],
            help="The coins you wish to reward miners for. Use CoinGecko token naming",
        )
        bt.subtensor.add_args(parser)
        bt.logging.add_args(parser)
        bt.wallet.add_args(parser)
        Pool.add_args(parser)
        CoinPriceAPI.add_args(parser)

        config = bt.config(parser)
        config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                config.logging.logging_dir,
                config.wallet.name,
                config.wallet.hotkey_str,
                config.netuid,
                "validator",
            )
        )
        os.makedirs(config.full_path, exist_ok=True)
        return config

    def setup_logging(self):
        bt.logging(config=self.config, logging_dir=self.config.full_path)
        bt.logging.info(
            f"Running validator for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:"
        )
        bt.logging.info(self.config)

    def setup_bittensor_objects(self):
        bt.logging.info("Setting up Bittensor objects.")

        self.wallet = bt.wallet(config=self.config)
        bt.logging.info(f"Wallet: {self.wallet}")

        self.subtensor = bt.subtensor(config=self.config)
        bt.logging.info(f"Subtensor: {self.subtensor}")

        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        bt.logging.info(f"Metagraph: {self.metagraph}")

        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            bt.logging.error(
                f"\nYour validator: {self.wallet} is not registered to chain connection: {self.subtensor} \nRun 'btcli register' and try again."
            )
            exit()
        else:
            self.my_subnet_uid = self.metagraph.hotkeys.index(
                self.wallet.hotkey.ss58_address
            )
            bt.logging.info(f"Running validator on uid: {self.my_subnet_uid}")

        # Initial weights scoring
        bt.logging.info("Building validation weights.")
        self.scores = [1.0] * len(self.metagraph.S)
        bt.logging.info(f"Weights: {self.scores}")

        self._serve_axon(
            self.wallet,
            port=self.pool.port,
            ip=self.pool.ip,
        )

    def _set_pool_commitment(self) -> None:
        """Set the pool commitment for Braiins pool."""
        if isinstance(self.pool, BraiinsPool):
            data = f"{self.pool.index.value}:{self.config.pool.user_id}:{self.config.pool.password}"
        else:
            data = f"{self.pool.index.value}:"  # for now

        success = self.subtensor.commit(
            wallet=self.wallet, netuid=self.config.netuid, data=data
        )
        if not success:
            raise ValueError("Failed to set pool commitment")

    def _serve_axon(
        self,
        wallet: bt.wallet,
        ip: str,
        port: int,
    ) -> None:
        # Check if we're already serving this pool
        uid = self.metagraph.hotkeys.index(wallet.hotkey.ss58_address)
        current_axon = self.metagraph.axons[uid]

        try:
            if not ip.replace(".", "").isdigit():  # Check if ip is a domain name
                ip = socket.gethostbyname(ip)
        except socket.gaierror as e:
            raise RuntimeError(f"Could not resolve pool address: {ip}. Error: {str(e)}")

        if current_axon.ip == ip and current_axon.port == port:
            return  # same axon, don't serve twice

        axon = bt.axon(
            wallet=wallet,
            external_ip=ip,  # Use pool IP as external IP
            external_port=port,  # Use pool port for external port
        )
        bt.logging.info(f"Serving axon: {axon}")
        success = self.subtensor.serve_axon(
            axon=axon,
            netuid=self.config.netuid,
            wait_for_inclusion=True,
            wait_for_finalization=True,
        )
        if not success:
            raise RuntimeError("Pool address could not be served")

    def run(self):
        bt.logging.info("Starting validator loop.")
        while True:
            try:
                current_scores = [0.0] * len(self.metagraph.S)
                hotkey_to_uid = {n.hotkey: n.uid for n in self.metagraph.neurons}

                for coin in self.config.coins:
                    miner_metrics: List[MiningMetrics] = get_metrics_for_miners(
                        self.pool, self.metagraph.neurons
                    )
                    coin_price: Optional[float] = self.price_api.get_price(coin)
                    if coin_price is None:
                        # If we can't grab the price, don't count the shares
                        continue

                    fpps: float = self.pool.get_fpps(coin)

                    for metric in miner_metrics:
                        uid = hotkey_to_uid[metric.hotkey]

                        shares_value: float = metric.get_shares_value(fpps)
                        in_usd: float = shares_value * coin_price

                        current_scores[uid] += in_usd

                for i, current_score in enumerate(current_scores):
                    self.moving_avg_scores[i] = (
                        1 - self.alpha
                    ) * self.moving_avg_scores[i] + self.alpha * current_score

                bt.logging.info(f"Moving Average Scores: {self.moving_avg_scores}")

                self.last_update = self.subtensor.blocks_since_last_update(
                    self.config.netuid, self.my_uid
                )

                # Set weights once every tempo + 1
                if self.last_update > self.tempo + 1:
                    total = sum(self.moving_avg_scores)
                    weights = [score / total for score in self.moving_avg_scores]
                    bt.logging.info(f"Setting weights: {weights}")
                    self.subtensor.set_weights(
                        netuid=self.config.netuid,
                        wallet=self.wallet,
                        uids=self.metagraph.uids,
                        weights=weights,
                        wait_for_inclusion=True,
                    )
                    time.sleep(10) # For now to avoid too much throttling
                    self.metagraph.sync()

            except RuntimeError as e:
                bt.logging.error(e)
                traceback.print_exc()

            except KeyboardInterrupt:
                bt.logging.success("Keyboard interrupt detected. Exiting validator.")
                exit()


if __name__ == "__main__":
    validator = Validator()
    validator.run()
