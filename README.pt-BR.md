# PS4 PKG Extractor

[English](README.md) | **Português**

Extrator de pacotes PKG de PS4 em Python, com interface gráfica em português e inglês,
linha de comando e empacotamento AppImage para Linux.

Reconstrói os arquivos de fake PKGs (FPKG) compatíveis com o fluxo do
shadPS4 0.7.0, preservando a estrutura `CUSAxxxxx/`. Lê diretórios PFS com
múltiplos blocos, extrai os metadados do pacote e instala atualizações sobre
o jogo base ou em uma pasta separada.

## Baixar o aplicativo pronto

Baixe os arquivos na [última Release](https://github.com/Pedromvn/PKG_extractor_ps4/releases/latest):

| Sistema | Download |
| --- | --- |
| Linux x86_64 | [PS4PkgExtractor-x86_64.AppImage](https://github.com/Pedromvn/PKG_extractor_ps4/releases/latest/download/PS4PkgExtractor-x86_64.AppImage) |
| Windows 10/11 x64 | [PS4PkgExtractor-windows-x64.exe](https://github.com/Pedromvn/PKG_extractor_ps4/releases/latest/download/PS4PkgExtractor-windows-x64.exe) |
| SHA-256 | [SHA256SUMS.txt](https://github.com/Pedromvn/PKG_extractor_ps4/releases/latest/download/SHA256SUMS.txt) |

No Windows, execute o `.exe`: ele abre somente a interface gráfica, sem
janela de terminal. Não é necessário instalar Python. No Linux:

```bash
chmod +x PS4PkgExtractor-x86_64.AppImage
./PS4PkgExtractor-x86_64.AppImage
# Se FUSE não estiver disponível:
APPIMAGE_EXTRACT_AND_RUN=1 ./PS4PkgExtractor-x86_64.AppImage
```

Use o seletor **Idioma / Language**, no topo da janela, para alternar entre
**Português** e **English**. A preferência fica salva na pasta de configuração
do usuário, fora do executável. Os botões, diálogos, mensagens e o progresso
acompanham o idioma selecionado. A troca fica disponível quando não há uma
operação em andamento; o histórico já exibido no log é preservado. As últimas
pastas de PKG e de jogos também são lembradas ao reabrir o aplicativo.

## Requisitos e instalação

- Python **3.11 ou superior**.
- `cryptography`, instalada pelo arquivo de dependências.
- Tcl/Tk para a interface gráfica. No Linux, o pacote costuma se chamar
  `python3-tk` em Debian/Ubuntu ou `tk` em Arch/CachyOS.

Dentro da pasta do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

A linha de comando funciona sem Tcl/Tk. O AppImage inclui suas próprias
bibliotecas e dispensa a instalação de Python no computador de destino.

## Interface gráfica

Com o ambiente virtual ativado:

```bash
./run_gui.sh
```

Selecione o PKG e a pasta de jogos e clique em **Instalar**. **Analisar**
mostra os metadados do pacote sem exigir uma pasta de saída. O seletor abre
na pasta do AppImage ou do último PKG selecionado e mostra todos os arquivos
por padrão.

## Verificações antes de instalar

Antes de gravar qualquer arquivo, o aplicativo confere o espaço livre na
unidade de destino considerando todos os arquivos descompactados e metadados,
mais uma margem de 1% (no mínimo 16 MiB). Arquivos já existentes não são
descontados dessa estimativa conservadora, inclusive em reinstalações e patches.

Durante uma operação, os campos ficam desativados e o fechamento da janela é
bloqueado até a conclusão, para evitar uma instalação parcial causada por
fechamento acidental.

## Linha de comando

```bash
# Lista apenas os metadados externos do pacote.
python pkgextract.py jogo.pkg --list

# Mensagens e ajuda em inglês.
python pkgextract.py jogo.pkg --list --language en
python pkgextract.py --help --language en

# Lista também todos os arquivos do PFS.
python pkgextract.py jogo.pkg --list-files

# Valida todos os blocos sem gravar uma extração.
python pkgextract.py jogo.pkg --verify

# Extrai diretamente em dump/.
python pkgextract.py jogo.pkg --output dump

# Instala em games/CUSAxxxxx/.
python pkgextract.py jogo.pkg --games-path games

# Forma equivalente usando --output.
python pkgextract.py jogo.pkg --install --output games
```

`--verify` descriptografa e descompacta os blocos e verifica a estrutura e os
tamanhos. Não verifica assinaturas nem compara hashes com outro dump.

## Atualizações

O jogo base precisa estar instalado e conter `eboot.bin` e
`sce_sys/param.sfo`. O pacote de atualização é identificado automaticamente.
O `TITLE_ID`, os `CONTENT_ID` disponíveis, a categoria e a versão instalada
são validados antes de extrair. Pacotes incompatíveis são recusados. Um patch
mais antigo exige confirmação explícita na interface; no terminal, a operação
para com código de saída 2, a menos que você use `--allow-downgrade`
conscientemente. Essa opção não ignora a identificação do jogo. A versão de
uma pasta de atualização separada também é conferida.

```bash
# Substitui os arquivos correspondentes do jogo instalado.
python pkgextract.py update.pkg --games-path games

# Permite conscientemente um patch compatível mais antigo.
python pkgextract.py update.pkg --games-path games --allow-downgrade

# Grava a atualização em games/CUSAxxxxx-UPDATE/.
python pkgextract.py update.pkg --games-path games --separate-update
```

A extração escreve cada arquivo em um temporário e o substitui ao concluir.
Em caso de falha, os arquivos já concluídos permanecem na pasta; a operação
completa não é uma transação.

## Gerar um AppImage

O build requer Linux x86_64, Python com Tcl/Tk e as ferramentas de
empacotamento. Instale as dependências e baixe o `appimagetool` das
[releases oficiais](https://github.com/AppImage/appimagetool/releases).

```bash
python -m pip install -r requirements-build.txt
chmod +x /caminho/appimagetool
APPIMAGETOOL=/caminho/appimagetool ./build_appimage.sh
```

O resultado padrão é `PS4PkgExtractor-x86_64.AppImage`. Para executar:

```bash
chmod +x PS4PkgExtractor-x86_64.AppImage
./PS4PkgExtractor-x86_64.AppImage

# Alternativa para ambientes sem FUSE.
APPIMAGE_EXTRACT_AND_RUN=1 ./PS4PkgExtractor-x86_64.AppImage
```

Opções de build:

| Variável | Finalidade |
| --- | --- |
| `APPIMAGETOOL` | Caminho do empacotador executável. |
| `APPIMAGE_RUNTIME` | Runtime local opcional, disponível no [projeto oficial](https://github.com/AppImage/type2-runtime/releases). |
| `OUTPUT_APPIMAGE` | Caminho completo do arquivo final; a pasta precisa existir. |
| `SKIP_DEPENDENCIES=1` | Reutiliza as dependências instaladas no ambiente de build. |
| `TK_ROOT` | Pasta com Tcl/Tk extraídos localmente, sem instalar no sistema. |

Para `TK_ROOT`, use a estrutura `usr/lib/x86_64-linux-gnu` e
`usr/share/tcltk/{tcl8.6,tk8.6}`. O script também reconhece dependências locais
em `build-appimage/{appimagetool,runtime-x86_64,tkroot}`. Esses artefatos são
gerados ou obtidos separadamente e não integram o repositório.

O build gera o arquivo `.spec` dentro de `build-appimage/` e substitui o
AppImage de destino somente após o empacotamento terminar com sucesso.
## Gerar o executável Windows

No Windows x64 com Python instalado, execute no PowerShell:

```powershell
./build_windows.ps1
```

O resultado é `build-windows/dist/PS4PkgExtractor-windows-x64.exe`. É um
executável único com Python, Tcl/Tk e as dependências incluídas. O build
Windows precisa ser executado no Windows; não é uma compilação cruzada.

O workflow **Build executables** também pode ser executado manualmente no
GitHub Actions. Ele testa a interface real nos dois sistemas, gera os arquivos
e testa o backend empacotado em português e inglês com um PKG sintético.
Tags `v*` disparam os builds e publicam os dois executáveis e seus hashes em
uma Release, após os dois sistemas passarem nos testes.

## Desenvolvimento

```bash
python -m unittest discover -s tests -v
```

Os testes usam dados sintéticos e não dependem de jogos ou PKGs locais.
Os testes da lógica da interface precisam das bibliotecas Tcl/Tk, mas não
de um display. Quando Tcl/Tk não está disponível, eles são ignorados.
O GitHub Actions instala essas bibliotecas e executa a suíte em Python
3.11, 3.12, 3.13 e 3.14.

Arquivos principais:

| Arquivo | Responsabilidade |
| --- | --- |
| `pkgextract.py` | Interface de linha de comando e instalação. |
| `pkgextract_gui.py` | Interface gráfica Tkinter. |
| `pkg_full.py` | Leitura do PKG, índice PFS e extração. |
| `pkg_checks.py` | Espaço em disco, leitura SFO e validação de patches. |
| `pkg_crypto.py` | Operações criptográficas e descompressão. |
| `pkg_i18n.py` | Traduções e preferência de idioma. |
| `tests/` | Testes de regressão do parser, CLI e interface. |
| `build_appimage.sh` | Build do executável para Linux. |
| `build_windows.ps1` | Build do executável para Windows. |

## Compatibilidade

O projeto suporta os fake PKGs compatíveis com o fluxo implementado.
Pacotes comerciais que exigem outras chaves não são suportados. A extração
não garante que um jogo seja compatível com uma versão específica do emulador.
DLCs com instalação em diretório separado ainda não são implementados;
`--addons-path` está reservado para essa integração futura.

## Licença e créditos

Licença **GPL-2.0-or-later**, conforme [LICENSE](LICENSE).
O parser e o fluxo criptográfico usam como referência o projeto shadPS4
0.7.0. Créditos e referências estão em [NOTICE.md](NOTICE.md).
