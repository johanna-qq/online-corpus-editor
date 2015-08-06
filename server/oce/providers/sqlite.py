"""
A data provider that interacts with an SQLite database using SQLAlchemy's ORM
functionality.

When writing new memoised functions, be sure to reference them in
_clear_caches() so that they can be reset when the DB is updated.
"""
import functools
import sqlalchemy
import sqlalchemy.dialects
import sqlalchemy.orm
import sqlalchemy.sql.expression
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext.declarative.api

import re
import sqlite3
import timeit

import oce.exceptions
import oce.logger

logger = oce.logger.getLogger(__name__)

from oce.providers.template import DataProvider
from oce.providers.util import SQLAlchemyORM
from oce.providers.util import fts_tag, fts_detag
from oce.providers.util import langid_normalise_language

Records = SQLAlchemyORM.Records
RecordsFTS = SQLAlchemyORM.RecordsFTS
RecordCount = SQLAlchemyORM.RecordCount
RecordTags = SQLAlchemyORM.RecordTags

from oce.providers.sqlite_tokeniser import make_tokenizer_module
from oce.providers.sqlite_tokeniser import Tokenizer
from oce.providers.sqlite_tokeniser import register_tokenizer

from oce.providers.sqlite_schema import db_schema


class SQLiteProvider(DataProvider):
    # Startup/Shutdown
    def __init__(self, address):
        super().__init__(address)
        self.db_file = address

        # Figure out whether our SQLite supports the FTS Enhanced Query Syntax
        # (Although it almost definitely should, considering we bundle SQLite)
        self.enhanced_query_syntax = False
        compile_options = (sqlite3
                           .connect(':memory:')
                           .cursor()
                           .execute("PRAGMA compile_options")
                           .fetchall()
                           )
        for option in compile_options:
            if option[0] == "ENABLE_FTS3_PARENTHESIS":
                self.enhanced_query_syntax = True

        # Prep the DB connection
        self.engine = sqlalchemy.create_engine('sqlite:///' + self.db_file)
        sqlalchemy.event.listen(self.engine, 'connect', self._setup_connection)
        self.engine.connect()

        # ... and the ORM session
        self.session = sqlalchemy.orm.sessionmaker(bind=self.engine)()
        logger.info(
            "SQLite data provider initialised. ({0})".format(self.db_file)
        )

    def shutdown(self):
        self.session.commit()
        self.session.close()
        logger.info("SQLite data provider shut down.")

    # Metadata
    def fetch_total(self):
        return self.session.query(RecordCount.count).scalar()

    def fetch_tags(self):
        return [x[0] for x in
                self.session.query(RecordTags.tag).order_by(RecordTags.tag)]

    # Selection
    def fetch_record(self, row_id):
        return self.session.query(Records) \
            .filter(Records.rowid == row_id).one().dictionary

    def fetch_records(self, first, last):
        return [row.dictionary for row in self.session.query(Records).filter(
            Records.rowid.between(first, last)).order_by(Records.rowid)]

    def fetch_search_results(self, query, offset=0, limit=0):
        start_time = timeit.default_timer()

        # Pre-process the query

        # [Illegal characters and other invalid queries]
        # If there's an odd number of double inverted commas, drop the last one
        commas = re.findall('"', query)
        if len(commas) % 2 == 1:
            query = ''.join(query.rsplit(sep="\"", maxsplit=1))

        # [Special commands]
        # We will return the query to the client, including canonical forms of
        # special commands
        query, return_query = self._process_query(query)

        logger.info("Searching for '{0}'.".format(query))

        try:
            # Get the results for the query, hitting the memoisation caches
            # if we can.
            count = self._cached_search_results_count(query)
            logger.debug(self._cached_search_results_count.cache_info())

            results = self._cached_search_results(query, offset, limit)
            logger.debug(self._cached_search_results.cache_info())

            elapsed = "{:.3f}".format(timeit.default_timer() - start_time)
            return {'total': count, 'results': results, 'query': return_query,
                    'elapsed': elapsed, 'offset': offset}
        except sqlalchemy.exc.SQLAlchemyError as e:
            # Whoops.
            logger.error(e)
            return {'total': 0, 'results': 'error'}

    # Modification
    # TODO: This doesn't conform to the API spec yet.
    def update_record(self, row_id, field, value):
        try:
            for row in self.session.query(Records) \
                    .filter(Records.rowid == row_id):

                # ====================
                # Field-specific hooks
                # ====================
                # Process record tags to update tweets_tags table
                if field == 'tag':
                    old_tags = fts_detag('tag', row.tag)
                    self._update_tags(value, old_tags)
                elif field == 'language':
                    value = langid_normalise_language(value)
                # ====================

                # Add FTS tags if needed
                value = fts_tag(field, value)
                logger.info("Updating '{0}' on row {1}: {2} -> {3}"
                            .format(field,
                                    row.rowid,
                                    str(getattr(row, field)).replace('\n',
                                                                     '\\n'),
                                    str(value).replace('\n', '\\n')
                                    ))
                setattr(row, field, value)

                self.session.commit()

            # Also clear all memoisation caches, in case the update
            # invalidates their results
            self._clear_caches()

            return 'success'
        except sqlalchemy.exc.SQLAlchemyError as e:
            # Uh oh.
            logger.error(e)
            return 'error'

    # Literal SQL
    def execute_orm_filter(self, where_conditions, table="Records"):
        """
        Executes a select on the specified table with a literal where clause.
        Uses the SQLAlchemy ORM, so results are dictionaries.
        """
        try:
            _table = globals()[table]
            if not isinstance(_table,
                              sqlalchemy.ext.declarative.api.DeclarativeMeta):
                raise KeyError
        except KeyError:
            # The specified table wasn't properly defined.
            logger.error(
                "Could not find ORM mappings for table: {}".format(table)
            )
            return "error"

        return [row.dictionary for row in
                self.session.query(_table).filter(
                    sqlalchemy.sql.expression.text(where_conditions))]

    def execute_literal(self, query, limit=0):
        """
        Executes a literal sql query on the DB.
        Bypasses the ORM, so results are tuples.
        Raises an error if the result set is larger than limit, if limit is
        specified.
        """
        start_time = timeit.default_timer()
        try:
            results, time = self._execute_literal_statements([query])
            if 0 < limit < len(results):
                raise oce.exceptions.CustomError(
                    "Too many results from literal SQL query.\r\n"
                    "(Got {}, limit was {})\r\n"
                    "Took {:.3f}s.".format(len(results), limit, time)
                )
            return results, time
        except Exception as e:
            return ("Server returned a message after {:.3f}s:\r\n"
                    "{}\r\n".format(timeit.default_timer() - start_time,
                                    str(e))
                    )

    # Database structure
    def execute_drop(self, target):
        """
        Drops various DB structures on request
        """
        start_time = timeit.default_timer()
        try:
            statements = []
            if target == "fts":
                statements += db_schema["drop_fts"]
            elif target == "suffixes":
                statements += db_schema["drop_suffixes"]
            elif target == "triggers":
                statements += db_schema["drop_triggers"]
            elif target == "all":
                statements += db_schema["drop_fts"]
                statements += db_schema["drop_suffixes"]
                statements += db_schema["drop_triggers"]
            else:
                raise oce.exceptions.CustomError(
                    "'{}' was not recognised as a valid target.\r\n"
                    "Options are:\r\n"
                    "fts suffixes triggers all".format(target)
                )

            results, time = self._execute_literal_statements(statements)

            return results, time
        except Exception as e:
            return ("Server returned a message after {:.3f}s:\r\n"
                    "{}\r\n".format(timeit.default_timer() - start_time,
                                    str(e))
                    )

    def execute_recreate(self, target):
        """
        Recreates various DB structures on request
        """
        start_time = timeit.default_timer()
        try:
            statements = []
            if target == "fts":
                statements += db_schema["drop_fts"]
                statements += db_schema["create_fts"]
            elif target == "suffixes":
                statements += db_schema["drop_suffixes"]
                statements += db_schema["create_suffixes"]
            elif target == "triggers":
                statements += db_schema["drop_triggers"]
                statements += db_schema["create_triggers"]
            elif target == "all":
                statements += db_schema["drop_fts"]
                statements += db_schema["create_fts"]
                statements += db_schema["drop_suffixes"]
                statements += db_schema["create_suffixes"]
                statements += db_schema["drop_triggers"]
                statements += db_schema["create_triggers"]
            else:
                raise oce.exceptions.CustomError(
                    "'{}' was not recognised as a valid target.\r\n"
                    "Options are:\r\n"
                    "fts suffixes triggers all".format(target)
                )

            results, time = self._execute_literal_statements(statements)

            return results, time
        except Exception as e:
            return ("Server returned a message after {:.3f}s:\r\n"
                    "{}\r\n".format(timeit.default_timer() - start_time,
                                    str(e))
                    )

    # ===============
    # Private helpers
    # ===============
    def _process_query(self, query):
        if self.enhanced_query_syntax:
            # Maybe do something differently?
            pass

        query_words = query.split()
        query = ''
        return_query = ''

        # If all the search terms are negative, we'll force a full table scan
        # (SQLite FTS does not support searching for only negative terms)
        found_positive = False

        for word in query_words:
            # The FTS engine doesn't care about case, except where the word is
            # one of the query syntax keywords, which should always be in
            # uppercase
            if word != "OR" and word != "AND" and word != "NOT":
                word = word.lower()

            if word == 'is:commented' or word == 'has:comment':
                query += 'comment:cmt '
                return_query += 'has:comment '
                found_positive = True
            elif word == 'is:flagged' or word == 'has:flag':
                query += 'flag:1 '
                return_query += 'is:flagged '
                found_positive = True
            elif word == 'is:tagged' or word == 'has:tag':
                query += 'tag:tags '
                return_query += 'has:tag '
                found_positive = True
            elif word == 'has:language' or word == 'has:lang':
                query += 'language:lang '
                return_query += 'has:language '
                found_positive = True
            elif word.startswith("lang:"):
                language = word.split("lang:", 1)[1]
                query = query + "language:" + language + " "
                return_query = return_query + "language:" + language + " "
                found_positive = True
            elif word == '&':
                # Not needed, and FTS does not search for literal &s anyway
                continue
            else:
                # Look at the start of the term or after a filter for a NOT
                # operator
                negs = re.findall(r'(^-|:-)', word)
                if len(negs) == 0:
                    found_positive = True
                query = query + word + ' '
                return_query = return_query + word + ' '

        if not found_positive:
            query += 'fullscan:1'

        # Final check for Enhanced Query Syntax
        if query.startswith("NOT "):
            query = 'fullscan:1 {0}'.format(query)

        return [query.strip(), return_query.strip()]

    def _update_tags(self, new_tags, old_tags):
        """
        Given comma-delimited lists of record tags, update the RecordTags table.
        :param new_tags:
        :param old_tags:
        :return:
        """
        # Start by preparing the lists of old and new record tags
        if new_tags == '':
            # Splitting the empty string will give us an array with one (empty)
            # element, which we don't want
            new_tags = []
        else:
            new_tags = new_tags.split(',')
        if old_tags == '':
            old_tags = []
        else:
            old_tags = old_tags.split(',')

        added = [x for x in new_tags if x not in old_tags]
        removed = [x for x in old_tags if x not in new_tags]

        # Start by looking at the tags that were added
        for tag in added:
            rows = self.session.query(RecordTags) \
                .filter(RecordTags.tag == tag).all()
            if len(rows) == 0:
                # This is a completely new tag.
                self.session.add(RecordTags(tag=tag, count=1))
            else:
                # Tag is already in the DB -- Update the count.
                row = rows[0]
                row.count += 1
            self.session.commit()

        # Deal with the tags that were removed next
        for tag in removed:
            rows = self.session.query(RecordTags) \
                .filter(RecordTags.tag == tag).all()
            if len(rows) == 0:
                # Woah, this shouldn't have happened.
                logger.warning(
                    ("Tried to remove tag that isn't in DB: {0}. "
                     "Ignoring.").format(tag))
            else:
                row = rows[0]
                row.count -= 1
                if row.count == 0:
                    # Remove the row entirely.
                    self.session.delete(row)
                self.session.commit()

    def debug(self):
        pass

    @functools.lru_cache(maxsize=128)
    def _cached_search_results_count(self, query):
        """
        Memoise the relatively expensive count() function on search results
        `query` should be the actual query string.
        """
        search = self.session.query(RecordsFTS.docid)
        filter_string = RecordsFTS.__tablename__ + " MATCH :text"
        search = search.filter(
            sqlalchemy.sql.expression.text(filter_string)
        ).params(
            text=query
        ).order_by(RecordsFTS.docid)
        return search.count()

    @functools.lru_cache(maxsize=128)
    def _cached_search_results(self, query, offset, limit):
        """
        Memoised call to get the results of a search query; useful when the
        user is thumbing through the results pages without making modifications.
        """
        # Prepare the FTS subquery: We'll only select docid to prevent
        # loading everything to memory (docid can be taken straight from
        # the FTS index)
        # Rough benchmarking -- Search times for query "a*"
        # 1) Ordering on `rowid` instead of `docid`: 21.986s
        # 2) Ordering on `docid` but without limiting subquery: 7.049s
        # 3) Ordering on `docid` with limited subquery: 3.538s
        search = self.session.query(RecordsFTS.docid)
        filter_string = RecordsFTS.__tablename__ + " MATCH :text"
        search = search.filter(
            sqlalchemy.sql.expression.text(filter_string)
        ).params(
            text=query
        ).order_by(RecordsFTS.docid)

        if offset > 0:
            search = search.offset(offset)
        if limit > 0:
            search = search.limit(limit)
        search = search.subquery()

        # And now the main query
        main = self.session.query(Records) \
            .join(search, Records.rowid == search.c.docid) \
            .order_by(Records.rowid)

        return [row.dictionary for row in main]

    def _clear_caches(self):
        """
        Clear all memoisation caches that are in use
        """
        self._cached_search_results_count.cache_clear()
        self._cached_search_results.cache_clear()

    def _setup_connection(self, db_connection, _):
        """
        Sets up custom functions and the like when the DB connection is
        initialised.
        """
        # Initialise our custom tokenisers
        main_tokeniser = self.OCETokeniser()
        tokeniser_module = make_tokenizer_module(main_tokeniser)
        register_tokenizer(db_connection, 'oce', tokeniser_module)
        suffix_module = make_tokenizer_module(self.OCESuffixes(main_tokeniser))
        register_tokenizer(db_connection, 'oce_suffixes', suffix_module)

    class OCETokeniser(Tokenizer):
        """
        Custom tokeniser:
        1) Folds text to lower case
        2) Treats all non-alphanumeric ASCII chars as delimiters
        3) Each character outside the ASCII range is treated as one single
           token
        """

        @functools.lru_cache(maxsize=256)
        def _tokenize(self, text):
            """
            Memoised version of the tokeniser; returns a list instead of an
            iterator.  This cache should not need to be cleared; any
            modifications to the tokeniser will only take effect on restart
            """
            logger.debug('Tokenising: {}'.format(text))

            tokenised_list = []
            text = text.lower()

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

                        # Yield one more character
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

        def tokenize(self, text):
            """
            Reads along the given string, yielding tokens along the way.
            Memoises the results of the tokenisation to minimise calculations.
            """
            iterator_list = self._tokenize(text)
            return iter(iterator_list)

    class OCESuffixes(Tokenizer):
        """
        Custom tokeniser:
        1) Runs against OCETokeniser to get tokenised input string.
        2) For each token in the input, returns the suffix array for that token
           if the token has length > 1
        """

        def __init__(self, main_tokeniser):
            self.records_processed = 0
            self.columns_processed = 0
            self.main_tokeniser = main_tokeniser

        def tokenize(self, text):
            # We want our output to be lowercase as well, but we'll feed
            # main_tokeniser the original input so that memoisation works
            lower_text = text.lower()
            b_text = lower_text.encode('utf-8')

            for token, b_start, b_end in self.main_tokeniser.tokenize(text):
                if len(token) == 1:
                    # One character token.  No need to extract suffixes.
                    continue

                # The start and end values given by OCETokeniser are in
                # bytes. Convert them to characters.
                c_before = len(b_text[:b_start].decode('utf-8'))

                # Skip the first suffix (i.e., the whole token)
                c_start = c_before + 1
                c_end = c_before + len(token)
                for suffix_start in range(c_start, c_end):
                    yield self.yield_token(lower_text, suffix_start, c_end)

            self.columns_processed += 1
            if self.columns_processed == 7:
                self.records_processed += 1
                self.columns_processed = 0
            logger.debug(
                "OCESuffixes has looked at: "
                "{} records, {} cols.".format(
                    self.records_processed,
                    self.columns_processed)
            )

    def _execute_literal_statements(self, statements):
        """
        Given a List of single SQL statements to execute, does so.
        """
        start_time = timeit.default_timer()
        try:
            assert (type(statements) is list and len(statements) > 0)
            results = []

            with self.engine.begin() as connection:
                for statement in statements:
                    raw = connection.execute(statement)
                    if raw.returns_rows:
                        results += raw.fetchall()

            time = "{:.3f}".format(timeit.default_timer() - start_time)
            return results, float(time)

        except Exception as e:
            logger.debug(e)
            raise e
