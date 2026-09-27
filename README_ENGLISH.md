# [!] Project Héstia - Limine OpenRGB: RAM Detection Fix on Linux (CachyOS)

This repository provides technical documentation and an automation script to resolve the issue where RAM modules are not detected by OpenRGB on Linux systems (focusing on Arch Linux / CachyOS using the Limine bootloader).

The solution relies on surgical adjustments to kernel boot parameters, ensuring the hardware is properly recognized across the SMBus/I2C bus without compromising boot stability.

---

## The Problem: ACPI Conflict and SMBus/I2C Bus Lock

OpenRGB communicates with most motherboard LED controllers and peripherals via internal USB connections. However, controlling the lighting on RAM modules requires direct access to the SMBus/I2C bus.

By default, the Linux kernel locks access to these hardware resources due to strict ACPI resource management and power policy conflicts. With this communication channel blocked by the kernel, OpenRGB cannot access memory modules, and RAM sticks do not show up in the application.

---

## Pre-test Communication

Before applying a permanent boot fix, it is recommended to test whether your system can load the appropriate I2C communication kernel modules for your processor. Open a terminal and run the commands corresponding to your platform:

### [>] For AMD Processors (Ryzen, Chipsets B450, B550, X570, etc.):
```bash
sudo modprobe i2c-dev
sudo modprobe i2c-piix4
```

### [>] For Intel Processors:
```bash
sudo modprobe i2c-dev
sudo modprobe i2c-i801
```

After running the commands, open OpenRGB and click **"Scan for devices"** / **"Find Devices"**. If the RAM modules still do not appear, it confirms that the ACPI conflict is actively enforced at the kernel boot level.

---

## The Unlock (Manual Fix)

To release access to the SMBus/I2C bus, the parameter `acpi_enforce_resources=lax` must be passed to the kernel command line. In Limine, this can be done manually:

1. [>] Edit the Limine configuration file with root privileges:
   ```bash
   sudo nano /boot/limine.conf
   ```

2. [>] Locate the entry block for your primary kernel (example: `//linux-cachyos`)

3. [>] Find the `cmdline:` directive for that entry and navigate to the exact end of the line

4. [>] Add a blank space followed by the parameter:
   ```text
   acpi_enforce_resources=lax
   ```

5. [>] Save the file and reboot your system. OpenRGB will now detect your RAM modules. Once confirmed, you can proceed with the automation via Héstia.

---

## The Definitive Solution:

### [*] The Fragility of Manual Edits
On *rolling release* distributions such as CachyOS and Arch Linux, whenever a kernel update or Snapper snapshot sync occurs, system tools (such as `limine-entry-tool` or `limine-snapper-sync`) regenerate `/boot/limine.conf`. This process wipes manual changes, and OpenRGB loses access to RAM modules on the very next boot (from personal experience).

### [+] How Héstia Automation Works
Héstia was designed to execute at session logout or system shutdown. Any changes made to `/boot/limine.conf` during the session are verified and corrected before the machine turns off, ensuring that the next boot already starts with the correct parameter.

### [SEC] Héstia Security Pillars:
* [OK] **Entry Isolation:** Exclusively analyzes the primary kernel entry (`//linux-cachyos`), keeping LTS kernel entries and Snapshots completely intact.
* [OK] **In-Memory Execution & Sanity Check:** All parsing and modifications occur in RAM first. Before physical disk write, the script validates structural file integrity.
* [OK] **Atomic Write with Disk Sync (`fsync`):** Writes to a temporary file on the same filesystem, forces physical disk synchronization via `fsync`, and concludes with an atomic replacement (`os.replace`), preventing corruption in case of power failure and cleaning up temporary files upon errors.
* [OK] **Rotating Backup System:** On every run that requires modification, a timestamped copy is saved in the `backups/` directory. The system automatically preserves the last 5 backups, removing older ones.
* [OK] **Guardian Function with Anti-Loop Lock:** After writing to disk, the physical file is re-read to verify changes. The cycle is capped at 3 attempts. If any error persists, the script triggers emergency rollback, safely restoring the backup.
* [OK] **Rotating Logs:** Generates execution history in `hestia_execucao.log` limited to 5 files of at most 50 MB each.
* [OK] **Zero External Dependencies:** Built purely using the Python 3 standard library.

---

## [5] System Installation and Setup

To ensure Guardian Héstia runs atomically and safely at the exact moment the computer shuts down, we use a native **Systemd** service. This prevents abrupt termination of the graphical desktop (KDE/GNOME) from aborting the script midway.

### [>] Step 1: Execution Permissions
Grant execution permissions to the wrapper script, the Python code, and the RGB helper script. Navigate to the project folder and run:

```bash
chmod +x executar_hestia.sh Hestia.py aplicar_rgb.sh
```
*(Note: The wrapper `executar_hestia.sh` acts as a security bridge, ensuring the correct working directory is activated and passing arguments natively).*

### [>] Step 2: Create Systemd Service
Create the system service file with administrative privileges:

```bash
sudo nano /etc/systemd/system/Héstia.service
```

### [>] Step 3: Configure the Service
Paste the configuration below into the editor. **Important:** Be sure to replace `/caminho/completo/para/Héstia` with the actual path where the project directory is located on your machine.

```ini
[Unit]
Description=Guardian Héstia - Limine protection on shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot

# Sets project folder as root so backups and logs are saved in the correct location
WorkingDirectory=/full/path/for/Hestia

# Points to the wrapper script that manages Python execution
ExecStart=/full/path/for/Hestia/executar_hestia.sh

[Install]
WantedBy=shutdown.target reboot.target halt.target
```
Save the file (Press **Ctrl+O**, then **Enter**) and exit the editor (**Ctrl+X**).

### [>] Step 4: Enable Automation
Tell Linux that a new service has been created and enable it to run on all future system shutdowns/reboots:

```bash
sudo systemctl daemon-reload
sudo systemctl enable Hestia.service
```

From now on, Héstia will run in the background with native system privileges whenever the machine shuts down or restarts, ensuring `/boot` remains protected.

---

## [6] Manual Testing

### [>] Real Environment Validation:
To test the automation at any time via the terminal:

```bash
./executar_hestia.sh
```

### [>] Safe Test Mode (Example File):
To validate the automation without modifying the real `/boot/limine.conf` on your system, run the test using the sample file provided in the repository:

```bash
./executar_hestia.sh ./limine.conf.exemplo
```

### [>] Inspecting Logs:
The complete log for each check can be followed in the local log file:

```bash
cat hestia_execucao.log
```

---

## [7] Complementary Script: Lighting Profile on Startup (KDE Plasma)

To ensure OpenRGB automatically applies your configured lighting profile when logging into your desktop, the repository includes the helper script `aplicar_rgb.sh`.

When KDE Plasma starts, display servers, monitor drivers, and USB/I2C controller buses are still loading during the first few seconds. If OpenRGB tries to apply settings immediately upon login, the command may fail silently or some devices may not respond in time. The 15-second pause ensures the entire desktop environment and hardware buses are 100% ready before sending lighting commands.

### [>] How to Configure:

1. **Set and save your profile in OpenRGB:**
   - Open OpenRGB, configure your desired colors and effects for RAM and peripherals.
   - Save the profile with a name of your choice (example: `MyProfile`).

2. **Adjust the `aplicar_rgb.sh` script:**
   - Open `aplicar_rgb.sh` in a text editor and replace `NomeDoSeuPerfil` with the exact profile name saved in OpenRGB:

     ```bash
     openrgb --profile MyProfile
     ```

3. **Grant execution permissions:**

   ```bash
   chmod +x aplicar_rgb.sh
   ```

4. **Register in KDE Autostart:**
   - Open KDE Plasma **System Settings**.
   - Navigate to **Startup and Shutdown** -> **Autostart**.
   - Click **+ Add...** and select **Add Login Script...**.
   - Browse and select the `aplicar_rgb.sh` file.
   - Ensure the checkbox next to the script is enabled.

That's it! On every subsequent login, KDE will launch the script in the background and, after the 15-second stabilization delay, your custom RGB profile will be applied automatically.