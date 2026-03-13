"""Internet Archive client for Compute! magazine collection."""

import gzip
import httpx
from typing import Optional, Dict, Any, List

IA_BASE = "https://archive.org"


class ArchiveClient:
    def __init__(self):
        self._metadata_cache: Dict[str, Any] = {}
        self._text_cache: Dict[str, str] = {}
        self._page_index_cache: Dict[str, List] = {}
        self._client: Optional[httpx.AsyncClient] = None

    async def get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                follow_redirects=True,
                headers={"User-Agent": "RetroCodeBuilder/1.0"},
            )
        return self._client

    async def search_issues(
        self, query: str = "", page: int = 1, limit: int = 50
    ) -> Dict:
        """Search Compute! magazine issues."""
        client = await self.get_client()
        q = 'collection:"compute-magazine"'
        if query:
            q += f" {query}"

        resp = await client.get(
            f"{IA_BASE}/advancedsearch.php",
            params={
                "q": q,
                "fl[]": ["identifier", "title", "date", "description", "imagecount"],
                "sort[]": "date asc",
                "rows": limit,
                "page": page,
                "output": "json",
            },
        )
        data = resp.json()
        return {
            "total": data["response"]["numFound"],
            "issues": data["response"]["docs"],
        }

    async def get_metadata(self, identifier: str) -> Dict:
        """Get full item metadata (cached)."""
        if identifier in self._metadata_cache:
            return self._metadata_cache[identifier]

        client = await self.get_client()
        resp = await client.get(f"{IA_BASE}/metadata/{identifier}")
        metadata = resp.json()
        self._metadata_cache[identifier] = metadata
        return metadata

    async def get_page_image_url(
        self, identifier: str, page: int, scale: int = 3
    ) -> Optional[str]:
        """Construct a BookReader image URL for a specific page."""
        metadata = await self.get_metadata(identifier)
        server = metadata.get("d1") or metadata.get("server")
        dir_path = metadata.get("dir")

        if not server or not dir_path:
            return None

        # Find the jp2 zip file
        jp2_zip = None
        files = metadata.get("files", [])
        for f in files:
            name = f.get("name", "") if isinstance(f, dict) else str(f)
            if name.endswith("_jp2.zip"):
                jp2_zip = name
                break

        if not jp2_zip:
            return None

        # Construct leaf name — standard IA naming convention
        base = jp2_zip.replace("_jp2.zip", "")
        leaf = f"{base}_jp2/{base}_{page:04d}.jp2"

        return (
            f"https://{server}/BookReader/BookReaderImages.php"
            f"?zip={dir_path}/{jp2_zip}"
            f"&file={leaf}"
            f"&id={identifier}"
            f"&scale={scale}"
            f"&rotate=0"
        )

    async def get_page_count(self, identifier: str) -> int:
        """Get total page count for an issue."""
        metadata = await self.get_metadata(identifier)
        md = metadata.get("metadata", {})

        # Try imagecount from metadata
        if isinstance(md, dict) and "imagecount" in md:
            return int(md["imagecount"])

        # Fallback: use hOCR page index length
        page_index = await self.get_page_index(identifier)
        if page_index:
            return len(page_index)

        # Fallback: count _jp2 entries in scandata or estimate from file list
        files = metadata.get("files", [])
        for f in files:
            name = f.get("name", "") if isinstance(f, dict) else str(f)
            if name.endswith("_scandata.xml"):
                # scandata lists all pages — but that requires parsing XML
                # For now, estimate from the jp2 zip size
                break

        # Last resort: count any numbered image files
        count = 0
        for f in files:
            name = f.get("name", "") if isinstance(f, dict) else str(f)
            if name.endswith(".jpg") and "/" not in name:
                count += 1
        return count if count > 0 else 200  # reasonable default for a magazine

    async def _find_text_file(self, identifier: str) -> Optional[str]:
        """Find the djvu.txt filename from metadata (names vary across items)."""
        metadata = await self.get_metadata(identifier)
        files = metadata.get("files", [])
        for f in files:
            name = f.get("name", "") if isinstance(f, dict) else str(f)
            if name.endswith("_djvu.txt"):
                return name
        return None

    async def get_ocr_text(self, identifier: str) -> Optional[str]:
        """Download the full OCR text for an issue (cached)."""
        if identifier in self._text_cache:
            return self._text_cache[identifier]

        client = await self.get_client()

        # Find the actual djvu.txt filename from metadata
        txt_file = await self._find_text_file(identifier)
        if not txt_file:
            return None

        url = f"{IA_BASE}/download/{identifier}/{txt_file}"
        resp = await client.get(url)
        if resp.status_code == 200:
            self._text_cache[identifier] = resp.text
            return resp.text
        return None

    async def _find_file(self, identifier: str, suffix: str) -> Optional[str]:
        """Find a file by suffix in an item's file list."""
        metadata = await self.get_metadata(identifier)
        for f in metadata.get("files", []):
            name = f.get("name", "") if isinstance(f, dict) else str(f)
            if name.endswith(suffix):
                return name
        return None

    async def get_page_index(self, identifier: str) -> Optional[List]:
        """Get the hOCR page index: list of [char_start, char_end, byte_start, byte_end]."""
        if identifier in self._page_index_cache:
            return self._page_index_cache[identifier]

        client = await self.get_client()
        idx_file = await self._find_file(identifier, "_hocr_pageindex.json.gz")
        if not idx_file:
            return None

        url = f"{IA_BASE}/download/{identifier}/{idx_file}"
        resp = await client.get(url)
        if resp.status_code != 200:
            return None

        import json
        try:
            data = json.loads(gzip.decompress(resp.content))
            self._page_index_cache[identifier] = data
            return data
        except Exception:
            return None

    async def get_page_text(self, identifier: str, page: int) -> Optional[str]:
        """Get OCR text for a specific page using the hOCR page index."""
        full_text = await self.get_ocr_text(identifier)
        if not full_text:
            return None

        page_index = await self.get_page_index(identifier)
        if page_index and page < len(page_index):
            entry = page_index[page]
            char_start, char_end = entry[0], entry[1]
            return full_text[char_start:char_end].strip()

        # Fallback: try form-feed splitting
        pages = full_text.split("\x0c")
        if page < len(pages):
            return pages[page].strip()

        return None

    async def get_page_text_range(
        self, identifier: str, start_page: int, num_pages: int = 3
    ) -> Dict[int, str]:
        """Get OCR text for a range of pages."""
        result = {}
        for p in range(start_page, start_page + num_pages):
            text = await self.get_page_text(identifier, p)
            if text:
                result[p] = text
        return result

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()


# Singleton for the web app
archive_client = ArchiveClient()
