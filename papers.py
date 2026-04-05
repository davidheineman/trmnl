"""
Fresh Finds — push latest papers to TRMNL display.

Usage:
    export TRMNL_API_KEY=...
    export TRMNL_PLUGIN_UUID=...
    export TRMNL_MAC_ADDRESS=...

    python papers.py                          # fetch & push latest papers
    python papers.py --count 10               # show 10 papers
    python papers.py --setup                  # set the markup template on the plugin

As a library:
    from papers import fetch_papers, push_papers
    papers = fetch_papers(count=8)
    push_papers(papers, plugin_uuid="...", mac_address="...")
"""

from __future__ import annotations

import argparse
import os

import requests

from trmnl import TRMNL

PAPERS_URL = "https://raw.githubusercontent.com/davidheineman/fresh-finds/main/papers.json"

MARKUP = """\
<div class="layout">
  <div class="columns">
    {% assign half = papers.size | plus: 1 | divided_by: 2 %}
    <div class="column">
      <div class="list" data-list-limit="true" data-list-max-height="440" data-list-hidden-count="true" data-list-max-columns="1">
        {% for paper in papers limit: half %}
          <div class="item">
            <div class="meta">
              <span class="index">{{ forloop.index }}</span>
            </div>
            <div class="content">
              <span class="title title--small">{{ paper.title }}</span>
              <span class="description">{{ paper.authors }}</span>
              <div class="flex gap--xsmall" style="flex-wrap:nowrap">
                <span class="label label--small label--underline" style="white-space:nowrap">{{ paper.date }}</span>
              </div>
            </div>
          </div>
        {% endfor %}
      </div>
    </div>
    <div class="column">
      <div class="list" data-list-limit="true" data-list-max-height="440" data-list-hidden-count="true" data-list-max-columns="1">
        {% for paper in papers offset: half %}
          <div class="item">
            <div class="meta">
              <span class="index">{{ forloop.index | plus: half }}</span>
            </div>
            <div class="content">
              <span class="title title--small">{{ paper.title }}</span>
              <span class="description">{{ paper.authors }}</span>
              <div class="flex gap--xsmall" style="flex-wrap:nowrap">
                <span class="label label--small label--underline" style="white-space:nowrap">{{ paper.date }}</span>
              </div>
            </div>
          </div>
        {% endfor %}
      </div>
    </div>
  </div>
</div>

<div class="title_bar">
  <img class="image" src="https://trmnl.com/images/plugins/trmnl--render.svg">
  <span class="title">Fresh Finds</span>
  <span class="instance">{{ subtitle }}</span>
</div>"""


def fetch_papers(count: int = 8, url: str = PAPERS_URL) -> list[dict[str, str]]:
    """Fetch papers from the fresh-finds JSON and return formatted entries."""
    raw = requests.get(url, timeout=30).json()
    papers = []
    for entry in raw[:count]:
        authors = ", ".join(entry.get("authors", []))
        papers.append({
            "title": entry.get("title", ""),
            "authors": authors,
            "date": entry.get("published", ""),
        })
    return papers


def _make_client(plugin_uuid: str = "", mac_address: str = "") -> TRMNL:
    return TRMNL(
        plugin_uuid=plugin_uuid or os.environ.get("TRMNL_PLUGIN_UUID", ""),
        mac_address=mac_address or os.environ.get("TRMNL_MAC_ADDRESS", ""),
    )


def push_papers(papers: list[dict[str, str]], subtitle: str = "Latest Papers",
                plugin_uuid: str = "", mac_address: str = "",
                trmnl: TRMNL | None = None) -> dict:
    """Push papers to the TRMNL device."""
    t = trmnl or _make_client(plugin_uuid, mac_address)
    return t.show({"papers": papers, "subtitle": subtitle})


def setup_markup(plugin_uuid: str = "", mac_address: str = "",
                 trmnl: TRMNL | None = None) -> None:
    """Set the papers markup template on the plugin."""
    t = trmnl or _make_client(plugin_uuid, mac_address)
    t.set_markup_all(t.plugin_uuid, MARKUP)
    print("Markup set on all layout sizes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="papers", description="Push latest papers to TRMNL")
    parser.add_argument("--count", "-n", type=int, default=8, help="Number of papers (default: 8)")
    parser.add_argument("--setup", action="store_true", help="Set the markup template on the plugin")
    parser.add_argument("--plugin-uuid", default="", help="Plugin UUID (or TRMNL_PLUGIN_UUID env)")
    parser.add_argument("--mac-address", default="", help="MAC address (or TRMNL_MAC_ADDRESS env)")
    args = parser.parse_args()

    if args.setup:
        setup_markup(plugin_uuid=args.plugin_uuid, mac_address=args.mac_address)

    papers = fetch_papers(count=args.count)
    result = push_papers(papers, plugin_uuid=args.plugin_uuid, mac_address=args.mac_address)
    print(f"Pushed {len(papers)} papers to TRMNL")
    for i, p in enumerate(papers, 1):
        print(f"  {i}. {p['title']}")
