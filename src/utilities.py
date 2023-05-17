import aiohttp
import os

from fastecdsa.keys import import_key, gen_keypair, export_key
from fastecdsa import ecdsa, curve


class Utilities:

    @staticmethod
    def generate_key_pair():
        # Generate private/public key pair
        pvt, pub = gen_keypair(curve.secp256k1)
        # Specify filenames for keys
        private_key_filename = './keys/private_key.pem'
        public_key_filename = './keys/public_key.pem'

        # Check if the files exist and delete them if they do
        if os.path.exists(private_key_filename):
            os.remove(private_key_filename)
        if os.path.exists(public_key_filename):
            os.remove(public_key_filename)

        # Export keys and overwrite files if they exist
        export_key(pvt, curve=curve.secp256k1, filepath='./keys/private_key.pem')
        export_key(pub, curve=curve.secp256k1, filepath='./keys/public_key.pem')

    @staticmethod
    async def make_post(url, data):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=data) as response:
                    return await response.json()
            except aiohttp.ClientConnectorError as e:
                # handle connection error
                print("POST request failed:", e)
            except aiohttp.ServerDisconnectedError as e:
                # handle server disconnected error
                print("POST request failed:", e)
            except Exception as e:
                # handle all other errors
                print("POST request failed:", e)

    @staticmethod
    async def make_get(url):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    return await response.json()
            except aiohttp.ClientConnectorError as e:
                # handle connection error
                print("GET request failed:", e)
            except aiohttp.ServerDisconnectedError as e:
                # handle server disconnected error
                print("GET request failed:", e)
            except Exception as e:
                # handle all other errors
                print("GET request failed:", e)
