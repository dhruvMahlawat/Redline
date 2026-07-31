# Redline

A tool that reads a rental lease and tells you the stuff that actually matters —
rent, deposit, notice period — plus anything worth double-checking, like a sketchy
auto-renewal clause or a fee that doesn't quite add up. Every fact is backed by the
exact line it came from, with the actual page shown (boxed, if it can be located
exactly), so you're never just taking its word for it.

## Results

On the 5-fixture synthetic eval set (`eval/run_eval.py`):

- **100% field accuracy** (10/10) on rent and deposit extraction
- **0% false-confidence rate** — every fact marked "high confidence" was actually correct
- Correctly found 0 red flags on clean leases, both planted red flags on the red-flag
  fixture, and didn't invent values on the blank template

This is a small, synthetic sample built to stress-test the verification logic, not a
claim of production-grade accuracy on real-world leases at scale — see "Does it
actually work?" below for how to reproduce it.

## The idea behind it

Anyone can paste a lease into ChatGPT and ask "summarize this." The problem is that
LLMs will happily hand you a confident, wrong answer, and you have no easy way to
tell the difference between a real extraction and a hallucinated one.

So instead of extract → show result, this does extract → **check the extraction
against the actual document** → only then show it. If something can't be verified,
it's labeled "needs human review" instead of presented as fact. That verification
step is really the whole point of this project — lease-parsing is just the excuse
to build it around something real.

## How it works

**1. Parse the PDF.** `pymupdf` pulls the text out. If a page comes back with almost
no text (a scanned photo of a lease, no real text layer), it falls back to OCR via
tesseract instead of giving up. A regex pass also tries to find section headings,
used only for display/page-tracking — never for what the AI actually reads.

**2. Extract facts with Groq/Gemini.** The full document text goes in with a schema —
rent, deposit, notice period, red flags — and every claim needs an exact quote. No
quote, no fact.

**3. Verify each quote**, two ways: does it actually exist in the document (catches
an invented citation), and does it actually support the claim (a second, separate
Groq/Gemini call, so it's not just agreeing with its own first answer).

**4. Show it honestly, with the receipts.** Passed both checks → shown with its page
number, clickable to see that page rendered with a box around the actual line.
Failed either check → flagged for a human instead of silently guessing.

There's a bug I hit and fixed worth mentioning: early on, clause-splitting was
deciding what text the AI got to see, and on some documents it quietly stripped
labels off values (a line like "Monthly Rent  $1,250" got split so the AI only saw
"$1,250," no label). Fixed by having the AI read the full raw text directly, and the
clause splitter is display-only now. `tests/test_parser.py` has a regression test
for it.

## Does it actually work? (eval)

`eval/` has 5 synthetic test leases with known correct answers — clean numbered,
clean unnumbered, one with two planted red flags, a blank template (checking it
doesn't invent values for empty fields), and the label-value layout that exposed the
bug above.

```bash
python3 eval/run_eval.py
```

Makes real Groq/Gemini calls (needs your key, costs a few cents). Paces itself between
fixtures and retries automatically if it hits Groq's/Gemini's free-tier rate limit — if
you're on the free tier, hitting that limit is expected, and the script handles it
instead of crashing. Reports field accuracy and, more
importantly, what fraction of "high confidence" facts were actually correct — that
number is the one that matters, since this tool is only as good as its confidence
labels being trustworthy.

## Running it

```bash
pip install -r requirements.txt
```

OCR needs the actual tesseract binary too, not just the Python wrapper:
```bash
# Ubuntu/Debian
sudo apt-get install tesseract-ocr
# Mac
brew install tesseract
```

```bash
cp .env.example .env   # add your Groq API key
python3 app.py
```

Go to `http://127.0.0.1:5000` and drag in a lease PDF.

It's not fast — two sequential AI calls means a real result takes several seconds.
That's the cost of not trusting the first answer blindly, and I'd rather it be a
little slow and honest than fast and occasionally wrong.

## Rate limiting

`/analyze` is capped at 10 requests/hour per IP, since each call makes 2 real Groq/Gemini
requests and I didn't want an open endpoint that could run up a bill. It's in-memory,
which means two honest caveats: the count resets if the server restarts, and if you
deploy with multiple workers, each worker counts separately (2 workers ≈ 20/hour in
practice, not 10). Fine for a small deployment; a real production setup would back
this with Redis instead.

## Tests

```bash
python3 -m pytest tests/
```

Covers parsing, OCR fallback, and quote-matching — the parts that don't need an API
call. Extraction/verification quality is covered by the eval instead, since testing
that meaningfully needs the real API.

## Deploying

There's a `Procfile` for Render/Railway/similar (`gunicorn --workers=2 --threads=4
--timeout=60`). The threads matter — gunicorn's default is 1 worker, 1 thread, which
would make every visitor wait in line behind whoever uploaded first. The longer
timeout is because two sequential Groq/Gemini calls can take a while on a longer lease,
and the default 30s can cut that off mid-request. Set `GROQ_API_KEY` as a real
environment variable on the platform, never in a committed file.

## What's here vs. what's just planned

Built: everything above — parse (with OCR fallback), extract, verify, page
citations with visual highlighting, rate limiting, eval, tests. In-memory only,
nothing saved to disk, in this free version.

Not built, just designed: a paid tier for businesses that would store leases in an
encrypted dashboard with logins. A deliberate opt-in tradeoff for teams that want
history over the free tier's zero-storage guarantee — future work, not faked here.

## Where it still breaks

- OCR is a decent fallback, not a great one — tesseract can still stumble on messy
  scans, tilted photos, or handwriting.
- The clause splitter (display-only) can still merge two adjacent short headings on
  unusual layouts. Cosmetic, not a correctness issue.
- Page numbers/boxes for fuzzy-matched quotes are approximate, not exact — see the
  comment in `pipeline/textmatch.py`.
- Rate limiting is per-IP and in-memory - not real abuse protection at scale, just
  enough to stop accidental cost blowouts on a small deployment.

## Stack

Flask, pymupdf, tesseract (via pytesseract), Groq (`groq`), Flask-Limiter,
vanilla JS for the drag-and-drop, pytest for tests. No database, no build step, no
frontend framework — kept it small on purpose.

## License

MIT License

Copyright (c) 2026 

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
