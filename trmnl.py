"""
TRMNL Device API Client

A minimal Python client for the TRMNL e-ink device API.

    from trmnl import TRMNL

    t = TRMNL(plugin_uuid="...", mac_address="...")
    t.status()
    t.show({"title": "hi"})
    t.set_markup(t.plugin_uuid, "<div>{{ title }}</div>")

Authentication: set TRMNL_API_KEY and TRMNL_USER_API_KEY as environment variables.
"""

from __future__ import annotations

import json
import os
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

_API_BASE = "https://trmnl.com"


class TRMNLError(Exception):
    def __init__(self, status_code: int, body: Any):
        self.status_code = status_code
        self.body = body
        super().__init__(f"HTTP {status_code}: {body}")


class TRMNL:
    """Client for the TRMNL device API.

    Args:
        plugin_uuid:  Plugin UUID for show(). Required for pushing content.
        mac_address:  Device MAC address. Required for device-level requests.
        api_key:      Device API key. Falls back to TRMNL_API_KEY env var.
        user_api_key: User API key for account-level ops. Falls back to TRMNL_USER_API_KEY env var.
        base_url:     API base URL (default: https://trmnl.com).
    """

    def __init__(
        self,
        plugin_uuid: str = "",
        mac_address: str = "",
        api_key: str | None = None,
        user_api_key: str | None = None,
        base_url: str = _API_BASE,
    ):
        self.api_key = api_key or os.environ.get("TRMNL_API_KEY", "")
        self.user_api_key = user_api_key or os.environ.get("TRMNL_USER_API_KEY", "")
        self.plugin_uuid = plugin_uuid
        self.mac_address = mac_address
        self.base_url = base_url.rstrip("/")

        if not self.api_key:
            raise ValueError("No API key. Set TRMNL_API_KEY env var or pass api_key=.")

    # ── HTTP helpers ──────────────────────────────────────────────────

    def _device_headers(self) -> dict[str, str]:
        h: dict[str, str] = {"access-token": self.api_key, "Content-Type": "application/json"}
        if self.mac_address:
            h["ID"] = self.mac_address
        return h

    def _user_headers(self) -> dict[str, str]:
        if not self.user_api_key:
            raise ValueError("User API key required. Set TRMNL_USER_API_KEY env var or pass user_api_key=.")
        return {"Authorization": f"Bearer {self.user_api_key}", "Content-Type": "application/json"}

    def _request(self, method: str, path: str, *, auth: str = "device", **kwargs: Any) -> requests.Response:
        headers = self._user_headers() if auth == "user" else self._device_headers()
        r = requests.request(method, f"{self.base_url}{path}", headers=headers, timeout=30, **kwargs)
        if r.status_code >= 400:
            raise TRMNLError(r.status_code, r.text)
        return r

    # ── Display ───────────────────────────────────────────────────────

    def next_screen(self) -> dict:
        """Advance playlist and fetch next screen (what the device does on wake)."""
        return self._request("GET", "/api/display").json()

    def current_screen(self) -> dict:
        """Get current screen without advancing the playlist."""
        return self._request("GET", "/api/current_screen").json()

    def download_screen(self, dest: str | Path | None = None, advance: bool = False) -> Path:
        """Download the current screen image to a local file."""
        info = self.next_screen() if advance else self.current_screen()
        image_url = info.get("image_url")
        if not image_url:
            raise TRMNLError(0, "No image_url in response")
        r = requests.get(image_url, timeout=60)
        r.raise_for_status()
        if dest is None:
            ext = ".png"
            ct = r.headers.get("Content-Type", "")
            if "bmp" in ct or image_url.endswith(".bmp"):
                ext = ".bmp"
            elif "jpeg" in ct or "jpg" in ct:
                ext = ".jpg"
            dest = Path(f"trmnl-screen-{datetime.now():%Y%m%d-%H%M%S}{ext}")
        dest = Path(dest)
        dest.write_bytes(r.content)
        return dest

    # ── Plugin content ────────────────────────────────────────────────

    def show(self, data: dict, plugin_uuid: str | None = None,
             strategy: str | None = None, stream_limit: int | None = None) -> dict:
        """Push merge variables to a private plugin webhook."""
        uuid = plugin_uuid or self.plugin_uuid
        if not uuid:
            raise ValueError("No plugin_uuid. Pass it to TRMNL() or to show().")
        payload: dict[str, Any] = {"merge_variables": data}
        if strategy:
            payload["merge_strategy"] = strategy
        if stream_limit is not None:
            payload["stream_limit"] = stream_limit
        return self._request("POST", f"/api/custom_plugins/{uuid}", json=payload).json()

    def get_plugin(self, plugin_uuid: str | None = None) -> dict:
        """Get existing merge variables for a private plugin."""
        uuid = plugin_uuid or self.plugin_uuid
        if not uuid:
            raise ValueError("No plugin_uuid.")
        return self._request("GET", f"/api/custom_plugins/{uuid}").json()

    # ── Markup ────────────────────────────────────────────────────────

    def set_markup(self, plugin_uuid: str, markup: str, size: str = "markup_full") -> dict:
        """Write an HTML/Liquid template for a plugin layout size."""
        url = f"{self.base_url}/api/plugin_settings/{plugin_uuid}/markup/{size}"
        r = requests.put(url, headers=self._user_headers(), json={"content": markup}, timeout=30)
        if r.status_code >= 400:
            raise TRMNLError(r.status_code, r.text)
        return {"status": r.status_code, "size": size}

    def set_markup_all(self, plugin_uuid: str, markup: str) -> None:
        """Set the same markup on all four layout sizes."""
        for size in ["markup_full", "markup_half_horizontal", "markup_half_vertical", "markup_quadrant"]:
            self.set_markup(plugin_uuid, markup, size)

    # ── Account ───────────────────────────────────────────────────────

    def devices(self) -> list[dict]:
        return self._request("GET", "/api/devices", auth="user").json()["data"]

    def device(self, device_id: int | None = None) -> dict:
        if device_id is None:
            device_id = self.devices()[0]["id"]
        return self._request("GET", f"/api/devices/{device_id}", auth="user").json()["data"]

    def plugins(self) -> list[dict]:
        return self._request("GET", "/api/plugin_settings", auth="user").json()["data"]

    def playlist(self) -> list[dict]:
        return self._request("GET", "/api/playlists/items", auth="user").json()["data"]

    def playlist_toggle(self, item_id: int, visible: bool) -> dict:
        return self._request("PATCH", f"/api/playlists/items/{item_id}", auth="user", json={"visible": visible}).json()

    # ── Status ────────────────────────────────────────────────────────

    def status(self) -> dict:
        result: dict[str, Any] = {}
        try:
            s = self.current_screen()
            result["screen"] = {k: s.get(k) for k in ("status", "refresh_rate", "image_url", "filename")}
        except TRMNLError as e:
            result["screen"] = {"error": str(e)}
        if self.user_api_key:
            try:
                d = self.device()
                result["device"] = {
                    "name": d.get("name"), "friendly_id": d.get("friendly_id"),
                    "battery": f"{d.get('percent_charged', '?')}%",
                    "wifi": f"{d.get('wifi_strength', '?')}%",
                    "last_ping": d.get("last_ping_at"),
                }
            except TRMNLError:
                pass
        result["plugin_uuid"] = self.plugin_uuid or None
        return result

    def __repr__(self) -> str:
        key = self.api_key[:4] + "..." + self.api_key[-4:] if len(self.api_key) > 8 else "***"
        plug = self.plugin_uuid[:8] + "..." if len(self.plugin_uuid) > 8 else self.plugin_uuid or "none"
        return f"TRMNL(key='{key}', plugin='{plug}')"


# ── CLI ───────────────────────────────────────────────────────────────

def _cli():
    import argparse

    parser = argparse.ArgumentParser(prog="trmnl", description="TRMNL device CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            examples:
              TRMNL_API_KEY=xxx python trmnl.py status
              python trmnl.py show '{"title": "hi"}' --plugin-uuid UUID
              python trmnl.py download -o screen.png
              python trmnl.py devices
        """))
    parser.add_argument("--plugin-uuid", help="Plugin UUID (or set TRMNL_PLUGIN_UUID env var)")
    parser.add_argument("--mac-address", help="Device MAC address")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("status", help="Device & screen status")
    sub.add_parser("screen", help="Current screen info")
    sub.add_parser("next", help="Advance playlist, get next screen")
    dl = sub.add_parser("download", help="Download screen image")
    dl.add_argument("-o", "--output", help="Output file path")
    dl.add_argument("--advance", action="store_true")
    sh = sub.add_parser("show", help="Push data to plugin")
    sh.add_argument("data", help='JSON merge variables')
    gp = sub.add_parser("get-plugin", help="Get plugin merge variables")
    gp.add_argument("uuid", nargs="?")
    sub.add_parser("devices", help="List devices")
    sub.add_parser("plugins", help="List plugin settings")
    sub.add_parser("playlist", help="List playlist items")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    t = TRMNL(
        plugin_uuid=args.plugin_uuid or os.environ.get("TRMNL_PLUGIN_UUID", ""),
        mac_address=args.mac_address or os.environ.get("TRMNL_MAC_ADDRESS", ""),
    )
    if args.command == "status":
        print(json.dumps(t.status(), indent=2))
    elif args.command == "screen":
        print(json.dumps(t.current_screen(), indent=2))
    elif args.command == "next":
        print(json.dumps(t.next_screen(), indent=2))
    elif args.command == "download":
        p = t.download_screen(dest=args.output, advance=args.advance)
        print(f"Saved to {p}")
    elif args.command == "show":
        print(json.dumps(t.show(json.loads(args.data)), indent=2))
    elif args.command == "get-plugin":
        print(json.dumps(t.get_plugin(getattr(args, "uuid", None)), indent=2))
    elif args.command == "devices":
        print(json.dumps(t.devices(), indent=2))
    elif args.command == "plugins":
        print(json.dumps(t.plugins(), indent=2))
    elif args.command == "playlist":
        print(json.dumps(t.playlist(), indent=2))


if __name__ == "__main__":
    _cli()
