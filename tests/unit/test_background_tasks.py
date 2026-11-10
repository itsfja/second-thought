"""Listeners and watchers run for as long as the program does. asyncio keeps only a weak reference to a task, so one
nobody holds can be collected while it waits, and its listener silently stops (as CI saw, on Python 3.11). The runtime
keeps hold of them."""
import asyncio
import gc
import unittest

import support  # noqa: F401
from second_thought.runtime import Runtime


class Background(unittest.TestCase):
    def test_a_waiting_task_survives_garbage_collection(self):
        async def go():
            r = Runtime()
            done = []

            async def listener():
                await asyncio.get_running_loop().create_future()  # waits on something only this task knows about

            async def quick():
                done.append(True)
            r._background(listener())
            r._background(quick())
            await asyncio.sleep(0)
            gc.collect()
            await asyncio.sleep(0)
            waiting = list(r._background_tasks)
            self.assertEqual((len(waiting), waiting[0].done(), done), (1, False, [True]), "the listener is held; the finished one is let go")
            waiting[0].cancel()
        asyncio.run(go())

    def test_nothing_long_lived_is_started_without_being_held(self):
        for name in ("connectors.py", "runtime.py"):
            for n, line in enumerate((support.ROOT / "python" / "second_thought" / name).read_text(encoding="utf-8").splitlines(), 1):
                if "ensure_future(" in line or "create_task(" in line:
                    self.assertRegex(line.strip(), r"^(\w[\w.]*) = ", f"{name}:{n} starts a task and keeps no reference to it")


if __name__ == "__main__":
    unittest.main()
