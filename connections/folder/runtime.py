    async def _choose_file_live(self):
        if getattr(self, "testing", False):
            f = self._from_test("file", tr("Choose a file"))
            return to_str(f.get("text") if isinstance(f, dict) else f)
        print(tr("\n? Choose a file: type the path to a PDF, a .docx, or a text file (.txt, .md, .csv, .json ...)."), flush=True)
        while True:
            path = (await self._input(tr("Path > "))).strip().strip('"').strip("'")
            if not os.path.isfile(path):
                print(tr("  That file doesn't exist. Try again."))
                continue
            if os.path.getsize(path) > 25 * 1024 * 1024:
                print(tr("  That file is over 25 MB. Choose a smaller one."))
                continue
            try:
                text = read_text_file(path)
            except RunError as e:
                print("  " + str(e))
                continue
            if not text.strip():
                print(tr("  No text could be found in that file. A scanned PDF holds pictures of pages, not text."))
                continue
            self.log(tr("Chose file"), tr("{path} · {x} characters", path=path, x=format(len(text), ',')), tr("chosen"))
            return text

    def _picture_path(self, pic):
        if not pic.path or not os.path.exists(pic.path):
            pic.path = self._save_file(pic)
        return pic.path

    def _save_file(self, pic, data=None, ext=None):
        ext = ext or _EXT.get(pic.media_type, ".png")
        base = re.sub(r"[^\w\-]+", "-", pic.name).strip("-") or "picture"
        path = os.path.join(OUTPUT_DIR, base + ext)
        i = 2
        while os.path.exists(path):
            path = os.path.join(OUTPUT_DIR, f"{base}-{i}{ext}")
            i += 1
        if self._skip_action(f"save {os.path.basename(path)} to {OUTPUT_DIR}"):  # a test or rehearsal saves nothing (#430)
            return path
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(path, "wb") as f:
            f.write(data if data is not None else pic.data)
        return path

    async def choose_file(self):
        return await self._journaled("choose_file", self._key("file"), self._choose_file_live)

    async def choose_picture(self):
        if getattr(self, "testing", False):
            raise RunError(tr("Test cases don't keep pictures, so a test can't choose one. Test this part by running the program."))
        print(tr("\n? Choose a picture: type the path to a JPEG, PNG, WebP, GIF or SVG file."), flush=True)
        while True:
            path = (await self._input(tr("Path > "))).strip().strip('"').strip("'")
            ext = os.path.splitext(path)[1].lower()
            if not os.path.isfile(path):
                print(tr("  That file doesn't exist. Try again."))
                continue
            if ext not in _MEDIA:
                print(tr("  That isn't a JPEG, PNG, WebP, GIF or SVG file."))
                continue
            with open(path, "rb") as f:
                data = f.read()
            name = os.path.splitext(os.path.basename(path))[0]
            if ext == ".svg":
                svg = clean_svg(data.decode("utf-8", "replace"))
                if not svg:
                    print(tr("  That SVG file couldn't be read."))
                    continue
                pic = Picture(svg.encode("utf-8"), "image/svg+xml", name, svg)
            else:
                pic = Picture(data, _MEDIA[ext], name)
            pic.path = path
            self.log(tr("Chose picture"), path, tr("chosen"))
            return pic

    async def save_file(self, value, name, ext):
        if isinstance(value, Picture):
            raise RunError(tr("To save a picture, use the 'save picture' block."))
        if ext == "json" and not isinstance(value, str):
            text = json.dumps(value, default=str, indent=2, ensure_ascii=False)
        elif ext == "csv" and isinstance(value, list):
            text = "\n".join(",".join('"' + to_str(c).replace('"', '""') + '"' for c in r) if isinstance(r, list) else to_str(r) for r in value)
        else:
            text = to_str(value)
        if not text:
            raise RunError(tr("There's nothing to save: the value in the 'save as file' block is empty."))
        base = re.sub(r"[^\w\-]+", "-", to_str(name)).strip("-") or "output"
        path = os.path.join(OUTPUT_DIR, f"{base}.{ext}")
        if not await self._allowed(["files"], f"save {path} ({len(text):,} characters)"):
            return
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.log(tr("Save file"), tr("Saved {path}", path=path), tr("saved"))

    async def save_picture(self, pic, fmt):
        pic = _need_picture(pic, "save picture")
        if not await self._allowed(["files"], f"save the picture {pic.name}"):
            return
        if fmt == "svg":
            if pic.svg is None:
                raise RunError(tr("Only drawn pictures can be saved as SVG. Choose PNG instead."))
            path = self._save_file(pic, pic.svg.encode("utf-8"), ".svg")
        elif fmt == "png" and pic.media_type != "image/png":
            if pic.svg is not None:
                try:
                    import cairosvg  # optional: pip install cairosvg
                    path = self._save_file(pic, cairosvg.svg2png(bytestring=pic.svg.encode("utf-8")), ".png")
                except ImportError:
                    path = self._save_file(pic, pic.svg.encode("utf-8"), ".svg")
                    self.log(tr("Save picture"), tr("PNG needs the cairosvg package (pip install cairosvg), so it was saved as SVG."), tr("note"))
            else:
                path = self._save_file(pic)
        else:
            path = self._save_file(pic)
        self.log(tr("Save picture"), tr("Saved {path}", path=path), tr("saved"))

    # ----- Draft and Review -----

    @staticmethod
    def _folder_path(d):
        """A folder from a block: a full path, ~/…, or a folder next to the program ("inbox" if empty)."""
        d = os.path.expanduser(to_str(d).strip() or "inbox")
        return d if os.path.isabs(d) else os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), d)

    @staticmethod
    def _folder_file(path, size):
        """What a new file in a watched folder gives: its name, path and size, the words in it (PDF, Word or text),
        and for a picture (PNG, JPEG, WebP or GIF, up to 20 MB), the picture itself, for the picture blocks."""
        name = os.path.basename(path)
        try:
            text = read_text_file(path)[:100000] if size <= 25 * 1024 * 1024 else ""
        except Exception:  # noqa: BLE001 - a picture or other file: no text, but the script still runs
            text = ""
        rec = {"name": name, "path": path, "size": size, "text": text}
        media = _MEDIA.get(os.path.splitext(name)[1].lower())
        if media and media != "image/svg+xml" and size <= 20 * 1024 * 1024:
            with open(path, "rb") as f:
                rec["picture"] = Picture(f.read(), media, os.path.splitext(name)[0])
        return rec

    async def folder_files(self, folder, match=""):
        """The files in a folder, newest first, as records: name, path, modified (YYYY-MM-DD HH:MM) and size. match is a
        pattern like *.pdf (every file if empty). Only looks: it doesn't read the files."""
        d, match = self._folder_path(folder), to_str(match).strip() or "*"
        if not os.path.isdir(d):
            raise RunError(tr("There's no folder {folder}.", folder=d))
        rows = []
        for n in os.listdir(d):
            path = os.path.join(d, n)
            if n.startswith((".", "~")) or not os.path.isfile(path) or not fnmatch.fnmatch(n.lower(), match.lower()):
                continue
            st = os.stat(path)
            rows.append({"name": n, "path": path, "modified": datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                         "size": st.st_size})
        return sorted(rows, key=lambda r: r["modified"], reverse=True)[:500]

    async def _listen_folder(self, items):
        folders = []
        for d, fn in items:
            d = self._folder_path(d)
            os.makedirs(d, exist_ok=True)
            folders.append((d, fn))
        known, waiting = {d: set(os.listdir(d)) for d, _ in folders}, {}
        print(tr("Watching for new files in {x}.", x=", ".join(d for d, _ in folders)), flush=True)
        while True:
            await asyncio.sleep(self._poll(5))
            for d, fn in folders:
                try:
                    names = set(os.listdir(d))
                except OSError:
                    continue
                for n in sorted(names - known[d]):
                    path = os.path.join(d, n)
                    if n.startswith((".", "~")) or n.endswith((".tmp", ".part", ".crdownload")) or not os.path.isfile(path):
                        continue
                    size = os.path.getsize(path)
                    if waiting.get(path) != size:  # still being written: wait until its size stops changing
                        waiting[path] = size
                        continue
                    waiting.pop(path, None)
                    known[d].add(n)
                    self._fire(fn, self._folder_file(path, size), tr("New file: {name}", name=n))
                known[d] &= names
