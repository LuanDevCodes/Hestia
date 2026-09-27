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
if [ "$(id -u)" -ne 0 ]; then
    echo "A automação Hestia precisa de permissões de administrador para proteger o /boot"
    echo "Elevando privilégios via sudo..."
    
    # Usa o caminho absoluto garantido em vez de $0
    exec sudo "${BASH_SOURCE[0]}" "$@"
    echo "[ERRO] (x_x) Falha ao elevar privilegios com sudo"
    exit 1
fi

# Validação de dependência do interpretador Python3
if ! command -v python3 &> /dev/null; then
    echo "[ERRO] (x_x) Interpretador python3 não foi encontrado no sistema"
    exit 1
fi

# Execução da automação em Python
echo "[#] (◕‿◕) Iniciando execução da Guardiã Hestia"

# Força o terminal a entrar na pasta do projeto
# Isso garante que a pasta /backups seja criada no local certo
cd "$DIRETORIO_ATUAL" || exit 1

# Garante a chamada via python3 nativo do CachyOS repassando os parâmetros recebidos
python3 "$SCRIPT_PYTHON" "$@"
CODIGO_RETORNO=$?

# Finalização repassando o código de saída original
exit $CODIGO_RETORNO