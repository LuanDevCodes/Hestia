# Projeto Hestia - Guardiã da Configuração do Bootloader (Limine) e OpenRGB
# Seu propósito é garantir que as informações necessárias para a sincronização do led da RAM sempre existam
# ----------------------------------------------------------------------------------
# Bibliotecas usadas no projeto ([*N*] -> Nativa, [*E*] -> Externa, [*L*] -> Local)
# ----------------------------------------------------------------------------------
import os                                              # [*N*] - Manipulação de caminhos e arquivos do sistema operacional
import sys                                             # [*N*] - Controle de saída do interpretador e argumentos
import shutil                                          # [*N*] - Cópia segura de arquivos preservando metadados originais
import logging                                         # [*N*] - Registro formal e rastreabilidade dos passos da automação
import tempfile                                        # [*N*] - Criação segura de arquivos temporários
from datetime import datetime                          # [*N*] - Geração de carimbos de data e hora para os backups
from logging.handlers import RotatingFileHandler       # [*N*] - Gerenciamento de rotação de logs para não estourar o disco
from typing import List, Tuple, Optional               # [*N*] - Tipagem de dados para maior clareza e segurança no código

# --------------------------------------------------------------------------------------------------------------------
# ORGANIZANDO AS VARIÁVEIS GLOBAIS E CONFIGURAÇÕES
# --------------------------------------------------------------------------------------------------------------------

# Caminho do arquivo de configuração do Limine no sistema operacional Linux (CachyOS)
CAMINHO_LIMINE = '/boot/limine.conf'

# Parâmetro do kernel necessário para liberar a comunicação I2C/SMBus com as memórias RAM no OpenRGB
PARAMETRO_ALVO = 'acpi_enforce_resources=lax'

# Identificador específico do kernel primário (garante que entradas LTS e Snapshots fiquem intactas)
BLOCO_KERNEL_PRIMARIO = '//linux-cachyos'

# Limite máximo de backups históricos mantidos na pasta local
LIMITE_BACKUPS = 5

# Limite máximo de arquivos de log rotacionados e tamanho máximo de 50 MB por arquivo
LIMITE_ARQUIVOS_LOG = 5
TAMANHO_MAXIMO_LOG_BYTES = 50 * 1024 * 1024  # 50 Megabytes em bytes

# Limite máximo de tentativas da função guardiã antes de acionar o rollback preventivo
MAX_TENTATIVAS = 3

# Definição dos caminhos locais da automação (onde o script reside)
caminho_base = os.path.dirname(os.path.abspath(__file__))
pasta_backups = os.path.join(caminho_base, "backups")
caminho_arquivo_log = os.path.join(caminho_base, "hestia_execucao.log")

# ---------------------------------------------------------------------------------------------------------------
# ***************************************************************************************************************
# ---------------------------------------------------------------------------------------------------------------

def configurar_logger() -> logging.Logger:
    
    """
    Configura o logger do Hestia utilizando RotatingFileHandler
    Garante que os logs não ultrapassem 50 MB por arquivo e mantém no máximo 5 cópias
    Também direciona a saída para o terminal para visualização em tempo real
    """

    logger = logging.getLogger("Hestia")
    logger.setLevel(logging.INFO)

    # Evita duplicação de handlers caso a função seja chamada mais de uma vez
    if not logger.handlers:
        
        # Handler para o arquivo rotativo (50 MB por arquivo, até 5 backups)
        handler_arquivo = RotatingFileHandler(
            caminho_arquivo_log,
            maxBytes=TAMANHO_MAXIMO_LOG_BYTES,
            backupCount=LIMITE_ARQUIVOS_LOG,
            encoding='utf-8'
        )
        formato_arquivo = logging.Formatter(
            '%(asctime)s [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler_arquivo.setFormatter(formato_arquivo)
        logger.addHandler(handler_arquivo)

        # Handler para o console (saída visual imediata)
        handler_console = logging.StreamHandler(sys.stdout)
        formato_console = logging.Formatter('%(message)s')
        handler_console.setFormatter(formato_console)
        logger.addHandler(handler_console)

    return logger

# Inicialização global do logger para ser usado em todas as rotinas
logger = configurar_logger()

# -------------------------------
# *******************************
# -------------------------------

def criar_backup_preventivo(caminho_origem: str) -> Optional[str]:
    
    """
    Copia o arquivo de configuração atual para a pasta de backups com data e hora
    Aplica a regra de rotação para manter apenas os 5 backups mais recentes
    """
    
    try:
        # Garante a existência da subpasta de backups
        if not os.path.exists(pasta_backups):
            os.makedirs(pasta_backups, exist_ok=True)
            logger.info(f"[DIR] (◕‿◕) Pasta de backups criada em: {pasta_backups}")

        # Gera o nome do backup contendo timestamp para identificação fácil
        timestamp_atual = datetime.now().strftime("%Y-%m-%d_%H-%M-%S_%f")
        nome_backup = f"limine_backup_{timestamp_atual}.conf"
        caminho_destino = os.path.join(pasta_backups, nome_backup)

        # Copia o arquivo preservando os metadados
        shutil.copy2(caminho_origem, caminho_destino)
        logger.info(f"[OK] (•̀ᴗ•́)و Backup preventivo realizado com sucesso: {nome_backup}")

        # Realiza a limpeza de backups antigos se ultrapassar o limite de 5
        gerenciar_rotacao_backups()

        return caminho_destino

    except Exception as e:
        logger.error(f"[ERRO] (x_x) Falha crítica ao gerar backup preventivo: {e}")
        return None

# -------------------------------
# *******************************
# -------------------------------

def gerenciar_rotacao_backups() -> None:

    """
    Lista todos os backups existentes na subpasta e remove os mais antigos
    caso a contagem exceda o limite estipulado
    """

    try:
        arquivos = [
            os.path.join(pasta_backups, f)
            for f in os.listdir(pasta_backups)
            if f.startswith("limine_backup_") and f.endswith(".conf")
        ]

        # Se houver mais arquivos que o limite, ordena pelo tempo de modificação (do mais velho para o mais novo)
        if len(arquivos) > LIMITE_BACKUPS:
            arquivos.sort(key=os.path.getmtime)
            quantidade_para_remover = len(arquivos) - LIMITE_BACKUPS

            for i in range(quantidade_para_remover):
                arquivo_antigo = arquivos[i]
                os.remove(arquivo_antigo)
                logger.info(f"[*] (^_~) Rotação de backup: cópia antiga removida -> {os.path.basename(arquivo_antigo)}")

    except Exception as e:
        logger.warning(f"[AVISO] (o_o;) Aviso na rotação de backups (não impede a execução): {e}")

# -------------------------------
# *******************************
# -------------------------------

def restaurar_backup_emergencia(caminho_backup: str, caminho_destino: str) -> bool:

    """
    Função de resgate em caso crítico, restaura o arquivo do backup copiando-o
    de volta para o destino original sem remover a cópia da pasta de backup

    """
    try:
        logger.warning(f"[ALERTA] (╯°□°)╯ Acionando reversão de emergência! Restaurando: {os.path.basename(caminho_backup)}")
        
        # Apenas copia, mantendo o arquivo na pasta de backups
        shutil.copy2(caminho_backup, caminho_destino)
        logger.info("[OK] (´▽｀) Reversão concluída: Arquivo restaurado para a versão anterior segura")
        return True

    except Exception as e:
        logger.critical(f"[FATAL] (X_X) ERRO CRÍTICO: Falha ao restaurar o backup de emergência: {e}")
        return False

# -------------------------------
# *******************************
# -------------------------------

def analisar_bloco_limine(linhas: List[str]) -> Tuple[bool, bool, Optional[int]]:

    """
    Analisa cirurgicamente as linhas do limine.conf em memória
    Identifica se está dentro do bloco do kernel primário (//linux-cachyos)
    
    Retorna uma tupla contendo:
    - bloco_encontrado (bool): Indica se localizou o bloco //linux-cachyos
    - precisa_alterar (bool): Indica se a string acpi_enforce_resources=lax está ausente
    - indice_cmdline (Optional[int]): Índice exato da linha 'cmdline:' a ser modificada
    """

    dentro_do_bloco_primario = False
    indice_cmdline = None

    for indice, linha in enumerate(linhas):
        linha_limpa = linha.strip()

        # Identifica se entrou em uma seção de kernel ou snapshot
        if linha_limpa.startswith('//'):
            if linha_limpa == BLOCO_KERNEL_PRIMARIO:
                dentro_do_bloco_primario = True
            else:
                # Se encontrar qualquer outra entrada (ex: //linux-cachyos-lts ou //Snapshots), sai do bloco primário
                dentro_do_bloco_primario = False

        # Se estivermos dentro do bloco primário, procuramos a diretiva 'cmdline:'
        if dentro_do_bloco_primario and linha_limpa.startswith('cmdline:'):
            indice_cmdline = indice
            
            # Verifica se o parâmetro já está presente na linha
            if PARAMETRO_ALVO in linha:
                return True, False, indice_cmdline
            else:
                return True, True, indice_cmdline

    # Caso percorra todo o arquivo
    bloco_encontrado = (indice_cmdline is not None)
    return bloco_encontrado, False, indice_cmdline

# -------------------------------
# *******************************
# -------------------------------

def aplicar_injecao_memoria(linhas: List[str], indice_cmdline: int) -> List[str]:

    """
    Aplica a injeção cirúrgica da string na linha específica da memória
    Preserva a estrutura original e adiciona a string precedida de espaço
    """

    linhas_modificadas = list(linhas)
    linha_original = linhas_modificadas[indice_cmdline]

    # Remove quebras de linha e eventuais espaços extras no final antes de injetar
    linha_base = linha_original.rstrip('\r\n').rstrip()
    
    # Injeta a string com espaço prévio conforme os requisitos
    linhas_modificadas[indice_cmdline] = f"{linha_base} {PARAMETRO_ALVO}\n"
    
    return linhas_modificadas

# -------------------------------
# *******************************
# -------------------------------

def validar_sanidade_conteudo(linhas_originais: List[str], linhas_modificadas: List[str], indice_cmdline: int) -> bool:
    
    """
    Sanity Check (Validação Pré-Aprovação):
    Verifica se a estrutura do arquivo se manteve íntegra antes de autorizar a gravação no disco seguindo as diretrizes:
    -> Mesma quantidade total de linhas
    -> A linha modificada contém a diretiva 'cmdline:' e o parâmetro alvo
    -> As outras linhas do arquivo permaneceram idênticas
    """

    # Checagem de quantidade de linhas
    if len(linhas_originais) != len(linhas_modificadas):
        logger.error("[ERRO] (>_<) Sanity Check falhou, a contagem de linhas foi alterada indevidamente")
        return False

    # Checagem da linha modificada
    linha_nova = linhas_modificadas[indice_cmdline]
    if not (linha_nova.strip().startswith('cmdline:') and PARAMETRO_ALVO in linha_nova):
        logger.error("[ERRO] (¬_¬) Sanity Check falhou, linha alvo não contém o parâmetro ou perdeu a sintaxe 'cmdline:'")
        return False

    # Checagem de integridade das demais linhas
    for i in range(len(linhas_originais)):
        if i != indice_cmdline and linhas_originais[i] != linhas_modificadas[i]:
            logger.error(f"[ERRO] (O_O) Sanity Check falhou, linha {i + 1} foi alterada sem autorização")
            return False

    logger.info("[OK] (ง'̀-'́)ง Sanity Check aprovado, modificação em memória verificada e segura")
    return True

# -------------------------------
# *******************************
# -------------------------------

def salvar_alteracoes_disco(caminho_arquivo: str, linhas_para_salvar: List[str]) -> bool:

    """
    Função de aprovação, escreve no disco apenas após todas as validações prévias passarem
    Utiliza escrita atômica para garantir integridade mesmo durante falhas de energia
    """

    try:
        diretorio = os.path.dirname(caminho_arquivo)
        
        # Escreve em um arquivo temporário primeiro
        with tempfile.NamedTemporaryFile('w', dir=diretorio, suffix='.tmp', delete=False, encoding='utf-8') as tmp:
            tmp.writelines(linhas_para_salvar)
            tmp.flush()                 # Força o Python a esvaziar seu buffer
            os.fsync(tmp.fileno())      # Força o S.O. a gravar fisicamente no disco
            nome_temporario = tmp.name

        # Substituição atômica no mesmo filesystem
        os.replace(nome_temporario, caminho_arquivo)
        
        logger.info("[OK] (b^_^)b Gravação física atômica concluída no disco")
        return True

    except PermissionError:
        if 'nome_temporario' in locals() and os.path.exists(nome_temporario):
            os.remove(nome_temporario)
        logger.error("[ERRO] (T_T) Permissão negada, a automação precisa de permissão de superusuário (sudo) para gravar no /boot")
        return False
    except Exception as e:
        if 'nome_temporario' in locals() and os.path.exists(nome_temporario):
            os.remove(nome_temporario)
        logger.error(f"[ERRO] (x_x) Erro inesperado ao salvar no disco: {e}")
        return False

# -------------------------------
# *******************************
# -------------------------------

def guardiao_validacao_final(caminho_arquivo: str) -> bool:

    """
    Função Guardiã Pós-Gravação
    Relê o arquivo diretamente do disco físico e confirma se a modificação
    no bloco primário foi persistida com sucesso e sem corrupções
    """

    try:
        with open(caminho_arquivo, 'r', encoding='utf-8') as arquivo:
            linhas_disco = arquivo.readlines()

        bloco_encontrado, precisa_alterar, _ = analisar_bloco_limine(linhas_disco)

        # Se o bloco existe e não é preciso alterar, significa que a string está lá perfeitamente
        if bloco_encontrado and not precisa_alterar:
            logger.info("[OK] (*^‿^*) Guardiã Hestia: Verificação física do disco confirmada com sucesso!")
            return True
        else:
            logger.warning("[AVISO] (o_o;) Guardiã Hestia: Inconsistência detectada na leitura pós-gravação")
            return False

    except Exception as e:
        logger.error(f"[ERRO] (x_x) Guardiã Hestia: Falha ao reler o arquivo do disco: {e}")
        return False

# ---------------------------------------------------------------------------------------------------------------
# ***************************************************************************************************************
# ---------------------------------------------------------------------------------------------------------------

def main(caminho_teste: Optional[str] = None):

    """
    Ciclo principal de execução da Hestia:
    Controla o fluxo, invoca os testes, aciona tentativas
    e executa o rollback automático em caso de qualquer falha persistente
    Permite passar um caminho alternativo para testes em ambiente de desenvolvimento
    """

    caminho_alvo = caminho_teste or (sys.argv[1] if len(sys.argv) > 1 else CAMINHO_LIMINE)

    logger.info("")
    logger.info("=" * 70)
    logger.info(f"[#] (◕‿◕) Hestia iniciando verificação de integridade - {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    logger.info(f"[FILE] ( -_・) Arquivo sob proteção: {caminho_alvo}")
    logger.info("=" * 70)

    # Verifica se o arquivo alvo existe no sistema
    if not os.path.exists(caminho_alvo):
        logger.warning(f"[AVISO] (O_O) Arquivo de configuração não encontrado: {caminho_alvo}")
        return

    # Leitura inicial do arquivo para memória
    try:
        with open(caminho_alvo, 'r', encoding='utf-8') as arquivo:
            linhas_originais = arquivo.readlines()
    except Exception as e:
        logger.error(f"[ERRO] (x_x) Não foi possível ler o arquivo {caminho_alvo}: {e}")
        return

    # Análise em memória para determinar a necessidade de modificação
    bloco_encontrado, precisa_alterar, indice_cmdline = analisar_bloco_limine(linhas_originais)

    if not bloco_encontrado:
        logger.error(f"[ERRO] (o_O) Bloco primário '{BLOCO_KERNEL_PRIMARIO}' não foi localizado no arquivo")
        return

    if not precisa_alterar:
        logger.info(f"[*] (^o^) Configuração já presente no bloco {BLOCO_KERNEL_PRIMARIO}. Nenhuma ação necessária")
        logger.info("OpenRGB apto para comunicação I2C/SMBus com as memórias")
        logger.info("=" * 70)
        return

    logger.info(f"[!] (•̀o•́)v Parâmetro '{PARAMETRO_ALVO}' ausente no kernel primário. Iniciando protocolo de injeção")

    # Geração do Backup Preventivo Obrigatório
    caminho_backup = criar_backup_preventivo(caminho_alvo)
    if not caminho_backup:
        logger.critical("[FATAL] (X_X) Execução abortada preventivamente, não foi possível assegurar o backup")
        return

    # Ciclo de Modificação com trava de tentativas (Circuit Breaker)
    sucesso_operacao = False

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        logger.info(f"[>] (ง •̀_•́)ง Tentativa {tentativa} de {MAX_TENTATIVAS} para aplicar e validar as alterações")

        # Aplica alteração em memória
        linhas_modificadas = aplicar_injecao_memoria(linhas_originais, indice_cmdline)

        # Sanity Check pré-gravação
        if not validar_sanidade_conteudo(linhas_originais, linhas_modificadas, indice_cmdline):
            logger.warning("[AVISO] (¬_¬) Sanity check reprovou as alterações na memória. Abortando tentativa")
            continue

        # Função de Aprovação (gravação física)
        if not salvar_alteracoes_disco(caminho_alvo, linhas_modificadas):
            logger.warning("[AVISO] (T_T) Falha na escrita em disco")
            continue

        # Função Guardiã (validação pós-gravação no disco físico)
        if guardiao_validacao_final(caminho_alvo):
            sucesso_operacao = True
            logger.info("[SUCESSO] \\(^o^)/ Parâmetro acpi_enforce_resources=lax injetado e validado!")
            break
        else:
            logger.warning(f"[AVISO] (o_o;) A validação guardiã falhou na tentativa {tentativa}")
            # Atualiza o estado da memória lendo novamente o arquivo para a próxima tentativa do loop
            try:
                with open(caminho_alvo, 'r', encoding='utf-8') as arquivo:
                    linhas_originais = arquivo.readlines()
                bloco_encontrado, precisa_alterar, indice_cmdline = analisar_bloco_limine(linhas_originais)
            except Exception as e:
                logger.error(f"[ERRO] (x_x) Falha ao reler o arquivo para nova tentativa: {e}")

    # Verificação do desfecho e acionamento do Rollback se necessário
    if not sucesso_operacao:
        logger.critical(f"[FATAL] (╯°□°)╯ Todas as {MAX_TENTATIVAS} tentativas falharam!")
        restauracao_ok = restaurar_backup_emergencia(caminho_backup, caminho_alvo)
        if not restauracao_ok:
            logger.critical("[FATAL] (X_X) Sistema em estado potencialmente inconsistente! Verificação manual necessária")
        sys.exit(1)
    else:
        logger.info("[#] (づ｡◕‿‿◕｡)づ Hestia concluiu o ciclo com proteção e estabilidade mantidas")
        logger.info("=" * 70)
        sys.exit(0)

# -------------------------------
# *******************************
# -------------------------------

# Ponto de entrada padrão
if __name__ == "__main__":
    main()