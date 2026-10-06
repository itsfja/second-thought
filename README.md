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
- It can ask **Gemini** to help too. Gemini is another clever helper, made by a company called Google. Claude can write something, and Gemini can check it. Two helpers spot more mistakes than one.
- It can ask **Llama**, a helper that can live on your own computer and keep everything private.
- It can ask **DeepSeek** and **Grok** too. Grok is made by a company called xAI.
- It can ask **GPT**, the helper made by **OpenAI**. Lots of people know it from ChatGPT.
- It can ask helpers from all round the world: **Mistral** from France, **Qwen** from Alibaba and **Kimi** from Moonshot.
- It can ask **Perplexity**, a helper that looks things up on the internet every time, and tells you where it found them.
- It can ask open helpers from **Hugging Face**, super-speedy ones from **Groq**, and **GLM** and **MiniMax** too.
- With **OpenRouter**, it can ask almost *any* helper in the world, using just one key.

---

## Page 8: Examples to try

*Picture: a shelf of little books, each with a different title.*

You do not have to start from nothing.

At the top of the screen there is a box called **Example**. Choose an example, then press **Load**. Now press **Run** and watch what happens.

There are nearly fifty examples, sorted into groups: **Writing, Research, Design, Learning, Work, Home and baking, Code and data,** and **Automation**. Press **Browse examples** to see them all, with a sentence about each one and an idea for something to change.

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

If your program uses Gemini, it needs a second key, from Google, and one more part to install:

```
pip install google-genai
export GEMINI_API_KEY=your-gemini-key
```

There is a third helper too, called **Llama**. Llama is special because it can live on *your own computer*, so nothing you ask it ever leaves the house. To use it, install a free program called **Ollama** and download a Llama model:

```
ollama pull llama3.2-vision:11b
```

If Llama lives on a different computer, tell the program where to find it:

```
export LLAMA_BASE_URL=http://that-computer:11434/v1
```

A fourth helper, **DeepSeek**, is very cheap to use. It lives on DeepSeek's own computers in China, so it needs its own key, and it's best kept for things that aren't private:

```
export DEEPSEEK_API_KEY=your-deepseek-key
```

A fifth helper, **Grok**, is made by a company called **xAI**. It lives on xAI's own computers, and it needs its own key too:

```
export XAI_API_KEY=your-xai-key
```

A sixth helper, **GPT**, is made by **OpenAI**, the company behind ChatGPT. A ChatGPT subscription is not the same as an API key, so you need a key from OpenAI's developer site:

```
export OPENAI_API_KEY=your-openai-key
```

There are lots more helpers. Each one needs its own key, from its own company:

| Helper | Made by | Lives in | The key line |
|---|---|---|---|
| **Mistral** | Mistral AI | France | `export MISTRAL_API_KEY=your-key` |
| **Qwen** | Alibaba | Singapore, for people outside China | `export DASHSCOPE_API_KEY=your-key` |
| **Kimi** | Moonshot AI | China | `export MOONSHOT_API_KEY=your-key` |
| **Perplexity** | Perplexity | America | `export PERPLEXITY_API_KEY=your-key` |
| **Hugging Face** | lots of different people | all over the world | `export HF_TOKEN=your-token` |
| **Groq** | Groq | America | `export GROQ_API_KEY=your-key` |
| **GLM** | Z.ai | China | `export ZAI_API_KEY=your-key` |
| **MiniMax** | MiniMax | China | `export MINIMAX_API_KEY=your-key` |

Perplexity is different from the others. It searches the internet for every question, then lists the pages it read at the end of its answer. That makes it good for things that change, like prices and opening times. It can't look at photos, though.

**Hugging Face** is like a huge library of free, open helpers that anyone can share. Second Thought starts you off with Google's Gemma, but you can choose almost any helper in the library.

**Groq** (spelt with a q, so it is not the same as Grok) is very, very fast. It is good for jobs with lots of little steps.

**OpenRouter** is like a big switchboard. One key reaches hundreds of helpers from lots of different companies. Choose **OpenRouter, auto-pick** and it chooses a good helper for each job. Or use the block called **with OpenRouter model**, and type in the name of any helper you like from openrouter.ai/models:

```
export OPENROUTER_API_KEY=your-openrouter-key
```

All the helpers except Claude only work in the Python program. On the Second Thought page, Claude does their jobs instead, and the run log says so.

---

## Page 10½: A clever house

*Picture: a cosy house at night. A little light glows in every window, and the ladybird waves from the doorstep.*

Some homes have a helper called **Home Assistant**. It knows which lights are on, whether the doors are shut, and how warm each room is. It can switch things on and off, too.

Second Thought can talk to Home Assistant. It has its own blue blocks for this.

- One block asks "Is the back door open?"
- One block takes a photo from a camera, so Claude can say who is at the door.
- One block turns a light off, or sends a message to a phone.
- A special yellow block starts a script by itself when something changes, like the doorbell ringing.

On the Second Thought page, these blocks use a **pretend house**, so you can try everything safely. Press the **Home Assistant** button to see the pretend house. Change something, like the doorbell, and watch your program spring into action.

There are more than sixty Home Assistant examples to try. You will find them in **Browse examples**.

**A safety rule:** Second Thought will never unlock a door, open the garage or switch off the alarm without asking you first.

**Grown-ups, here is how to use your real Home Assistant:**

Export the program as Python and run it on a computer at home, on the same network as Home Assistant. Make a long-lived access token in Home Assistant (your profile, then the Security tab), then:

```
export HA_URL=http://homeassistant.local:8123
export HA_TOKEN=your-long-lived-token
python my-program.py --schedule
```

`--schedule` keeps it running, so timed jobs and "when it changes" scripts start by themselves. A small virtual machine or container that's always on is a good home for it.

---

## Page 11: What is in this folder

*Picture: an open toy box with labelled compartments.*

This folder is where all the parts of Second Thought are kept. Each part has its own place.

| Name | What it is |
|---|---|
| `second-thought.html` | The Second Thought page itself. This is the part you see on the screen. |
| `python/runtime.py` | The helper that comes with every Python program. It knows how to do each block's job. |
| `prompts/convert-guide.txt` | The instructions Claude reads when it turns Python back into blocks. |
| `ha/sample-house.json` | The pretend house that the Home Assistant blocks use on the page. |
| `tools/sync.py` | A little tool that copies the parts above into the page, so they always match. |
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
