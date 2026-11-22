"""End-to-end tests of named inputs (#442): a program declares a few in 'this program's inputs'; Run asks for them in a
form, exported Python takes --input name=value, and --mcp gives each its own typed property."""
from e2e.common import *  # noqa: F401,F403


def inputs_program():
    def inp(name):
        return {"block": {"type": "rb_input", "fields": {"NAME": name}}}
    decls = {"type": "rb_input_def", "fields": {"NAME": "town", "TYPE": "text", "DEFAULT": "Rye"}, "next": {"block":
             {"type": "rb_input_def", "fields": {"NAME": "loaves", "TYPE": "number", "DEFAULT": ""}, "next": {"block":
              {"type": "rb_input_def", "fields": {"NAME": "spelt", "TYPE": "yesno", "DEFAULT": "no"}}}}}}
    join = {"type": "text_join", "extraState": {"itemCount": 5}, "inputs": {"ADD0": inp("town"), "ADD1": tx(": "), "ADD2": inp("loaves"),
            "ADD3": tx(" loaves, spelt "), "ADD4": inp("spelt")}}
    return {"blocks": {"languageVersion": 0, "blocks": [
        {"type": "rb_inputs", "x": 20, "y": 20, "inputs": {"INPUTS": {"block": decls}}},
        {"type": "rb_start", "x": 20, "y": 300, "next": {"block": add({"block": join})}}]}}


async def inputs_tests():
    print("Named inputs")
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        pg = await browser.new_page(viewport={"width": 1400, "height": 1000})
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        await pg.route("**/*", route)
        await pg.add_init_script(MOCK)
        await pg.goto("http://test/")
        await pg.wait_for_timeout(1500)
        await load_state(pg, inputs_program())
        await pg.click("#run")
        await pg.wait_for_selector(".inputs-form", timeout=5000)
        shown = await pg.evaluate("""() => [...document.querySelectorAll('.inputs-form label')].map(l => [l.firstChild.textContent,
            (l.querySelector('input,select') || {}).value, (l.querySelector('input,select') || {}).type])""")
        check(shown == [["town", "Rye", "text"], ["loaves", "", "text"], ["spelt", "no", "select-one"]],
              f"Run asks for the inputs in a form, filled in with the defaults ({shown})")
        await pg.click(".ask button.primary")
        await pg.wait_for_timeout(200)
        msg = await pg.text_content(".ask .msg")
        check(msg == "Input loaves needs a value.", f"an input with no default must be filled in ({msg!r})")
        fields = await pg.query_selector_all(".inputs-form input")
        await fields[1].fill("three")
        await pg.click(".ask button.primary")
        await pg.wait_for_timeout(200)
        msg = await pg.text_content(".ask .msg")
        check(msg == "Input loaves must be a number, not three.", f"a number input takes only a number ({msg!r})")
        await fields[1].fill("3")
        await pg.select_option(".inputs-form select", "yes")
        await pg.click(".ask button.primary")
        for _ in range(60):
            await pg.wait_for_timeout(150)
            if not await pg.is_disabled("#run"):
                break
        items = await pg.eval_on_selector_all(".result-text", "e => e.map(x => x.textContent)")
        check(items == ["Rye: 3 loaves, spelt true"], f"the 'input' blocks give what was filled in, as their kinds ({items})")

        code = await export_python(pg, "bake-inputs")
        check('INPUTS = [("town", "text", "Rye"), ("loaves", "number", ""), ("spelt", "yesno", "no")]' in code
              and ", inputs=INPUTS, can=CAN)" in code and 'R.input("loaves", "number", "")' in code,
              "the export declares INPUTS and passes them to R.main")
        await load_state(pg, script(add(tx("no inputs"))))
        plain = await export_python(pg, "plain")
        check("INPUTS" not in plain.split("# ---- Second Thought program")[0].split("# Your program")[1] and "inputs=" not in plain.split("R.main(")[-1].split(")")[0],
              "a program without inputs exports as before")
        check(not errors, "no page errors with named inputs" + (f": {errors[:2]}" if errors else ""))
        await browser.close()

    with tempfile.TemporaryDirectory() as tmp:
        prog = pathlib.Path(tmp) / "bake-inputs.py"
        prog.write_text(code, encoding="utf-8")
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_ACTIONS"}

        def run(*args, stdin=None):
            return subprocess.run([sys.executable, "-u", str(prog), *args], env=env, cwd=tmp, capture_output=True,
                                  encoding="utf-8", errors="replace", timeout=120, input=stdin)
        r = run("--input", "loaves=2", "--input", "town=Hastings", "--input", "spelt=yes")
        check(r.returncode == 0 and "Hastings: 2 loaves, spelt true" in r.stdout, f"--input gives each input its value ({r.stdout[-200:]!r})")
        r = run("--input", "loaves=2")
        check(r.returncode == 0 and "Rye: 2 loaves, spelt false" in r.stdout, f"the rest take their defaults ({r.stdout[-200:]!r})")
        for args, want in ((), "Input loaves needs a value."), (("--input", "loaves=many"), "Input loaves must be a number, not many."), \
                          (("--input", "loafs=2"), "There's no input called loafs. Its inputs: town, loaves, spelt."), \
                          (("--input", "spelt=maybe", "--input", "loaves=1"), "Input spelt must be yes or no, not maybe."), \
                          (("--input", "loaves"), "--input wants a name and a value, like --input town=Rye."):
            r = run(*args)
            check(r.returncode != 0 and want in r.stderr, f"{' '.join(args) or 'no --input'}: stops, saying {want!r} ({r.stderr.strip()[-160:]!r})")
        calls = "\n".join(json.dumps(m) for m in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "bake-inputs", "arguments": {"loaves": 4, "spelt": True}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "bake-inputs", "arguments": {}}})) + "\n"
        r = run("--mcp", stdin=calls)
        got = {m["id"]: m.get("result", {}) for m in map(json.loads, filter(None, r.stdout.splitlines()))}
        schema = got.get(2, {}).get("tools", [{}])[0].get("inputSchema", {})
        props = schema.get("properties", {})
        check(props.get("loaves") == {"type": "number"} and props.get("spelt") == {"type": "boolean", "default": False}
              and props.get("town") == {"type": "string", "default": "Rye"} and schema.get("required") == ["loaves"] and "value" in props,
              f"--mcp gives each input a typed property, with defaults, and requires the one without ({schema})")
        text = lambda i: (got.get(i, {}).get("content") or [{}])[0].get("text", "")
        check(text(3) == "Rye: 4 loaves, spelt true" and not got[3].get("isError") and got.get(4, {}).get("isError") and text(4) == "Input loaves needs a value.",
              f"an MCP call fills them by name, and one missing a required input is an error ({text(3)!r}; {text(4)!r})")
