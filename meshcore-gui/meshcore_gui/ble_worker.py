"""
BLE communication worker for MeshCore GUI.

Runs in a separate thread with its own asyncio event loop.  Connects to
the MeshCore device, subscribes to events, and processes commands sent
from the GUI via the SharedData command queue.
"""

import asyncio
import threading
from datetime import datetime
from typing import Dict, Optional

from meshcore import MeshCore, EventType

from meshcore_gui.config import CHANNELS_CONFIG, debug_print
from meshcore_gui.protocols import SharedDataWriter


class BLEWorker:
    """
    BLE communication worker that runs in a separate thread.

    Attributes:
        address: BLE MAC address of the device
        shared:  SharedDataWriter for thread-safe communication
        mc:      MeshCore instance after connection
        running: Boolean to control the worker loop
    """

    def __init__(self, address: str, shared: SharedDataWriter) -> None:
        self.address = address
        self.shared = shared
        self.mc: Optional[MeshCore] = None
        self.running = True

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the worker in a new daemon thread."""
        thread = threading.Thread(target=self._run, daemon=True)
        thread.start()
        debug_print("BLE worker thread started")

    def _run(self) -> None:
        """Entry point for the worker thread."""
        asyncio.run(self._async_main())

    async def _async_main(self) -> None:
        """Connect, then process commands in an infinite loop."""
        await self._connect()
        if self.mc:
            while self.running:
                await self._process_commands()
                await asyncio.sleep(0.1)

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def _connect(self) -> None:
        """Connect to the BLE device and load initial data."""
        self.shared.set_status(f"🔄 Connecting to {self.address}...")

        try:
            print(f"BLE: Connecting to {self.address}...")
            self.mc = await MeshCore.create_ble(self.address)
            print("BLE: Connected!")

            await asyncio.sleep(1)

            # Subscribe to events
            self.mc.subscribe(EventType.CHANNEL_MSG_RECV, self._on_channel_msg)
            self.mc.subscribe(EventType.CONTACT_MSG_RECV, self._on_contact_msg)
            self.mc.subscribe(EventType.RX_LOG_DATA, self._on_rx_log)

            await self._load_data()
            await self.mc.start_auto_message_fetching()

            self.shared.set_connected(True)
            self.shared.set_status("✅ Connected")
            print("BLE: Ready!")

        except Exception as e:
            print(f"BLE: Connection error: {e}")
            self.shared.set_status(f"❌ {e}")

    async def _load_data(self) -> None:
        """
        Load device data with retry mechanism.

        Tries send_appstart and send_device_query each up to 5 times.
        Channels come from hardcoded config.
        """
        # send_appstart
        self.shared.set_status("🔄 Device info...")
        for i in range(5):
            debug_print(f"send_appstart attempt {i + 1}")
            r = await self.mc.commands.send_appstart()
            if r.type != EventType.ERROR:
                print(f"BLE: send_appstart OK: {r.payload.get('name')}")
                self.shared.update_from_appstart(r.payload)
                break
            await asyncio.sleep(0.3)

        # send_device_query
        for i in range(5):
            debug_print(f"send_device_query attempt {i + 1}")
            r = await self.mc.commands.send_device_query()
            if r.type != EventType.ERROR:
                print(f"BLE: send_device_query OK: {r.payload.get('ver')}")
                self.shared.update_from_device_query(r.payload)
                break
            await asyncio.sleep(0.3)

        # Channels (hardcoded — BLE get_channel is unreliable)
        self.shared.set_status("🔄 Channels...")
        self.shared.set_channels(CHANNELS_CONFIG)
        print(f"BLE: Channels loaded: {[c['name'] for c in CHANNELS_CONFIG]}")

        # Contacts
        self.shared.set_status("🔄 Contacts...")
        r = await self.mc.commands.get_contacts()
        if r.type != EventType.ERROR:
            self.shared.set_contacts(r.payload)
            print(f"BLE: Contacts loaded: {len(r.payload)} contacts")

    # ------------------------------------------------------------------
    # Command handling
    # ------------------------------------------------------------------

    async def _process_commands(self) -> None:
        """Process all commands queued by the GUI."""
        while True:
            cmd = self.shared.get_next_command()
            if cmd is None:
                break
            await self._handle_command(cmd)

    async def _handle_command(self, cmd: Dict) -> None:
        """
        Process a single command from the GUI.

        Supported actions: send_message, send_dm, send_advert, refresh.
        """
        action = cmd.get('action')

        if action == 'send_message':
            channel = cmd.get('channel', 0)
            text = cmd.get('text', '')
            if text and self.mc:
                await self.mc.commands.send_chan_msg(channel, text)
                self.shared.add_message({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'sender': 'Me',
                    'text': text,
                    'channel': channel,
                    'direction': 'out',
                    'sender_pubkey': '',
                })
                debug_print(f"Sent message to channel {channel}: {text[:30]}")

        elif action == 'send_advert':
            if self.mc:
                await self.mc.commands.send_advert(flood=True)
                self.shared.set_status("📢 Advert sent")
                debug_print("Advert sent")

        elif action == 'send_dm':
            pubkey = cmd.get('pubkey', '')
            text = cmd.get('text', '')
            contact_name = cmd.get('contact_name', pubkey[:8])
            if text and pubkey and self.mc:
                await self.mc.commands.send_msg(pubkey, text)
                self.shared.add_message({
                    'time': datetime.now().strftime('%H:%M:%S'),
                    'sender': 'Me',
                    'text': text,
                    'channel': None,
                    'direction': 'out',
                    'sender_pubkey': pubkey,
                })
                debug_print(f"Sent DM to {contact_name}: {text[:30]}")

        elif action == 'refresh':
            if self.mc:
                debug_print("Refresh requested")
                await self._load_data()

    # ------------------------------------------------------------------
    # Event callbacks
    # ------------------------------------------------------------------

    def _on_channel_msg(self, event) -> None:
        """Callback for received channel messages."""
        payload = event.payload
        sender = payload.get('sender_name') or payload.get('sender') or ''

        debug_print(f"Channel msg payload keys: {list(payload.keys())}")
        debug_print(f"Channel msg payload: {payload}")

        self.shared.add_message({
            'time': datetime.now().strftime('%H:%M:%S'),
            'sender': sender[:15] if sender else '',
            'text': payload.get('text', ''),
            'channel': payload.get('channel_idx'),
            'direction': 'in',
            'snr': payload.get('SNR') or payload.get('snr'),
            'path_len': payload.get('path_len', 0),
            'sender_pubkey': payload.get('sender', ''),
        })

    def _on_contact_msg(self, event) -> None:
        """Callback for received DMs; resolves sender name via pubkey."""
        payload = event.payload
        pubkey = payload.get('pubkey_prefix', '')
        sender = ''

        debug_print(f"DM payload keys: {list(payload.keys())}")
        debug_print(f"DM payload: {payload}")

        if pubkey:
            sender = self.shared.get_contact_name_by_prefix(pubkey)

        if not sender:
            sender = pubkey[:8] if pubkey else ''

        self.shared.add_message({
            'time': datetime.now().strftime('%H:%M:%S'),
            'sender': sender[:15] if sender else '',
            'text': payload.get('text', ''),
            'channel': None,
            'direction': 'in',
            'snr': payload.get('SNR') or payload.get('snr'),
            'path_len': payload.get('path_len', 0),
            'sender_pubkey': pubkey,
        })

        debug_print(f"DM received from {sender}: {payload.get('text', '')[:30]}")

    def _on_rx_log(self, event) -> None:
        """Callback for RX log data."""
        payload = event.payload
        self.shared.add_rx_log({
            'time': datetime.now().strftime('%H:%M:%S'),
            'snr': payload.get('snr', 0),
            'rssi': payload.get('rssi', 0),
            'payload_type': payload.get('payload_type', '?'),
            'hops': payload.get('path_len', 0),
        })
