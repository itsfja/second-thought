"""tools/merge_i18n.py: translation files merge key by key."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import support

sys.path.insert(0, str(support.ROOT / "tools"))
import merge_i18n  # noqa: E402

BASE = {"name": "Français", "page": {"Run": "Lancer", "Stop": "Arrêter"}, "python": {"Done": "Fini"}}


class Merge(unittest.TestCase):
    def merged(self, ours, theirs):
        conflicts = []
        return merge_i18n.merge(BASE, ours, theirs, "", conflicts), conflicts

    def test_words_added_on_both_sides_are_kept(self):
        ours = json.loads(json.dumps(BASE)); ours["page"]["Save"] = "Enregistrer"; ours["python"]["Keys"] = "Clés"
        theirs = json.loads(json.dumps(BASE)); theirs["page"]["Load"] = "Charger"
        out, conflicts = self.merged(ours, theirs)
        self.assertEqual(conflicts, [])
        self.assertEqual(out["page"], {"Run": "Lancer", "Stop": "Arrêter", "Save": "Enregistrer", "Load": "Charger"})
        self.assertEqual(out["python"], {"Done": "Fini", "Keys": "Clés"})

    def test_a_change_on_one_side_wins(self):
        theirs = json.loads(json.dumps(BASE)); theirs["page"]["Run"] = "Exécuter"
        out, conflicts = self.merged(json.loads(json.dumps(BASE)), theirs)
        self.assertEqual((out["page"]["Run"], conflicts), ("Exécuter", []))

    def test_a_removal_on_one_side_wins(self):
        theirs = json.loads(json.dumps(BASE)); del theirs["page"]["Stop"]
        out, conflicts = self.merged(json.loads(json.dumps(BASE)), theirs)
        self.assertNotIn("Stop", out["page"])
        self.assertEqual(conflicts, [])

    def test_different_changes_to_one_word_conflict(self):
        ours = json.loads(json.dumps(BASE)); ours["page"]["Run"] = "Démarrer"
        theirs = json.loads(json.dumps(BASE)); theirs["page"]["Run"] = "Exécuter"
        out, conflicts = self.merged(ours, theirs)
        self.assertEqual((out["page"]["Run"], conflicts), ("Démarrer", ["/page/Run"]))

    def test_as_git_runs_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for side, data in [("base", BASE), ("ours", dict(BASE, page=dict(BASE["page"], Save="Enregistrer"))),
                               ("theirs", dict(BASE, page=dict(BASE["page"], Load="Charger")))]:
                paths[side] = pathlib.Path(tmp) / side
                paths[side].write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            r = subprocess.run([sys.executable, str(support.ROOT / "tools" / "merge_i18n.py"), str(paths["base"]), str(paths["ours"]),
                                str(paths["theirs"]), "i18n/fr.json"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            text = paths["ours"].read_text(encoding="utf-8")
            self.assertEqual(json.loads(text)["page"], {"Run": "Lancer", "Stop": "Arrêter", "Save": "Enregistrer", "Load": "Charger"})
            self.assertTrue(text.startswith('{\n "name": "Français"'), "written like the repository's files")


if __name__ == "__main__":
    unittest.main()
