# Second Thought

### A Ladybird-style book about a clever helper

---

## Page 1: Hello

*Picture: a child at a table with a computer. A friendly ladybird sits on the screen.*

This is a computer.

A computer is a machine that follows instructions.

An instruction is a thing you ask someone to do. "Please shut the door" is an instruction.

The computer can follow lots of instructions, one after another, very fast.

This book is about a program called **Second Thought**.

A program is a list of instructions for a computer.

---

## Page 2: Meet Claude

*Picture: a speech bubble coming out of the computer, saying "How can I help?"*

This is Claude.

Claude lives inside the computer. Claude can read and write.

You can ask Claude to write a story, answer a question, or explain something hard in an easy way.

Claude is very helpful. But Claude is not perfect. Sometimes Claude makes mistakes, just like people do.

---

## Page 3: Having a second thought

*Picture: a child writing in an exercise book, then crossing something out and writing it again, neater.*

When you write a story at school, you write it once.

Then you read it again. You spot a spelling mistake. You see a part that is muddled. You fix them.

Now the story is better.

Reading your work again and making it better is called **having a second thought**.

Second Thought helps Claude do the same thing. Claude writes something. Then Claude checks it. Then Claude makes it better.

---

## Page 4: Building blocks

*Picture: bright, coloured blocks that click together like toy bricks. Each block has words on it.*

In Second Thought, you do not need to type long instructions.

Instead, you use **blocks**.

Each block is one instruction. One block says "write a first draft". Another block says "check the draft". Another says "make it better".

You pick up a block with the mouse and drag it to the big space on the screen. You click the blocks together, one under another, like building a tower.

The computer follows the blocks from top to bottom.

If you have used Scratch at school, this will feel familiar. It is very like Scratch.

---

## Page 5: The colours

*Picture: a box of blocks sorted into coloured piles.*

The blocks come in different colours. Blocks of the same colour do the same sort of job.

- **Yellow blocks** start things. The yellow block "when Run is clicked" always goes at the very top.
- **Orange blocks** repeat things, or choose between things.
- **Blue blocks** ask Claude to write.
- **Purple blocks** ask Claude to check the writing.
- **Teal blocks** ask *you* a question and wait for your answer.
- **Green blocks** show the result at the end.

There are more colours too. You will find them all down the left side of the screen.

---

## Page 6: Pressing Run

*Picture: a big blue button with the word "Run" on it, and a finger about to press it.*

When your blocks are ready, press the blue **Run** button.

On the right-hand side of the screen there is a list called the **run log**. A log is a diary of what happened.

Each time a block does its job, a new line appears in the run log. You can watch Claude working, step by step.

At the end, a green box shows the **result**. The result is what your program made.

If something goes wrong, press **Stop**. Everything will stop straight away.

---

## Page 7: Things Second Thought can do

*Picture: a ladybird holding a long scroll, with a list written on it.*

Second Thought can do many things. Here are some of them.

- It can ask Claude to write, then check, then try again until the writing is good.
- It can ask you questions and wait for your answer.
- It can look at a picture you give it and tell you about it.
- It can draw simple pictures, like a cartoon loaf of bread.
- It can read a document, such as a PDF or a Word file, and tell you what is in it.
- It can save its work as a file, so you can keep it.
- It can **remember** things for next time, like a notebook it keeps in a drawer.
- It can do several jobs at the same time.
- It can wait until a certain time of day, and then start a job by itself.
- If something goes wrong, it can try again.

---

## Page 8: Examples to try

*Picture: a shelf of little books, each with a different title.*

You do not have to start from nothing.

At the top of the screen there is a box called **Example**. Choose an example, then press **Load**. Now press **Run** and watch what happens.

Try the example called **Review loop** first. Claude writes about bread, checks its own work, and makes it better.

Then try your own ideas. Change the words on the blocks. Add new blocks. See what happens.

You cannot break anything. If you get in a muddle, just load an example again.

---

## Page 9: Saving your programs

*Picture: a child putting a drawing carefully into a folder.*

When you make a program you like, you will want to keep it.

Press the **Programs** button at the top of the screen. Type a name for your program and press **Save**.

Next time, open the same box and press **Open** to get your program back.

You can also keep a copy as a file on your computer. Press **Import / export** to do that.

---

## Page 10: Making a program run on its own

*Picture: a small computer in a cupboard, quietly working while everyone is asleep.*

Second Thought can turn your blocks into **Python**.

Python is a language that computers understand. It is written with words and symbols instead of blocks.

Once your program is in Python, it can run on another computer by itself, even when the Second Thought page is closed.

This part needs a grown-up, because the Python program needs a special key to talk to Claude. The key is a bit like a library card. It tells Claude who is asking, and it costs a little money each time it is used.

**Grown-ups, here is how:**

```
pip install anthropic
export ANTHROPIC_API_KEY=your-key
python my-program.py
```

The first line installs the part that lets Python talk to Claude. The second line gives Python the key. The third line runs the program.

To keep a program running so its timed jobs start by themselves, add `--schedule` to the end of the third line.

---

## Page 11: What is in this folder

*Picture: an open toy box with labelled compartments.*

This folder is where all the parts of Second Thought are kept. Each part has its own place.

| Name | What it is |
|---|---|
| `second-thought.html` | The Second Thought page itself. This is the part you see on the screen. |
| `python/runtime.py` | The helper that comes with every Python program. It knows how to do each block's job. |
| `prompts/convert-guide.txt` | The instructions Claude reads when it turns Python back into blocks. |
| `tools/sync.py` | A little tool that copies the two parts above into the page, so they always match. |
| `tests/` | Checks that make sure everything still works. |
| `README.md` | This book! |

---

## Page 12: Checking it still works

*Picture: a doctor with a stethoscope, listening to a computer.*

When somebody changes Second Thought, they must check it still works.

The `tests` folder does this. It pretends to be Claude, so the checks do not cost anything. Then it tries every example, one by one, and makes sure each one finishes properly.

**Grown-ups, here is how:**

```
bash tests/setup.sh
python tests/run_tests.py
```

You only need the first line once. It fetches the things the checks need.

The second line runs the checks. At the end it says **All checks passed**, or it tells you which check went wrong.

If you change `python/runtime.py` or `prompts/convert-guide.txt`, run `python tools/sync.py` first, so the page has your changes too.

---

## Page 13: A few things to know

*Picture: a ladybird holding up one finger, as if to say "Remember this".*

- Second Thought keeps its secrets safe. Things it remembers are only seen by you.
- Inside the page, Claude cannot look things up on the internet. A Python program can.
- Timed jobs on the page only work while the page is open. For jobs that run while you sleep, use Python.
- Some hidden names inside the page still say `reflection-blocks`. That was Second Thought's name when it was very young. They stay the same so that old saved programs still work.

---

## The end

*Picture: the ladybird flying away over a field, towards the sunset.*

Now you know all about Second Thought.

Have fun building. And remember: a second thought is often a better one.
