# SPDX-License-Identifier: GPL-2.0-or-later
"""Shared Portuguese/English messages and the GUI language preference."""
from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path

VERSION = "0.2.0"
LANGUAGES = {"pt": "Português", "en": "English"}
_language = ContextVar("pkg_language", default="pt")

# Portuguese source strings keep the original API diagnostics compatible.
ENGLISH = {
    "Arquivo PKG": "PKG file",
    "Pasta de jogos": "Games folder",
    "Selecionar": "Browse",
    "Idioma": "Language",
    "Analisar": "Analyze",
    "Instalar": "Install",
    "Separar patch em CUSAxxxxx-UPDATE (mantém o jogo original intacto)": "Install update in CUSAxxxxx-UPDATE (preserves the base game)",
    "Selecione um PKG para começar.": "Select a PKG to get started.",
    "Selecionar PKG de PS4": "Select a PS4 PKG",
    "Selecionar pasta de jogos do shadPS4": "Select the shadPS4 games folder",
    "Todos os arquivos": "All files",
    "PKG de PS4": "PS4 PKG",
    "Selecione um arquivo PKG válido.": "Select a valid PKG file.",
    "Selecione uma pasta de jogos existente.": "Select an existing games folder.",
    "Confirmar instalação": "Confirm installation",
    "A extração pode ocupar dezenas de GB e substituir arquivos existentes. Continuar?": "Extraction may use tens of GB and replace existing files. Continue?",
    "Dados inválidos": "Invalid input",
    "Analisando...": "Analyzing...",
    "Extraindo, aguarde...": "Extracting, please wait...",
    "Concluído.": "Completed.",
    "Falhou.": "Failed.",
    "Concluído": "Completed",
    "Operação finalizada.": "Operation completed.",
    "Erro": "Error",
    "A operação falhou. Consulte o log.": "The operation failed. Check the log.",
    "ERRO: {error}\n": "ERROR: {error}\n",
    " - restante ~{duration}": " - remaining ~{duration}",
    "{minutes}min {seconds:02d}s": "{minutes}m {seconds:02d}s",
    "{hours}h {minutes:02d}min": "{hours}h {minutes:02d}m",
    "Lista e extrai arquivos de um PKG de PS4": "List and extract files from a PS4 PKG",
    "arquivo .pkg de entrada": "input .pkg file",
    "diretório de saída": "output directory",
    "lista os metadados externos do PKG": "list outer PKG metadata",
    "lista também todos os arquivos do PFS": "also list all PFS files",
    "valida todos os blocos PFS sem gravar arquivos": "validate all PFS blocks without writing files",
    "cria uma pasta com o Title ID dentro do diretório de saída": "create a Title ID folder inside the output directory",
    "diretório de jogos do shadPS4": "shadPS4 games directory",
    "diretório de DLCs do shadPS4": "shadPS4 add-ons directory",
    "instala o patch em CUSAxxxxx-UPDATE em vez de misturá-lo ao jogo": "install the patch in CUSAxxxxx-UPDATE instead of merging into the game",
    "idioma das mensagens": "message language",
    "Tipo: {kind}": "Type: {kind}",
    "JOGO/DLC": "GAME/DLC",
    "Versão: {version}": "Version: {version}",
    "Arquivos: {count}": "Files: {count}",
    "Arquivos PFS: {count}": "PFS files: {count}",
    "Tamanho PFS: {size} bytes": "PFS size: {size} bytes",
    "PFS verificado: {count} arquivos, {size} bytes (sem gravar)": "PFS verified: {count} files, {size} bytes (no files written)",
    "Title ID CUSA inválido; não é possível instalar o pacote": "Invalid CUSA Title ID; cannot install this package",
    "aviso: jogo {title} não encontrado em {root}; o patch não foi aplicado": "warning: game {title} not found in {root}; the patch was not applied",
    "Extraído em: {path}": "Extracted to: {path}",
    "erro: {error}": "error: {error}",
}


ENGLISH.update({'nome de arquivo inseguro: {value0!r}': 'unsafe filename: {value0!r}',
 'destino fora da pasta de extração: {value0!r}': 'destination outside the extraction folder: {value0!r}',
 'entrada de diretório PFS inválida em 0x{value0:x}': 'invalid PFS directory entry at 0x{value0:x}',
 'nome de arquivo PFS inseguro: {value0!r}': 'unsafe PFS filename: {value0!r}',
 'leitura fora do PKG: 0x{value0:x}+0x{value1:x}': 'read outside the PKG: 0x{value0:x}+0x{value1:x}',
 'param.sfo inválido': 'invalid param.sfo',
 'tabela param.sfo inválida': 'invalid param.sfo table',
 'entrada PKG ausente: {value0:#x}': 'missing PKG entry: {value0:#x}',
 'Lendo imagem PFS': 'Reading PFS image',
 'tamanho de cache PFS inválido': 'invalid PFS cache size',
 'PFSC não encontrado; PKG cifrado ou formato não suportado': 'PFSC not found; encrypted PKG or unsupported '
                                                              'format',
 'geometria PFSC não suportada': 'unsupported PFSC geometry',
 'mapa de blocos PFSC truncado': 'truncated PFSC block map',
 'mapa de blocos PFSC fora da imagem': 'PFSC block map outside the image',
 'extensão de bloco PFSC inválida': 'invalid PFSC block extent',
 'índice de bloco PFS inválido: {value0}': 'invalid PFS block index: {value0}',
 'bloco PFS truncado: {value0}': 'truncated PFS block: {value0}',
 'quantidade de inodes PFS inválida': 'invalid PFS inode count',
 'diretório uroot PFS não encontrado': 'PFS uroot directory not found',
 'índice PFS incompleto: {value0} inodes sem caminho': 'incomplete PFS index: {value0} inodes without a path',
 'Índice PFS: {value0} arquivos': 'PFS index: {value0} files',
 'arquivo PFS incompleto: {value0}': 'incomplete PFS file: {value0}',
 'nome PFS não é UTF-8 válido': 'PFS name is not valid UTF-8',
 'cabeçalho PKG truncado': 'truncated PKG header',
 'assinatura PKG inválida': 'invalid PKG signature',
 'tabela de entradas PKG inválida': 'invalid PKG entry table',
 'arquivo PKG truncado: tamanho menor que o declarado': 'truncated PKG file: smaller than the declared size',
 'entrada param.sfo truncada': 'truncated param.sfo entry',
 'inode de diretório PFS inválido: {value0}': 'invalid PFS directory inode: {value0}',
 'nome de entrada PKG inválido: {value0:#x}': 'invalid PKG entry name: {value0:#x}',
 'inode PFS inválido ou não suportado: {value0}': 'invalid or unsupported PFS inode: {value0}',
 'entrada PFS não suportada: {value0!r} (tipo {value1})': 'unsupported PFS entry: {value0!r} (type {value1})',
 'caminho PFS duplicado: {value0}': 'duplicate PFS path: {value0}',
 'referência de diretório PFS inválida: {value0}': 'invalid PFS directory reference: {value0}',
 'diretório PFS cíclico ou inválido: {value0}': 'cyclic or invalid PFS directory: {value0}',
 'inode de arquivo PFS inválido: {value0}': 'invalid PFS file inode: {value0}',
 'RSA PKG: bloco inválido ou truncado': 'RSA PKG: invalid or truncated block',
 'RSA PKG: padding inválido': 'RSA PKG: invalid padding',
 'RSA PKG: mensagem inválida': 'RSA PKG: invalid message',
 'AES-XTS exige dados alinhados em blocos de 16 bytes': 'AES-XTS requires data aligned to 16-byte blocks',
 'tamanho de bloco PFSC inválido': 'invalid PFSC block size',
 'bloco PFSC truncado ou com tamanho descomprimido inválido': 'truncated PFSC block or invalid decompressed '
                                                              'size',
 'bloco PFSC comprimido inválido': 'invalid compressed PFSC block',
 'Verificando': 'Verifying',
 'Extraindo': 'Extracting'})


def tr(message: str, language: str | None = None, **values) -> str:
    language = language or _language.get()
    return (ENGLISH.get(message, message) if language == "en" else message).format(**values)


@contextmanager
def language_context(language: str):
    token = _language.set(language if language in LANGUAGES else "pt")
    try:
        yield
    finally:
        _language.reset(token)


def settings_path() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData/Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "ps4pkg-extractor" / "settings.json"


def load_language() -> str:
    try:
        value = json.loads(settings_path().read_text(encoding="utf-8")).get("language")
        return value if isinstance(value, str) and value in LANGUAGES else "pt"
    except (OSError, ValueError, AttributeError):
        return "pt"


def save_language(language: str) -> bool:
    if language not in LANGUAGES:
        return False
    try:
        target = settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"language": language}) + "\n", encoding="utf-8")
        return True
    except OSError:
        return False
