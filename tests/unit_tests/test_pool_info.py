
import unittest
from taohash.core.chain_data.pool_info import PoolInfo, encode_pool_infos, decode_pool_infos
from taohash.core.pool import PoolIndex

class TestPoolInfo(unittest.TestCase):
    def test_pool_info_encoding_decoding(self):
        # Create sample pool infos
        pool_btc = PoolInfo(
            pool_index=PoolIndex.BTC.value,
            port=3333,
            ip="127.0.0.1",
            domain="btc.example.com",
            username="btc_user",
            password="x",
            high_diff_port=3334
        )
        
        pool_kas = PoolInfo(
            pool_index=PoolIndex.KAS.value,
            port=4444,
            ip="192.168.1.1",
            domain="kas.example.com",
            username="kas_user",
            password="y",
            high_diff_port=4445
        )
        
        pool_infos = [pool_btc, pool_kas]
        
        # Encode
        encoded = encode_pool_infos(pool_infos)
        self.assertIsInstance(encoded, bytes)
        self.assertLessEqual(len(encoded), 128, "Encoded data exceeds 128 bytes limit")
        
        # Decode
        decoded_infos = decode_pool_infos(encoded)
        
        # Verify
        self.assertEqual(len(decoded_infos), 2)
        
        # Check BTC
        decoded_btc = decoded_infos[0]
        self.assertEqual(decoded_btc.pool_index, PoolIndex.BTC.value)
        self.assertEqual(decoded_btc.port, 3333)
        self.assertEqual(decoded_btc.domain, "btc.example.com")
        self.assertEqual(decoded_btc.username, "btc_user")
        
        # Check KAS
        decoded_kas = decoded_infos[1]
        self.assertEqual(decoded_kas.pool_index, PoolIndex.KAS.value)
        self.assertEqual(decoded_kas.port, 4444)
        self.assertEqual(decoded_kas.domain, "kas.example.com")
        self.assertEqual(decoded_kas.username, "kas_user")

    def test_single_pool_info_encoding(self):
        # Regression test for single item
        pool_bch = PoolInfo(
            pool_index=PoolIndex.BCH.value,
            port=5555,
            ip="10.0.0.1"
        )
        
        pool_infos = [pool_bch]
        encoded = encode_pool_infos(pool_infos)
        decoded = decode_pool_infos(encoded)
        
        self.assertEqual(len(decoded), 1)
        self.assertEqual(decoded[0].pool_index, PoolIndex.BCH.value)
        self.assertEqual(decoded[0].port, 5555)

if __name__ == '__main__':
    unittest.main()
