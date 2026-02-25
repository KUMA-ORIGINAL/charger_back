"""
Simulate an OCPP 1.6 charge point connecting to the proxy.

Usage:
    python simulate_station.py [cp_id] [ws_url]

Defaults:
    cp_id   = TEST_CP_001
    ws_url  = ws://localhost:8000/ws/ocpp/{cp_id}

The script walks through a full lifecycle:
    1. BootNotification
    2. Heartbeat
    3. StatusNotification (Available)
    4. Wait for RemoteStartTransaction from proxy
    5. Authorize + StartTransaction
    6. MeterValues (every 3 sec, incrementing)
    7. Wait for RemoteStopTransaction (or stop after N iterations)
    8. StopTransaction
    9. StatusNotification (Available)
"""

import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone

import websockets


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def msg_id():
    return str(uuid.uuid4())[:8]


class StationSimulator:
    def __init__(self, uri: str):
        self.uri = uri
        self.ws = None
        self.transaction_id = None
        self.meter_wh = 0
        self.running = True

    async def run(self):
        print(f"[SIM] Connecting to {self.uri}")
        async with websockets.connect(
            self.uri, subprotocols=["ocpp1.6"]
        ) as ws:
            self.ws = ws
            print("[SIM] Connected!\n")

            # --- Boot ---
            await self.call("BootNotification", {
                "chargePointVendor": "SimVendor",
                "chargePointModel": "SimModel",
            })

            # --- Heartbeat ---
            await self.call("Heartbeat", {})

            # --- Available ---
            await self.call("StatusNotification", {
                "connectorId": 1,
                "errorCode": "NoError",
                "status": "Available",
                "timestamp": now(),
            })

            print("\n[SIM] Station is Available.")
            print("[SIM] Waiting for commands (RemoteStart/Stop)...")
            print("[SIM] Or press Ctrl+C to simulate a manual start.\n")

            # --- Listen loop ---
            listener = asyncio.create_task(self._listen())

            try:
                await listener
            except asyncio.CancelledError:
                pass

    async def _listen(self):
        async for raw in self.ws:
            print(f"[SIM] ← {raw}")
            frame = json.loads(raw)

            if frame[0] == 2:  # Call from proxy
                action = frame[2]
                payload = frame[3] if len(frame) > 3 else {}

                if action == "RemoteStartTransaction":
                    # Accept and begin charging cycle
                    await self._send_result(frame[1], {"status": "Accepted"})
                    await self._charging_cycle(
                        payload.get("idTag", "UNKNOWN"),
                        payload.get("connectorId", 1),
                    )

                elif action == "RemoteStopTransaction":
                    await self._send_result(frame[1], {"status": "Accepted"})
                    self.running = False

                else:
                    await self._send_result(frame[1], {})

            elif frame[0] == 3:  # CallResult
                pass  # already printed

    async def _charging_cycle(self, id_tag: str, connector_id: int):
        print(f"\n[SIM] === CHARGING CYCLE START (tag={id_tag}) ===\n")

        # Preparing
        await self.call("StatusNotification", {
            "connectorId": connector_id,
            "errorCode": "NoError",
            "status": "Preparing",
            "timestamp": now(),
        })

        # Authorize
        await self.call("Authorize", {"idTag": id_tag})

        # StartTransaction
        self.meter_wh = 0
        resp = await self.call("StartTransaction", {
            "connectorId": connector_id,
            "idTag": id_tag,
            "meterStart": self.meter_wh,
            "timestamp": now(),
        })
        self.transaction_id = resp.get("transactionId")
        print(f"[SIM] transactionId = {self.transaction_id}\n")

        # Charging
        await self.call("StatusNotification", {
            "connectorId": connector_id,
            "errorCode": "NoError",
            "status": "Charging",
            "timestamp": now(),
        })

        # MeterValues loop
        self.running = True
        iterations = 0
        while self.running and iterations < 20:
            await asyncio.sleep(3)
            self.meter_wh += 500  # +0.5 kWh per tick
            iterations += 1

            await self.call("MeterValues", {
                "connectorId": connector_id,
                "transactionId": self.transaction_id,
                "meterValue": [{
                    "timestamp": now(),
                    "sampledValue": [{
                        "value": str(self.meter_wh),
                        "measurand": "Energy.Active.Import.Register",
                        "unit": "Wh",
                    }],
                }],
            })
            print(f"    meter = {self.meter_wh} Wh ({self.meter_wh/1000:.1f} kWh)")

        # StopTransaction
        print(f"\n[SIM] === STOPPING ===\n")
        await self.call("StopTransaction", {
            "transactionId": self.transaction_id,
            "meterStop": self.meter_wh,
            "timestamp": now(),
            "reason": "Local",
        })

        # Available again
        await self.call("StatusNotification", {
            "connectorId": connector_id,
            "errorCode": "NoError",
            "status": "Available",
            "timestamp": now(),
        })
        print("[SIM] === CHARGING CYCLE DONE ===\n")

    async def call(self, action: str, payload: dict) -> dict:
        mid = msg_id()
        frame = [2, mid, action, payload]
        raw = json.dumps(frame)
        print(f"[SIM] → {action} (id={mid})")
        await self.ws.send(raw)

        # wait for response [3, mid, ...]
        while True:
            resp_raw = await self.ws.recv()
            resp = json.loads(resp_raw)
            if resp[0] == 3 and resp[1] == mid:
                print(f"[SIM] ← RESULT: {json.dumps(resp[2], indent=2)}")
                return resp[2]
            else:
                # got something else (e.g. a command) — handle inline
                print(f"[SIM] ← (other) {resp_raw}")
                if resp[0] == 2:
                    # auto-accept unexpected commands
                    await self._send_result(resp[1], {"status": "Accepted"})

    async def _send_result(self, mid: str, payload: dict):
        frame = [3, mid, payload]
        await self.ws.send(json.dumps(frame))
        print(f"[SIM] → RESULT for {mid}")


async def main():
    cp_id = sys.argv[1] if len(sys.argv) > 1 else "TEST_CP_001"
    base = sys.argv[2] if len(sys.argv) > 2 else "ws://localhost:8000"
    uri = f"{base}/ws/ocpp/{cp_id}"

    sim = StationSimulator(uri)
    await sim.run()


if __name__ == "__main__":
    asyncio.run(main())
