# Community gallery

Programs people have shared. Each file here appears on the page in a **Community** group, by its category (Community: news, Community: home and baking and so on), in both the Example menu and **Browse examples**, with who shared it,
what it does, and what it can do, which the page works out from its blocks.

## Sharing a program

1. **Make it on the page and save it.** Open **Import / export**, give it a name and press **Save .json file** (or
   **Copy as text** and paste it into a new `.json` file). That's a block file.
2. **Add a `"gallery"` part** at the top level of that file, next to `"program"`:

   ```json
   {
     "format": "reflection-blocks",
     "version": 1,
     "name": "bake-day-timeline",
     "gallery": {
       "title": "Bake-day timeline",
       "category": "home",
       "description": "Say when you want the bread out of the oven, and Claude works backwards to a timeline.",
       "tip": "Change the recipe in the blue block to your own.",
       "author": "your GitHub name",
       "runtime": "2.0.0"
     },
     "program": { "...": "as the page saved it" }
   }
   ```

   | Field | What to put |
   |---|---|
   | `title` | A short name, up to 40 characters. |
   | `category` | Where it's grouped on the page: `github`, `coding`, `news`, `money`, `calendar` (calendar and email), `home` (home and baking) or `odds` (odds and ends, if you leave it out). |
   | `description` | What it does, in a sentence or two, up to 300 characters. |
   | `tip` | One thing to try or change first, up to 200 characters. |
   | `author` | Your name or GitHub name, up to 40 characters. |
   | `runtime` | The runtime you made it with: the Import / export panel says which (for example `2.0.0`). |

   Don't list what the program can do (send email, control devices and so on). The page works that out from the
   blocks and shows it on the card, so it can't be wrong.
3. **Name the file** in lowercase words joined by `-`, such as `bake-day-timeline.json`, and put it in this folder.
   Some programs here are written as Python in `tools/gallery_build.py` instead, so their blocks can be reviewed as code.
   To change one of those, edit it there and run `python tools/gallery_build.py`; the tests check the two match.
4. **Run `python tools/sync.py`**, which copies the gallery into `second-thought.html`, and open a pull request with
   both files. If you don't use git, open an issue with the block file attached and the `"gallery"` part filled in.

## What's checked

The tests run on every pull request:

- **The file** (`tests/unit/test_gallery.py`): it's a block file with every `"gallery"` field filled in and short
  enough, made with this runtime or an older one, with a title no other entry has. It doesn't say what it can do. It
  doesn't run another saved program (whoever loads it won't have that one). It carries nothing that looks like a key,
  token or password, and no real email address (use `you@example.com`).
- **The program** (`tests/run_tests.py`): it loads on the page with no unknown blocks, runs to the end against the
  test stand-ins, exports to Python, and the exported program runs too.

Then a person reads it. Things to look at: does it do what the description says, and is what it can do (shown on its
card) what you'd expect from that description? A program that sends messages or controls devices should say so in
its description.

When someone loads a shared program on the page, they see what it can do first. Exported to Python, a program that
acts asks before its first run.
