from .base import SimpleService


class UPSService(SimpleService):
    name = "ups"
    etc = ["ups"]
    systemd_unit = "nut-monitor"

    async def systemd_extra_units(self):
        return ["nut-server"] if (await self.middleware.call("ups.config"))["mode"] == "MASTER" else []

    async def before_start(self):
        await self.middleware.call("ups.dismiss_alerts")

    async def start(self):
        if (await self.middleware.call("ups.config"))["mode"] == "MASTER":
            await self._systemd_unit("nut-server", "start")
        await self._unit_action("Start")

    async def before_stop(self):
        await self.middleware.call("ups.dismiss_alerts")

    async def stop(self):
        await self._unit_action("Stop")
        await self._systemd_unit("nut-server", "stop")
