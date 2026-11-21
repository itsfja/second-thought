        if has("files_save"):
            async def outputs():
                here = os.path.abspath(OUTPUT_DIR)
                where = here if os.path.isdir(here) else os.path.dirname(here)
                if not os.access(where, os.W_OK):
                    raise RunError(tr("files can't be saved: {where} can't be written to", where=where))
                return tr("files will be saved in {here}", here=here)
            out.append(("Saving files", outputs))
