// The run log's second thought (#449): results render as Markdown, sanitised — every character of the model's text
// is escaped before any tag is emitted, and only http(s) links become anchors; and the review loop's revisions show
// as a line diff.
"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const { load, plain } = require("./page.cjs");

const page = load();
const md = page.__markdownHtml;
const diff = page.__diffLines;

test("markdown renders headings, lists, bold, italic, code, tables, quotes and links", () => {
  const html = md("# Title\n\nSome **bold** and *italic* and `code` text.\n\n- one\n- two\n\n1. first\n2. second\n\n> quoted\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\nSee [the guide](https://example.com/docs).");
  assert.match(html, /<h1>Title<\/h1>/);
  assert.match(html, /<strong>bold<\/strong>/);
  assert.match(html, /<em>italic<\/em>/);
  assert.match(html, /<code>code<\/code>/);
  assert.match(html, /<ul><li>one<\/li><li>two<\/li><\/ul>/);
  assert.match(html, /<ol><li>first<\/li><li>second<\/li><\/ol>/);
  assert.match(html, /<blockquote>/);
  assert.match(html, /<th>a<\/th>/);
  assert.match(html, /<td>2<\/td>/);
  assert.match(html, /<a href="https:\/\/example\.com\/docs" target="_blank" rel="noopener noreferrer">the guide<\/a>/);
});

test("script and event-handler injection is escaped, never markup", () => {
  const html = md('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n<div onclick="x()">hi</div>\n\n# <b>not bold</b>');
  // after removing the tags this renderer itself emits, no < or > from the model's text is left
  const stripped = html.replace(/<\/?(?:p|strong|em|code|a|h[1-6]|ul|ol|li|table|thead|tbody|tr|th|td|pre|blockquote|br)(?:\s[^>]*)?>/g, "");
  assert.ok(!/[<>]/.test(stripped), "only the renderer's own tags are markup: " + stripped);
  assert.ok(html.includes("&lt;script&gt;alert(1)&lt;/script&gt;"));
  assert.ok(html.includes("&lt;b&gt;not bold&lt;/b&gt;"), "even in a heading, tags stay text");
  assert.ok(!/<b>/.test(html));
});

test("only http(s) links become anchors; javascript:, data: and relative links stay text", () => {
  const html = md("[a](javascript:alert(1)) [b](data:text/html,<script>) [c](https://ok.example/x?a=1&b=2) [d](http://ok.example) [e](/local) [f](ftp://x)");
  const hrefs = [...html.matchAll(/href="([^"]*)"/g)].map(m => m[1]);
  assert.deepEqual(hrefs, ["https://ok.example/x?a=1&amp;b=2", "http://ok.example"]);
  assert.ok(!/javascript:/i.test(html.replace(/&amp;/g, "&")) || !/<a[^>]*javascript/.test(html));
  assert.ok(!/<a[^>]*javascript/i.test(html) && !/<a[^>]*data:/i.test(html) && !/<a[^>]*ftp/i.test(html));
  assert.ok(html.includes("[a](javascript:alert(1))"), "an unsafe link is shown as written, not followed");
  assert.ok(html.includes("&lt;script&gt;") || html.includes("data:text/html"), "the data: link's text is escaped or plain");
  assert.match(html, /rel="noopener noreferrer"/);
});

test("a link's url cannot break out of the attribute, and a url with spaces is not a link at all", () => {
  const spaced = md('[**x**](https://ok.example/" onmouseover="alert(1))');
  assert.ok(!/<a[\s>]/.test(spaced), "a url with a space in it forms no anchor: " + spaced);
  assert.match(spaced, /<strong>x<\/strong>/);
  const html = md('[x](https://ok.example/"onmouseover="alert(1))');
  assert.ok(!/<a[^>]*onmouseover="/.test(html), "no raw attribute from the url: " + html);
  assert.match(html, /<a href="https:\/\/ok\.example\/&quot;onmouseover=&quot;alert\(1" target="_blank" rel="noopener noreferrer">x<\/a>/);
});

test("fenced code blocks keep their text escaped and unformatted", () => {
  const html = md("```\n<b>**not bold**</b>\n```");
  assert.match(html, /<pre><code>&lt;b&gt;\*\*not bold\*\*&lt;\/b&gt;<\/code><\/pre>/);
});

test("diffLines marks removals and additions and keeps the unchanged lines", () => {
  assert.deepEqual(plain(diff("a\nb\nc", "a\nx\nc")), [
    { type:"same", text:"a" }, { type:"del", text:"b" }, { type:"add", text:"x" }, { type:"same", text:"c" },
  ]);
  assert.deepEqual(plain(diff("", "new")), [{ type:"add", text:"new" }]);
  assert.deepEqual(plain(diff("old", "")), [{ type:"del", text:"old" }]);
  assert.deepEqual(plain(diff("same", "same")), [{ type:"same", text:"same" }]);
  // a big rewrite still diffs (fallback for huge texts shows removed then added)
  const big = diff("x".repeat(1), "y".repeat(600) + "\n" + "z".repeat(600));
  assert.ok(big.some(d => d.type === "add") && big.some(d => d.type === "del"));
});
