"""
Route data builder for MeshCore GUI.

Pure data logic — no UI code.  Given a message and a data snapshot, this
module constructs a route dictionary that describes the path the message
has taken through the mesh network (sender → repeaters → receiver).

The route information comes from two sources:

1. **path_len** (from the message itself) — number of hops the message
   traveled.  Always available for received messages.

2. **out_path** (from the sender's contact record) — hex string where
   each byte (2 hex chars) is the first byte of a repeater's public
   key.  Only available when the sender is a known contact with a stored
   route.
"""

from typing import Dict, List, Optional

from meshcore_gui.config import debug_print
from meshcore_gui.protocols import ContactLookup


class RouteBuilder:
    """
    Builds route data for a message from available contact information.

    Uses only data already in memory — no extra BLE commands are sent.

    Args:
        shared: ContactLookup for resolving pubkey prefixes to contacts
    """

    def __init__(self, shared: ContactLookup) -> None:
        self._shared = shared

    def build(self, msg: Dict, data: Dict) -> Dict:
        """
        Build route data for a single message.

        Args:
            msg:  Message dict (must contain 'sender_pubkey', may contain
                  'path_len' and 'snr')
            data: Snapshot dictionary from SharedData.get_snapshot()

        Returns:
            Dictionary with keys:
                sender:        {name, lat, lon, type, pubkey} or None
                self_node:     {name, lat, lon}
                path_nodes:    [{name, lat, lon, type, pubkey}, …]
                snr:           float or None
                msg_path_len:  int — hop count from the message itself
                has_locations: bool — True if any node has GPS coords
        """
        result: Dict = {
            'sender': None,
            'self_node': {
                'name': data['name'] or 'Me',
                'lat': data['adv_lat'],
                'lon': data['adv_lon'],
            },
            'path_nodes': [],
            'snr': msg.get('snr'),
            'msg_path_len': msg.get('path_len', 0),
            'has_locations': False,
        }

        # Look up sender in contacts
        pubkey = msg.get('sender_pubkey', '')
        if pubkey:
            contact = self._shared.get_contact_by_prefix(pubkey)
            if contact:
                result['sender'] = {
                    'name': contact.get('adv_name', pubkey[:8]),
                    'lat': contact.get('adv_lat', 0),
                    'lon': contact.get('adv_lon', 0),
                    'type': contact.get('type', 0),
                    'pubkey': pubkey,
                }

                # Parse out_path for intermediate hops
                out_path = contact.get('out_path', '')
                out_path_len = contact.get('out_path_len', 0)

                debug_print(
                    f"Route: sender={contact.get('adv_name')}, "
                    f"out_path={out_path!r}, out_path_len={out_path_len}, "
                    f"msg_path_len={result['msg_path_len']}"
                )

                if out_path and out_path_len and out_path_len > 0:
                    result['path_nodes'] = self._parse_out_path(
                        out_path, out_path_len, data['contacts']
                    )

        # Determine if any node has GPS coordinates
        all_points = [result['self_node']]
        if result['sender']:
            all_points.append(result['sender'])
        all_points.extend(result['path_nodes'])

        result['has_locations'] = any(
            p.get('lat', 0) != 0 or p.get('lon', 0) != 0
            for p in all_points
        )

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_out_path(
        out_path: str,
        out_path_len: int,
        contacts: Dict,
    ) -> List[Dict]:
        """
        Parse out_path hex string into a list of hop nodes.

        Each byte (2 hex chars) in out_path is the first byte of a
        repeater's public key.

        Returns:
            List of hop node dicts.
        """
        nodes: List[Dict] = []
        hop_hex_len = 2  # 1 byte = 2 hex chars

        for i in range(0, min(len(out_path), out_path_len * 2), hop_hex_len):
            hop_hash = out_path[i:i + hop_hex_len]
            if not hop_hash or len(hop_hash) < 2:
                continue

            hop_contact = RouteBuilder._find_contact_by_pubkey_hash(
                hop_hash, contacts
            )

            if hop_contact:
                nodes.append({
                    'name': hop_contact.get('adv_name', f'0x{hop_hash}'),
                    'lat': hop_contact.get('adv_lat', 0),
                    'lon': hop_contact.get('adv_lon', 0),
                    'type': hop_contact.get('type', 0),
                    'pubkey': hop_hash,
                })
            else:
                nodes.append({
                    'name': f'Unknown (0x{hop_hash})',
                    'lat': 0,
                    'lon': 0,
                    'type': 0,
                    'pubkey': hop_hash,
                })

        return nodes

    @staticmethod
    def _find_contact_by_pubkey_hash(
        hash_hex: str, contacts: Dict
    ) -> Optional[Dict]:
        """
        Find a contact whose pubkey starts with the given 1-byte hash.

        Note: with only 256 possible values, collisions are possible
        when there are many contacts.  Returns the first match.
        """
        hash_hex = hash_hex.lower()
        for pubkey, contact in contacts.items():
            if pubkey.lower().startswith(hash_hex):
                return contact
        return None
