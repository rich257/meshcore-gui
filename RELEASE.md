# Release Notes — MeshCore GUI

**Date:** 4 February 2026

---

## Summary

This release replaces the single-file monolith (`meshcore_gui.py`, 1,395 lines, 3 classes, 51 methods) with a modular package of 16 files (1,955 lines, 10 classes, 90 methods). The refactoring introduces a `meshcore_gui/` package with Protocol-based dependency inversion, a `widgets/` subpackage with six independent UI components, a message route visualisation page, and full type coverage.

---

## Starting point

The repository contained one file with everything in it:

**`meshcore_gui.py`** — 1,395 lines, 3 classes, 51 methods

| Section | Lines | Methods | Responsibility |
|---------|-------|---------|----------------|
| Config + `debug_print` | 80 | 1 | Constants, debug helper |
| `SharedData` | 225 | 12 | Thread-safe data store |
| `BLEWorker` | 268 | 11 | BLE communication thread |
| `MeshCoreGUI` | 740 | 24 | All GUI: rendering, data updates, user actions |
| Main entry | 74 | 3 | Page handler, `main()` |

All three classes lived in one file. BLEWorker and MeshCoreGUI both depended directly on the concrete SharedData class. MeshCoreGUI handled everything: 8 render methods, 7 data-update methods, 5 user-action methods, the 500ms update timer, and the DM dialog.

---

## Current state

16 files across a package with a `widgets/` subpackage:

| File | Lines | Class | Depends on |
|------|-------|-------|------------|
| `meshcore_gui.py` | 101 | *(entry point)* | concrete SharedData (composition root) |
| `meshcore_gui/__init__.py` | 8 | — | — |
| `meshcore_gui/config.py` | 54 | — | — |
| `meshcore_gui/protocols.py` | 83 | 4 Protocol classes | — |
| `meshcore_gui/shared_data.py` | 263 | SharedData | config |
| `meshcore_gui/ble_worker.py` | 252 | BLEWorker | SharedDataWriter protocol |
| `meshcore_gui/main_page.py` | 148 | DashboardPage | SharedDataReader protocol |
| `meshcore_gui/route_builder.py` | 174 | RouteBuilder | ContactLookup protocol |
| `meshcore_gui/route_page.py` | 258 | RoutePage | SharedDataReadAndLookup protocol |
| `meshcore_gui/widgets/__init__.py` | 22 | — | — |
| `meshcore_gui/widgets/device_panel.py` | 100 | DevicePanel | config |
| `meshcore_gui/widgets/map_panel.py` | 80 | MapPanel | — |
| `meshcore_gui/widgets/contacts_panel.py` | 114 | ContactsPanel | config |
| `meshcore_gui/widgets/message_input.py` | 83 | MessageInput | — |
| `meshcore_gui/widgets/message_list.py` | 156 | MessageList | — |
| `meshcore_gui/widgets/rx_log_panel.py` | 59 | RxLogPanel | — |
| **Total** | **1,955** | **10 classes** | |

---

## What changed

### 1. Monolith → package

The single file was split into a `meshcore_gui/` package. Each class got its own module. Constants and `debug_print` moved to `config.py`. The original `meshcore_gui.py` became a thin entry point (101 lines) that wires components and starts the server.

### 2. Protocol-based dependency inversion

Four `typing.Protocol` interfaces were introduced in `protocols.py`:

| Protocol | Consumer | Methods |
|----------|----------|---------|
| SharedDataWriter | BLEWorker | 10 |
| SharedDataReader | DashboardPage | 4 |
| ContactLookup | RouteBuilder | 1 |
| SharedDataReadAndLookup | RoutePage | 5 |

No consumer imports `shared_data.py` directly. Only the entry point knows the concrete class.

### 3. MeshCoreGUI decomposed into DashboardPage + 6 widgets

The 740-line MeshCoreGUI class was split:

| Old (MeshCoreGUI) | New | Lines |
|--------------------|-----|-------|
| 8 `_render_*` methods | 6 widget classes in `widgets/` | 592 total |
| 7 `_update_*` methods | Widget `update()` methods | *(inside widgets)* |
| 5 user-action methods | Widget `on_command` callbacks | *(inside widgets)* |
| `render()` + `_update_ui()` | DashboardPage (orchestrator) | 148 |

DashboardPage now has 4 methods. It composes widgets and drives the timer. Widgets have zero knowledge of SharedData — they receive plain `Dict` snapshots and callbacks.

### 4. Route visualisation (new feature)

Two new modules that did not exist in the monolith:

| Module | Lines | Purpose |
|--------|-------|---------|
| `route_builder.py` | 174 | Constructs route data from message metadata (pure logic) |
| `route_page.py` | 258 | Renders route on a Leaflet map in a separate browser tab |

Clicking a message in the message list opens `/route/{msg_index}` showing sender → repeater hops → receiver on a map.

### 5. SharedData extended

SharedData gained 4 new methods to support the protocol interfaces and route feature:

| New method | Purpose |
|------------|---------|
| `set_connected()` | Explicit setter (was direct attribute access) |
| `put_command()` | Queue command from GUI (was `cmd_queue.put()` directly) |
| `get_next_command()` | Dequeue command for BLE worker (was `cmd_queue.get_nowait()` directly) |
| `get_contact_by_prefix()` | Contact lookup for route building |
| `get_contact_name_by_prefix()` | Contact name lookup for DM display |

The direct `self.shared.lock` and `self.shared.cmd_queue` access from BLEWorker and MeshCoreGUI was replaced with proper method calls through protocol interfaces.

### 6. Full type coverage

All 90 methods now have complete type annotations (parameters and return types). The old monolith had 51 methods with partial coverage.

---

## Metrics

| Metric | Old | Current |
|--------|-----|---------|
| Files | 1 | 16 |
| Lines | 1,395 | 1,955 |
| Classes | 3 | 10 |
| Methods | 51 | 90 |
| Largest class (lines) | MeshCoreGUI (740) | SharedData (263) |
| Protocol interfaces | 0 | 4 |
| Type-annotated methods | partial | 90/90 |
| Widget classes | 0 | 6 |

---

## Documentation

| Document | Status |
|----------|--------|
| `README.md` | Updated: architecture diagram, project structure, features |
| `docs/MeshCore_GUI_Design.docx` | Updated: widget tables, component descriptions, version history |
| `docs/SOLID_ANALYSIS.md` | Updated: widget SRP, dependency tree, metrics |
| `docs/RELEASE.md` | New (this document) |
