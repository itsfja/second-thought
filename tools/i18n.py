#!/usr/bin/env python3
"""Helps with the translations in i18n/<language>.json.

    python tools/i18n.py missing             # the words each language still needs, page and Python (exit 1 if any)
    python tools/i18n.py add words.json      # put new translations into every language file
    python tools/i18n.py script gmy "ka-ra-pe {name}"   # show how a romanised line is written in Linear B (or akk, sux, hit: cuneiform; got: Gothic)
    python tools/i18n.py derive              # write the languages made from another's words (qnr, qar, qcg: Old Norse and Old English in runes, Church Slavonic in Glagolitic)

words.json says, for each English text, its translation in each language:

    {"page":   {"Save test": {"de": "Test speichern", "fr": "Enregistrer le test", ...}},
     "python": {"Test run":  {"de": "Testlauf", ...}}}

Two languages write the page in a script most keyboards can't type: Mycenaean Greek (gmy) in Linear B and Akkadian
(akk) in cuneiform. Give their page words romanised, as their Python words are (ka-ra-pe, nēpešum annûm), and this
writes the page's in the script. Placeholders like {name}, names like GitHub, file names and code stay as they are.
Linear B signs come from Unicode's sign names; cuneiform signs are learned from the akk words already translated both
ways. A syllable with no known sign is left romanised and reported, so the word can be put another way. Sumerian (sux)
is given in its standard transliteration (e2-dub-ba, ĝeš-ḫur, digits for sign indices) and written in cuneiform from
tools/sux_signs.json, the readings of the Oracc Global Sign List (CC0); a reading the list hasn't got is reported the
same way. Hittite (hit) uses the same sign list, written as Hittitologists do: syllables in lowercase (ne-e-ši-li),
Sumerograms in capitals joined by dots (DUB.SAR), Akkadograms in capitals (A-NA), and an accent for the sign's index
(ú is u2); an English abbreviation in capitals that should stay Latin is marked ^ (^MQTT). Gothic (got) is given in its usual
transliteration (gutisk, þiudans, ƕas) and written letter for letter in the Gothic alphabet.

Old Norse in runes (qnr) and Old English in runes (qar) have no words of their own: each file is made from its
language's (non, ang), the page's words written in runes (the Younger Futhark, the Anglo-Saxon futhorc) and the Python
words left in Latin letters. Church Slavonic in Glagolitic (qcg) is made the same way from cu, letter
for letter from its Cyrillic. So words.json needs none of the three, "add" writes them again after adding, and "derive"
writes them after any other change to i18n/non.json, i18n/ang.json or i18n/cu.json.

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
    for Syriac and Ugaritic with ꜣ and ꜥ (Latin letters) for ʾ and ʿ, so a terminal shows it in Latin script."""
    text = unmark(text)
    return text.replace("ʾ", "ꜣ").replace("ʿ", "ꜥ") if code in ("syc", "uga") else text


# ----- Sumerian (#137) -----
# Sumerian in the usual transliteration, each sign by one of its readings with the index as a digit (e2, du11, ĝeš),
# the signs of a word joined by hyphens: e2-dub-ba. Each reading is looked up in the Oracc Global Sign List (CC0),
# kept in tools/sux_signs.json. A lowercase word that should stay in Latin letters is written with ^ in front, as for
# Coptic and Syriac.
SUX_WORD = re.compile(r"[a-zšĝḫ]+[0-9]*(?:-[a-zšĝḫ]+[0-9]*)*")
_SUX = None


def sumerian(word):
    """e2-dub-ba → 𒂍𒁾𒁀, or None if a reading isn't in the sign list."""
    global _SUX
    if _SUX is None:
        _SUX = json.loads((ROOT / "tools" / "sux_signs.json").read_text(encoding="utf-8"))["signs"]
    signs = [_SUX.get(part.replace("ḫ", "h")) for part in word.split("-")]
    return "".join(signs) if all(signs) else None


def _to_sumerian(text, missing, lookup=None, reading=None):
    """A transliterated line in cuneiform. A word is split at its hyphens (and, for Hittite, the dots of a Sumerogram),
    and each run of readings becomes signs; a part that is a placeholder, a name, a number, code or marked ^ stays as
    it is, joined to the signs by a hyphen (%1-da, Claude-e, 2-kam)."""
    lookup = lookup or sumerian
    reading = reading or SUX_PART
    if "\n" in text:
        return "\n".join(_to_sumerian(line, missing, lookup, reading) for line in text.split("\n"))
    out = []
    for token in text.split(" "):
        if re.search(r"</?[a-z]+>", token):
            out.append("".join(part if re.fullmatch(r"</?[a-z]+>", part) else _to_sumerian(part, missing, lookup, reading)
                               for part in re.split(r"(</?[a-z]+>)", token)))
            continue
        if PLACEHOLDER.search(token) and "-" not in token or re.search(r"[_/@]|:\S|https?:|\.[a-z]", token):
            out.append(unmark(token))
            continue
        groups = []  # [is_signs, text, trailing punctuation]
        pieces = re.split(r"(-|(?<=[^\W_])\.(?=[A-ZŠḪÚÙÁÀÉÈÍÌ]))", token) if reading is HIT_PART else re.split("(-)", token)
        for part, sep in zip(pieces[::2], pieces[1::2] + [""]):
            m = re.fullmatch(r"([^\w^%{]*)(.*?)([^\w}%]*)", part)
            pre, core, post = m.groups()
            if reading.fullmatch(core):
                written = lookup(core)
                if written is None:
                    missing.add(core)
                    groups.append([False, part, sep])
                elif groups and groups[-1][0] and not pre and not groups[-1][3]:
                    groups[-1][1] += written + post
                    groups[-1][3] = post
                else:
                    groups.append([True, pre + written + post, sep, post])
            else:
                groups.append([False, unmark(part), sep])
        text_ = ""
        for i, g in enumerate(groups):
            text_ += g[1]
            if i + 1 < len(groups) and not (g[0] and groups[i + 1][0]):
                text_ += g[2] if g[2] else "-"
        out.append(text_)
    return " ".join(out)


SUX_PART = re.compile(r"[a-zšĝḫ]+[0-9]*")


# ----- Hittite (#138) -----
# Hittite in the usual transliteration: phonetic signs in lowercase, joined by hyphens (ne-e-ši-li); Sumerograms in
# capitals, their signs joined by dots (DUB.SAR, É, LÚ.MEŠ); Akkadograms in capitals joined by hyphens (A-NA). An
# accent is the sign's index, as Hittitologists write it (ú is u2, ù is u3). Each sign comes from the same Oracc sign
# list as Sumerian. An English abbreviation in capitals that should stay in Latin letters is written with ^ (^MQTT).
HIT_PART = re.compile(r"[a-zšḫúùáàéèíì]+[0-9]*|[A-ZŠḪÚÙÁÀÉÈÍÌ]+[0-9]*")
_ACUTE, _GRAVE = dict(zip("áéíú", "aeiu")), dict(zip("àèìù", "aeiu"))


def hittite(part):
    """One Hittite sign (ú, ša, DUB, É) → its cuneiform, or None. All capitals or all lowercase, nothing mixed."""
    if part != part.lower() and part != part.upper():
        return None
    p = part.lower()
    index = ""
    for marks, digit in ((_ACUTE, "2"), (_GRAVE, "3")):
        if any(c in marks for c in p):
            p, index = "".join(marks.get(c, c) for c in p), digit
    return sumerian(p + index if not re.search(r"[0-9]$", p) else p)


def unmark(text):
    """The text with the ^ marks (keep this word in Latin letters) taken out, as exported Python shows it."""
    return re.sub(r"\^(?=[\w*~.\-])", "", re.sub(r"(?<=\w)\^(?=[\w*~.\-])", "-", text))


def to_script(lang, text, missing=None):
    """A romanised line in Linear B (gmy), cuneiform (akk, sux, hit), hieroglyphs (egy), Coptic (cop), Syriac (syc), Gothic (got)
    or the Ugaritic alphabet (uga).
    Placeholders, names, file names and code are kept."""
    missing = set() if missing is None else missing
    if lang == "cop":
        return _to_coptic(text, missing)
    if lang == "syc":
        return _to_marked(text, missing, SYC_LETTERS, syriac)
    if lang == "got":
        return _to_marked(text, missing, GOT_LETTERS, gothic)
    if lang == "uga":
        return _to_marked(text, missing, UGA_LETTERS, ugaritic)
    if lang == "sux":
        return _to_sumerian(text, missing)
    if lang == "hit":
        return _to_sumerian(text, missing, hittite, HIT_PART)
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


# ----- Gothic (#139) -----
# Gothic in its usual transliteration, one Latin letter for each Gothic one (þ, ƕ, q for kw); ï is i with its dots.
GOT_LETTERS = "abgdeqzhþiklmnjuprstwfxƕoï"
GOT = dict(zip("abgdeqzhþiklmnjuprstwfxƕoï", "𐌰𐌱𐌲𐌳𐌴𐌵𐌶𐌷𐌸𐌹𐌺𐌻𐌼𐌽𐌾𐌿𐍀𐍂𐍃𐍄𐍅𐍆𐍇𐍈𐍉𐌹"))


def gothic(word):
    """A transliterated Gothic word in Gothic letters, or None if it has a letter Gothic doesn't (c, v, y)."""
    return "".join(GOT[c] for c in word) if word and all(c in GOT for c in word) else None


# ----- Ugaritic (#471) -----
# Ugaritic in the usual transliteration (as KTU and the dictionaries write it): consonants only, as the alphabet writes
# them, with ả, ỉ and ủ for its three alephs. One letter for each sign; a word with a letter the alphabet doesn't have
# (plain a, e, o, c, f) stays in Latin letters, so English names and field names keep themselves.
UGA_LETTERS = "ảbgḫdhwzḥṭykšlmḏnẓsʿpṣqrṯġtỉủś"
UGA = dict(zip(UGA_LETTERS, (chr(0x10380 + i) for i in range(30))))


def ugaritic(word):
    """A transliterated Ugaritic word in its alphabet (mlk → 𐎎𐎍𐎋), or None if it has a letter Ugaritic doesn't."""
    return "".join(UGA[c] for c in word) if word and all(c in UGA for c in word) else None


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


SCRIPTS = {"gmy", "akk", "egy", "cop", "syc", "sux", "hit", "got", "uga"}


# ----- Old Norse in runes (#465) -----
# The Younger Futhark's sixteen runes, in their long-branch shapes, spelled the way the Viking Age inscriptions spell:
#   - one rune stands for several sounds: ᚢ for u, o, y, ø and v; ᛁ for i, e and j; ᛅ for a and æ; ᚴ for k and g;
#     ᛏ for t and d; ᛒ for b and p; ᚦ for þ and ð; length isn't written
#   - ei is ᛅᛁ (stain, steinn), au and ey are ᛅᚢ, and ǫ is ᛅᚢ too (tanmaurk, Danmǫrk, on the Jelling stone)
#   - a doubled letter is written once, and n isn't written before k or g (kunukʀ, konungr)
#   - the r of endings (from older z) is ᛦ: after a consonant that isn't a dental, and after the vowel of an ending
#     (kunukʀ, stainaʀ, aftiʀ, þaiʀ); every other r is ᚱ
#   - á (on) and án (without) are ᚬ and ᚬᚾ: the rune kept for a spoken through the nose
# Unlike the script languages above, the words aren't written in a transliteration first: this reads the Old Norse
# spelling of i18n/non.json itself, so names and modern words have to be told from Old Norse ones. tools/latin_kept.json
# lists them: `names` (Claude, GitHub, Settings) and `words` (field names, values and modern words: name, title, email).
# A word with a capital after its first letter, a number, or code's marks stays as it is too, and both sides of a
# hyphen are judged apart (Homey-ᛏᛅᚴᛁ).
RUNES = {"a": "ᛅ", "á": "ᛅ", "æ": "ᛅ", "e": "ᛁ", "é": "ᛁ", "i": "ᛁ", "í": "ᛁ", "j": "ᛁ", "o": "ᚢ", "ó": "ᚢ", "u": "ᚢ", "ú": "ᚢ",
         "y": "ᚢ", "ý": "ᚢ", "ø": "ᚢ", "œ": "ᚢ", "ö": "ᛅᚢ", "ǫ": "ᛅᚢ", "v": "ᚢ", "w": "ᚢ", "b": "ᛒ", "p": "ᛒ", "d": "ᛏ", "t": "ᛏ",
         "ð": "ᚦ", "þ": "ᚦ", "g": "ᚴ", "k": "ᚴ", "c": "ᚴ", "q": "ᚴ", "x": "ᚴᛋ", "z": "ᛋ", "f": "ᚠ", "h": "ᚼ", "l": "ᛚ", "m": "ᛘ",
         "n": "ᚾ", "r": "ᚱ", "s": "ᛋ", "ʀ": "ᛦ"}
RUNE_LETTERS = "a-záéíóúýæœøöǫþð"
_RUNE_VOWELS = "aáeéiíoóuúyýæœøöǫ"
_ENDING_R = {"þeir", "þær", "þér", "vér", "ér", "mér", "sér", "ór", "tveir", "þrír"}  # one syllable, and ᛦ all the same
_KEPT = None


def latin_kept():
    """(names, words): the words that stay in Latin letters in a language written in another script from its own
    Latin spelling, from tools/latin_kept.json."""
    global _KEPT
    if _KEPT is None:
        d = json.loads((ROOT / "tools" / "latin_kept.json").read_text(encoding="utf-8"))
        _KEPT = (set(d["names"]), set(d["words"]))
    return _KEPT


def younger_futhark(word):
    """One Old Norse word, in lowercase, in runes: konungr → ᚴᚢᚾᚢᚴᛦ. None if it has a letter Old Norse doesn't."""
    if not word or not re.fullmatch(f"[{RUNE_LETTERS}]+", word):
        return None
    if word in ("á", "án"):
        return "ᚬ" + ("ᚾ" if word == "án" else "")
    w = word.replace("th", "þ")
    before = w[-2:-1]
    if w.endswith("r") and before and before != "r":
        ending = len(re.findall(f"[{_RUNE_VOWELS}]+", w)) > 1 if before in _RUNE_VOWELS else before not in "tdþð"
        if ending or w in _ENDING_R:
            w = w[:-1] + "ʀ"
    w = re.sub(r"n(?=[kg])", "", w)
    w = w.replace("ei", "ai").replace("ey", "au")
    out = []
    for i, c in enumerate(w):
        if i and c == w[i - 1]:
            continue  # a doubled letter is written once
        out.append(RUNES[c])
    text = "".join(out)
    return re.sub(r"(.)\1+", r"\1", text)  # and so is a rune doubled by two letters that share it (ᚢ for o and u)


def _rune_part(part, names, words, write):
    """A word, or one side of a hyphen, with the marks around it: in runes unless it's a name, a kept word or code."""
    m = re.fullmatch(r"([^\w]*)(.*?)([^\w]*)", part, re.S)
    pre, core, post = m.groups()
    if not core or core in names or core.lower() in words or core[:-1] in names and core[-1] == "s":
        return part, True
    if re.search(r"[0-9_]", core) or re.search(r"[A-ZÁÉÍÓÚÝÆŒØǪÞÐ]", core[1:]) or not core.isalpha():
        return part, True
    written = write(core.lower())
    return (part, True) if written is None else (pre + written + post, False)


_KEPT_WORD = r"[(„“\"'‘]*[A-Za-z_]+[,.;:)”’]*"
_AND_OR = {"and", "oþþe", "ok", "eða", "og"}


def _in_runes(text, write, code):
    """A line in a language's Latin spelling, in runes, word by word with `write`. Placeholders, %1, <tags>, names,
    kept words, code, addresses and file names stay as they are."""
    names, words = latin_kept()
    own = _own(code)
    out, own_at = [], {}
    for piece in re.split(r"(\{[^{}]*\}|%\d+|</?[a-zA-Z][^<>]*>|&\w+;|\s+)", text):
        if not piece:
            continue
        if piece.isspace() or re.fullmatch(r"\{[^{}]*\}|%\d+|</?[a-zA-Z][^<>]*>|&\w+;", piece, re.S):
            out.append(piece)
            continue
        if re.search(r"[/@=\\~<>*#+]|://|\w\.\w|^--\w|^-[a-z]\b|^\.\w|\w:\w", piece):
            # An address, a file name, a setting, an option or code. A word of the language joined to a file name or
            # a quoted time is still written: claude.ai-ᚱᛅᛁᚴᚾᛁᚴᛁ, .json-ᛋᚴᛁᛅᛚ.
            head, hyphen, tail = piece.rpartition("-")
            if hyphen and re.search(r"\w\.\w+$|^\.\w+$|“$", head) and not re.search(r"[/@]", head) and re.fullmatch(r"[^\W\d_]+[.,;:)]*", tail):
                tail = _rune_part(tail, names, words - own, write)[0]
            out.append(head + hyphen + tail)
            continue
        if re.sub(r"\W", "", piece).lower() in own and piece == piece.lower():
            own_at[len(out)] = piece  # on, to: the language's own word, unless it stands in a list of field names
        parts = [_rune_part(p, names, words - own, write) for p in piece.split("-")]
        if len(parts) > 1 and all(kept for _, kept in parts):
            out.append(piece)
            continue
        out.append("-".join(p for p, _ in parts))
    kept = lambda j: j >= 0 and bool(re.fullmatch(_KEPT_WORD, out[j])) and j not in own_at
    and_or = _AND_OR | {write(w) for w in _AND_OR}
    for i, latin in own_at.items():
        # "entity, name, from and to": after a kept word and a comma, or closing such a list after and/or
        before = i - 2
        if kept(before) and out[before].rstrip(")”’").endswith(",") or \
                before >= 2 and out[before] in and_or and (kept(before - 2) or before - 2 in own_at and out[before - 2] == own_at[before - 2]) \
                and before >= 4 and out[before - 4].endswith(","):
            out[i] = latin
        else:
            own_at[i] = None
    own_at = {i: v for i, v in own_at.items() if v}
    article = write("a")
    for i in range(2, len(out) - 2):  # "not a tool": an English a between two kept words isn't the language's
        if out[i] == article and all(re.fullmatch(_KEPT_WORD, out[j]) for j in (i - 2, i + 2)):
            out[i] = "a"
    return "".join(out)


def _own(code):
    """Words of the language itself that are spelled like kept words (Old English on, to, open)."""
    return set(json.loads((ROOT / "tools" / "latin_kept.json").read_text(encoding="utf-8")).get("own", {}).get(code, []))


def to_runes(text, missing=None):
    """A line of Old Norse in its Latin spelling, in the Younger Futhark."""
    return _in_runes(text, younger_futhark, "qnr")


# ----- Old English in runes (#466) -----
# The Anglo-Saxon futhorc, which has a rune for nearly every Old English letter, so this goes letter for letter, as the
# Ruthwell Cross and the Franks Casket do:
#   - æ is ᚫ, a is ᚪ, o is ᚩ, y is ᚣ, ea is ᛠ; eo and io are two runes (ᛖᚩ, ᛁᚩ), as on the Ruthwell Cross
#   - ng is ᛝ (kyniŋc, ᛣᚣᚾᛁᛝᚳ), and h before t is ᛇ (almehttig, ᚪᛚᛗᛖᛇᛏᛏᛁᚷ)
#   - þ and ð are both ᚦ, w (and ƿ) is ᚹ, x is ᛉ; c is ᚳ, and the k of a later word is ᛣ
#   - doubled letters are written twice, as there; length marks and the dot of ġ and ċ aren't written
FUTHORC = {"a": "ᚪ", "æ": "ᚫ", "b": "ᛒ", "c": "ᚳ", "d": "ᛞ", "e": "ᛖ", "f": "ᚠ", "g": "ᚷ", "h": "ᚻ", "i": "ᛁ", "j": "ᛄ", "k": "ᛣ",
           "l": "ᛚ", "m": "ᛗ", "n": "ᚾ", "o": "ᚩ", "œ": "ᛟ", "p": "ᛈ", "q": "ᚳ", "r": "ᚱ", "s": "ᛋ", "t": "ᛏ", "u": "ᚢ", "v": "ᚠ",
           "w": "ᚹ", "x": "ᛉ", "y": "ᚣ", "z": "ᛋ", "þ": "ᚦ", "ð": "ᚦ", "ŋ": "ᛝ", "ç": "ᛇ", "ɛ": "ᛠ"}
_OE_PLAIN = str.maketrans("ǣāēīōūȳġċƿȝóéáíú", "æaeiouygcwgoeaiu")


def futhorc(word):
    """One Old English word, in lowercase, in runes: cyning → ᚳᚣᚾᛁᛝ. None if it has a letter Old English doesn't."""
    w = word.translate(_OE_PLAIN)
    if not w or not re.fullmatch("[a-zæœþð]+", w):
        return None
    w = w.replace("th", "þ").replace("ng", "ŋ").replace("ht", "çt").replace("ea", "ɛ").replace("qu", "cw")
    return "".join(FUTHORC[c] for c in w)


def to_futhorc(text, missing=None):
    """A line of Old English in its Latin spelling, in the futhorc."""
    return _in_runes(text, futhorc, "qar")


# ----- Church Slavonic in Glagolitic (#467) -----
# Glagolitic, the alphabet the language was first written in, letter for letter from the Cyrillic of i18n/cu.json, as
# the two alphabets were matched in the manuscripts: ѣ is ⱑ, and so are я and ꙗ (Glagolitic has one letter for both);
# ы is ⱏⰹ (yer and izhe), ѿ is ⱉⱅ, и and й are ⰻ, і and ї are ⰹ, у, ѹ and ꙋ are ⱆ, є and ѥ are ⰵ. Capitals stay
# capitals. Only Cyrillic letters change, so names, field names, code and placeholders, in Latin letters, stay as they are.
_GLAGOLITIC = {"а": "AZU", "б": "BUKY", "в": "VEDE", "г": "GLAGOLI", "д": "DOBRO", "е": "YESTU", "ж": "ZHIVETE", "ѕ": "DZELO",
               "з": "ZEMLJA", "ꙁ": "ZEMLJA", "и": "I", "й": "I", "ѝ": "I", "і": "IZHE", "ї": "IZHE", "ꙇ": "IZHE", "к": "KAKO", "л": "LJUDIJE",
               "м": "MYSLITE", "н": "NASHI", "о": "ONU", "п": "POKOJI", "р": "RITSI", "с": "SLOVO", "т": "TVRIDO", "у": "UKU",
               "ѹ": "UKU", "ꙋ": "UKU", "ф": "FRITU", "х": "HERU", "ѡ": "OTU", "щ": "SHTA", "ц": "TSI", "ч": "CHRIVI", "ш": "SHA",
               "ъ": "YERU", "ь": "YERI", "ѣ": "YATI", "я": "YATI", "ꙗ": "YATI", "ю": "YU", "ѧ": "SMALL YUS", "ꙙ": "SMALL YUS",
               "ѩ": "IOTATED SMALL YUS", "ѫ": "BIG YUS", "ꙛ": "BIG YUS", "ѭ": "IOTATED BIG YUS", "ѳ": "FITA", "ѵ": "IZHITSA",
               "є": "YESTU", "ѥ": "YESTU", "ѐ": "YESTU", "э": "YESTU", "ё": "YO"}
GLAGOLITIC = {}
for _c, _name in _GLAGOLITIC.items():
    GLAGOLITIC[_c] = unicodedata.lookup("GLAGOLITIC SMALL LETTER " + _name)
    if _c.upper() != _c:
        GLAGOLITIC[_c.upper()] = unicodedata.lookup("GLAGOLITIC CAPITAL LETTER " + _name)
GLAGOLITIC.update({"ы": GLAGOLITIC["ъ"] + GLAGOLITIC["і"], "Ы": GLAGOLITIC["Ъ"] + GLAGOLITIC["і"],
                   "ѿ": GLAGOLITIC["ѡ"] + GLAGOLITIC["т"], "Ѿ": GLAGOLITIC["Ѡ"] + GLAGOLITIC["т"],
                   "̾": "", "́": "", "̀": "", "҃": ""})  # and no marks over the letters
_TO_GLAGOLITIC = str.maketrans(GLAGOLITIC)


def to_glagolitic(text, missing=None):
    """A line of Church Slavonic in Cyrillic, in Glagolitic. Whatever isn't a Cyrillic letter stays as it is."""
    return text.translate(_TO_GLAGOLITIC)


# Languages made from another's words: {code: (the language it's made from, how its page words are written, and what
# its file says of itself)}. `python tools/i18n.py derive` writes i18n/<code>.json; the tests check it is up to date.
DERIVED = {
    "qnr": ("non", to_runes, {
        "name": "ᚾᚢᚱᚢᚾᛏ ᛘᛅᛚ",
        "font": "Noto Sans Runic",
        "note": "Old Norse in runes: the words of i18n/non.json, written in the Younger Futhark (long-branch runes, U+16A0-U+16FF) "
                "by tools/i18n.py (`python tools/i18n.py derive`): edit non.json, not this file. The page shows runes in blocks, "
                "options, categories, labels, page, examples, starters and blocklyMsg, with the Noto Sans Runic font named in "
                "\"font\"; python holds non.json's Latin spelling, which exported programs print, since few terminals have a "
                "runic font. The spelling follows the Viking Age inscriptions: sixteen runes for all the sounds (ᚢ for u, o, y, "
                "ø and v; ᛁ for i, e and j; ᚴ for k and g; ᛏ for t and d; ᛒ for b and p), no length marks, doubled letters "
                "written once, n left out before k and g, ei as ᛅᛁ and ǫ as ᛅᚢ, and ᛦ for the r of endings. Names, modern "
                "words, field names, keys and placeholders stay in Latin letters (tools/latin_kept.json lists them). The code "
                "qnr is from ISO 639-3's private-use range (qaa-qtz), since Old Norse in runes (non-Runr) has no code of its own.",
    }),
    "qar": ("ang", to_futhorc, {
        "name": "ᚫᛝᛚᛁᛋᚳ",
        "font": "Noto Sans Runic",
        "note": "Old English in runes: the words of i18n/ang.json, written in the Anglo-Saxon futhorc (U+16A0-U+16FF) by "
                "tools/i18n.py (`python tools/i18n.py derive`): edit ang.json, not this file. The page shows runes in blocks, "
                "options, categories, labels, page, examples, starters and blocklyMsg, with the Noto Sans Runic font named in "
                "\"font\"; python holds ang.json's Latin spelling, which exported programs print, since few terminals have a "
                "runic font. The futhorc has a rune for nearly every Old English letter, so the words go letter for letter, as "
                "on the Ruthwell Cross and the Franks Casket: ᚫ for æ, ᚪ for a, ᚩ for o, ᚣ for y, ᛠ for ea, ᛝ for ng, ᛇ for "
                "the h of ht, ᚦ for þ and ð, ᚹ for w, with doubled letters written twice and no length marks. Names, modern "
                "words, field names, keys and placeholders stay in Latin letters (tools/latin_kept.json lists them). The code "
                "qar is from ISO 639-3's private-use range (qaa-qtz), since Old English in runes (ang-Runr) has no code of its own.",
    }),
    "qcg": ("cu", to_glagolitic, {
        "name": to_glagolitic("словѣнскїй"),
        "font": "Noto Sans Glagolitic",
        "note": "Church Slavonic in Glagolitic: the words of i18n/cu.json, written in the Glagolitic alphabet (U+2C00-U+2C5F), "
                "the one the language was first written in, by tools/i18n.py (`python tools/i18n.py derive`): edit cu.json, not "
                "this file. The page shows Glagolitic in blocks, options, categories, labels, page, examples, starters and "
                "blocklyMsg, with the Noto Sans Glagolitic font named in \"font\"; python holds cu.json's Cyrillic, which "
                "exported programs print, since few terminals have a Glagolitic font. The letters go one for one, as the two "
                "alphabets were matched in the manuscripts: ⱑ for ѣ, я and ꙗ; ⱏⰹ for ы; ⱉⱅ for ѿ; ⰻ for и and й; ⰹ for і and ї; "
                "ⱆ for у, ѹ and ꙋ. Names, field names, keys and placeholders, in Latin letters, stay as they are. The code qcg "
                "is from ISO 639-3's private-use range (qaa-qtz), since Church Slavonic in Glagolitic (cu-Glag) has no code of its own.",
    }),
}
PAGE_SIDE = ("blocks", "options", "categories", "labels", "page", "examples", "starters", "blocklyMsg")


def _written(value, write):
    return {k: _written(v, write) for k, v in value.items()} if isinstance(value, dict) else write(value) if isinstance(value, str) else value


def derived(code):
    """i18n/<code>.json for a derived language, as it should be now: its source's words, the page's in the other script."""
    source, write, about = DERIVED[code]
    d = json.loads((I18N / f"{source}.json").read_text(encoding="utf-8"))
    out = {}
    for key, value in d.items():
        if key == "name":
            out.update(name=about["name"], blockly=d["blockly"], font=about["font"], note=about["note"])
        elif key in ("page", "starters"):  # a text left as its English (a sample value, a name) stays as it is
            out[key] = {english: text if text == english else write(text) for english, text in value.items()}
        elif key in PAGE_SIDE:
            out[key] = _written(value, write)
        elif key not in ("blockly", "font", "note"):
            out[key] = value
    return out


def cmd_derive():
    for code in DERIVED:
        write(I18N / f"{code}.json", derived(code))
        print(f"Wrote i18n/{code}.json from i18n/{DERIVED[code][0]}.json.")
    print("Now run: python tools/sync.py")
    return 0


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
            for code in sorted(set(langs) - set(by_lang) - set(DERIVED)):
                problems.append(f"{section} “{english[:50]}”: no {code}")
            for code, text in by_lang.items():
                if code not in files:
                    problems.append(f"{section} “{english[:50]}”: there's no language {code}")
                    continue
                gaps = set()
                value = to_script(code, text, gaps) if code in SCRIPTS and section == "page" else printed(code, text) if code in ("cop", "syc", "sux", "hit", "got", "uga") else text
                if gaps:
                    problems.append(f"{section} “{english[:50]}”: {code} has no sign for {', '.join(sorted(gaps))}, so those stay romanised")
                if sorted(PLACEHOLDER.findall(value)) != want:
                    problems.append(f"{section} “{english[:50]}”: {code} has {PLACEHOLDER.findall(value)}, not {want}")
                    continue
                files[code].setdefault(section, {})[english] = value
                added += 1
    for code, data in files.items():
        write(langs[code], data)
    for code in DERIVED:  # a language made from another's words follows it
        if code in langs:
            write(langs[code], derived(code))
    print(f"Added {added} translations.")
    for p in problems:
        print("  " + p)
    print("Now run: python tools/sync.py")
    return 1 if problems else 0


def main(argv):
    if argv[:1] == ["missing"]:
        return cmd_missing(set(argv[1:]))
    if argv == ["derive"]:
        return cmd_derive()
    if argv[:1] == ["script"] and len(argv) == 3 and argv[1] in DERIVED:
        print(DERIVED[argv[1]][1](argv[2]))
        return 0
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
