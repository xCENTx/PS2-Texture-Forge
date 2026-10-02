from pathlib import Path
import subprocess
import time
import sys


# ============================================================================
# PCSX2 TEXTURE FORGE
# ============================================================================
#
# Watches a PCSX2 texture dump directory for newly dumped textures.
#
# When a new texture is detected:
#
#     PCSX2 dumps texture
#            ↓
#     Texture Forge detects it
#            ↓
#     Real-ESRGAN upscales it
#            ↓
#     Replacement is written using the SAME filename
#            ↓
#     PCSX2 can load the HD replacement
#
#
# Expected directory structure:
#
#   PCSX2/
#       textures/
#           PCSX2-Texture-Forge/
#               texture_forge.py
#               realesrgan-ncnn-vulkan.exe
#               models/
#
#           SCUS-97134/
#               dumps/
#               replacements/
#
# ============================================================================


# ============================================================================
# CONFIG
# ============================================================================

# PCSX2 game serial / texture directory.
GAME_TITLE = "SCUS-97134"

# Real-ESRGAN upscale factor.
SCALE = 4

# Real-ESRGAN model.
MODEL = "realesrgan-x4plus"

# How frequently we scan for newly dumped textures.
POLL_INTERVAL = 0.25

# How frequently we check whether PCSX2 finished writing a file.
FILE_READY_INTERVAL = 0.05

# Number of identical file-size checks required before considering a dump
# finished.
FILE_READY_CHECKS = 3

# Supported dump formats.
SUPPORTED_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
}


# ============================================================================
# PATHS
# ============================================================================

# Directory containing this script:
#
#   ...\PCSX2\textures\PCSX2-Texture-Forge
#
TOOL_DIR = Path(__file__).resolve().parent


# Parent directory:
#
#   ...\PCSX2\textures
#
TEXTURES_DIR = TOOL_DIR.parent


# Game texture directory:
#
#   ...\PCSX2\textures\SCUS-97134
#
GAME_DIR = TEXTURES_DIR / GAME_TITLE


# PCSX2 directories.
DUMPS_DIR = GAME_DIR / "dumps"
REPLACEMENTS_DIR = GAME_DIR / "replacements"


# Real-ESRGAN executable.
REALESRGAN_EXE = TOOL_DIR / "realesrgan-ncnn-vulkan.exe"


# ============================================================================
# CONSOLE
# ============================================================================

def print_header():
    print()
    print("============================================================")
    print("                    PCSX2 TEXTURE FORGE")
    print("============================================================")
    print()
    print(f" Game:          {GAME_TITLE}")
    print(f" Scale:         {SCALE}x")
    print(f" Model:         {MODEL}")
    print()
    print(f" Tool:")
    print(f"   {TOOL_DIR}")
    print()
    print(f" Dumps:")
    print(f"   {DUMPS_DIR}")
    print()
    print(f" Replacements:")
    print(f"   {REPLACEMENTS_DIR}")
    print()
    print("============================================================")
    print()


# ============================================================================
# VALIDATION
# ============================================================================

def validate_environment():
    """
    Make sure Real-ESRGAN exists and create the required PCSX2 directories.
    """

    if not REALESRGAN_EXE.exists():
        print("[ERROR] Real-ESRGAN executable was not found.")
        print()
        print("Expected:")
        print(f"  {REALESRGAN_EXE}")
        print()
        return False

    DUMPS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    REPLACEMENTS_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    return True


# ============================================================================
# FILE READY CHECK
# ============================================================================

def wait_for_file(file: Path):
    """
    Wait for PCSX2 to finish writing a dumped texture.

    A file is considered ready after its size remains unchanged for several
    consecutive checks.
    """

    previous_size = -1
    stable_checks = 0

    while stable_checks < FILE_READY_CHECKS:

        try:
            current_size = file.stat().st_size

        except FileNotFoundError:
            return False

        # Empty file isn't ready.
        if current_size <= 0:
            stable_checks = 0

        elif current_size == previous_size:
            stable_checks += 1

        else:
            stable_checks = 0

        previous_size = current_size

        time.sleep(FILE_READY_INTERVAL)

    return True


# ============================================================================
# REAL-ESRGAN
# ============================================================================

def upscale_texture(input_file: Path, output_file: Path):
    """
    Upscale one texture using Real-ESRGAN.
    """

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    print(f"[NEW] {input_file.name}")

    command = [
        str(REALESRGAN_EXE),

        "-i",
        str(input_file),

        "-o",
        str(output_file),

        "-n",
        MODEL,

        "-s",
        str(SCALE),

        "-f",
        "png",
    ]

    try:
        result = subprocess.run(
            command,
            cwd=TOOL_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )

    except Exception as error:
        print(f"[ERROR] Failed to start Real-ESRGAN:")
        print(f"        {error}")
        print()

        return False

    if result.returncode != 0:

        print(f"[FAIL] {input_file.name}")

        if result.stderr:
            print(result.stderr.strip())

        print()

        return False

    if not output_file.exists():
        print(f"[FAIL] Real-ESRGAN returned successfully but no output exists:")
        print(f"       {output_file}")
        print()

        return False

    print(f"[ OK ] {input_file.name}")
    print()

    return True


# ============================================================================
# PROCESS TEXTURE
# ============================================================================

def process_texture(input_file: Path):
    """
    Process a single PCSX2 texture dump.
    """

    # Preserve the relative path underneath dumps.
    #
    # Example:
    #
    # dumps\foo\texture.png
    #
    # becomes:
    #
    # replacements\foo\texture.png
    #

    relative_path = input_file.relative_to(DUMPS_DIR)

    # Real-ESRGAN outputs PNG.
    relative_path = relative_path.with_suffix(".png")

    output_file = REPLACEMENTS_DIR / relative_path


    # ------------------------------------------------------------------------
    # Already processed
    # ------------------------------------------------------------------------

    if output_file.exists():
        return False


    # ------------------------------------------------------------------------
    # Wait for PCSX2 to finish writing
    # ------------------------------------------------------------------------

    if not wait_for_file(input_file):
        print(f"[SKIP] File disappeared: {input_file.name}")
        return False


    # ------------------------------------------------------------------------
    # Upscale
    # ------------------------------------------------------------------------

    return upscale_texture(
        input_file,
        output_file
    )


# ============================================================================
# FIND TEXTURES
# ============================================================================

def find_dumped_textures():
    """
    Recursively find supported texture dumps.
    """

    textures = []

    if not DUMPS_DIR.exists():
        return textures

    for file in DUMPS_DIR.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        textures.append(file)

    return textures


# ============================================================================
# INITIAL SCAN
# ============================================================================

def initial_scan():
    """
    Process textures that PCSX2 dumped before Texture Forge was started.
    """

    textures = find_dumped_textures()

    if not textures:
        print("[INFO] No existing texture dumps found.")
        print()
        return

    pending = []

    for file in textures:

        relative_path = file.relative_to(DUMPS_DIR)
        output_file = (
            REPLACEMENTS_DIR /
            relative_path.with_suffix(".png")
        )

        if not output_file.exists():
            pending.append(file)


    print(
        f"[INFO] Found {len(textures)} dumped texture(s), "
        f"{len(pending)} pending."
    )

    print()

    for file in pending:
        process_texture(file)


# ============================================================================
# WATCHER
# ============================================================================

def watch():
    """
    Continuously watch PCSX2's dump directory.
    """

    print("[WATCHING]")
    print("Waiting for new PCSX2 texture dumps...")
    print()
    print("Press Ctrl+C to stop Texture Forge.")
    print()

    # We only use this to prevent repeatedly examining the same file during
    # this execution.
    #
    # Existing replacements are independently checked by process_texture().

    known_files = set(find_dumped_textures())

    while True:

        textures = find_dumped_textures()

        for file in textures:

            if file in known_files:
                continue

            known_files.add(file)

            process_texture(file)

        time.sleep(POLL_INTERVAL)


# ============================================================================
# MAIN
# ============================================================================

def main():

    print_header()

    if not validate_environment():
        return 1


    # ------------------------------------------------------------------------
    # Process anything PCSX2 already dumped.
    # ------------------------------------------------------------------------

    initial_scan()


    # ------------------------------------------------------------------------
    # Watch for new dumps.
    # ------------------------------------------------------------------------

    watch()

    return 0


# ============================================================================
# ENTRY
# ============================================================================

if __name__ == "__main__":

    try:
        sys.exit(main())

    except KeyboardInterrupt:
        print()
        print()
        print("============================================================")
        print(" Texture Forge stopped.")
        print("============================================================")
        print()

        sys.exit(0)