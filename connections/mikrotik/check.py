        if has("mikrotik_read"):
            async def mikrotik():
                return await self._doctor_mikrotik()
            out.append(("MikroTik", mikrotik))
