# Second Thought

A Scratch-style block editor for AI workflows. You snap steps together (write a draft, have Claude review it, revise until it passes) and press Run. The name comes from the idea at its heart: Claude has a second thought about its own work before the result goes out.

It runs as a single web page published as a claude.ai artifact, using the viewer's own Claude account. Any program can also be exported as plain Python that runs on its own machine or server, unattended if you like.

## What it can do

- **Scratch's core:** events, control (repeat, if/else, for each, wait until), operators, text, variables, lists, and My Blocks (your own reusable blocks, with return values).
- **AI blocks:** write, rework and revise a draft; ask Claude for text, yes/no, numbers, lists or structured records; review against criteria in a loop; score and pick the better of two.
- **Conversations:** standing instructions for Claude, and named multi-turn chats.
- **People in the loop:** ask me and wait, approve or send back, choose from a list, pause until Continue.
- **Parallel scripts:** several scripts run at once; broadcasts (optionally carrying a value) start listening scripts.
- **Time:** schedules ("when it's 09:00 on weekdays", "every 30 minutes"), waits, timer and clock.
- **Pictures:** pick a photo and ask Claude about it or score it; Claude draws SVG illustrations and can redraw them from its own critique.
- **Files:** read PDFs, Word .docx and text files; save results as .md, .txt, .csv, .json or .html.
- **Memory:** values kept while the page is open, forever, or for a set time, saved privately to the viewer's account.
- **Reliability:** try / if it fails, and retries with backoff for temporary failures.
- **Tools for building:** a live watch panel, step mode, right-click "Run this script", block search, saved programs and a prompt library.
- **Python export and import:** export runs the same program from the command line; importing exported code restores the blocks exactly, and Claude can convert other code into blocks.

## Repository layout

| Path | What it is |
|---|---|
| `second-thought.html` | The page, exactly as published. Self-contained apart from Blockly (and pdf.js on demand) from a CDN. |
| `python/runtime.py` | The runtime that every exported Python program includes. Embedded in the page. |
| `prompts/convert-guide.txt` | The instructions Claude gets when converting other code into blocks. Embedded in the page. |
| `tools/sync.py` | Copies the two files above into the page. |
| `tests/` | Headless-browser and exported-Python tests, with stand-ins for Claude and the Anthropic SDK. |

## Making changes

1. Edit `second-thought.html`, `python/runtime.py` or `prompts/convert-guide.txt`.
2. If you changed either of the last two, run `python tools/sync.py` to embed them in the page.
3. Run the tests:

   ```
   bash tests/setup.sh          # once: browser and offline copies of the CDN libraries
   python tests/run_tests.py
   ```

   The tests run every example in the page, check block search, export every example to Python, import one back, and run all the exported programs. They never call the real API.
4. Publish the page as a claude.ai artifact. It declares these capabilities: `sample` (Claude calls), `downloads`, `db` and `user` (memory, saved programs and the prompt library).

## Running an exported program

```
pip install anthropic          # plus pypdf for PDFs, cairosvg for PNG pictures (both optional)
export ANTHROPIC_API_KEY=your-key
python my-program.py              # runs the "when Run is clicked" scripts
python my-program.py --schedule   # keeps running and fires the scheduled scripts
```

Exported programs use the Anthropic API, billed to your API account rather than a claude.ai plan. They print a token total at the end of each run. Memory goes in `memory.json` and saved files in `outputs/`, next to the program.

## Notes

- **Internal storage names:** keys and the block-file format still say `reflection-blocks`, the project's working name, so saved programs and exported files from before the rename keep working.
- **Web search:** the "search the web" block only searches the live web in exported Python. Inside the page Claude can't browse, so it answers from its own knowledge and the log says so.
- **Schedules:** inside the page, schedules only run while the page is open. Use the Python export for unattended jobs.
