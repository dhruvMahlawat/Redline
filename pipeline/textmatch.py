import difflib

MATCH_THRESHOLD = 0.85  # allows for minor whitespace/newline differences, not much else


def find_quote(quote: str, document_text: str) -> tuple[bool, int]:
    """
    Checks whether a quote actually exists in the document, and if so, roughly where.
    Returns (found, char_index) - char_index is an offset into document_text (the
    original, non-normalized text), or -1 if not found.

    Tries an exact match on the raw text first, since that gives a precise offset.
    Only falls back to whitespace-normalized fuzzy matching for near-verbatim quotes
    (PDF line wraps, etc.) - in that case the offset is an approximation, scaled from
    the normalized text back onto the original, since the two texts don't line up
    character-for-character once whitespace is collapsed.
    """
    exact_index = document_text.find(quote)
    if exact_index != -1:
        return True, exact_index

    normalized_quote = " ".join(quote.split())
    normalized_doc = " ".join(document_text.split())

    exact_normalized_index = normalized_doc.find(normalized_quote)
    if exact_normalized_index != -1:
        ratio = exact_normalized_index / max(len(normalized_doc), 1)
        return True, int(ratio * len(document_text))

    matcher = difflib.SequenceMatcher(None, normalized_quote, normalized_doc)
    match = matcher.find_longest_match(0, len(normalized_quote), 0, len(normalized_doc))
    overlap_ratio = match.size / max(len(normalized_quote), 1)

    if overlap_ratio >= MATCH_THRESHOLD:
        position_ratio = match.b / max(len(normalized_doc), 1)
        return True, int(position_ratio * len(document_text))

    return False, -1
