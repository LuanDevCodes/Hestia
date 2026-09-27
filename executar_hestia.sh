#!/usr/bin/env bash
# ==============================================================================
# Projeto Hestia - Script Shell Wrapper de Inicialização e Permissões
# Propósito: Garantir que a automação Hestia execute com privilégios de superusuário (sudo)
# e localize o interpretador Python e caminhos corretos independentemente de onde for invocada
# ==============================================================================

# Identifica o diretório real onde este script reside no sistema de arquivos
DIRETORIO_ATUAL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_PYTHON="$DIRETORIO_ATUAL/Hestia.py"

# Validação de privilégios administrativos (Root)
# No Linux, $(id -u) igual a 0 indica que o processo já está rodando como root
# Como o arquivo /boot/limine.conf pertence ao root, permissões elevadas são obrigatórias para gravação
if [ "$(id -u)" -ne 0 ]; then
    echo "A automação Hestia precisa de permissões de administrador para proteger o /boot"
    echo "Elevando privilégios via sudo..."
    
    # Reexecuta este mesmo script repassando todos os argumentos através do sudo
    exec sudo "$0" "$@"
    echo "[ERRO] (x_x) Falha ao elevar privilegios com sudo"
    exit 1
fi

# Validação de dependência do interpretador Python3
if ! command -v python3 &> /dev/null; then
    echo "[ERRO] (x_x) Interpretador python3 não foi encontrado no sistema"
    exit 1
fi

# Execução da automação em Python
# Garante a chamada via python3 nativo do CachyOS repassando os parâmetros recebidos
echo "[#] (◕‿◕) Iniciando execução da Guardiã Hestia"
python3 "$SCRIPT_PYTHON" "$@"
CODIGO_RETORNO=$?

# Finalização repassando o código de saída original
exit $CODIGO_RETORNO