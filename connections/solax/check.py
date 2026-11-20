        if has("solax_read"):
            async def solax():
                got = await self.solax_now()  # one call: the figures are cached for five minutes after it
                return tr("reached SolaxCloud: {status}, figures from {time}", status=got.get("status") or "?", time=got.get("upload_time") or "?")
            out.append(("Solax", solax))
