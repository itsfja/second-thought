        if has("homey_read", "homey_act"):
            async def homey():
                home = await self._homey_home()
                return tr("reached: {home} devices", home=len(home))
            out.append(("Homey", homey))
