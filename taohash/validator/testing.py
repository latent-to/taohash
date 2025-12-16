import bittensor
from bittensor.core.subtensor import Subtensor
from bittensor.core.axon import Axon
from bittensor_wallet import Wallet

def main():
    # Configuration
    wallet_name = "sdk_testing"
    wallet_hotkey = "default"
    network = "local"
    netuid = 2
    axon_port = 8091
    axon_ip = "192.168.1.1"

    print(f"Connecting to {network} network...")
    subtensor = Subtensor(network=network)
    
    print(f"Loading wallet {wallet_name}:{wallet_hotkey}...")
    wallet = Wallet(name=wallet_name, hotkey=wallet_hotkey)
    
    print(f"Creating Axon on {axon_ip}:{axon_port}...")
    axon = Axon(
        wallet=wallet,
        port=axon_port,
        ip=axon_ip,
        external_ip=axon_ip,
        external_port=axon_port
    )

    print(f"Serving axon on netuid {netuid} with MEV protection...")
    success = subtensor.serve_axon(
        netuid=netuid,
        axon=axon,
        # mev_protection=True,
        wait_for_inclusion=True,
        wait_for_finalization=True,
        # wait_for_revealed_execution=True,
    )

    if success:
        print("Axon served successfully!")
    else:
        print("Failed to serve axon.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
