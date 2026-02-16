#!/usr/bin/env python3
"""
MeshCore GUI — Threaded BLE Edition
====================================

Entry point.  Parses arguments, wires up the components, registers
NiceGUI pages and starts the server.

Usage:
    python meshcore_gui.py <BLE_ADDRESS>
    python meshcore_gui.py <BLE_ADDRESS> --debug-on
    python meshcore_gui.py <BLE_ADDRESS> --port=9090
    python meshcore_gui.py <BLE_ADDRESS> --ble-pin=000000
    python -m meshcore_gui <BLE_ADDRESS>

                   Author: PE1HVH
                  Version: 5.0
  SPDX-License-Identifier: MIT
                Copyright: (c) 2026 PE1HVH
"""

import sys

from nicegui import app, ui

# Allow overriding DEBUG before anything imports it
import meshcore_gui.config as config

try:
    from meshcore import MeshCore, EventType  # noqa: F401 — availability check
except ImportError:
    print("ERROR: meshcore library not found")
    print("Install with: pip install meshcore")
    sys.exit(1)

from meshcore_gui.ble.worker import BLEWorker
from meshcore_gui.core.shared_data import SharedData
from meshcore_gui.gui.dashboard import DashboardPage
from meshcore_gui.gui.route_page import RoutePage
from meshcore_gui.gui.archive_page import ArchivePage
from meshcore_gui.services.pin_store import PinStore
from meshcore_gui.services.room_password_store import RoomPasswordStore


# Global instances (needed by NiceGUI page decorators)
_shared = None
_dashboard = None
_route_page = None
_archive_page = None


@ui.page('/')
def _page_dashboard():
    """NiceGUI page handler — main dashboard."""
    if _dashboard:
        _dashboard.render()


@ui.page('/route/{msg_key}')
def _page_route(msg_key: str):
    """NiceGUI page handler — route visualization (new tab)."""
    if _route_page:
        _route_page.render(msg_key)


@ui.page('/archive')
def _page_archive():
    """NiceGUI page handler — message archive."""
    if _archive_page:
        _archive_page.render()


def main():
    """
    Main entry point.

    Parses CLI arguments, initialises all components and starts the
    NiceGUI server.
    """
    global _shared, _dashboard, _route_page, _archive_page

    # Parse arguments
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = [a for a in sys.argv[1:] if a.startswith('--')]

    if not args:
        print("MeshCore GUI - Threaded BLE Edition")
        print("=" * 40)
        print("Usage: python meshcore_gui.py <BLE_ADDRESS> [--debug-on] [--port=PORT] [--ble-pin=PIN]")
        print("Example: python meshcore_gui.py literal:AA:BB:CC:DD:EE:FF")
        print("         python meshcore_gui.py literal:AA:BB:CC:DD:EE:FF --debug-on")
        print("         python meshcore_gui.py literal:AA:BB:CC:DD:EE:FF --port=9090")
        print("         python meshcore_gui.py literal:AA:BB:CC:DD:EE:FF --ble-pin=000000")
        print()
        print("Options:")
        print("  --debug-on        Enable verbose debug logging")
        print("  --port=PORT       Web server port (default: 8081)")
        print("  --ble-pin=PIN     BLE pairing PIN (default: 123456)")
        print()
        print("Tip: Use 'bluetoothctl scan on' to find devices")
        sys.exit(1)

    ble_address = args[0]
    config.set_log_file_for_device(ble_address)

    # Apply --debug-on flag
    if '--debug-on' in flags:
        config.DEBUG = True

    # Apply --port flag
    port = 8081
    for flag in flags:
        if flag.startswith('--port='):
            try:
                port = int(flag.split('=', 1)[1])
            except ValueError:
                print(f"ERROR: Invalid port number: {flag}")
                sys.exit(1)

    # Apply --ble-pin flag
    for flag in flags:
        if flag.startswith('--ble-pin='):
            config.BLE_PIN = flag.split('=', 1)[1]

    # Startup banner
    print("=" * 50)
    print("MeshCore GUI - Threaded BLE Edition")
    print("=" * 50)
    print(f"Device:     {ble_address}")
    print(f"Port:       {port}")
    print(f"BLE PIN:    {config.BLE_PIN}")
    print(f"Debug mode: {'ON' if config.DEBUG else 'OFF'}")
    print("=" * 50)

    # Assemble components
    _shared = SharedData(ble_address)
    _pin_store = PinStore(ble_address)
    _room_password_store = RoomPasswordStore(ble_address)
    _dashboard = DashboardPage(_shared, _pin_store, _room_password_store)
    _route_page = RoutePage(_shared)
    _archive_page = ArchivePage(_shared)

    # Start BLE worker in background thread
    worker = BLEWorker(ble_address, _shared)
    worker.start()

    # Serve static PWA assets (manifest, icons)
    from pathlib import Path
    static_dir = Path(__file__).parent / 'static'
    if static_dir.is_dir():
        app.add_static_files('/static', str(static_dir))

    # Start NiceGUI server (blocks)
    ui.run(show=False, host='0.0.0.0', title='DOMCA MeshCore', port=port, reload=False, storage_secret='meshcore-gui-secret')


if __name__ == "__main__":
    main()
