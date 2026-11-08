#!/usr/bin/env python3
"""Helps with the translations in i18n/<language>.json.

    python tools/i18n.py missing             # the words each language still needs, page and Python (exit 1 if any)
    python tools/i18n.py add words.json      # put new translations into every language file
    python tools/i18n.py script gmy "ka-ra-pe {name}"   # show how a romanised line is written in Linear B (or akk: cuneiform)

words.json says, for each English text, its translation in each language:

    {"page":   {"Save test": {"de": "Test speichern", "fr": "Enregistrer le test", ...}},
     "python": {"Test run":  {"de": "Testlauf", ...}}}

Two languages write the page in a script most keyboards can't type: Mycenaean Greek (gmy) in Linear B and Akkadian
(akk) in cuneiform. Give their page words romanised, as their Python words are (ka-ra-pe, nēpešum annûm), and this
writes the page's in the script. Placeholders like {name}, names like GitHub, file names and code stay as they are.
Linear B signs come from Unicode's sign names; cuneiform signs are learned from the akk words already translated both
ways. A syllable with no known sign is left romanised and reported, so the word can be put another way.

After adding, run python tools/sync.py, then the tests.
"""
import collections
import json
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
I18N = ROOT / "i18n"
PLACEHOLDER = re.compile(r"\{[^{}]*\}")

# ----- Linear B -----
LINEAR_B = {}
for _cp in range(0x10000, 0x10080):
    try:
        _m = re.match(r"LINEAR B SYLLABLE B\d+ (\w+)$", unicodedata.name(chr(_cp)))
    except ValueError:
        continue
    if _m:
        LINEAR_B[_m.group(1).lower()] = chr(_cp)

# ----- Cuneiform -----
AKK_LETTERS = "a-zšṣṭḫʾāēīūâêîû"
_PLAIN = str.maketrans("āēīūâêîû", "aeiuaeiu")


def syllables(word):
    """An Akkadian word as the syllables cuneiform writes, like šumātim → šu ma ti im (a closed syllable is written
    as two signs: CV then VC). None if it isn't one plain word."""
    segs = re.findall(r"[aeiu]|[^aeiu]", word.lower().translate(_PLAIN))
    if not segs or not re.fullmatch(r"[a-zšṣṭḫʾ]+", "".join(segs)):
        return None
    vowels = [i for i, s in enumerate(segs) if s in "aeiu"]
    if not vowels:
        return None
    bounds = [a + 1 if b - a == 1 else b - 1 for a, b in zip(vowels, vowels[1:])]  # one consonant goes with the next vowel
    out = []
    for start, end in zip([0] + bounds, bounds + [len(segs)]):
        part = segs[start:end]
        vi = next(i for i, s in enumerate(part) if s in "aeiu")
        onset, coda = part[:vi], part[vi + 1:]
        if len(onset) > 1 or len(coda) > 1:
            return None
        v = part[vi]
        out += [onset[0] + v, v + coda[0]] if onset and coda else ["".join(part)]
    return out


def learn_cuneiform():
    """syllable → sign, learned from akk's Python words (romanised) and page words (cuneiform) for the same text."""
    d = json.loads((I18N / "akk.json").read_text(encoding="utf-8"))
    seen = collections.defaultdict(collections.Counter)
    for key, roman in d.get("python", {}).items():
        signs = d.get("page", {}).get(key)
        if not isinstance(roman, str) or not isinstance(signs, str):
            continue
        rw, sw = roman.split(), signs.split()
        if len(rw) != len(sw):
            continue
        for a, b in zip(rw, sw):
            sy = syllables(re.sub(f"[^{AKK_LETTERS}]", "", a))
            cu = [ch for ch in b if 0x12000 <= ord(ch) <= 0x1254F]
            if sy and len(sy) == len(cu):
                for s, c in zip(sy, cu):
                    seen[s][c] += 1
    return {s: c.most_common(1)[0][0] for s, c in seen.items()}


_CUNEIFORM = None


def _sign(syllable):
    global _CUNEIFORM
    if _CUNEIFORM is None:
        _CUNEIFORM = learn_cuneiform()
    if syllable in _CUNEIFORM:
        return _CUNEIFORM[syllable]
    try:
        return unicodedata.lookup("CUNEIFORM SIGN " + syllable.upper().replace("Š", "SH").replace("Ṣ", "S2").replace("Ṭ", "T2"))
    except KeyError:
        return None


# ----- Hieroglyphs (#136) -----
# Middle Egyptian in standard transliteration, each sound written with its one-consonant sign (Gardiner's uniliterals)
# in a linear run: no biliterals, logograms, determinatives or groupings, which fonts and browsers show patchily.
# Markers in the transliteration (. and = for endings and suffixes, - between parts) aren't written.
EGY_SIGNS = {"ꜣ": "G001", "j": "M017", "i": "M017", "y": "Z004", "ꜥ": "D036", "w": "G043", "b": "D058", "p": "Q003", "f": "I009",
             "m": "G017", "n": "N035", "r": "D021", "h": "O004", "ḥ": "V028", "ḫ": "AA001", "ẖ": "F032", "s": "S029", "z": "O034",
             "š": "N037", "q": "N029", "k": "V031", "g": "W011", "t": "X001", "ṯ": "V013", "d": "D046", "ḏ": "I010"}
EGY_SIGNS = {k: unicodedata.lookup("EGYPTIAN HIEROGLYPH " + v) for k, v in EGY_SIGNS.items()}
EGY_LETTERS = "ꜣjiyꜥwbpfmnrhḥḫẖszšqkgtṯdḏ.=-"

# ----- Coptic (#131) -----
# Sahidic in a Latin transliteration, letter for letter: š f h j c are ϣ ϥ ϩ ϫ ϭ, ē ō are ⲏ ⲱ, u and y are ⲩ. In the
# Greek words Coptic borrowed (COP_GREEK: praksis, khartēs, kephalē…), th ph kh ps ks are the one letters ⲑ ⲫ ⲭ ⲯ ⲝ;
# elsewhere they're two (p-shai, the writing, is ⲡⲥϩⲁⲓ). Supralinear strokes aren't written. A lowercase word that should
# stay in Latin letters (email, token, web) is written with ^ in front: ^email. Words with capitals, numbers or dots
# stay as they are anyway.
COP_PAIRS = {"th": "ⲑ", "ph": "ⲫ", "kh": "ⲭ", "ps": "ⲯ", "ks": "ⲝ"}
COP_GREEK = re.compile(r"arkh|bathm|boēth|kephal|khair|khart|khrōm|praks|taks|phōn|zōgraph|tukh|graph|thēk|psykh|ksen|thron|phil|phys")
COP_SIGNS = dict(zip("abgdezēiklmnoprstuyōšfhjc", "ⲁⲃⲅⲇⲉⲍⲏⲓⲕⲗⲙⲛⲟⲡⲣⲥⲧⲩⲩⲱϣϥϩϫϭ"))
COP_LETTERS = "abgdezēiklmnoprstuyōšfhjc"


def coptic(word):
    """A transliterated Sahidic word in Coptic letters, or None if it has a letter Coptic doesn't."""
    out, i = [], 0
    greek = [range(m.start(), m.end()) for m in COP_GREEK.finditer(word)]
    while i < len(word):
        if word[i:i + 2] in COP_PAIRS and any(i in r and i + 1 in r for r in greek):
            out.append(COP_PAIRS[word[i:i + 2]])
            i += 2
        elif word[i] in COP_SIGNS:
            out.append(COP_SIGNS[word[i]])
            i += 1
        else:
            return None
    return "".join(out)


# Classical Syriac (#130), written in transliteration and shown in Estrangela. Consonants one letter each; doubled ones
# are written once. Vowels as unpointed Syriac writes them: a, e and a medial ā not at all; i, ī and ē as ܝ, o, u, ō and
# ū as ܘ; a final ā or ē (the emphatic state, singular and plural) as ܐ; a word that starts with a vowel gets ܐ first.
SYC_CONSONANTS = dict(zip("ʾbgdhwzḥṭyklmnsʿpṣqrštḇḡḏḵṯ", "ܐܒܓܕܗܘܙܚܛܝܟܠܡܢܣܥܦܨܩܪܫܬܒܓܕܟܬ"))  # ḇ ḡ ḏ ḵ ṯ: soft, same letters
SYC_VOWELS = {"a": "", "e": "", "ā": "", "i": "ܝ", "ī": "ܝ", "ē": "ܝ", "o": "ܘ", "u": "ܘ", "ō": "ܘ", "ū": "ܘ"}
SYC_LETTERS = "ʾbgdhwzḥṭyklmnsʿpṣqrštḇḡḏḵṯaeiouāēīōū"


def syriac(word):
    """A transliterated Classical Syriac word in Syriac letters, or None if it has a letter Syriac doesn't."""
    if any(c not in SYC_LETTERS for c in word):
        return None
    out = []
    for i, c in enumerate(word):
        if c in SYC_CONSONANTS:
            letter = SYC_CONSONANTS[c]
            if not (out and out[-1] == letter and word[i - 1] == c):  # a doubled consonant is written once
                out.append(letter)
            continue
        if i == 0:
            out.append("ܐ")
        if i == len(word) - 1 and c in "āē":
            out.append("ܐ")
        elif not (i == 0 and c in "aeā"):
            out.append(SYC_VOWELS[c])
    return "".join(out)


def printed(code, text):
    """What exported Python prints for a word list in a script language: the transliteration, without the ^ marks, and
    for Syriac with ꜣ and ꜥ (Latin letters) for ʾ and ʿ, so a terminal shows it in Latin script."""
    text = unmark(text)
    return text.replace("ʾ", "ꜣ").replace("ʿ", "ꜥ") if code == "syc" else text


def unmark(text):
    """The text with the ^ marks (keep this word in Latin letters) taken out, as exported Python shows it."""
    return re.sub(r"\^(?=[\w*~.\-])", "", re.sub(r"(?<=\w)\^(?=[\w*~.\-])", "-", text))


def to_script(lang, text, missing=None):
    """A romanised line in Linear B (gmy), cuneiform (akk) or hieroglyphs (egy). Placeholders, names, file names and
    code are kept."""
    missing = set() if missing is None else missing
    if lang == "cop":
        return _to_coptic(text, missing)
    if lang == "syc":
        return _to_marked(text, missing, SYC_LETTERS, syriac)
    letters = "a-z0-9-" if lang == "gmy" else EGY_LETTERS if lang == "egy" else AKK_LETTERS
    out = []
    for token in text.split(" "):
        m = re.fullmatch(f"([^{letters}]*?)([{letters}]+)([^{letters}]*)", token)
        if not m or PLACEHOLDER.search(token) or re.search(r"[A-Z]", token) or (lang == "egy" and re.search(r"[acelouvx0-9]", token)):
            out.append(token)
            continue
        pre, word, post = m.groups()
        if pre.endswith((".", "/", "_")) or (post[:1] in "._/" and re.match(r"[._/]\w", post)):
            out.append(token)  # part of a file name, an address or code
            continue
        if lang == "egy":
            sounds = [c for c in word if c not in ".=-"]
            written = "".join(EGY_SIGNS[c] for c in sounds) if sounds and all(c in EGY_SIGNS for c in sounds) else None
            if written is None:
                missing.update(c for c in sounds if c not in EGY_SIGNS)
        elif lang == "gmy":
            parts = word.split("-")
            written = "".join(LINEAR_B[p] for p in parts) if parts and all(p in LINEAR_B for p in parts) else None
            if written is None:
                missing.update(p for p in parts if p not in LINEAR_B)
        else:
            sy = syllables(word)
            signs = [_sign(s) for s in sy] if sy else None
            written = "".join(signs) if signs and all(signs) else None
            if written is None:
                missing.update(s for s, g in zip(sy or [word], signs or [None]) if not g)
        out.append(pre + (written or word) + post)
    return " ".join(out)


def _to_coptic(text, missing):
    return _to_marked(text, missing, COP_LETTERS, coptic)


def _to_marked(text, missing, letters, convert):
    """A transliterated line in its own letters (Coptic, Syriac), word by word. A word marked ^, placeholders, names,
    code and file names stay as they are; a Syriac proclitic joined by a hyphen to one of those (d-Claude) is written in
    Syriac letters with the hyphen kept."""
    if "\n" in text:
        return "\n".join(_to_marked(line, missing, letters, convert) for line in text.split("\n"))
    out = []
    for token in text.split(" "):
        if re.search(r"</?[a-z]+>", token):  # <b>word</b>: the words beside the tags
            out.append("".join(part if re.fullmatch(r"</?[a-z]+>", part) else _to_marked(part, missing, letters, convert)
                               for part in re.split(r"(</?[a-z]+>)", token)))
            continue
        if convert is syriac and "'" in token and not re.search(r"[A-Z0-9_/@{\\\"]", token.replace("'", "")):  # d'sīm ʿbādā'
            out.append("'".join(_to_marked(part, missing, letters, convert) if part else part for part in token.split("'")))
            continue
        pp = re.fullmatch(r"(\W*)([bdlw]{1,2})([A-Z0-9].*)", token) if convert is syriac else None
        if pp:  # dClaude, bPython, l3: a proclitic on a name or a number
            out.append(pp.group(1) + convert(pp.group(2)) + "-" + unmark(pp.group(3)))
            continue
        kept = lambda t: re.match(r"\W*\^", t) or PLACEHOLDER.search(t) or re.search(r'[A-Z0-9_/@"]|:\S', t) or re.search(r"(^|\w|\()\.\w", t)
        pm = re.fullmatch(f"([^{letters}]*?)([{letters}]+)(-|(?=\\^))(.+)", token) if convert is syriac else None
        if pm and kept(pm.group(4)) and convert(pm.group(2)):  # d-Claude, w^text: a proclitic on a word kept as it is
            out.append(pm.group(1) + convert(pm.group(2)) + "-" + unmark(pm.group(4)))
            continue
        if kept(token):
            out.append(unmark(token))
            continue
        m = re.fullmatch(f"([^{letters}]*?)([{letters}]+)([^{letters}]*)", token)
        if not m:
            missing.update(c for c in token if c.isalpha() and c not in letters)
            out.append(token)
            continue
        pre, word, post = m.groups()
        written = convert(word)
        if written is None or re.search(r"[a-zāīū]", post) or re.search(r"[A-Za-z]", pre):
            missing.update(c for c in token if c.isalpha() and c not in letters)
            out.append(token)
            continue
        out.append(pre + written + post)
    return " ".join(out)


SCRIPTS = {"gmy", "akk", "egy", "cop", "syc"}


# ----- The words each language needs -----
def needed():
    """{"page": set of texts, "python": set of texts} that every language must translate, as the tests count them."""
    sys.path.insert(0, str(ROOT / "tests"))
    sys.path.insert(0, str(ROOT / "tests" / "unit"))
    from test_python_words import runtime_texts
    try:
        from e2e.i18n import code_texts
    except ImportError:
        print("(The page's words need the test setup: tests/setup.sh. Showing the Python words only.)")
        return {"page": set(), "python": runtime_texts()}
    page = (ROOT / "second-thought.html").read_text(encoding="utf-8")
    return {"page": code_texts(page), "python": runtime_texts()}


def languages():
    return {p.stem: p for p in sorted(I18N.glob("*.json"))}


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_missing(only):
    need = needed()
    gaps = 0
    for code, path in languages().items():
        if only and code not in only:
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        for section in ("page", "python"):
            lack = sorted(k for k in need[section] if k not in d.get(section, {}))
            gaps += len(lack)
            for k in lack:
                print(f"{code}  {section:<6}  {k}")
    print(("Nothing missing." if not gaps else f"\n{gaps} missing.") +
          " (Words written straight into the page's HTML are checked by the tests: python tests/run_tests.py i18n)")
    return 1 if gaps else 0


def cmd_add(path):
    words = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    langs = languages()
    files = {code: json.loads(p.read_text(encoding="utf-8")) for code, p in langs.items()}
    problems, added = [], 0
    for section in ("page", "python"):
        for english, by_lang in (words.get(section) or {}).items():
            want = sorted(PLACEHOLDER.findall(english))
            for code in sorted(set(langs) - set(by_lang)):
                problems.append(f"{section} “{english[:50]}”: no {code}")
            for code, text in by_lang.items():
                if code not in files:
                    problems.append(f"{section} “{english[:50]}”: there's no language {code}")
                    continue
                gaps = set()
                value = to_script(code, text, gaps) if code in SCRIPTS and section == "page" else printed(code, text) if code in ("cop", "syc") else text
                if gaps:
                    problems.append(f"{section} “{english[:50]}”: {code} has no sign for {', '.join(sorted(gaps))}, so those stay romanised")
                if sorted(PLACEHOLDER.findall(value)) != want:
                    problems.append(f"{section} “{english[:50]}”: {code} has {PLACEHOLDER.findall(value)}, not {want}")
                    continue
                files[code].setdefault(section, {})[english] = value
                added += 1
    for code, data in files.items():
        write(langs[code], data)
    print(f"Added {added} translations.")
    for p in problems:
        print("  " + p)
    print("Now run: python tools/sync.py")
    return 1 if problems else 0


def main(argv):
    if argv[:1] == ["missing"]:
        return cmd_missing(set(argv[1:]))
    if argv[:1] == ["add"] and len(argv) == 2:
        return cmd_add(argv[1])
    if argv[:1] == ["script"] and len(argv) == 3 and argv[1] in SCRIPTS:
        gaps = set()
        print(to_script(argv[1], argv[2], gaps))
        if gaps:
            print("No sign for: " + ", ".join(sorted(gaps)))
        return 1 if gaps else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
