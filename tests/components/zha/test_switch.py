"""Test ZHA switch."""

from collections.abc import Callable, Coroutine
from datetime import timedelta
from unittest.mock import call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from zigpy.device import Device
from zigpy.profiles import zha
from zigpy.typing import UNDEFINED
from zigpy.zcl.clusters import general
import zigpy.zcl.foundation as zcl_f

from homeassistant.components.homeassistant import (
    DOMAIN as HOMEASSISTANT_DOMAIN,
    SERVICE_UPDATE_ENTITY,
)
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zha.entity import COMMAND_CONTEXT_EXPIRY_SECONDS
from homeassistant.components.zha.helpers import (
    ZHADeviceProxy,
    ZHAGatewayProxy,
    get_zha_gateway,
    get_zha_gateway_proxy,
)
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_component import DATA_INSTANCES, EntityComponent
from homeassistant.setup import async_setup_component

from .common import find_entity_id, send_attributes_report
from .conftest import SIG_EP_INPUT, SIG_EP_OUTPUT, SIG_EP_PROFILE, SIG_EP_TYPE

ON = 1
OFF = 0


async def _setup_switch(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> tuple[str, general.OnOff]:
    """Set up a single on/off switch and return its entity id and cluster."""
    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.OnOff.cluster_id,
                    general.Groups.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    assert entity_id is not None
    return entity_id, zigpy_device.endpoints[1].on_off


def _set_entity_context(hass: HomeAssistant, entity_id: str, context: Context) -> None:
    """Stamp a context on the entity, as helpers.service does for a command."""
    component: EntityComponent[Entity] = hass.data[DATA_INSTANCES][SWITCH_DOMAIN]
    entity = component.get_entity(entity_id)
    assert entity is not None
    entity.async_set_context(context)


@pytest.fixture(autouse=True)
def switch_platform_only():
    """Only set up the switch and required base platforms to speed up tests."""
    with patch(
        "homeassistant.components.zha.PLATFORMS",
        (
            Platform.DEVICE_TRACKER,
            Platform.SENSOR,
            Platform.SELECT,
            Platform.SWITCH,
        ),
    ):
        yield


async def test_switch(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """Test ZHA switch platform."""

    await setup_zha()
    gateway = get_zha_gateway(hass)
    gateway_proxy: ZHAGatewayProxy = get_zha_gateway_proxy(hass)

    zigpy_device = zigpy_device_mock(
        {
            1: {
                SIG_EP_INPUT: [
                    general.Basic.cluster_id,
                    general.OnOff.cluster_id,
                    general.Groups.cluster_id,
                ],
                SIG_EP_OUTPUT: [],
                SIG_EP_TYPE: zha.DeviceType.ON_OFF_SWITCH,
                SIG_EP_PROFILE: zha.PROFILE_ID,
            }
        },
        ieee="01:2d:6f:00:0a:90:69:e8",
        node_descriptor=b"\x02@\x8c\x02\x10RR\x00\x00\x00R\x00\x00",
    )

    gateway.get_or_create_device(zigpy_device)
    await gateway.async_device_initialized(zigpy_device)
    await hass.async_block_till_done(wait_background_tasks=True)

    zha_device_proxy: ZHADeviceProxy = gateway_proxy.get_device_proxy(zigpy_device.ieee)
    entity_id = find_entity_id(Platform.SWITCH, zha_device_proxy, hass)
    cluster = zigpy_device.endpoints[1].on_off
    assert entity_id is not None

    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on at switch
    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: ON}
    )
    assert hass.states.get(entity_id).state == STATE_ON

    # turn off at switch
    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: OFF}
    )
    assert hass.states.get(entity_id).state == STATE_OFF

    # turn on from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x00, zcl_f.Status.SUCCESS],
    ):
        # turn on via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False,
            ON,
            cluster.commands_by_name["on"].schema,
            expect_reply=True,
            manufacturer=None,
        )
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_ON

    # turn off from HA
    with patch(
        "zigpy.zcl.Cluster.request",
        return_value=[0x01, zcl_f.Status.SUCCESS],
    ):
        # turn off via UI
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {"entity_id": entity_id}, blocking=True
        )
        assert len(cluster.request.mock_calls) == 1
        assert cluster.request.call_args == call(
            False,
            OFF,
            cluster.commands_by_name["off"].schema,
            expect_reply=True,
            manufacturer=None,
        )
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_OFF

    await async_setup_component(hass, HOMEASSISTANT_DOMAIN, {})

    cluster.read_attributes.reset_mock()
    await hass.services.async_call(
        HOMEASSISTANT_DOMAIN,
        SERVICE_UPDATE_ENTITY,
        {"entity_id": entity_id},
        blocking=True,
    )
    assert len(cluster.read_attributes.mock_calls) == 1
    assert cluster.read_attributes.call_args == call(
        ["on_off"], allow_cache=False, only_cache=False, manufacturer=UNDEFINED
    )


@pytest.mark.parametrize(
    ("delay", "expected_user_id"),
    [
        pytest.param(6, "user123", id="within_window_keeps_attribution"),
        pytest.param(
            COMMAND_CONTEXT_EXPIRY_SECONDS + 10, None, id="past_window_drops_context"
        ),
    ],
)
async def test_command_context_survives_delayed_report(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
    freezer: FrozenDateTimeFactory,
    delay: int,
    expected_user_id: str | None,
) -> None:
    """A slow device report keeps user attribution within the command window.

    The context is stamped before the command (as helpers.service does) but the
    device only reports the new state ``delay`` seconds later, past core's 5s
    recent-context window.
    """
    entity_id, cluster = await _setup_switch(hass, setup_zha, zigpy_device_mock)
    assert hass.states.get(entity_id).state == STATE_OFF

    _set_entity_context(hass, entity_id, Context(user_id="user123"))

    freezer.tick(timedelta(seconds=delay))
    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: ON}
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.context.user_id == expected_user_id


async def test_device_initiated_change_not_attributed_after_command(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A device-initiated change after the confirmed command is not attributed.

    Once the commanded transition has been attributed, the captured context is
    consumed, so a later physical toggle within the window stays unattributed.
    """
    entity_id, cluster = await _setup_switch(hass, setup_zha, zigpy_device_mock)

    _set_entity_context(hass, entity_id, Context(user_id="user123"))

    freezer.tick(timedelta(seconds=3))
    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: ON}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.context.user_id == "user123"

    freezer.tick(timedelta(seconds=3))
    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: OFF}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF
    assert state.context.user_id is None


async def test_device_initiated_change_without_command_not_attributed(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
) -> None:
    """A report with no preceding command carries no user context."""
    entity_id, cluster = await _setup_switch(hass, setup_zha, zigpy_device_mock)

    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: ON}
    )
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.context.user_id is None


async def test_command_context_last_writer_wins(
    hass: HomeAssistant,
    setup_zha: Callable[..., Coroutine[None]],
    zigpy_device_mock: Callable[..., Device],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Two quick commands attribute the confirming report to the latest user."""
    entity_id, cluster = await _setup_switch(hass, setup_zha, zigpy_device_mock)

    _set_entity_context(hass, entity_id, Context(user_id="user_a"))
    _set_entity_context(hass, entity_id, Context(user_id="user_b"))

    freezer.tick(timedelta(seconds=4))
    await send_attributes_report(
        hass, cluster, {general.OnOff.AttributeDefs.on_off.id: ON}
    )

    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.context.user_id == "user_b"
