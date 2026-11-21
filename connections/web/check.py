        if has("webhook"):
            async def hook():
                if not os.environ.get("WEBHOOK_SECRET", "").strip():
                    raise RunError(tr("no WEBHOOK_SECRET {where_keys}, so the program won't listen for web requests. Set it to a long password.", where_keys=WHERE_KEYS))
                host, port = webhook_host(), int(os.environ.get("WEBHOOK_PORT") or 8765)
                with socket.socket() as so:
                    try:
                        so.bind((host, port))
                    except OSError as e:
                        raise RunError(tr("port {port} can't be used ({e}): something else may be listening. Change WEBHOOK_PORT.", port=port, e=_short(e, 80))) from None
                return tr("port {port} is free, and WEBHOOK_SECRET is set", port=port)
            out.append(("Web requests", hook))
        for name in mcp:
            async def server(name=name):
                key = mcp_env_name(name)
                command = os.environ.get(key, "").strip() or self.__dict__.get("_mcp_defaults", {}).get(key, "")
                if re.search(r"(^|\s)--allow-dangerous\b", command):
                    raise RunError(tr("{key} starts the server with --allow-dangerous, which turns off its own check before tools that move money. Take it out.", key=key))
                if re.match(r"^\s*kraken(\.exe)?\s", command) and not shutil.which("kraken"):
                    raise RunError(tr("kraken-cli isn't installed, so Kraken's tools can't start. Install it: https://docs.kraken.com/home/mcp"))
                fr24 = mcp_is_fr24(name, command)
                vaillant = mcp_is_vaillant(name, command)
                if fr24 and not shutil.which("npx"):
                    raise RunError(tr("Node.js isn't installed, so Flightradar24's tools can't start (they come from npx). Install it: https://nodejs.org"))
                if fr24 and not os.environ.get("FR24_API_KEY", "").strip():
                    raise RunError(tr("Flightradar24 needs a key: set FR24_API_KEY in second-thought.ini, next to this program (a paid subscription, from https://fr24api.flightradar24.com)"))
                tools = await self.mcp_tools(name)
                text = tr("{tools} tools, MCP {version}", tools=len(tools), version=self._mcp(name).version)
                twak = mcp_is_twak(name, command)  # its tools carry no marks, so its own safe list says which only look (#320)
                changes = sum(1 for t in tools if not (isinstance(t.get("annotations"), dict) and t["annotations"].get("readOnlyHint") is True)
                              and not (twak and t.get("name") in SAFETY["mcp_twak_safe"])
                              and not (fr24 and t.get("name") in SAFETY["mcp_fr24_safe"])
                              and not (vaillant and t.get("name") in SAFETY["mcp_vaillant_safe"]))
                if changes:  # worth knowing: GitHub's server, say, started without --read-only (#333)
                    text += " · " + tr("{n} of them can change things", n=changes)
                names = {to_str(t.get("name")) for t in tools}
                if key == "MCP_KRAKEN" and os.environ.get("KRAKEN_API_KEY") and names & {"kraken_auth_test", "kraken_balance"}:
                    # The key, checked with a read-only call; what it reads isn't shown.
                    reply, failed = await self.mcp_call(name, "kraken_auth_test" if "kraken_auth_test" in names else "kraken_balance", {})
                    if failed:
                        raise RunError(tr("Kraken refused KRAKEN_API_KEY: {problem}", problem=_short(reply, 160)))
                    text += " · " + tr("your Kraken key works")
                if fr24:  # each call costs credits, so the key is only checked for being there, not by spending one
                    text += " · " + tr("your FR24_API_KEY is set (each call costs credits, so it isn't checked here)")
                return text
            out.append((f"MCP server “{name}”", server))
