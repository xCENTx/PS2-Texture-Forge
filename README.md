# PS2 Texture Forge

An automated AI texture upscaling tool for PCSX2.

PS2 Texture Forge watches a PCSX2 texture dump directory, detects newly dumped textures, upscales them using Real-ESRGAN, and automatically places the resulting textures into the game's replacement directory.

This allows an HD texture pack to effectively build itself while you play.

## How It Works

PCSX2 already provides support for dumping and replacing textures.

PS2 Texture Forge automates the process between the two:

    PCSX2 encounters a texture
                ↓
         Texture is dumped
                ↓
       PS2 Texture Forge
          detects the file
                ↓
          Real-ESRGAN
          upscales it 4x
                ↓
      Replacement is written
       using the same filename
                ↓
       PCSX2 loads the HD
          replacement

The original PCSX2 texture filename and directory structure are preserved so the resulting files can be used directly by PCSX2's texture replacement system.

## Features

- Automatic monitoring of PCSX2 texture dumps
- Real-ESRGAN AI upscaling
- 4x texture upscaling
- Automatic output to the PCSX2 replacement directory
- Preserves PCSX2 texture filenames
- Preserves nested dump directory structures
- Processes existing texture dumps on startup
- Detects newly dumped textures while the game is running
- Automatically skips textures that have already been processed
- Resume support — stop and restart at any time
- Live progress bar
- Processing time statistics
- Average processing time per texture
- Estimated time remaining
- Estimated completion time
- Current texture display
- Session processing statistics
- No additional Python packages required

## Requirements

### PCSX2

A recent version of PCSX2 with texture dumping and texture replacement support.

Texture dumping and replacement must be enabled through PCSX2's graphics settings.

### Python

Python 3 is required to run PS2 Texture Forge.

You can verify Python is installed with:

    python --version

or on Windows:

    py --version

### Real-ESRGAN

PS2 Texture Forge currently uses the portable Vulkan version of Real-ESRGAN:

    realesrgan-ncnn-vulkan.exe

The Real-ESRGAN executable and its model files must be placed inside the PS2 Texture Forge directory.

Real-ESRGAN:

https://github.com/xinntao/Real-ESRGAN

## Installation

Place the PS2 Texture Forge directory inside your PCSX2 `textures` directory.

Example:

    PCSX2/
    └── textures/
        │
        ├── PS2-Texture-Forge/
        │   ├── upscale.py
        │   ├── realesrgan-ncnn-vulkan.exe
        │   └── models/
        │
        └── SCUS-97134/
            ├── dumps/
            └── replacements/

PS2 Texture Forge determines the PCSX2 texture directory automatically based on the location of the script.

No absolute PCSX2 path needs to be configured.

## Configuration

Open `upscale.py` and configure the game directory:

    GAME_TITLE = "SCUS-97134"

The value must match the directory PCSX2 creates for the game.

For example:

    textures/
        SCUS-97134/
        SLUS-97275/
        SLES-XXXXX/

The default upscale configuration is:

    SCALE = 4
    MODEL = "realesrgan-x4plus"

## Usage

First, enable texture dumping and texture replacement in PCSX2.

Then start PS2 Texture Forge:

    py upscale.py

or:

    python upscale.py

PS2 Texture Forge will scan the game's existing `dumps` directory.

Any texture that does not already have a corresponding replacement will automatically be processed.

After the existing queue is finished, Texture Forge remains running and watches for newly dumped textures.

You can then launch the game and play normally.

As PCSX2 encounters new textures, they will automatically be detected and upscaled.

## Example

While running, the console displays a live dashboard:

    ==============================================================
                         PCSX2 TEXTURE FORGE
    ==============================================================

     Game:           SCUS-97134
     Model:          realesrgan-x4plus
     Scale:          4x

     [################################--------]  80.24%

     Textures:          853 / 1,063
     Remaining:         210
     This Session:        5
     Failed:              0

     Work Time:      00:32
     Avg / Texture:  5.36s
     ETA:            18:45
     Finish:         06:58:47 PM

     Status:         UPSCALING

     Current Texture:
       34674fd53ec5d0f-46a9a1623d6e0cf7-000015d3.png

     Last Completed:
       33c63af899736f93-957a2e2c618492ec-00001dd3.png
       Processing Time: 5.40s

    ==============================================================
     Ctrl+C to stop

## Stopping and Resuming

PS2 Texture Forge can be stopped at any time using:

    Ctrl+C

Previously generated replacements are not deleted or processed again.

When Texture Forge is restarted, it compares the files in:

    dumps/

against:

    replacements/

Existing replacements are considered complete and skipped.

For example:

    Dumps:          1,063
    Replacements:     853
    Pending:           210

Only the 210 missing textures will be processed.

This makes it possible to process very large texture packs over multiple sessions.

## Directory Behavior

A dumped texture such as:

    dumps/
        1a09dae0f5d8bae7-98d1c7111f817bba-00001553.png

will produce:

    replacements/
        1a09dae0f5d8bae7-98d1c7111f817bba-00001553.png

Nested directories are also preserved.

For example:

    dumps/
        environment/
            texture.png

becomes:

    replacements/
        environment/
            texture.png

## Performance

Upscaling is currently performed sequentially.

Only one instance of Real-ESRGAN is launched at a time.

This is intentional.

A game can dump dozens or hundreds of textures in a short period of time. Running multiple AI upscaling operations simultaneously could consume large amounts of GPU memory and significantly impact PCSX2 performance.

New textures therefore form a natural processing queue.

Processing speed depends on:

- GPU performance
- Source texture resolution
- Target resolution
- Real-ESRGAN model
- Texture complexity

The live ETA is calculated using the average processing time of textures completed during the current session.

If PCSX2 discovers additional textures while Texture Forge is running, the total texture count and ETA will automatically adjust.

## Important Notes

Not every PS2 texture necessarily benefits from AI upscaling.

Games may use textures for purposes such as:

- Color maps
- UI graphics
- Character textures
- Environment textures
- Alpha masks
- Effects
- Lookup textures
- Dynamically generated textures
- Render targets

The current version processes supported dumped images without attempting to determine their purpose.

Future versions may introduce texture classification and specialized processing rules.

For this reason, generated texture packs should be visually tested in-game.

## Why?

Creating a PCSX2 HD texture pack manually can involve dumping hundreds or thousands of individual textures, processing each texture, preserving PCSX2's generated filenames, and copying the results into the appropriate replacement directory.

PS2 Texture Forge turns that process into:

    Start Texture Forge
            ↓
        Play the game
            ↓
        Explore everything
            ↓
     Let the pack build itself

## Roadmap

Potential future improvements include:

- Automatic game directory detection
- Monitoring multiple games simultaneously
- Texture type classification
- Detection of masks and utility textures
- Different upscale models for UI and world textures
- Configurable upscale factors
- Persistent processing statistics
- Failed-texture retry queue
- Optional texture filtering
- GUI
- Direct PCSX2 integration

## Credits

### PCSX2

Texture dumping and replacement functionality is provided by the PCSX2 project.

https://pcsx2.net/

https://github.com/PCSX2/pcsx2

### Real-ESRGAN

AI texture upscaling is performed using Real-ESRGAN.

Real-ESRGAN is developed by Xintao Wang and contributors.

https://github.com/xinntao/Real-ESRGAN

## Disclaimer

PS2 Texture Forge is an independent project and is not affiliated with or endorsed by the PCSX2 or Real-ESRGAN projects.

Users are responsible for ensuring they have the appropriate rights to any game assets or texture packs they distribute.

## License

See `LICENSE` for project licensing information.