"""Retro Code Builder — Web app for extracting code from Compute! magazine."""

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
import httpx

from archive_client import archive_client
from code_extractor import extract_listings, clean_listing, identify_platform

app = FastAPI(title="Retro Code Builder")
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


# ── Issue browsing ──────────────────────────────────────────────────


@app.get("/api/issues")
async def list_issues(q: str = "", page: int = 1, limit: int = 50):
    """Search/list Compute! magazine issues."""
    return await archive_client.search_issues(q, page, limit)


@app.get("/api/issue/{identifier}")
async def get_issue(identifier: str):
    """Get details for a specific issue."""
    metadata = await archive_client.get_metadata(identifier)
    page_count = await archive_client.get_page_count(identifier)
    md = metadata.get("metadata", {})

    title = md.get("title", identifier)
    if isinstance(title, list):
        title = title[0]

    date = md.get("date", "")
    if isinstance(date, list):
        date = date[0]

    desc = md.get("description", "")
    if isinstance(desc, list):
        desc = desc[0]

    return {
        "identifier": identifier,
        "title": title,
        "date": date,
        "description": desc,
        "page_count": page_count,
        "thumbnail": f"https://archive.org/services/img/{identifier}",
    }


# ── Page images ─────────────────────────────────────────────────────


@app.get("/api/issue/{identifier}/page/{page}/image")
async def get_page_image(identifier: str, page: int, scale: int = 3):
    """Proxy a page image from the Internet Archive."""
    url = await archive_client.get_page_image_url(identifier, page, scale)
    if not url:
        raise HTTPException(404, "Could not construct image URL")

    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            raise HTTPException(resp.status_code, "Failed to fetch page image from IA")

        content_type = resp.headers.get("content-type", "image/jpeg")
        return StreamingResponse(iter([resp.content]), media_type=content_type)


# ── OCR text & code extraction ──────────────────────────────────────


@app.get("/api/issue/{identifier}/page/{page}/text")
async def get_page_text(identifier: str, page: int):
    """Get OCR text for a specific page."""
    text = await archive_client.get_page_text(identifier, page)
    if text is None:
        return {"text": "", "error": "OCR text not available for this page"}
    return {"text": text}


@app.get("/api/issue/{identifier}/page/{page}/extract")
async def extract_code(
    identifier: str,
    page: int,
    num_pages: int = Query(default=3, ge=1, le=10),
):
    """Extract code listings starting from a page (scans multiple pages)."""
    page_texts = await archive_client.get_page_text_range(identifier, page, num_pages)
    all_text = "\n".join(page_texts.get(p, "") for p in sorted(page_texts.keys()))

    listings = extract_listings(all_text)
    platform = identify_platform(all_text)

    for listing in listings:
        listing["cleaned"] = clean_listing(listing["code"])
        listing["platform"] = platform

    return {
        "listings": listings,
        "platform": platform,
        "pages_scanned": sorted(page_texts.keys()),
        "raw_text": all_text[:8000],
    }


class CleanRequest(BaseModel):
    code: str


@app.post("/api/clean")
async def clean_code(req: CleanRequest):
    """Clean up a code listing."""
    return {"cleaned": clean_listing(req.code)}


# ── Lifecycle ───────────────────────────────────────────────────────


@app.on_event("shutdown")
async def shutdown():
    await archive_client.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8580)
