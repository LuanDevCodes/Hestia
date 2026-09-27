# [!] Projeto Héstia - Limine OpenRGB: Correção de detecção de RAM no Linux (CachyOS)

Este repositório fornece a documentação técnica e uma automação para resolver o problema de memórias RAM que não são detectadas pelo OpenRGB em sistemas Linux (foco em Arch Linux / CachyOS utilizando o gestor de arranque Limine).

A solução baseia-se em alterações cirúrgicas nos parâmetros de inicialização do kernel, garantindo que o hardware seja reconhecido pelo barramento I2C sem comprometer a estabilidade do boot.

---

## O Problema: bloqueio ACPI e barramento I2C

O OpenRGB comunica com a maioria dos controladores de LED da placa-mãe e periféricos através de conexões USB internas. No entanto, o controle de iluminação das memórias RAM exige acesso direto ao barramento SMBus/I2C.

Por padrão, o kernel do Linux bloqueia o acesso a esses recursos de hardware devido a políticas estritas de gestão de energia e segurança da tabela ACPI. Com esse canal de comunicação travado pelo kernel, o OpenRGB fica sem acesso aos módulos de memória e as memórias RAM não são listadas no aplicativo.

---

## Teste prévio de comunicação

Antes de aplicar a correção permanente no arranque, é recomendado testar se o sistema consegue carregar os módulos de comunicação I2C adequados ao seu processador. Abra o terminal e execute os comandos correspondentes à sua plataforma:

### [>] Para processadores AMD (Ryzen, Chipsets B450, B550, X570, etc.):
```bash
sudo modprobe i2c-dev
sudo modprobe i2c-piix4
```

### [>] Para processadores Intel:
```bash
sudo modprobe i2c-dev
sudo modprobe i2c-i801
```

Após executar os comandos, abra o OpenRGB e clique em "Buscar dispositivos". Se as memórias continuarem sem aparecer, a confirmação de que o bloqueio ACPI está atuando ao nível do arranque do kernel é absoluta.

---

## O desbloqueio (Correção Manual)

Para liberar o acesso ao barramento I2C, é necessário injetar o parâmetro `acpi_enforce_resources=lax` na linha de comandos do kernel. No Limine, isso pode ser feito manualmente:

1. [>] Edite o arquivo de configuração do Limine com permissões de root:
   ```bash
   sudo nano /boot/limine.conf
   ```

2. [>] Localize o bloco referente ao seu kernel primário (exemplo: `//linux-cachyos`)

3. [>] Encontre a diretiva `cmdline:` referente a essa entrada e navegue até o final exato da linha

4. [>] Adicione um espaço em branco seguido do parâmetro:
   ```text
   acpi_enforce_resources=lax
   ```

5. [>] Salve o arquivo e reinicie a máquina. O OpenRGB passará a detectar as memórias RAM, se passar a detectar, então você poderá seguir com os passos para a automatização via Héstia.

---

## A solução definitiva:

### [*] A fragilidade da edição manual
Em distribuições *rolling release* como CachyOS e Arch Linux, sempre que ocorre uma atualização de kernel ou sincronização de snapshots do Snapper, as ferramentas do sistema (como `limine-entry-tool` ou `limine-snapper-sync`) regeram o arquivo `/boot/limine.conf`. Esse processo apaga as alterações manuais e o OpenRGB volta a perder o acesso às memórias no boot seguinte (experiência pessoal).

### [+] Como a automação Héstia funciona
A automação Hestia foi projetada para ser executada no momento do encerramento da sessão ou desligamento do computador. Dessa forma, qualquer alteração sofrida pelo `/boot/limine.conf` durante a sessão é verificada e corrigida antes da máquina desligar, garantindo que o próximo arranque já inicie com o parâmetro correto.

### [SEC] Pilares de segurança da Héstia:
* [OK] **Isolamento de Entrada:** Analisa exclusivamente o bloco primário (`//linux-cachyos`), mantendo entradas de kernel LTS e Snapshots completamente intactas.
* [OK] **Execução em Memória e Sanity Check:** Todas as análises e modificações ocorrem primeiro na memória RAM. Antes da gravação física, o script valida se a integridade estrutural do arquivo foi mantida.
* [OK] **Gravação Atômica com Sincronização em Disco (`fsync`):** Grava primeiro em um arquivo temporário no mesmo sistema de arquivos, força a sincronização física no disco via `fsync` e conclui com substituição atômica (`os.replace`), prevenindo corrupção em caso de queda de energia e limpando temporários em falhas.
* [OK] **Sistema de Backups Rotativos:** A cada execução que exige modificação, uma cópia com carimbo de data e hora é salva na pasta `backups/`. O sistema mantém automaticamente as últimas 5 cópias, excluindo excedentes mais velhos.
* [OK] **Função Guardiã com Trava Anti-Loop:** Após gravar no disco, o arquivo físico é relido para confirmar a alteração. O ciclo limita-se a 3 tentativas. Se persistir qualquer erro, o script aciona a reversão de emergência restaurando o backup de forma segura.
* [OK] **Logs Rotativos:** Gera histórico de execução em `hestia_execucao.log` limitado a 5 arquivos de no máximo 50 MB cada.
* [OK] **Zero Dependências Externas:** Construída utilizando exclusivamente bibliotecas nativas da biblioteca padrão do Python 3.

---

## [5] Instalação e Configuração no Sistema

Para garantir que a Guardiã Héstia execute de forma atômica e segura no momento exato em que o computador é desligado, será necessário usar um serviço nativo do **Systemd**. Isso evita que o encerramento abrupto da interface gráfica (KDE/GNOME) aborte o script pela metade.

### [>] Passo 1: Permissão de Execução
Conceda permissão de execução para o script wrapper e para o código Python. Navegue até a pasta do projeto e execute:

```bash
chmod +x executar_hestia.sh Hestia.py
```
*(Nota: O wrapper `executar_hestia.sh` atua como uma ponte de segurança, garantindo que o diretório de trabalho correto seja ativado e repassando argumentos nativamente).*

### [>] Passo 2: Criação do Serviço Systemd
Crie o arquivo de serviço do sistema com privilégios de administrador:

```bash
sudo nano /etc/systemd/system/hestia.service
```

### [>] Passo 3: Configuração do Serviço
Cole o código abaixo no editor. **Atenção:** Lembre-se de substituir o `/caminho/completo/para/Hestia` pelo caminho real de onde você salvou a pasta do projeto no seu computador.

```ini
[Unit]
Description=Guardiã Hestia - Proteção do Limine ao desligar
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot

# Define a pasta do projeto como raiz para que os backups sejam salvos no local correto
WorkingDirectory=/caminho/completo/para/Hestia

# Aponta para o script wrapper que gerenciará a chamada do Python
ExecStart=/caminho/completo/para/Hestia/executar_hestia.sh

[Install]
WantedBy=shutdown.target reboot.target halt.target
```
Salve o arquivo (Pressione **Ctrl+O**, depois **Enter**) e feche o editor (**Ctrl+X**).

### [>] Passo 4: Ativação da Automação
Agora, informe ao Linux que um novo serviço foi criado e ative-o para rodar em todos os futuros encerramentos do sistema:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hestia.service
```

A partir de agora, a Héstia rodará nos bastidores com privilégios nativos de sistema todas as vezes que a máquina for desligada ou reiniciada, garantindo a proteção do `/boot`.

---

## [6] Teste manual

### [>] Validação em ambiente real:
Para validar o funcionamento a qualquer momento pelo terminal:
```bash
./executar_hestia.sh
```

### [>] Modo de teste seguro (arquivo de exemplo):
Para validar a automação sem alterar o `/boot/limine.conf` real do sistema, você pode executar o teste utilizando o arquivo de exemplo disponibilizado no repositório:
```bash
./executar_hestia.sh ./limine.conf.exemplo
```

### [>] Verificação de logs:
O log completo de cada verificação pode ser acompanhado no arquivo local:
```bash
cat hestia_execucao.log
```