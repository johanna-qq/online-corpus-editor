"""
Custom FTS tokeniser and suffixer.

For our suffix table tokeniser, we have two modes: When search_mode is False,
all terms are expanded to their suffixes.  When search_mode is True, it acts
like the normal tokeniser.  (We don't want to get search results for *all*
the possible suffixes within the search terms.)
"""
import functools
import re

import oce.logger

logger = oce.logger.getLogger(__name__)

from oce.providers.sqlite.tokeniser_bindings import Tokenizer


class OCETokeniser(Tokenizer):
    """
    Custom tokeniser:
    1) Folds text to lower case
    2) Treats all non-alphanumeric ASCII chars as delimiters
    3) Each character outside the ASCII range is treated as one single
       token
    """

    def tokenize(self, text):
        """
        Expected to return an iterator over the tokens in `text`.
        """
        text = text.lower()
        list_tokens = self.tokenise_as_list(text)
        return iter(list_tokens)

    @functools.lru_cache(maxsize=128)
    def tokenise_as_list(self, text):
        """
        Memoised version of the tokeniser; returns a list instead of an
        iterator.  This cache should not need to be cleared; any
        modifications to the tokeniser will only take effect on restart
        """
        logger.debug('Running OCETokeniser: {}'.format(text))

        tokenised_list = []

        token_open = False
        token_start = 0
        token_end = 0
        for char in text:
            if re.match(r'[^a-zA-Z0-9]', char):
                # The character is non-alphanumeric.  If it is within the
                # ASCII range, close the current token and yield it.  If
                # not, yield it as a new token.
                if ord(char) <= 127:
                    if token_open:
                        # Was in token.  Yield token and advance cursors
                        # to next character.
                        token_open = False
                        tokenised_list.append(self.yield_token(text,
                                                               token_start,
                                                               token_end))
                        token_end += 1
                        token_start = token_end
                    else:
                        # Was not in token.  Advance cursors in tandem.
                        token_end += 1
                        token_start += 1
                else:
                    if token_open:
                        # Was in token.  Yield and advance start cursor.
                        token_open = False
                        tokenised_list.append(self.yield_token(text,
                                                               token_start,
                                                               token_end))
                        token_start = token_end

                    # Yield one more character (the non-ASCII one)
                    token_end += 1
                    tokenised_list.append(self.yield_token(text,
                                                           token_start,
                                                           token_end))
                    token_start = token_end
            else:
                # In a token.  Move the end cursor.
                token_open = True
                token_end += 1

        # Yield the last token
        if token_open:
            tokenised_list.append(self.yield_token(text,
                                                   token_start,
                                                   token_end))

        return tokenised_list


class OCESuffixes(Tokenizer):
    """
    Custom tokeniser:
    1) Runs against OCETokeniser to get tokenised input string.
    2) For each token in the input, returns the suffix array for that token
       if the token has length > 1

    UNLESS:
    1) If search_mode is True, returns only the output of OCETokeniser (
       so that we don't unnecessarily process search queries)
    """

    def __init__(self, main_tokeniser):
        self.main_tokeniser = main_tokeniser
        self.search_mode = False

    def tokenize(self, text):
        """
        Expected to return an iterator over the tokens in `text`.
        """
        text = text.lower()
        list_suffixes = self.suffixes_as_list(text, self.search_mode)
        return iter(list_suffixes)

    @functools.lru_cache(maxsize=128)
    def suffixes_as_list(self, text, search_mode):
        """
        Memoised version of the suffixer; returns a list instead of an
        iterator.  This cache should not need to be cleared; any
        modifications to the tokeniser will only take effect on restart
        """
        logger.debug(
            "Running OCESuffixer: {}, search_mode: {}".format(text,
                                                              search_mode)
        )

        # Perform any pre-processing that might be appropriate
        text = self._preprocess_text(text)

        # The start and end values given by OCETokeniser are in bytes,
        # but we prefer to work with characters; we'll convert them in the
        # loop.
        b_text = text.encode('utf-8')

        main_tokenised = self.main_tokeniser.tokenise_as_list(text)
        if search_mode:
            return main_tokenised

        tokenised_list = []
        for token, b_start, b_end in main_tokenised:
            if len(token) == 1:
                # One character token.  No need to extract suffixes.
                continue

            # Byte position -> Character position
            c_before = len(b_text[:b_start].decode('utf-8'))

            # Skip the first suffix (i.e., the whole token)
            c_start = c_before + 1
            c_end = c_before + len(token)
            for suffix_start in range(c_start, c_end):
                tokenised_list.append(self.yield_token(text,
                                                       suffix_start,
                                                       c_end))

        return tokenised_list

    def _preprocess_text(self, text):
        """
        Do stuff to the record before finding its suffixes.
        """
        # Try to remove the UUID part of URLs from Twitter's URL shortener.
        # (They gum up the suffix database with a whole bunch of
        # single-record entries)
        # http://t.co/<UUID>
        text = re.sub(r'http://t[.]co/[a-zA-Z0-9]+', 'http://t.co/', text)

        return text
