import os
import sys
import shutil
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def build():
    print("=======================================================")
    print("       🚀 COMPILADOR NATIVO F3NIX PARA WINDOWS 11      ")
    print("=======================================================")
    
    # 1. Asegurar icono
    icon_path = "f3nix_icon.ico"
    if not os.path.exists(icon_path):
        try:
            from PIL import Image
            img = Image.open("thruster_avatar.jpg")
            img.save(icon_path, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            print("✓ Icono f3nix_icon.ico generado exitosamente.")
        except Exception as e:
            print(f"Aviso generando icono: {e}")
            icon_path = None

    # 2. Configurar argumentos de PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "thruster.py",
        "--name=F3NIX",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--add-data=thruster_avatar.jpg;.",
        "--add-data=core/constitution;core/constitution",
        "--add-data=config.json;.",
        "--add-data=f3nix_memory.json;.",
        "--hidden-import=PyQt6",
        "--hidden-import=pygame",
        "--hidden-import=edge_tts",
        "--hidden-import=keyboard",
        "--hidden-import=sounddevice",
        "--hidden-import=numpy",
        "--hidden-import=requests",
        "--distpath=release"
    ]

    if icon_path and os.path.exists(icon_path):
        cmd.append(f"--icon={icon_path}")

    # Verificar si el usuario pasó --onefile
    if "--onefile" in sys.argv:
        cmd.append("--onefile")
        print("📦 Modo de compilación: Archivo Único (F3NIX.exe)")
    else:
        cmd.append("--onedir")
        print("⚡ Modo de compilación: Carpeta de Alto Rendimiento (F3NIX/F3NIX.exe)")

    print(f"\nEjecutando PyInstaller...")
    ret = subprocess.run(cmd)
    
    if ret.returncode == 0:
        print("\n=======================================================")
        print("   ✅ ¡COMPILACIÓN COMPLETADA EXITOSAMENTE!           ")
        print("=======================================================")
        dist_path = os.path.abspath("release/F3NIX")
        exe_path = os.path.join(dist_path, "F3NIX.exe")
        print(f"📂 Ubicación del ejecutable:\n   {exe_path}\n")

        # Asegurar copia directa de assets en la raíz de release y dist
        for asset in ["thruster_avatar.jpg", "f3nix_icon.ico", "config.json", "f3nix_memory.json"]:
            if os.path.exists(asset):
                for target_dir in ["release/F3NIX", "dist/F3NIX"]:
                    if os.path.exists(target_dir):
                        try:
                            shutil.copy2(asset, os.path.join(target_dir, asset))
                            print(f"✓ {asset} copiado en {target_dir}")
                        except Exception as copy_err:
                            pass

        # Sincronizar exe a dist/F3NIX si existe
        if os.path.exists("dist/F3NIX") and os.path.exists(exe_path):
            try:
                shutil.copy2(exe_path, os.path.join("dist/F3NIX", "F3NIX.exe"))
                print("✓ F3NIX.exe sincronizado en dist/F3NIX/")
            except Exception as dist_err:
                pass

        # Actualizar acceso directo en el Escritorio automáticamente
        try:
            import win32com.client
            wscript = win32com.client.Dispatch("WScript.Shell")
            desktop = wscript.SpecialFolders("Desktop")
            shortcut_path = os.path.join(desktop, "F3NIX.lnk")
            if os.path.exists(exe_path):
                sc = wscript.CreateShortcut(shortcut_path)
                sc.TargetPath = exe_path
                sc.WorkingDirectory = dist_path
                sc.IconLocation = f"{exe_path},0"
                sc.Description = "F3NIX - Asistente de Escritorio IA"
                sc.Save()
                print(f"✓ Acceso directo actualizado en tu Escritorio: {shortcut_path}")
        except Exception as e:
            print(f"Aviso creando acceso directo: {e}")
        print(f"📂 Ubicación del ejecutable:\n   {dist_path}\\F3NIX.exe\n")
    else:
        print("\n❌ Error durante la compilación. Revisa los mensajes arriba.")

if __name__ == "__main__":
    build()
