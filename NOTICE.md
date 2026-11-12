# Créditos e licença

Este projeto é distribuído sob a licença **GPL-2.0-or-later**: GNU General
Public License, versão 2 ou, a seu critério, qualquer versão posterior.
O texto da versão 2 está em [LICENSE](LICENSE).

O formato PKG/PFS, o fluxo criptográfico e os valores RSA de `pkg_crypto.py`
foram baseados no trabalho do [projeto shadPS4](https://github.com/shadps4-emu/shadPS4),
com referência à versão **0.7.0**:

- [`pkg.cpp`](https://github.com/shadps4-emu/shadPS4/blob/v.0.7.0/src/core/file_format/pkg.cpp)
- [`pfs.h`](https://github.com/shadps4-emu/shadPS4/blob/v.0.7.0/src/core/file_format/pfs.h)
- [`crypto.cpp`](https://github.com/shadps4-emu/shadPS4/blob/v.0.7.0/src/core/crypto/crypto.cpp)

Os arquivos de referência do shadPS4 identificam a licença GPL-2.0-or-later
e o copyright do shadPS4 Emulator Project. O extrator Python é um projeto
independente, sem vínculo oficial com shadPS4 ou Sony.

Dependências de execução e empacotamento, como Python, Tcl/Tk, cryptography,
PyInstaller e AppImage, mantêm suas próprias licenças. Jogos, pacotes PKG,
dumps e binários de emuladores não fazem parte deste repositório.
