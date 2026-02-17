"""Map panel — Leaflet map with own position and contact markers."""

from typing import Dict, List

from nicegui import ui

from meshcore_gui.config import DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM
from meshcore_gui.gui.constants import TYPE_ICONS


class MapPanel:
    """Interactive Leaflet map in the centre column."""

    def __init__(self) -> None:
        self._map = None
        self._contacts_markers: List = []
        self._own_marker = None

    @property
    def has_markers(self) -> bool:
        return bool(self._contacts_markers)

    def render(self) -> None:
        with ui.card().classes('w-full'):
            self._map = ui.leaflet(
                center=DEFAULT_MAP_CENTER, zoom=DEFAULT_MAP_ZOOM
            ).classes('w-full h-72')

    def update(self, data: Dict) -> None:
        if not self._map:
            return

        # Own position
        if (data['device_updated'] or self._own_marker is None) and (data['adv_lat'] and data['adv_lon']):
            try:
                self._map.remove_layer(self._own_marker)
            except Exception:
                pass

            self._own_marker = self._map.marker(latlng=(data['adv_lat'], data['adv_lon']), options={'title': '📡 ' + data['name']})
            self._map.set_center((data['adv_lat'], data['adv_lon']))

        # Contact markers
        if data['contacts_updated'] or not self.has_markers:
            # Remove old markers
            for marker in self._contacts_markers:
                try:
                    self._map.remove_layer(marker)
                except Exception:
                    pass
            self._contacts_markers.clear()

            for key, contact in data['contacts'].items():
                lat = contact.get('adv_lat', 0)
                lon = contact.get('adv_lon', 0)
                if lat != 0 or lon != 0:
                    icon = TYPE_ICONS.get(contact.get('type', 0), '○')
                    marker = self._map.marker(latlng=(lat, lon), options={'title': icon + ' ' + contact.get('adv_name', key[:16])})
                    self._contacts_markers.append(marker)
