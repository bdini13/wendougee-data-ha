"""Short, explicitly requested control sessions on HA's shared Bluetooth route."""

from homeassistant.core import HomeAssistant

from ._protocol.control_session import (
    Command,
    ControlRejected,
    ControlSession,
    command_request,
    set_boiler,
    start_stored_profile,
)
from ._protocol.controls import BoilerSetting, build_boiler_setting_request
from ._protocol.state import decode_operating_state
from ._protocol.telemetry import parse_telemetry_response
from .bluetooth import HomeAssistantReadTransport

READ_COMMANDS = frozenset({Command.CONFIGURATION, Command.TELEMETRY, Command.STATE})


class HomeAssistantControlTransport(HomeAssistantReadTransport):
    """An explicit finite allowlist, separate from every existing read transport."""

    def __init__(self, hass, address, commands: frozenset[Command]):
        super().__init__(hass, address)
        self._requests = frozenset(command_request(c) for c in commands)

    async def send(self, request: bytes) -> None:
        if request not in self._requests:
            raise ValueError("Request is not enabled for this control transaction")
        if self.client is None or self.modbus is None:
            raise ConnectionError("Transport not ready")
        await self.client.write_gatt_char(
            self.modbus,
            request,
            response="write-without-response" not in self.modbus.properties,
        )


async def execute_boiler(hass: HomeAssistant, address, setting, enabled):
    if setting not in (BoilerSetting.STEAM_ENABLED, BoilerSetting.BREW_ENABLED):
        raise ControlRejected("Only boiler enable settings are supported")
    request = build_boiler_setting_request(setting, enabled)
    write = next(c for c in Command if command_request(c) == request)
    transport = HomeAssistantControlTransport(hass, address, READ_COMMANDS | {write})
    async with ControlSession(transport) as session:
        return await set_boiler(session, setting, enabled)


async def execute_profile(hass: HomeAssistant, address):
    commands = READ_COMMANDS | {
        Command.PROFILE_MODE,
        Command.PROFILE_PRESS,
        Command.PROFILE_RELEASE,
    }
    transport = HomeAssistantControlTransport(hass, address, commands)
    async with ControlSession(transport) as session:
        state = await start_stored_profile(session)
        telemetry = parse_telemetry_response(await session.transact(Command.TELEMETRY))
        return telemetry, state


async def verify_idle(hass: HomeAssistant, address):
    transport = HomeAssistantControlTransport(hass, address, frozenset({Command.STATE}))
    async with ControlSession(transport) as session:
        state = decode_operating_state(await session.transact(Command.STATE))
        if state.state != "idle":
            raise ControlRejected(
                "Machine must report idle before clearing uncertainty"
            )
