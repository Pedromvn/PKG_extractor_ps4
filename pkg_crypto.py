# SPDX-License-Identifier: GPL-2.0-or-later
"""Small cryptographic primitives used by the PS4 PKG/PFS reader.

The RSA values are the public shadPS4 v0.7.0 package keysets. They are used
only to unwrap the per-package keys; game content remains protected by the
package's own AES/PFS keys.
"""

from __future__ import annotations

import hashlib
import hmac
import struct
import zlib

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


# Values from shadPS4 v0.7.0, PkgDerivedKey3Keyset and FakeKeyset.
DK3_N = int("d212fc335f6ddb831609628b0356273782d477853529392d526b8c4c8cfb06c1845be7d4f7bcd24e6245cd2abbd77776453655273fb3f5f98eda4befaa59aeb39bea5498d206326a58312ae0d44f90b50a7decf43a9c52672d99318e0c43e682fe0746e12e50d41f2d2f7ed908ba06b3bf2e203f4e3ffe44ffaa50435791699449158282e40f4c8d9d2cc95b1d64bf888bd4c594e76547841ee57910fb989347b97d8512a640982cf792bc951932ede890560d65c1aa78c62e54fd5f54a1f67ee5e05f61c120b4b9b4330870e4df8956ed012946775f8cb8a9f51e2eb3b9bfe009b78d28d4a6c3b81e1f07ebb4120b95b88530fddc3913d07cdc8fedf9c9a3c1", 16)
DK3_D = int("32d903908fbdb08f572b285e0b8db3ea5cd17ea890888cdd6a80bbb1dfc1f70daa32f0b77ccb88800e8b64b0be4cd60e9b8c1e2a64e1f35cd77601415e935c94fedd4662c31b5ae2a0bc2debc3980aa7b7856970682b644ab31fcc7ddc7c26f477f65cf2ae5a442dd3ab16620419bafb90ffe23050896ecb56b2ebc09116925e308eaec7945dfd35e120f8ad3ebc08bfc036749fd5bb5208fd0666f37ab304f475295de95faa1030b20f5a1ac12ab3fecb21ad80ec8f20091cdbc55894c29cc6ce82653e5790bca98b06b4f072f677df9864f1ecfe372dbcae8c08811fc3c9891ac742824b2edc8e8d73ceb1cc01d90870873c4408ec498f815ae240ff77fc0d", 16)
FAKE_N = int("c6cf71e7e59af0d12a2c458bf92a0ec143058bc37117801dcd497dde359d259ba0d7a0f27d6c087eaa5502682b23c644b84418eb56cf16a24803c9e74f87eb3d30c31588bf20e79dff770cde1d241e63a94f8abf5bbe601968333bfced9f474e5ff8eacb3d00bd6701f92c6dc6ac1364e76714f3dc52696ab9832c4230131bb2d8a5020d79ed96b10df8cc0cdf81954f035809570e80692efeff5277ea7528a8fbc9bebf9fbbb7798e1805e180bd50349481d353c269a2d24ccf6cf4572c104a3ffb22fd8b97e2c95ba62bcdd61b6bdb687f4bc2a05034c005e58def2467ff9340cf2d62a2a050b1f13aa83dfd80d1f9b80522afc8354590588ee33a7cbd3e27", 16)
FAKE_D = int("7f76cd0ee2d4de051cc6d9a80e8dfa7bca1eaa271a40f8f1228735dddbfdeef8c2bcbd01fb8be23e63b2b1225c56496e11be07440b9a2666d1492c8fd31bcfa4a1b8d1fba49ed2212883098af6a00ba3d60f9b6368ccbc0c4e145b27a4a9f42bb9b87bc0e651ad1d77d46bb9ce20d126667e5e9ea2e96b90f373b8528f4411030c1397393d132258d5438249da6e7ca1c58ca5b009e0ce3ddff49d3c9715e26ac72b3c509323dbba4a226644ac78bb0e1a2743b57167aff4ab48469373d042ab9363e56c9ade5024c0237d99793f2207e0c148561bdf830912b42d456bc9c06885999079961ad7f54d1f3783404aec3937a680927dc580c7d66ffe8a7989c6b1", 16)


def rsa_pkcs1_decrypt(ciphertext: bytes, modulus: int, exponent: int) -> bytes:
    if len(ciphertext) != 256 or int.from_bytes(ciphertext, "big") >= modulus:
        raise ValueError("RSA PKG: bloco inválido ou truncado")
    block = pow(int.from_bytes(ciphertext, "big"), exponent, modulus).to_bytes(256, "big")
    if not block.startswith(b"\0\2"):
        raise ValueError("RSA PKG: padding inválido")
    separator = block.find(b"\0", 2)
    if separator < 10:
        raise ValueError("RSA PKG: mensagem inválida")
    return block[separator + 1:]


def aes_cbc(key: bytes, iv: bytes, data: bytes) -> bytes:
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    return decryptor.update(data) + decryptor.finalize()


def derive_iv_key(entry: bytes, dk3: bytes) -> bytes:
    return hashlib.sha256(entry + dk3).digest()


def unwrap_keys(entry: bytes, dk3_cipher: bytes, image_key: bytes) -> tuple[bytes, bytes]:
    dk3 = rsa_pkcs1_decrypt(dk3_cipher, DK3_N, DK3_D)[:32]
    iv_key = derive_iv_key(entry, dk3)
    image = aes_cbc(iv_key[16:], iv_key[:16], image_key)
    ekpfs = rsa_pkcs1_decrypt(image, FAKE_N, FAKE_D)[:32]
    return dk3, ekpfs


def pfs_keys(ekpfs: bytes, seed: bytes) -> tuple[bytes, bytes]:
    digest = hmac.new(ekpfs, struct.pack("<I", 1) + seed, hashlib.sha256).digest()
    return digest[16:], digest[:16]


def xts_decrypt(data_key: bytes, tweak_key: bytes, data: bytes, sector: int) -> bytes:
    if not data or len(data) % 16:
        raise ValueError("AES-XTS exige dados alinhados em blocos de 16 bytes")

    # Let OpenSSL process each 0x1000 sector in native code. PS4 PFS resets
    # the XTS tweak at every sector; the previous implementation created one
    # AES context per 16-byte block.
    result = bytearray(len(data))
    for offset in range(0, len(data), 0x1000):
        extent = data[offset:offset + 0x1000]
        tweak = struct.pack("<Q", sector + offset // 0x1000) + b"\0" * 8
        cipher = Cipher(algorithms.AES(data_key + tweak_key), modes.XTS(tweak))
        result[offset:offset + len(extent)] = cipher.decryptor().update(extent)
    return bytes(result)


def inflate_block(data: bytes) -> bytes:
    if len(data) == 0x10000:
        return bytes(data)
    if not 0 < len(data) < 0x10000:
        raise ValueError("tamanho de bloco PFSC inválido")
    try:
        decoder = zlib.decompressobj()
        block = decoder.decompress(data, 0x10001)
    except zlib.error as error:
        raise ValueError("bloco PFSC comprimido inválido") from error
    if len(block) != 0x10000 or not decoder.eof or decoder.unused_data:
        raise ValueError("bloco PFSC truncado ou com tamanho descomprimido inválido")
    return block
