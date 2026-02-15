"""
Main dashboard page for MeshCore GUI.

Thin orchestrator that owns the layout and the 500 ms update timer.
All visual content is delegated to individual panel classes in
:mod:`meshcore_gui.gui.panels`.
"""

import logging

from nicegui import ui

from meshcore_gui import config

from meshcore_gui.core.protocols import SharedDataReader
from meshcore_gui.gui.panels import (
    ActionsPanel,
    ContactsPanel,
    DevicePanel,
    MapPanel,
    MessagesPanel,
    RoomServerPanel,
    RxLogPanel,
)
from meshcore_gui.gui.archive_page import ArchivePage
from meshcore_gui.services.pin_store import PinStore
from meshcore_gui.services.room_password_store import RoomPasswordStore


# Suppress the harmless "Client has been deleted" warning that NiceGUI
# emits when a browser tab is refreshed while a ui.timer is active.
class _DeletedClientFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return 'Client has been deleted' not in record.getMessage()

logging.getLogger('nicegui').addFilter(_DeletedClientFilter())


# ── DOMCA Theme ──────────────────────────────────────────────────────
# Fonts + CSS variables adapted from domca.nl style.css for NiceGUI/Quasar.
# Dark/light variable sets switch via Quasar's body--dark / body--light classes.

_DOMCA_HEAD = '''
<link href="https://fonts.googleapis.com/css2?family=Exo+2:wght@800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
<style>
/* ── DOMCA theme variables (dark) ── */
body.body--dark {
  --bg: #0A1628;
  --grid: #0077B6;   --grid-op: 0.15;
  --mesh-bg: #48CAE4; --mesh-bg-op: 0.08;
  --line: #0077B6;   --line-op: 0.6;
  --wave: #48CAE4;   --node: #00B4D8; --node-center: #CAF0F8;
  --hub-text: #0A1628; --outer: #0077B6;
  --title: #48CAE4;  --subtitle: #48CAE4;
  --tagline: #90E0EF; --tag-op: 0.5;
  --badge-stroke: #0077B6; --badge-text: #48CAE4;
  --pe1hvh: #0077B6;
}
/* ── DOMCA theme variables (light) ── */
body.body--light {
  --bg: #FFFFFF;
  --grid: #023E8A;   --grid-op: 0.04;
  --mesh-bg: #0077B6; --mesh-bg-op: 0.05;
  --line: #0096C7;   --line-op: 0.35;
  --wave: #0096C7;   --node: #0077B6; --node-center: #FFFFFF;
  --hub-text: #FFFFFF; --outer: #0096C7;
  --title: #0077B6;  --subtitle: #0077B6;
  --tagline: #0096C7; --tag-op: 0.4;
  --badge-stroke: #0077B6; --badge-text: #0077B6;
  --pe1hvh: #0096C7;
}

/* ── DOMCA page background ── */
body.body--dark  { background: #0A1628 !important; }
body.body--light { background: #f4f8fb !important; }
body.body--dark .q-page  { background: #0A1628 !important; }
body.body--light .q-page { background: #f4f8fb !important; }

/* ── DOMCA header ── */
body.body--dark .q-header  { background: #0d1f35 !important; }
body.body--light .q-header { background: #0077B6 !important; }

/* ── DOMCA drawer — distinct from page background ── */
body.body--dark .domca-drawer  { background: #0f2340 !important; border-right: 1px solid rgba(0,119,182,0.25) !important; }
body.body--light .domca-drawer { background: rgba(244,248,251,0.97) !important; }
.domca-drawer .q-btn__content  { justify-content: flex-start !important; }

/* ── DOMCA cards — dark mode readable ── */
body.body--dark .q-card {
  background: #112240 !important;
  color: #e0f0f8 !important;
  border: 1px solid rgba(0,119,182,0.15) !important;
}
body.body--dark .q-card .text-gray-600 { color: #48CAE4 !important; }
body.body--dark .q-card .text-gray-500 { color: #8badc4 !important; }
body.body--dark .q-card .text-gray-400 { color: #6a8fa8 !important; }
body.body--dark .q-card .text-xs       { color: #c0dce8 !important; }
body.body--dark .q-card .text-sm       { color: #d0e8f2 !important; }
body.body--dark .q-card .text-red-400  { color: #f87171 !important; }

/* ── Dark mode: message area, inputs, tables ── */
body.body--dark .bg-gray-50  { background: #0c1a2e !important; color: #c0dce8 !important; }
body.body--dark .bg-gray-100 { background: #152a45 !important; }
body.body--dark .hover\:bg-gray-100:hover { background: #1a3352 !important; }
body.body--dark .hover\:bg-blue-50:hover  { background: #0d2a4a !important; }
body.body--dark .bg-yellow-50 { background: rgba(72,202,228,0.06) !important; }

body.body--dark .q-field__control { background: #0c1a2e !important; color: #e0f0f8 !important; }
body.body--dark .q-field__native  { color: #e0f0f8 !important; }
body.body--dark .q-field__label   { color: #8badc4 !important; }

body.body--dark .q-table { background: #112240 !important; color: #c0dce8 !important; }
body.body--dark .q-table thead th { color: #48CAE4 !important; }
body.body--dark .q-table tbody td { color: #c0dce8 !important; }

body.body--dark .q-checkbox__label { color: #c0dce8 !important; }
body.body--dark .q-btn--flat:not(.domca-menu-btn) { color: #48CAE4 !important; }

body.body--dark .q-separator { background: rgba(0,119,182,0.2) !important; }

/* ── DOMCA menu link styling ── */
body.body--dark .domca-menu-btn        { color: #8badc4 !important; }
body.body--dark .domca-menu-btn:hover  { color: #48CAE4 !important; }
body.body--light .domca-menu-btn       { color: #3d6380 !important; }
body.body--light .domca-menu-btn:hover { color: #0077B6 !important; }

body.body--dark .domca-ext-link  { color: #8badc4 !important; }
body.body--light .domca-ext-link { color: #3d6380 !important; }

/* ── DOMCA active menu item ── */
body.body--dark .domca-menu-active  { color: #48CAE4 !important; background: rgba(72,202,228,0.1) !important; }
body.body--light .domca-menu-active { color: #0077B6 !important; background: rgba(0,119,182,0.08) !important; }

/* ── Landing page centering ── */
.domca-landing {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 64px);
  padding: 0.5rem;
}
.domca-landing svg {
  width: min(90vw, 800px);
  height: auto;
  display: block;
}

/* ── Panel container — responsive single column ── */
.domca-panel {
  width: 100%;
  max-width: 900px;
  margin: 0 auto;
  padding: 0.5rem;
}

/* ── Responsive heights — override fixed Tailwind heights in panels ── */
.domca-panel .h-40  { height: calc(100vh - 20rem) !important; min-height: 10rem; }
.domca-panel .h-32  { height: calc(100vh - 24rem) !important; min-height: 8rem; }
.domca-panel .h-72  { height: calc(100vh - 12rem) !important; min-height: 14rem; }
.domca-panel .max-h-48 { max-height: calc(100vh - 16rem) !important; min-height: 6rem; }

/* ── Allow narrow viewports down to 320px ── */
body, .q-layout, .q-page {
  min-width: 0 !important;
}
.q-drawer { max-width: 85vw !important; }

/* ── Mobile optimisations ── */
@media (max-width: 640px) {
  .domca-landing svg { width: 98vw; }
  .domca-panel       { padding: 0.25rem; }
  .domca-panel .q-card { border-radius: 8px !important; }
}
@media (max-width: 400px) {
  .domca-landing { padding: 0.25rem; }
  .domca-landing svg { width: 100vw; }
  .q-header { padding-left: 0.5rem !important; padding-right: 0.5rem !important; }
}

/* ── Footer label ── */
.domca-footer {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.65rem;
  letter-spacing: 2px;
  opacity: 0.3;
}
</style>
'''

# ── DOMCA Landing SVG ────────────────────────────────────────────────
# Extracted from domca.nl index.html — mesh logo, title, tagline.
# Uses CSS variables defined above for dark/light theme support.

_DOMCA_SVG = '''\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400">
  <defs>
    <pattern id="gp" width="20" height="20" patternUnits="userSpaceOnUse">
      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="var(--grid)" stroke-width="0.3"/>
    </pattern>
  </defs>
  <rect width="800" height="400" fill="var(--bg)"/>
  <rect width="800" height="400" fill="url(#gp)" opacity="var(--grid-op)"/>
  <g opacity="var(--mesh-bg-op)" stroke="var(--mesh-bg)" stroke-width="1">
    <line x1="50" y1="80" x2="200" y2="150"/><line x1="200" y1="150" x2="150" y2="300"/>
    <line x1="150" y1="300" x2="350" y2="250"/><line x1="350" y1="250" x2="200" y2="150"/>
    <line x1="600" y1="100" x2="750" y2="180"/><line x1="750" y1="180" x2="680" y2="320"/>
    <line x1="680" y1="320" x2="550" y2="280"/><line x1="550" y1="280" x2="600" y2="100"/>
  </g>
  <g transform="translate(80,80)">
    <g stroke="var(--line)" stroke-width="2.5" opacity="var(--line-op)">
      <line x1="100" y1="30" x2="45" y2="120"/><line x1="100" y1="30" x2="155" y2="120"/>
      <line x1="45" y1="120" x2="155" y2="120"/><line x1="100" y1="30" x2="100" y2="95"/>
      <line x1="45" y1="120" x2="100" y2="95"/><line x1="155" y1="120" x2="100" y2="95"/>
      <line x1="100" y1="30" x2="100" y2="5"/><line x1="45" y1="120" x2="15" y2="145"/>
      <line x1="155" y1="120" x2="185" y2="145"/><line x1="100" y1="95" x2="30" y2="60"/>
      <line x1="100" y1="95" x2="170" y2="60"/><line x1="100" y1="95" x2="100" y2="160"/>
    </g>
    <g fill="none" stroke="var(--wave)" stroke-width="1.5">
      <path d="M 115 80 Q 135 95 115 110" opacity="0.5"/>
      <path d="M 125 72 Q 155 95 125 118" opacity="0.35"/>
      <path d="M 135 64 Q 175 95 135 126" opacity="0.2"/>
    </g>
    <circle cx="100" cy="30" r="7" fill="var(--node)"/>
    <circle cx="100" cy="30" r="3" fill="var(--node-center)"/>
    <circle cx="45" cy="120" r="7" fill="var(--node)"/>
    <circle cx="45" cy="120" r="3" fill="var(--node-center)"/>
    <circle cx="155" cy="120" r="7" fill="var(--node)"/>
    <circle cx="155" cy="120" r="3" fill="var(--node-center)"/>
    <circle cx="100" cy="95" r="10" fill="var(--node)"/>
    <circle cx="100" cy="95" r="4.5" fill="var(--node-center)"/>
    <circle cx="100" cy="5" r="4" fill="var(--outer)" opacity="0.5"/>
    <circle cx="15" cy="145" r="4" fill="var(--outer)" opacity="0.5"/>
    <circle cx="185" cy="145" r="4" fill="var(--outer)" opacity="0.5"/>
    <circle cx="30" cy="60" r="4" fill="var(--outer)" opacity="0.4"/>
    <circle cx="170" cy="60" r="4" fill="var(--outer)" opacity="0.4"/>
    <circle cx="100" cy="160" r="4" fill="var(--outer)" opacity="0.4"/>
    <text x="100" y="99" text-anchor="middle" font-family="'JetBrains Mono',monospace"
          font-size="9" font-weight="700" fill="var(--hub-text)" letter-spacing="1">NL</text>
  </g>
  <g transform="translate(310,110)">
    <text x="0" y="65" font-family="'Exo 2',sans-serif" font-size="92"
          font-weight="800" fill="var(--title)" letter-spacing="8">DOMCA</text>
    <rect x="2" y="85" width="410" height="2" fill="var(--title)" rx="1"/>
    <text x="3" y="112" font-family="'JetBrains Mono',monospace" font-size="14.5"
          fill="var(--subtitle)" letter-spacing="4.5" opacity="0.9"
          >DUTCH OPEN MESHCORE ACTIVITY</text>
    <text x="3" y="140" font-family="'JetBrains Mono',monospace" font-size="11"
          fill="var(--tagline)" letter-spacing="2" opacity="var(--tag-op)"
          >CONNECTING THE MESH \u00b7 SINCE 2025</text>
  </g>
  <g transform="translate(600,330)">
    <rect width="140" height="32" rx="16" fill="none"
          stroke="var(--badge-stroke)" stroke-width="1.5" opacity="0.5"/>
    <text x="70" y="21" text-anchor="middle" font-family="'JetBrains Mono',monospace"
          font-size="13" fill="var(--badge-text)" letter-spacing="2" opacity="0.7">domca.nl</text>
  </g>
  <text x="80" y="365" font-family="'JetBrains Mono',monospace" font-size="10"
        fill="var(--pe1hvh)" letter-spacing="2" opacity="0.3">PE1HVH</text>
</svg>'''


# ── Menu definitions ─────────────────────────────────────────────────

_MENU_ITEMS = [
    ('\U0001f4ac', 'MESSAGES', 'messages'),
    ('\U0001f465', 'CONTACTS', 'contacts'),
    ('\U0001f5fa\ufe0f', 'MAP',      'map'),
    ('\U0001f4e1', 'DEVICE',   'device'),
    ('\u26a1',     'ACTIONS',  'actions'),
    ('\U0001f4ca', 'RX LOG',   'rxlog'),
    ('\U0001f3e0', 'ROOMS',    'rooms'),
    ('\U0001f4da', 'ARCHIVE',  'archive'),
]

_EXT_LINKS = [
    ('MeshCore',      'https://meshcore.co.uk'),
    ('Handleiding',   'https://www.pe1hvh.nl/pdf/MeshCore_Complete_Handleiding.pdf'),
    ('Netwerk kaart', 'https://meshcore.co.uk/map'),
    ('LocalMesh NL',  'https://www.localmesh.nl/'),
]


class DashboardPage:
    """Main dashboard rendered at ``/``.

    Args:
        shared: SharedDataReader for data access and command dispatch.
    """

    def __init__(self, shared: SharedDataReader, pin_store: PinStore, room_password_store: RoomPasswordStore) -> None:
        self._shared = shared
        self._pin_store = pin_store
        self._room_password_store = room_password_store

        # Panels (created fresh on each render)
        self._device: DevicePanel | None = None
        self._contacts: ContactsPanel | None = None
        self._map: MapPanel | None = None
        self._messages: MessagesPanel | None = None
        self._actions: ActionsPanel | None = None
        self._rxlog: RxLogPanel | None = None
        self._room_server: RoomServerPanel | None = None

        # Header status label
        self._status_label = None

        # Local first-render flag
        self._initialized: bool = False

        # Panel switching state (layout)
        self._panel_containers: dict = {}
        self._active_panel: str = 'landing'
        self._drawer = None
        self._menu_buttons: dict = {}

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def render(self) -> None:
        """Build the complete dashboard layout and start the timer."""
        self._initialized = False

        # Create panel instances (UNCHANGED functional wiring)
        put_cmd = self._shared.put_command
        self._device = DevicePanel()
        self._contacts = ContactsPanel(put_cmd, self._pin_store, self._shared.set_auto_add_enabled, self._on_add_room_server)
        self._map = MapPanel()
        self._messages = MessagesPanel(put_cmd)
        self._actions = ActionsPanel(put_cmd, self._shared.set_bot_enabled)
        self._rxlog = RxLogPanel()
        self._room_server = RoomServerPanel(put_cmd, self._room_password_store)

        # Inject DOMCA theme (fonts + CSS variables)
        ui.add_head_html(_DOMCA_HEAD)

        # Default to dark mode (DOMCA theme)
        dark = ui.dark_mode(True)

        # ── Left Drawer (must be created before header for Quasar) ────
        self._drawer = ui.left_drawer(value=False, bordered=True).classes(
            'domca-drawer'
        ).style('padding: 0')

        with self._drawer:
            # DOMCA branding
            with ui.column().style('padding: 1.5rem 1.2rem 0'):
                ui.label('DOMCA').style(
                    "font-family: 'Exo 2', sans-serif; font-size: 1.4rem; "
                    "font-weight: 800; color: var(--title); letter-spacing: 4px; "
                    "margin-bottom: 1rem"
                )

            # Panel menu items
            self._menu_buttons = {}
            for icon, label, panel_id in _MENU_ITEMS:
                btn = ui.button(
                    f'{icon}  {label}',
                    on_click=lambda pid=panel_id: self._show_panel(pid),
                ).props('flat no-caps align=left').classes(
                    'w-full justify-start domca-menu-btn'
                ).style(
                    "font-family: 'JetBrains Mono', monospace; "
                    "letter-spacing: 2px; font-size: 0.8rem; "
                    "padding: 0.55rem 1.2rem"
                )
                self._menu_buttons[panel_id] = btn

            ui.separator().classes('my-4')

            # External links (same as domca.nl navigation)
            with ui.column().style('padding: 0 1.2rem'):
                for label, url in _EXT_LINKS:
                    ui.link(label, url, new_tab=True).classes(
                        'domca-ext-link'
                    ).style(
                        "font-family: 'JetBrains Mono', monospace; "
                        "letter-spacing: 2px; font-size: 0.72rem; "
                        "text-decoration: none; opacity: 0.6; "
                        "display: block; padding: 0.35rem 0"
                    )

            # Footer in drawer
            ui.space()
            ui.label('\u00a9 2026 PE1HVH').classes('domca-footer').style('padding: 0 1.2rem 1rem')

        # ── Header ────────────────────────────────────────────────
        with ui.header().classes('items-center px-4 py-2 shadow-md'):
            menu_btn = ui.button(
                icon='menu',
                on_click=lambda: self._drawer.toggle(),
            ).props('flat round dense color=white')

            # Swap icon: menu ↔ close
            self._drawer.on_value_change(
                lambda e: menu_btn.props(f'icon={"close" if e.value else "menu"}')
            )

            ui.label(f'\U0001f517 MeshCore v{config.VERSION}').classes(
                'text-lg font-bold ml-2'
            ).style("font-family: 'JetBrains Mono', monospace")

            ui.space()

            self._status_label = ui.label('Starting...').classes(
                'text-sm opacity-70'
            )

            ui.button(
                icon='brightness_6',
                on_click=lambda: dark.toggle(),
            ).props('flat round dense color=white').tooltip('Toggle dark / light')

        # ── Main Content Area ─────────────────────────────────────
        self._panel_containers = {}

        # Landing page (DOMCA SVG splash — visible by default)
        landing = ui.column().classes('domca-landing w-full')
        with landing:
            ui.html(_DOMCA_SVG)
        self._panel_containers['landing'] = landing

        # Panel containers (hidden by default, shown on menu click)
        panel_defs = [
            ('messages', self._messages),
            ('contacts', self._contacts),
            ('map',      self._map),
            ('device',   self._device),
            ('actions',  self._actions),
            ('rxlog',    self._rxlog),
            ('rooms',    self._room_server),
        ]

        for panel_id, panel_obj in panel_defs:
            container = ui.column().classes('domca-panel')
            container.set_visibility(False)
            with container:
                panel_obj.render()
            self._panel_containers[panel_id] = container

        # Archive panel (inline — replaces separate /archive page)
        archive_container = ui.column().classes('domca-panel')
        archive_container.set_visibility(False)
        with archive_container:
            archive = ArchivePage(self._shared)
            archive.render()
        self._panel_containers['archive'] = archive_container

        self._active_panel = 'landing'

        # Start update timer
        ui.timer(0.5, self._update_ui)

    # ------------------------------------------------------------------
    # Panel switching (layout helper — no functional logic)
    # ------------------------------------------------------------------

    def _show_panel(self, panel_id: str) -> None:
        """Show the selected panel, hide all others, close the drawer."""
        for pid, container in self._panel_containers.items():
            container.set_visibility(pid == panel_id)
        self._active_panel = panel_id

        # Update active menu highlight
        for pid, btn in self._menu_buttons.items():
            if pid == panel_id:
                btn.classes('domca-menu-active', remove='')
            else:
                btn.classes(remove='domca-menu-active')

        # Close drawer after selection
        if self._drawer:
            self._drawer.hide()

    # ------------------------------------------------------------------
    # Room Server callback (from ContactsPanel)
    # ------------------------------------------------------------------

    def _on_add_room_server(self, pubkey: str, name: str, password: str) -> None:
        """Handle adding a Room Server from the contacts panel.

        Delegates to the RoomServerPanel which persists the entry,
        creates the UI card and sends the login command.
        """
        if self._room_server:
            self._room_server.add_room(pubkey, name, password)

    # ------------------------------------------------------------------
    # Timer-driven UI update
    # ------------------------------------------------------------------

    def _update_ui(self) -> None:
        try:
            if not self._status_label:
                return

            data = self._shared.get_snapshot()
            is_first = not self._initialized

            # Mark initialised immediately — even if a panel update
            # crashes below, we must NOT retry the full first-render
            # path every 500 ms (that causes the infinite rebuild).
            if is_first:
                self._initialized = True

            # Always update status
            self._status_label.text = data['status']

            # Device info
            if data['device_updated'] or is_first:
                self._device.update(data)

            # Channels → filter checkboxes + channel dropdown + BOT state
            if data['channels_updated'] or is_first:
                self._messages.update_filters(data)
                self._messages.update_channel_options(data['channels'])
                self._actions.update(data)

            # Contacts
            if data['contacts_updated'] or is_first:
                self._contacts.update(data)

            # Map
            if data['contacts'] and (
                data['contacts_updated'] or not self._map.has_markers or is_first
            ):
                self._map.update(data)

            # Messages (always — for live filter changes)
            self._messages.update(
                data,
                self._messages.channel_filters,
                self._messages.last_channels,
                room_pubkeys=self._room_server.get_room_pubkeys() if self._room_server else None,
            )

            # Room Server panels (always — for live messages + contact changes)
            self._room_server.update(data)

            # RX Log
            if data['rxlog_updated']:
                self._rxlog.update(data)

            # Clear flags
            self._shared.clear_update_flags()

            # Signal BLE worker that GUI is ready for data
            if is_first and data['channels'] and data['contacts']:
                self._shared.mark_gui_initialized()

        except Exception as e:
            err = str(e).lower()
            if "deleted" not in err and "client" not in err:
                import traceback
                print(f"GUI update error: {e}")
                traceback.print_exc()
