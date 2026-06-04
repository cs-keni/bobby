"""
Browser / URL tools — open any URL in Chrome (or default browser).

Bobby (Claude) resolves friendly names to URLs using training knowledge:
  "open youtube"              → open_url("https://www.youtube.com")
  "open tiktok careers"       → open_url("https://careers.tiktok.com")
  "search for lo-fi music"    → open_url("https://www.google.com/search?q=lo-fi+music")

Known job sites for quick reference:
  indeed.com, linkedin.com/jobs, glassdoor.com, levels.fyi,
  careers.google.com, jobs.netflix.com, grnh.se (Greenhouse ATS)

For companies whose exact career URL is uncertain, Bobby constructs a
Google search: "site:careers.{company}.com OR {company}.com/careers software engineer entry level"

Chrome is preferred (started via 'start chrome "url"'). Falls back to default
browser if Chrome is not installed.
"""

import subprocess
import sys
from urllib.parse import quote_plus

from core.logging import get_logger
from core.tool_result import ToolResult
from tools.registry import register_tool

log = get_logger(__name__)

# Well-known site shortcuts. Bobby mostly uses its own knowledge,
# but this covers the most common spoken aliases for fast lookup.
_KNOWN_SITES: dict[str, str] = {
    "youtube": "https://www.youtube.com",
    "youtube music": "https://music.youtube.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "instagram": "https://www.instagram.com",
    "tiktok": "https://www.tiktok.com",
    "discord": "https://discord.com/app",
    "github": "https://github.com",
    "stackoverflow": "https://stackoverflow.com",
    "google": "https://www.google.com",
    # Job sites
    "indeed": "https://www.indeed.com/q-software-engineer-entry-level-jobs.html",
    "linkedin jobs": "https://www.linkedin.com/jobs/search/?keywords=entry+level+software+engineer",
    "linkedin": "https://www.linkedin.com",
    "glassdoor": "https://www.glassdoor.com/Job/entry-level-software-engineer-jobs-SRCH_KO0,30.htm",
    "levels": "https://www.levels.fyi",
    "levels.fyi": "https://www.levels.fyi",
    "handshake": "https://app.joinhandshake.com/jobs",
    "wellfound": "https://wellfound.com/jobs?q=software+engineer&l=Remote",
    "angellist": "https://wellfound.com/jobs?q=software+engineer&l=Remote",
    # Career pages for common tech companies
    "google careers": "https://careers.google.com/jobs/results/?q=software+engineer&experience=INTERN_AND_ENTRY_LEVEL",
    "meta careers": "https://www.metacareers.com/jobs?q=software+engineer&teams%5B0%5D=Internship&teams%5B1%5D=University+Grad",
    "microsoft careers": "https://jobs.careers.microsoft.com/global/en/search?q=software+engineer&exp=Experienced+professionals",
    "amazon careers": "https://www.amazon.jobs/en/search?offset=0&result_limit=10&sort=relevant&category%5B%5D=software-development&distanceType=Mi&radius=24km&latitude=&longitude=&loc_group_id=&loc_query=&base_query=entry+level",
    "tiktok careers": "https://careers.tiktok.com/position?keywords=software+engineer&category=&location=&project=7322364765976046338,7247426205886669065",
    "apple careers": "https://jobs.apple.com/en-us/search?search=software+engineer&sort=newest",
    "netflix careers": "https://jobs.netflix.com/search?q=software+engineer",
    "spotify careers": "https://www.lifeatspotify.com/jobs?q=software+engineer",
    "airbnb careers": "https://careers.airbnb.com/positions/?department=Engineering",
    "stripe careers": "https://stripe.com/jobs/search?q=software+engineer",
    "openai careers": "https://openai.com/careers/search/?department=Engineering",
    "anthropic careers": "https://www.anthropic.com/careers#open-roles",
}


def _open_in_chrome(url: str) -> ToolResult:
    """Open a URL in Chrome (or default browser as fallback)."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(f'start chrome "{url}"', shell=True)
        else:
            # WSL: try Chrome first, fall back to default browser
            subprocess.Popen(f'cmd.exe /c start chrome "{url}"', shell=True)
        log.info(f"Browser opened: {url[:80]}")
        return ToolResult(success=True, message=f"Opening {url}", data={"url": url})
    except Exception as e:
        log.error(f"open_in_chrome failed: {e}")
        return ToolResult(success=False, message=f"Couldn't open browser: {e}")


@register_tool(
    name="open_url",
    description=(
        "Open a URL in Chrome. Use this for:\n"
        "- Opening any website: 'open youtube', 'go to reddit'\n"
        "- Job sites: 'open indeed', 'open linkedin jobs', 'open google careers'\n"
        "- Company career pages: 'open tiktok careers', 'open stripe careers'\n"
        "- Any URL the user asks for\n"
        "Bobby knows the URLs for thousands of sites — just pass the full https:// URL. "
        "For sites you're not sure about, use open_search instead."
    ),
    parameters={
        "url": {
            "type": "string",
            "description": "Full URL to open (must start with http:// or https://).",
            "required": True,
        },
    },
)
def open_url(url: str) -> ToolResult:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return _open_in_chrome(url)


@register_tool(
    name="open_search",
    description=(
        "Open a Google search in Chrome. Use when the exact URL isn't known. "
        "Examples: 'search for tiktok entry level software engineer jobs', "
        "'find the careers page for a small startup', "
        "'look up lo-fi playlists on YouTube'."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "What to search for.",
            "required": True,
        },
        "site": {
            "type": "string",
            "description": (
                "Restrict search to a specific site. "
                "E.g. 'youtube.com', 'linkedin.com', 'reddit.com'. "
                "Omit for a general Google search."
            ),
        },
    },
)
def open_search(query: str, site: str = "") -> ToolResult:
    q = query.strip()
    if site:
        q = f"site:{site.strip()} {q}"
    encoded = quote_plus(q)
    url = f"https://www.google.com/search?q={encoded}"
    result = _open_in_chrome(url)
    if result.success:
        result.message = f"Searching Google for: {query}"
    return result


@register_tool(
    name="open_site",
    description=(
        "Open a well-known site by friendly name. "
        "Knows shortcuts for: youtube, spotify, netflix, twitch, reddit, twitter, instagram, tiktok, discord, github, "
        "indeed, linkedin, glassdoor, levels.fyi, handshake, wellfound, "
        "and career pages for: google, meta, microsoft, amazon, tiktok, apple, netflix, spotify, airbnb, stripe, openai, anthropic. "
        "For anything not in this list, use open_url with the full URL."
    ),
    parameters={
        "name": {
            "type": "string",
            "description": (
                "Site name: 'youtube', 'indeed', 'tiktok careers', 'google careers', etc."
            ),
            "required": True,
        },
    },
)
def open_site(name: str) -> ToolResult:
    key = name.lower().strip()

    # Exact match first
    if key in _KNOWN_SITES:
        url = _KNOWN_SITES[key]
        result = _open_in_chrome(url)
        if result.success:
            result.message = f"Opening {name}."
        return result

    # Partial match
    for alias, url in _KNOWN_SITES.items():
        if key in alias or alias.startswith(key):
            result = _open_in_chrome(url)
            if result.success:
                result.message = f"Opening {alias}."
            return result

    # Unknown — fall back to Google search for the career page
    # (covers company career sites we don't have hardcoded)
    search_query = f"{name} careers software engineer entry level"
    return open_search(search_query)
