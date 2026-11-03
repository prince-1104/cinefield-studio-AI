"""Website content & brand asset extraction service with strict SSRF protection."""

import ipaddress
import logging
import mimetypes
import re
import socket
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.schemas.creative_ai import (
    WebsiteAnalysisResult,
    WebsiteAssetCandidate,
)

logger = logging.getLogger(__name__)

# Maximum download limits
MAX_PAGE_SIZE = 5 * 1024 * 1024       # 5 MB HTML
MAX_ASSET_SIZE = 10 * 1024 * 1024     # 10 MB images
REQUEST_TIMEOUT = 14.0                # seconds

# Blocked IP subnets / metadata targets (SSRF defense)
BLOCKED_IP_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # Cloud metadata (AWS, GCP, Azure, etc.)
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.0.0.0/24"),
    ipaddress.ip_network("192.0.2.0/24"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("198.51.100.0/24"),
    ipaddress.ip_network("203.0.113.0/24"),
    ipaddress.ip_network("224.0.0.0/4"),     # Multicast
    ipaddress.ip_network("240.0.0.0/4"),     # Reserved
    ipaddress.ip_network("::/128"),
    ipaddress.ip_network("::1/128"),         # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),        # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),       # IPv6 link-local
]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36 PexylCreativeBot/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}


def validate_safe_url(raw_url: str) -> str:
    """Validate a URL against SSRF and private network attacks.

    Ensures the protocol is http or https and that the destination IP does not
    resolve to a private, loopback, link-local, or cloud metadata network.
    """
    clean_url = raw_url.strip()
    # Check if a scheme is present
    if "://" in clean_url:
        parsed = urllib.parse.urlsplit(clean_url)
    else:
        clean_url = f"https://{clean_url}"
        parsed = urllib.parse.urlsplit(clean_url)

    if parsed.scheme.lower() not in ("http", "https"):
        raise ValueError(f"Unsupported URL protocol: '{parsed.scheme}'. Only http and https are permitted.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL must contain a valid domain name.")

    # Disallow known cloud metadata hostnames directly
    lower_host = hostname.lower()
    if lower_host in ("metadata.google.internal", "metadata", "instance-data", "localhost"):
        raise ValueError(f"Access to internal host '{hostname}' is forbidden.")

    # Resolve IP addresses and verify against blocklists
    try:
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve domain '{hostname}': {e}") from e

    resolved_ips: set[str] = set()
    for item in addr_info:
        sockaddr = item[4]
        ip_str = sockaddr[0]
        resolved_ips.add(ip_str)

    if not resolved_ips:
        raise ValueError(f"No IP address found for domain '{hostname}'.")

    for ip_str in resolved_ips:
        ip_obj = ipaddress.ip_address(ip_str)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast or ip_obj.is_reserved:
            raise ValueError(f"Target '{hostname}' resolves to restricted network address ({ip_str}). Access denied.")

        for blocked_net in BLOCKED_IP_NETWORKS:
            if ip_obj in blocked_net:
                raise ValueError(f"Target '{hostname}' resolves to disallowed subnet ({ip_str}). Access denied.")

    return clean_url


class RobustContentExtractor(HTMLParser):
    """HTML Parser that extracts metadata, headings, key copy, brand colors, and assets."""

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.title_parts: list[str] = []
        self.in_title = False
        self.in_heading = False
        self.heading_parts: list[str] = []
        self.current_heading_tag: str | None = None

        self.headings: list[str] = []
        self.paragraphs: list[str] = []
        self.current_p: list[str] = []
        self.in_p = False

        self.meta_desc: str | None = None
        self.og_title: str | None = None
        self.og_desc: str | None = None
        self.og_image: str | None = None
        self.twitter_image: str | None = None
        self.theme_color: str | None = None

        self.found_colors: set[str] = set()
        self.logo_urls: list[tuple[str, str | None]] = []
        self.product_image_urls: list[tuple[str, str | None]] = []

        # Tag filters
        self.ignored_tags = {"script", "style", "noscript", "svg", "nav", "footer", "iframe"}
        self.current_ignored: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        if tag_lower in self.ignored_tags:
            self.current_ignored.add(tag_lower)
            return

        attr_dict: dict[str, str] = {k.lower(): (v or "").strip() for k, v in attrs if k}

        if tag_lower == "title":
            self.in_title = True
        elif tag_lower in ("h1", "h2", "h3"):
            self.in_heading = True
            self.current_heading_tag = tag_lower
            self.heading_parts = []
        elif tag_lower in ("p", "article", "section"):
            self.in_p = True
            self.current_p = []

        # Parse Meta Tags
        if tag_lower == "meta":
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "").strip()

            if name == "description" and not self.meta_desc:
                self.meta_desc = content
            elif prop == "og:description" and not self.og_desc:
                self.og_desc = content
            elif prop == "og:title" and not self.og_title:
                self.og_title = content
            elif prop == "og:image" and not self.og_image:
                self.og_image = urllib.parse.urljoin(self.base_url, content)
            elif name == "twitter:image" and not self.twitter_image:
                self.twitter_image = urllib.parse.urljoin(self.base_url, content)
            elif name == "theme-color" and not self.theme_color:
                self.theme_color = content
                if content.startswith("#"):
                    self.found_colors.add(content.lower())

        # Parse Favicon and Logo links
        if tag_lower == "link":
            rel = attr_dict.get("rel", "").lower()
            href = attr_dict.get("href", "")
            if href and any(r in rel for r in ("icon", "apple-touch-icon", "shortcut icon")):
                abs_url = urllib.parse.urljoin(self.base_url, href)
                self.logo_urls.append((abs_url, "Site Favicon / Brand Icon"))

        # Parse Image tags
        if tag_lower == "img":
            src = attr_dict.get("src") or attr_dict.get("data-src") or attr_dict.get("srcset", "").split(" ")[0]
            alt = attr_dict.get("alt", "")
            img_class = attr_dict.get("class", "").lower()
            img_id = attr_dict.get("id", "").lower()

            if src:
                # Filter out trackers, tiny icons, beacons
                src_lower = src.lower()
                is_tracker = any(bad in src_lower for bad in ("pixel", "beacon", "analytics", "1x1", "spacer", "advert"))
                if not is_tracker and not src_lower.startswith("data:"):
                    abs_url = urllib.parse.urljoin(self.base_url, src)
                    is_logo = any(word in f"{src_lower} {alt.lower()} {img_class} {img_id}" for word in ("logo", "brand", "mark"))

                    if is_logo:
                        self.logo_urls.append((abs_url, alt or "Brand Logo"))
                    else:
                        # Check extension
                        ext = Path(urllib.parse.urlsplit(abs_url).path).suffix.lower()
                        if ext in (".png", ".jpg", ".jpeg", ".webp", ".svg", ""):
                            self.product_image_urls.append((abs_url, alt or "Product Visual"))

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in self.current_ignored:
            self.current_ignored.discard(tag_lower)
            return

        if tag_lower == "title":
            self.in_title = False
        elif tag_lower in ("h1", "h2", "h3"):
            self.in_heading = False
            text = " ".join("".join(self.heading_parts).split())
            if text and len(text) > 2 and text not in self.headings:
                self.headings.append(text)
            self.heading_parts = []
        elif tag_lower in ("p", "article", "section"):
            self.in_p = False
            text = " ".join("".join(self.current_p).split())
            if text and len(text) > 15:
                self.paragraphs.append(text)
            self.current_p = []

    def handle_data(self, data: str) -> None:
        if self.current_ignored:
            return

        cleaned = data.strip()
        if not cleaned:
            return

        if self.in_title:
            self.title_parts.append(cleaned)
        elif self.in_heading:
            self.heading_parts.append(data)
        elif self.in_p:
            self.current_p.append(data)

        # Search for hex colors in inline style blocks if any
        hex_matches = re.findall(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", data)
        for h in hex_matches:
            if len(self.found_colors) < 6:
                self.found_colors.add(h.lower())


async def analyze_website(raw_url: str) -> WebsiteAnalysisResult:
    """Fetch and securely parse a website to discover brand identity, messaging, and media."""
    safe_url = validate_safe_url(raw_url)
    parsed = urllib.parse.urlsplit(safe_url)
    domain = parsed.hostname or safe_url

    logger.info(f"Analyzing website: {safe_url}")

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers=BROWSER_HEADERS,
        verify=True,
    ) as client:
        try:
            resp = await client.get(safe_url)
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Website responded with HTTP status {e.response.status_code}") from e
        except Exception as e:
            raise RuntimeError(f"Unable to access website '{safe_url}': {e}") from e

        # Validate final redirected URL as well
        validate_safe_url(str(resp.url))

        # Check content length
        content = resp.text
        if len(content) > MAX_PAGE_SIZE:
            content = content[:MAX_PAGE_SIZE]

    # Parse HTML
    parser = RobustContentExtractor(str(resp.url))
    parser.feed(content)

    title = (
        parser.og_title
        or " ".join(parser.title_parts).strip()
        or (parser.headings[0] if parser.headings else domain)
    )
    description = (
        parser.og_desc
        or parser.meta_desc
        or (parser.paragraphs[0] if parser.paragraphs else f"Official website of {domain}")
    )

    # Key body content summary
    key_content_list: list[str] = []
    if parser.headings:
        key_content_list.append("Key Sections & Highlights:\n" + "\n".join(f"- {h}" for h in parser.headings[:8]))
    if parser.paragraphs:
        key_content_list.append("Overview & Product Features:\n" + "\n\n".join(parser.paragraphs[:6]))
    key_content = "\n\n".join(key_content_list)[:4000]

    # Deduplicate logo candidates
    seen_logos: set[str] = set()
    logo_candidates: list[WebsiteAssetCandidate] = []

    for url, alt in parser.logo_urls:
        if url not in seen_logos:
            seen_logos.add(url)
            logo_candidates.append(
                WebsiteAssetCandidate(
                    url=url,
                    asset_type="logo",
                    title=alt or "Discovered Brand Logo",
                )
            )

    # Add OpenGraph image if available
    seen_products: set[str] = set()
    product_candidates: list[WebsiteAssetCandidate] = []

    if parser.og_image and parser.og_image not in seen_logos:
        seen_products.add(parser.og_image)
        product_candidates.append(
            WebsiteAssetCandidate(
                url=parser.og_image,
                asset_type="product",
                title="Social Hero / Promotional Banner",
            )
        )

    if parser.twitter_image and parser.twitter_image not in seen_logos and parser.twitter_image not in seen_products:
        seen_products.add(parser.twitter_image)
        product_candidates.append(
            WebsiteAssetCandidate(
                url=parser.twitter_image,
                asset_type="product",
                title="Twitter Promo Asset",
            )
        )

    for url, alt in parser.product_image_urls:
        if url not in seen_products and url not in seen_logos:
            seen_products.add(url)
            product_candidates.append(
                WebsiteAssetCandidate(
                    url=url,
                    asset_type="product",
                    title=alt or "Product Imagery",
                )
            )
        if len(product_candidates) >= 12:
            break

    # Brand colors
    brand_colors = list(parser.found_colors)[:5]
    if parser.theme_color and parser.theme_color not in brand_colors:
        brand_colors.insert(0, parser.theme_color)

    return WebsiteAnalysisResult(
        url=str(resp.url),
        domain=domain,
        title=title[:200],
        description=description[:600],
        headings=parser.headings[:10],
        key_content=key_content,
        brand_colors=brand_colors,
        logo_candidates=logo_candidates[:6],
        product_image_candidates=product_candidates[:12],
    )


async def import_website_asset(
    asset_url: str,
    project_id: str | None = None,
    asset_type: str = "product",
) -> tuple[str, str, int, str]:
    """Safely download an image asset discovered from a website and persist to artifact storage."""
    safe_url = validate_safe_url(asset_url)
    logger.info(f"Importing website asset: {safe_url}")

    async with httpx.AsyncClient(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers=BROWSER_HEADERS,
    ) as client:
        resp = await client.get(safe_url)
        resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "")
    mime_main = content_type.split(";")[0].strip().lower()

    if not mime_main.startswith("image/"):
        guessed, _ = mimetypes.guess_type(safe_url)
        if guessed and guessed.startswith("image/"):
            mime_main = guessed
        else:
            raise ValueError(f"Downloaded asset has invalid content-type '{content_type}'. Must be an image.")

    data = resp.content
    if len(data) > MAX_ASSET_SIZE:
        raise ValueError(f"Asset size ({len(data)} bytes) exceeds 10MB limit.")

    # Determine extension
    ext = mimetypes.guess_extension(mime_main) or ".png"
    if ext == ".jpe":
        ext = ".jpg"

    # Save to artifact directory
    target_dir = Path(settings.ARTIFACT_DIR) / "imports"
    if project_id:
        target_dir = Path(settings.ARTIFACT_DIR) / "projects" / project_id / "assets"
    target_dir.mkdir(parents=True, exist_ok=True)

    import uuid
    filename = f"{asset_type}_{uuid.uuid4().hex[:10]}{ext}"
    filepath = target_dir / filename
    filepath.write_bytes(data)

    logger.info(f"Saved imported asset to {filepath} ({len(data)} bytes)")
    return str(filepath), filename, len(data), mime_main
