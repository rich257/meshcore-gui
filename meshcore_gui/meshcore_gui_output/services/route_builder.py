"""
Route data builder for MeshCore GUI.

Pure data logic — no UI code.  Given a message and a data snapshot, this
module constructs a route dictionary that describes the path the message
has taken through the mesh network (sender → repeaters → receiver).

v4.1 changes
~~~~~~~~~~~~~
- ``build()`` now accepts a :class:`~meshcore_gui.models.Message`
  dataclass instead of a plain dict.
- Route nodes returned as :class:`~meshcore_gui.models.RouteNode`.
"""

from typing import Dict, List, Optional

from meshcore_gui.config import debug_print
from meshcore_gui.core.models import Message, RouteNode
from meshcore_gui.core.protocols import ContactLookup


class RouteBuilder:
    """
    Builds route data for a message from available contact information.

    Uses only data already in memory — no extra BLE commands are sent.

    Args:
        shared: ContactLookup for resolving pubkey prefixes to contacts
    """

    def __init__(self, shared: ContactLookup) -> None:
        self._shared = shared

    def build(self, msg: Message, data: Dict) -> Dict:
        """
        Build route data for a single message.

        Args:
            msg:  Message dataclass instance.
            data: Snapshot dictionary from SharedData.get_snapshot().

        Returns:
            Dictionary with keys:
                sender:        RouteNode or None
                self_node:     RouteNode
                path_nodes:    List[RouteNode]
                snr:           float or None
                msg_path_len:  int — hop count from the message itself
                has_locations: bool — True if any node has GPS coords
                path_source:   str — 'rx_log', 'contact_out_path' or 'none'
        """
        result: Dict = {
            'sender': None,
            'self_node': RouteNode(
                name=data['name'] or 'Me',
                lat=data['adv_lat'],
                lon=data['adv_lon'],
            ),
            'path_nodes': [],
            'snr': msg.snr,
            'msg_path_len': msg.path_len,
            'has_locations': False,
            'path_source': 'none',
        }

        # Look up sender in contacts
        pubkey = msg.sender_pubkey
        contact: Optional[Dict] = None
        resolved_pubkey: str = pubkey  # tracks the best pubkey we find

        debug_print(
            f"Route build: sender_pubkey={pubkey!r} "
            f"(len={len(pubkey)}, first2={pubkey[:2]!r})"
        )

        # Step 1: pubkey → live contact lookup via SharedData
        if pubkey:
            contact = self._shared.get_contact_by_prefix(pubkey)
            if contact:
                debug_print(
                    f"Route build: step 1 (live pubkey) FOUND "
                    f"{contact.get('adv_name', '?')}"
                )

        # Step 2: pubkey → snapshot contacts (avoids lock-timing issues)
        if not contact and pubkey:
            for pk, c in data['contacts'].items():
                if pk.startswith(pubkey) or pubkey.startswith(pk):
                    contact = c
                    resolved_pubkey = pk
                    debug_print(
                        f"Route build: step 2 (snapshot pubkey) FOUND "
                        f"{c.get('adv_name', '?')}"
                    )
                    break

        # Step 3: sender name → live contact lookup
        if not contact and msg.sender:
            match = self._shared.get_contact_by_name(msg.sender)
            if match:
                matched_pubkey, contact = match
                resolved_pubkey = pubkey or matched_pubkey
                debug_print(
                    f"Route build: step 3 (live name) "
                    f"'{msg.sender}' → pubkey={resolved_pubkey[:16]!r}"
                )

        # Step 4: sender name → snapshot contacts (lock-free, most
        # reliable for archive messages where sender_pubkey may be empty)
        if not contact and msg.sender:
            sender_lower = msg.sender.lower()
            for pk, c in data['contacts'].items():
                adv_name = c.get('adv_name', '')
                if not adv_name:
                    continue
                if (adv_name == msg.sender
                        or adv_name.lower() == sender_lower
                        or msg.sender.startswith(adv_name)
                        or adv_name.startswith(msg.sender)):
                    contact = c
                    resolved_pubkey = pubkey or pk
                    debug_print(
                        f"Route build: step 4 (snapshot name) "
                        f"'{msg.sender}' matched '{adv_name}' "
                        f"→ pubkey={resolved_pubkey[:16]!r}"
                    )
                    break

        # Build RouteNode from best available data
        if contact:
            result['sender'] = RouteNode(
                name=contact.get('adv_name') or msg.sender or resolved_pubkey[:8],
                lat=contact.get('adv_lat', 0),
                lon=contact.get('adv_lon', 0),
                type=contact.get('type', 0),
                pubkey=resolved_pubkey,
            )
        elif msg.sender or pubkey:
            # Step 5: final fallback — create RouteNode from message data
            result['sender'] = RouteNode(
                name=msg.sender or (pubkey[:8] if pubkey else 'Unknown'),
                pubkey=pubkey,
            )
            debug_print(
                f"Route build: step 5 (fallback) "
                f"name={msg.sender!r}, pubkey={pubkey!r}"
            )

        # --- Resolve path nodes (priority order) ---

        # Priority 1: path_hashes from RX_LOG decode
        rx_hashes = msg.path_hashes

        if rx_hashes:
            result['path_nodes'] = self._resolve_hashes(
                rx_hashes, data['contacts'],
            )
            result['path_source'] = 'rx_log'

            debug_print(
                f"Route from RX_LOG: {len(rx_hashes)} hashes → "
                f"{len(result['path_nodes'])} nodes"
            )

        # Priority 2: out_path from sender's contact record
        elif contact:
            out_path = contact.get('out_path', '')
            out_path_len = contact.get('out_path_len', 0)

            debug_print(
                f"Route: sender={contact.get('adv_name')}, "
                f"out_path={out_path!r}, out_path_len={out_path_len}, "
                f"msg_path_len={result['msg_path_len']}"
            )

            if out_path and out_path_len and out_path_len > 0:
                result['path_nodes'] = self._parse_out_path(
                    out_path, out_path_len, data['contacts'],
                )
                result['path_source'] = 'contact_out_path'

        # Determine if any node has GPS coordinates
        all_nodes: List[RouteNode] = [result['self_node']]
        if result['sender']:
            all_nodes.append(result['sender'])
        all_nodes.extend(result['path_nodes'])

        result['has_locations'] = any(n.has_location for n in all_nodes)

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_hashes(
        hashes: List[str],
        contacts: Dict,
    ) -> List[RouteNode]:
        """Resolve a list of 1-byte path hashes into RouteNode objects."""
        nodes: List[RouteNode] = []

        for hop_hash in hashes:
            if not hop_hash or len(hop_hash) < 2:
                continue

            hop_contact = RouteBuilder._find_contact_by_pubkey_hash(
                hop_hash, contacts,
            )

            if hop_contact:
                nodes.append(RouteNode(
                    name=hop_contact.get('adv_name') or f'0x{hop_hash}',
                    lat=hop_contact.get('adv_lat', 0),
                    lon=hop_contact.get('adv_lon', 0),
                    type=hop_contact.get('type', 0),
                    pubkey=hop_hash,
                ))
            else:
                nodes.append(RouteNode(
                    name='-',
                    pubkey=hop_hash,
                ))

        return nodes

    @staticmethod
    def _parse_out_path(
        out_path: str,
        out_path_len: int,
        contacts: Dict,
    ) -> List[RouteNode]:
        """Parse out_path hex string into a list of RouteNode objects."""
        hashes: List[str] = []
        hop_hex_len = 2

        for i in range(0, min(len(out_path), out_path_len * 2), hop_hex_len):
            hop_hash = out_path[i:i + hop_hex_len]
            if hop_hash and len(hop_hash) == 2:
                hashes.append(hop_hash)

        return RouteBuilder._resolve_hashes(hashes, contacts)

    @staticmethod
    def _find_contact_by_pubkey_hash(
        hash_hex: str, contacts: Dict,
    ) -> Optional[Dict]:
        hash_hex = hash_hex.lower()
        for pubkey, contact in contacts.items():
            if pubkey.lower().startswith(hash_hex):
                return contact
        return None
