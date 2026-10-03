from pathlib import Path
import subprocess
import time
import sys
import os
from datetime import datetime, timedelta


# ============================================================================
# PCSX2 TEXTURE FORGE
# ============================================================================
#
# Watches a PCSX2 texture dump directory for newly dumped textures.
#
# PCSX2 dump
#      ↓
# Texture Forge detects texture
#      ↓
# Real-ESRGAN upscales texture
#      ↓
# Same filename written to replacements/
#      ↓
# PCSX2 loads HD replacement
#
#
# Expected structure:
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

GAME_TITLE = "SCUS-97134"

SCALE = 4

MODEL = "realesrgan-x4plus"

POLL_INTERVAL = 0.25

DASHBOARD_REFRESH_INTERVAL = 1.0

FILE_READY_INTERVAL = 0.05

FILE_READY_CHECKS = 3

PROGRESS_BAR_WIDTH = 40

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

# ...\PCSX2\textures\PCSX2-Texture-Forge
TOOL_DIR = Path(__file__).resolve().parent

# ...\PCSX2\textures
TEXTURES_DIR = TOOL_DIR.parent

# ...\PCSX2\textures\SCUS-97134
GAME_DIR = TEXTURES_DIR / GAME_TITLE

DUMPS_DIR = GAME_DIR / "dumps"

REPLACEMENTS_DIR = GAME_DIR / "replacements"

REALESRGAN_EXE = TOOL_DIR / "realesrgan-ncnn-vulkan.exe"


# ============================================================================
# SESSION STATE
# ============================================================================

SESSION_START_TIME = time.time()

PROCESSING_TIMES = []

SESSION_PROCESSED = 0

SESSION_FAILED = 0

LAST_COMPLETED = None

LAST_PROCESSING_TIME = None

CURRENT_TEXTURE = None

CURRENT_STATUS = "Starting"

LAST_DASHBOARD_REFRESH = 0.0


# ============================================================================
# TIME FORMATTING
# ============================================================================

def format_duration(seconds):
    """
    Convert seconds into HH:MM:SS or MM:SS.
    """

    seconds = max(0, int(seconds))

    hours, remainder = divmod(seconds, 3600)

    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


def get_elapsed_time():

    return time.time() - SESSION_START_TIME


# ============================================================================
# CONSOLE
# ============================================================================

def clear_console():
    """
    Clear the console so the dashboard remains stationary.
    """

    os.system(
        "cls" if os.name == "nt" else "clear"
    )


# ============================================================================
# VALIDATION
# ============================================================================

def validate_environment():

    if not REALESRGAN_EXE.exists():

        clear_console()

        print("==============================================================")
        print("                     PCSX2 TEXTURE FORGE")
        print("==============================================================")
        print()
        print("[ERROR] Real-ESRGAN executable was not found.")
        print()
        print("Expected:")
        print()
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
    Wait until PCSX2 appears to have finished writing the texture.
    """

    previous_size = -1

    stable_checks = 0


    while stable_checks < FILE_READY_CHECKS:

        try:

            current_size = file.stat().st_size

        except FileNotFoundError:

            return False


        if current_size <= 0:

            stable_checks = 0

        elif current_size == previous_size:

            stable_checks += 1

        else:

            stable_checks = 0


        previous_size = current_size

        time.sleep(
            FILE_READY_INTERVAL
        )


    return True


# ============================================================================
# TEXTURE PATHS
# ============================================================================

def get_output_file(input_file: Path):
    """
    Return the corresponding replacement path for a dump.
    """

    relative_path = input_file.relative_to(
        DUMPS_DIR
    )

    relative_path = relative_path.with_suffix(
        ".png"
    )

    return REPLACEMENTS_DIR / relative_path


# ============================================================================
# FIND TEXTURES
# ============================================================================

def find_dumped_textures():

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
# STATISTICS
# ============================================================================

def get_statistics():

    textures = find_dumped_textures()

    total = len(textures)

    completed = 0


    for texture in textures:

        output_file = get_output_file(
            texture
        )

        if output_file.exists():
            completed += 1


    remaining = max(
        0,
        total - completed
    )


    return (
        total,
        completed,
        remaining
    )


# ============================================================================
# ETA
# ============================================================================

def get_eta(remaining):

    if remaining <= 0:

        if PROCESSING_TIMES:

            average_time = (
                sum(PROCESSING_TIMES)
                / len(PROCESSING_TIMES)
            )

            average_string = (
                f"{average_time:.2f}s"
            )

        else:

            average_string = "--"


        return (
            average_string,
            "Complete",
            "Complete"
        )


    if not PROCESSING_TIMES:

        return (
            "--",
            "Calculating...",
            "Calculating..."
        )


    average_time = (
        sum(PROCESSING_TIMES)
        / len(PROCESSING_TIMES)
    )


    estimated_seconds_remaining = (
        average_time * remaining
    )


    estimated_finish = (
        datetime.now()
        + timedelta(
            seconds=estimated_seconds_remaining
        )
    )


    average_string = (
        f"{average_time:.2f}s"
    )

    eta_string = format_duration(
        estimated_seconds_remaining
    )

    finish_string = estimated_finish.strftime(
        "%I:%M:%S %p"
    )


    return (
        average_string,
        eta_string,
        finish_string
    )


# ============================================================================
# DASHBOARD
# ============================================================================

def draw_dashboard(
    force=False
):
    """
    Draw the complete dashboard.

    While idle, redraws are rate limited.

    Texture start/completion events use force=True so the display updates
    immediately.
    """

    global LAST_DASHBOARD_REFRESH


    now = time.time()


    # ------------------------------------------------------------------------
    # Rate limit idle dashboard refreshes
    # ------------------------------------------------------------------------

    if not force:

        if (
            now - LAST_DASHBOARD_REFRESH
            < DASHBOARD_REFRESH_INTERVAL
        ):

            return


    LAST_DASHBOARD_REFRESH = now


    # ------------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------------

    total, completed, remaining = (
        get_statistics()
    )


    if total > 0:

        percentage = (
            completed / total
        )

    else:

        percentage = 0.0


    filled = int(
        PROGRESS_BAR_WIDTH
        * percentage
    )


    filled = min(
        PROGRESS_BAR_WIDTH,
        max(
            0,
            filled
        )
    )


    bar = (
        "#" * filled
        + "-"
        * (
            PROGRESS_BAR_WIDTH
            - filled
        )
    )


    # ------------------------------------------------------------------------
    # Time
    # ------------------------------------------------------------------------

    elapsed = get_elapsed_time()


    (
        average_string,
        eta_string,
        finish_string

    ) = get_eta(
        remaining
    )


    # ------------------------------------------------------------------------
    # Draw
    # ------------------------------------------------------------------------

    clear_console()


    print(
        "=============================================================="
    )

    print(
        "                     PCSX2 TEXTURE FORGE"
    )

    print(
        "=============================================================="
    )

    print()


    print(
        f" Game:           {GAME_TITLE}"
    )

    print(
        f" Model:          {MODEL}"
    )

    print(
        f" Scale:          {SCALE}x"
    )


    print()


    print(
        f" [{bar}] "
        f"{percentage * 100:6.2f}%"
    )


    print()


    print(
        f" Textures:       "
        f"{completed:>6,} / {total:,}"
    )

    print(
        f" Remaining:      "
        f"{remaining:>6,}"
    )

    print(
        f" This Session:   "
        f"{SESSION_PROCESSED:>6,}"
    )

    print(
        f" Failed:         "
        f"{SESSION_FAILED:>6,}"
    )


    print()


    print(
        f" Work Time:      "
        f"{format_duration(elapsed)}"
    )

    print(
        f" Avg / Texture:  "
        f"{average_string}"
    )

    print(
        f" ETA:            "
        f"{eta_string}"
    )

    print(
        f" Finish:         "
        f"{finish_string}"
    )


    print()


    print(
        f" Status:         "
        f"{CURRENT_STATUS}"
    )


    print()


    print(
        " Current Texture:"
    )


    if CURRENT_TEXTURE is not None:

        print(
            f"   {CURRENT_TEXTURE.name}"
        )

    else:

        print(
            "   --"
        )


    print()


    print(
        " Last Completed:"
    )


    if LAST_COMPLETED is not None:

        if LAST_PROCESSING_TIME is not None:

            print(
                f"   {LAST_COMPLETED.name}"
            )

            print(
                f"   Processing Time: "
                f"{LAST_PROCESSING_TIME:.2f}s"
            )

        else:

            print(
                f"   {LAST_COMPLETED.name}"
            )

    else:

        print(
            "   --"
        )


    print()


    print(
        "=============================================================="
    )

    print(
        " Ctrl+C to stop"
    )


# ============================================================================
# REAL-ESRGAN
# ============================================================================

def upscale_texture(
    input_file: Path,
    output_file: Path
):

    global SESSION_PROCESSED
    global SESSION_FAILED

    global LAST_COMPLETED
    global LAST_PROCESSING_TIME

    global CURRENT_TEXTURE
    global CURRENT_STATUS


    output_file.parent.mkdir(
        parents=True,
        exist_ok=True
    )


    # ------------------------------------------------------------------------
    # Start
    # ------------------------------------------------------------------------

    CURRENT_TEXTURE = input_file

    CURRENT_STATUS = "UPSCALING"


    draw_dashboard(
        force=True
    )


    command = [

        str(
            REALESRGAN_EXE
        ),

        "-i",
        str(
            input_file
        ),

        "-o",
        str(
            output_file
        ),

        "-n",
        MODEL,

        "-s",
        str(
            SCALE
        ),

        "-f",
        "png",
    ]


    start_time = time.time()


    # ------------------------------------------------------------------------
    # Run Real-ESRGAN
    # ------------------------------------------------------------------------

    try:

        result = subprocess.run(

            command,

            cwd=TOOL_DIR,

            stdout=subprocess.DEVNULL,

            stderr=subprocess.PIPE,

            text=True,

            check=False
        )


    except Exception:

        SESSION_FAILED += 1

        CURRENT_STATUS = "ERROR"

        CURRENT_TEXTURE = None


        draw_dashboard(
            force=True
        )


        return False


    processing_time = (
        time.time()
        - start_time
    )


    # ------------------------------------------------------------------------
    # Real-ESRGAN failure
    # ------------------------------------------------------------------------

    if result.returncode != 0:

        SESSION_FAILED += 1

        CURRENT_STATUS = "FAILED"

        CURRENT_TEXTURE = None


        draw_dashboard(
            force=True
        )


        return False


    # ------------------------------------------------------------------------
    # Output missing
    # ------------------------------------------------------------------------

    if not output_file.exists():

        SESSION_FAILED += 1

        CURRENT_STATUS = "OUTPUT ERROR"

        CURRENT_TEXTURE = None


        draw_dashboard(
            force=True
        )


        return False


    # ------------------------------------------------------------------------
    # Success
    # ------------------------------------------------------------------------

    PROCESSING_TIMES.append(
        processing_time
    )


    SESSION_PROCESSED += 1


    LAST_COMPLETED = input_file

    LAST_PROCESSING_TIME = (
        processing_time
    )


    CURRENT_TEXTURE = None

    CURRENT_STATUS = (
        "PROCESSING QUEUE"
    )


    draw_dashboard(
        force=True
    )


    return True


# ============================================================================
# PROCESS TEXTURE
# ============================================================================

def process_texture(
    input_file: Path
):

    global CURRENT_TEXTURE
    global CURRENT_STATUS


    output_file = get_output_file(
        input_file
    )


    # ------------------------------------------------------------------------
    # Already processed
    # ------------------------------------------------------------------------

    if output_file.exists():

        return False


    # ------------------------------------------------------------------------
    # Wait for PCSX2
    # ------------------------------------------------------------------------

    CURRENT_TEXTURE = input_file

    CURRENT_STATUS = (
        "WAITING FOR FILE"
    )


    draw_dashboard(
        force=True
    )


    if not wait_for_file(
        input_file
    ):

        CURRENT_TEXTURE = None

        CURRENT_STATUS = (
            "FILE DISAPPEARED"
        )


        draw_dashboard(
            force=True
        )


        return False


    # ------------------------------------------------------------------------
    # Upscale
    # ------------------------------------------------------------------------

    return upscale_texture(
        input_file,
        output_file
    )


# ============================================================================
# INITIAL SCAN
# ============================================================================

def initial_scan():

    global CURRENT_STATUS


    CURRENT_STATUS = (
        "SCANNING"
    )


    draw_dashboard(
        force=True
    )


    textures = (
        find_dumped_textures()
    )


    pending = []


    for file in textures:

        output_file = (
            get_output_file(
                file
            )
        )


        if not output_file.exists():

            pending.append(
                file
            )


    # ------------------------------------------------------------------------
    # Nothing pending
    # ------------------------------------------------------------------------

    if not pending:

        CURRENT_STATUS = (
            "UP TO DATE"
        )


        draw_dashboard(
            force=True
        )


        return


    # ------------------------------------------------------------------------
    # Process queue
    # ------------------------------------------------------------------------

    CURRENT_STATUS = (
        "PROCESSING QUEUE"
    )


    draw_dashboard(
        force=True
    )


    for file in pending:

        process_texture(
            file
        )


# ============================================================================
# WATCHER
# ============================================================================

def watch():

    global CURRENT_STATUS
    global CURRENT_TEXTURE


    CURRENT_STATUS = (
        "WATCHING"
    )

    CURRENT_TEXTURE = None


    draw_dashboard(
        force=True
    )


    known_files = set(
        find_dumped_textures()
    )


    while True:

        textures = (
            find_dumped_textures()
        )


        found_new_texture = False


        for file in textures:

            if file in known_files:

                continue


            known_files.add(
                file
            )


            found_new_texture = True


            process_texture(
                file
            )


        # --------------------------------------------------------------------
        # Idle / watching
        # --------------------------------------------------------------------

        if not found_new_texture:

            CURRENT_STATUS = (
                "WATCHING"
            )

            CURRENT_TEXTURE = None


            draw_dashboard(
                force=False
            )


        time.sleep(
            POLL_INTERVAL
        )


# ============================================================================
# MAIN
# ============================================================================

def main():

    if not validate_environment():

        return 1


    # ------------------------------------------------------------------------
    # Existing dumps
    # ------------------------------------------------------------------------

    initial_scan()


    # ------------------------------------------------------------------------
    # Watch PCSX2
    # ------------------------------------------------------------------------

    watch()


    return 0


# ============================================================================
# ENTRY
# ============================================================================

if __name__ == "__main__":

    try:

        sys.exit(
            main()
        )


    except KeyboardInterrupt:

        CURRENT_STATUS = "STOPPED"

        CURRENT_TEXTURE = None


        draw_dashboard(
            force=True
        )


        print()
        print(
            "Texture Forge stopped."
        )
        print()


        sys.exit(0)