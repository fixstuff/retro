"""Extract and clean BASIC code listings from OCR text."""

import re
from typing import List, Dict

BASIC_KEYWORDS = {
    "PRINT",
    "GOTO",
    "GOSUB",
    "RETURN",
    "FOR",
    "NEXT",
    "TO",
    "STEP",
    "IF",
    "THEN",
    "ELSE",
    "ON",
    "INPUT",
    "READ",
    "DATA",
    "RESTORE",
    "DIM",
    "REM",
    "POKE",
    "PEEK",
    "SYS",
    "USR",
    "LET",
    "DEF",
    "END",
    "STOP",
    "CLR",
    "OPEN",
    "CLOSE",
    "GET",
    "CMD",
    "WAIT",
    "NOT",
    "AND",
    "OR",
    "TAB",
    "SPC",
    "LEFT$",
    "RIGHT$",
    "MID$",
    "CHR$",
    "ASC",
    "STR$",
    "VAL",
    "LEN",
    "ABS",
    "INT",
    "SGN",
    "SQR",
    "RND",
    "LOG",
    "EXP",
    "COS",
    "SIN",
    "TAN",
    "ATN",
    "FRE",
    "POS",
    "SCREEN",
    "COLOR",
    "COLOUR",
    "SOUND",
    "GRAPHICS",
    "PLOT",
    "DRAWTO",
    "SETCOLOR",
    "LOCATE",
    "HLIN",
    "VLIN",
    "HTAB",
    "VTAB",
    "CALL",
    "SPRITE",
}

# Common OCR misreads in code
OCR_FIXES = {
    "PRIMT": "PRINT",
    "PRJNT": "PRINT",
    "PR1NT": "PRINT",
    "G0TO": "GOTO",
    "GOT0": "GOTO",
    "G0SUB": "GOSUB",
    "GOS UB": "GOSUB",
    "RETIJRN": "RETURN",
    "TKEN": "THEN",
    "THEN": "THEN",
    "P0KE": "POKE",
    "PEEX": "PEEK",
    "IMPUT": "INPUT",
    "INPIJT": "INPUT",
    "1NPUT": "INPUT",
    "OATA": "DATA",
    "DAIA": "DATA",
    "NEKT": "NEXT",
    "NEXF": "NEXT",
    "GOSU8": "GOSUB",
}


def extract_listings(text: str) -> List[Dict]:
    """Find BASIC code listings in OCR text."""
    if not text:
        return []

    lines = text.split("\n")
    listings = []
    current_listing = []
    current_start = -1
    last_line_num = -1

    # Pattern for BASIC line numbers (1-63999)
    line_pattern = re.compile(r"^\s*(\d{1,5})\s+(.*)")

    for i, line in enumerate(lines):
        match = line_pattern.match(line)
        if match:
            line_num = int(match.group(1))
            code = match.group(2).strip()

            # Sanity check: line numbers should be in a reasonable range
            # and generally increasing
            if line_num > 63999:
                continue

            # Check if this looks like BASIC
            upper_code = code.upper()
            has_keyword = any(kw in upper_code for kw in BASIC_KEYWORDS)
            has_assignment = "=" in code
            has_string = '"' in code
            is_data_line = upper_code.startswith("DATA") or upper_code.startswith(
                "REM"
            )

            looks_like_basic = has_keyword or has_assignment or has_string or is_data_line

            if looks_like_basic or (current_listing and line_num > last_line_num):
                if not current_listing:
                    current_start = i
                current_listing.append(
                    {"line_num": line_num, "code": line.strip(), "raw": line}
                )
                last_line_num = line_num
            else:
                # Not BASIC - finalize any current listing
                if len(current_listing) >= 3:
                    listings.append(
                        _finalize_listing(current_listing, current_start)
                    )
                current_listing = []
                last_line_num = -1
        else:
            # Non-numbered line
            if current_listing:
                stripped = line.strip()
                if not stripped:
                    # Blank line — tolerate one or two within a listing
                    continue
                # If it looks like prose (many words), end the listing
                words = stripped.split()
                if len(words) > 10:
                    if len(current_listing) >= 3:
                        listings.append(
                            _finalize_listing(current_listing, current_start)
                        )
                    current_listing = []
                    last_line_num = -1

    # Finalize any remaining listing
    if len(current_listing) >= 3:
        listings.append(_finalize_listing(current_listing, current_start))

    return listings


def _finalize_listing(lines: List[Dict], start_offset: int) -> Dict:
    """Package a detected listing."""
    code = "\n".join(l["code"] for l in lines)
    line_nums = [l["line_num"] for l in lines]

    return {
        "code": code,
        "line_count": len(lines),
        "first_line": line_nums[0] if line_nums else 0,
        "last_line": line_nums[-1] if line_nums else 0,
        "start_offset": start_offset,
    }


def clean_listing(code: str) -> str:
    """Clean up common OCR artifacts in a BASIC listing."""
    lines = code.split("\n")
    cleaned = []

    for line in lines:
        # Apply known OCR keyword fixes
        for wrong, right in OCR_FIXES.items():
            line = re.sub(re.escape(wrong), right, line, flags=re.IGNORECASE)

        # Fix O/0 confusion in line numbers at start of line
        match = re.match(r"^(\s*)([O0-9]+)(\s+.+)", line)
        if match:
            prefix = match.group(1)
            num_part = match.group(2).replace("O", "0").replace("o", "0")
            rest = match.group(3)
            try:
                int(num_part)
                line = f"{prefix}{num_part}{rest}"
            except ValueError:
                pass

        # Fix l/1/I confusion in line numbers
        match = re.match(r"^(\s*)([lI1-9][lI0-9]*)(\s+.+)", line)
        if match:
            prefix = match.group(1)
            num_part = match.group(2).replace("l", "1").replace("I", "1")
            rest = match.group(3)
            try:
                int(num_part)
                line = f"{prefix}{num_part}{rest}"
            except ValueError:
                pass

        cleaned.append(line)

    return "\n".join(cleaned)


def identify_platform(text: str) -> str:
    """Try to identify the target platform from surrounding text."""
    t = text.upper()

    scores = {
        "Commodore 64": 0,
        "VIC-20": 0,
        "Atari 800/XL": 0,
        "Apple II": 0,
        "TI-99/4A": 0,
        "Commodore PET": 0,
    }

    # Keywords and their platform associations
    markers = {
        "Commodore 64": ["COMMODORE 64", "C-64", "C64", "64 VERSION"],
        "VIC-20": ["VIC-20", "VIC 20", "VIC20"],
        "Atari 800/XL": [
            "ATARI",
            "ATASCII",
            "GRAPHICS",
            "SETCOLOR",
            "ANTIC",
            "GTIA",
        ],
        "Apple II": [
            "APPLE",
            "APPLESOFT",
            "HLIN",
            "VLIN",
            "HTAB",
            "VTAB",
            "CALL -",
        ],
        "TI-99/4A": ["TI-99", "TI99", "TI BASIC", "EXTENDED BASIC"],
        "Commodore PET": ["PET", "CBM"],
    }

    for platform, keywords in markers.items():
        for kw in keywords:
            if kw in t:
                scores[platform] += 1

    # POKE/PEEK/SYS are strong C64/VIC indicators
    if "POKE" in t and "SYS" in t:
        scores["Commodore 64"] += 1
        scores["VIC-20"] += 1

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "Unknown"
