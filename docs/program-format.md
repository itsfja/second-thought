# The program format

[← Second Thought](../README.md) · [Using the page](using-the-page.md) · [The agent](agent.md) · [Connections](connections.md) · [MCP tools](mcp.md) · [Running exported programs](running.md) · **Program format** · [Settings and models](settings.md)

*A program saved as a file: one format, stated once, so anything that reads one — the page, `--doctor`, a script of your own — knows what it holds.*

## What the format is for

A Second Thought program is blocks. When you save one — **Import / export → Save blocks**, or as the block file inside an exported Python program — it becomes one JSON document in the **reflection-blocks** format, version 1. The page imports it again from either place, and `--doctor` checks an exported program against this page before it runs.

The blocks themselves are a tree, the shape Blockly saves: each block has a type, fields, inputs and a next. What each type *means* lives with the blocks' definitions in `web/editor/02-blocks.js`, and the words for each language in `i18n/`; this page says only the shape every block file shares, whatever the types.

## The grammar

```
file        = '{' format ',' version ',' name ',' [ exported ',' ] program [ ',' tests ] [ ',' gallery ] '}' ;
format      = '"format": "reflection-blocks"' ;
version     = '"version": 1' ;
name        = '"name": ' string ;                       a non-empty string
exported    = '"exported": ' string ;                   when it was saved, like "2026-11-08T09:00:00.000Z"
program     = '"program": ' program-part ;
program-part = '{' '"blocks":' block-list [ ',' '"languageVersion":' number ] '}' ;
block-list  = '"blocks":' '[' [ block-tree ] * ']'
block-tree  = block [ ',' block-tree ] ;               usually one top block, its followers under next
block       = '{' '"type":' string                      which block it is, like "rb_agent"
                  [ ',' '"fields":' fields ]
                  [ ',' '"inputs":' inputs ]
                  [ ',' '"next":' connection ]
                  [ ',' '"x":' number ',' '"y":' number ] '}' ;
fields      = '"fields":' '{' [ field ] * '}' ;
field       = string ':' field-value ;                 a string, number, true/false, null (an empty text block), or a variable reference {"id": "g_name"}
inputs      = '"inputs":' '{' [ input ] * '}' ;
input       = string ':' connection ;                    the name of the input slot, like "GOAL"
connection  = '{' [ '"block":' block ] [ ',' '"shadow":' block ] '}' ;   at least one of the two
tests       = '"tests":' '[' [ test ] * ']' ;
test        = '{' '"name":' string ',' '"value":' string ',' '"inputs":' object ',' '"criteria":' string '}' ;
gallery     = '"gallery":' object ;                     a community gallery program's title, description, tip, author and runtime
```

Read it as: a file is an object holding the format name and version, the program's name, the program part, and optionally its test cases and its gallery entry. The program part holds the block tree. A block names its type; its fields are plain values; its inputs are connections to other blocks, each either a full block or a shadow (the faded default behind it); `next` is the block below it in the same script.

Two promises keep the format workable:

- **Unknown keys are ignored.** A program saved by a newer page may carry keys this page doesn't name; anything that reads the file skips what it doesn't know, so newer files still open.
- **Shape is checked, not meaning.** The grammar says what a block *looks like*, not whether `rb_agent` may sit inside `rb_if`. Those rules live with the blocks' definitions, and the page enforces them while you edit.

## Where the format lives

- **A block file** (`.json`, from **Save blocks**) is the grammar's `file` as it stands.
- **An exported Python program** carries the same `file` as base64 text under the line `# ---- Second Thought program: lets the block editor import this file again ----`, after `# BLOCKS:` — one comment line per 76 characters. That's how **Change this program** gets your blocks back, and how `--doctor` checks the structure:

```
$ python my-program.py --doctor
  ok    Program: the block file inside this program matches the format, so the page can import it again
```

  A file the grammar rejects is a `FAIL`, because the page may not be able to import the program again; an exported program from an older page, with no block file embedded, is a `NOTE`.
- **The community gallery** (`gallery/*.json`) is the same `file` with a `gallery` part.

## Checking a file yourself

The check `--doctor` makes is `_grammar_problems` in `python/second_thought/doctor.py`: give it the parsed JSON of a block file and it returns where the file breaks the grammar, an empty list when it matches. It only reads — nothing is sent, posted or run.
