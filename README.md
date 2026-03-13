# RETRO CODE BUILDER

> I always have great fondness for Compute! magazine. I was an avid subscriber for years through my VIC20, C64, and Amiga years, and I built this to view magazines and OCR the code when it was in the magazine.

A web app and CLI tool for browsing scanned issues of **Compute! magazine** on the [Internet Archive](https://archive.org/details/compute-magazine) and extracting the BASIC type-in program listings from them via OCR.

![retro](https://img.shields.io/badge/platforms-C64%20%7C%20VIC--20%20%7C%20Atari%20%7C%20Apple%20II%20%7C%20TI--99-green)

## What It Does

Compute! magazine (1979–1994) published hundreds of type-in programs — BASIC listings you'd manually enter into your home computer. Those programs are now trapped inside scanned page images on the Internet Archive. This tool gets them out.

- **Browse** all 208 digitized issues with cover thumbnails
- **View** pages in a two-page magazine spread, just like the real thing
- **Extract** BASIC code listings from any page using OCR text + pattern detection
- **Clean** common OCR errors (0/O, 1/l/I, garbled keywords)
- **Copy/Edit** extracted code for use in emulators

## Screenshots

The web interface uses a CRT phosphor terminal aesthetic — green on black with scanlines.

## Quick Start

```bash
# Clone and set up
git clone https://github.com/fixstuff/retro.git
cd retro
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run the web app
python app.py
# Open http://localhost:8580
```

Or use the run script:

```bash
./run.sh
```

## Web Interface

The web app runs on port **8580** and gives you:

- **Issue Browser** — grid of all Compute! issues, searchable by keyword or date
- **Magazine Viewer** — two-page spread with proper book layout (cover on the right, then page pairs)
- **Code Extraction** — popup modal that scans pages for BASIC listings, cleans OCR artifacts, and lets you copy or edit the result
- **Keyboard shortcuts** — Arrow keys or A/D to flip pages, E/C to open code extraction, Escape to close

## CLI

```bash
# List issues
python cli.py issues

# Search for specific issues
python cli.py issues -q "1984 commodore"

# Get issue details
python cli.py info 1984-02-compute-magazine

# Extract code from a specific page (scans 3 pages by default)
python cli.py extract 1984-02-compute-magazine 80

# View raw OCR text for a page
python cli.py text 1984-02-compute-magazine 67

# Scan an entire issue for all code listings
python cli.py scan 1984-02-compute-magazine

# Start the web interface
python cli.py serve
```

## How It Works

1. **Internet Archive API** — searches the `compute-magazine` collection (208 issues, 1979–1994)
2. **BookReader Images** — proxies page scans from IA's BookReader infrastructure
3. **hOCR Page Index** — maps character offsets to page numbers in the djvu text (the raw OCR text has no page breaks, so the hOCR index is essential)
4. **Code Extraction** — regex-based detection of numbered BASIC lines, keyword matching, and OCR artifact cleanup

## Project Structure

```
retro/
├── app.py              # FastAPI web server
├── archive_client.py   # Internet Archive API client (cached)
├── code_extractor.py   # BASIC listing detection + OCR cleanup
├── cli.py              # CLI interface (Click + Rich)
├── run.sh              # Startup script
├── requirements.txt
└── static/
    ├── index.html      # Single-page app
    ├── style.css       # CRT terminal aesthetic
    └── app.js          # Frontend logic
```

## Supported Platforms

Compute! published listings for many home computers. The extractor detects the target platform from surrounding text:

- **Commodore 64** — the most common
- **VIC-20**
- **Atari 400/800/XL**
- **Apple II**
- **TI-99/4A**
- **Commodore PET**

## Roadmap

- [ ] In-browser emulation (C64, Atari) — run extracted code directly
- [ ] LLM-powered OCR cleanup for difficult scans
- [ ] Export to emulator formats (.prg, .bas, .d64)
- [ ] Index of all known program listings across all issues

## Powered By

- [Internet Archive](https://archive.org) — for preserving these magazines
- [Compute! magazine](https://en.wikipedia.org/wiki/Compute!) — for inspiring a generation

## License

MIT
