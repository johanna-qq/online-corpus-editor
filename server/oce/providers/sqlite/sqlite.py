"""
A data provider that interacts with an SQLite database using SQLAlchemy's ORM
functionality.

When writing new memoised functions, be sure to reference them in
_clear_caches() so that they can be reset when the DB is updated.
"""
import functools
import re
import sqlite3
import timeit

import sqlalchemy
import sqlalchemy.dialects
import sqlalchemy.orm
import sqlalchemy.sql.expression
import sqlalchemy.event
import sqlalchemy.exc
import sqlalchemy.ext.declarative.api

import oce.exceptions
import oce.logger

logger = oce.logger.getLogger(__name__)

from oce.config import debug_mode

from oce.providers.template import DataProvider
from oce.providers.util import SQLAlchemyORM
from oce.providers.util import fts_tag, fts_detag
from oce.providers.util import langid_normalise_language

Records = SQLAlchemyORM.Records
RecordsFTS = SQLAlchemyORM.RecordsFTS
RecordsSuffixes = SQLAlchemyORM.RecordsSuffixes
RecordCount = SQLAlchemyORM.RecordCount
RecordTags = SQLAlchemyORM.RecordTags

from oce.providers.sqlite.bindings import make_tokenizer_module
from oce.providers.sqlite.bindings import register_tokenizer

from oce.providers.sqlite.tokenisers import OCETokeniser, OCESuffixes

from oce.providers.sqlite.db_schema import db_schema


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

        # SQLAlchemy calls _setup_connection() multiple times, so we need to
        # make sure it always uses the same tokeniser instances.
        self.main_tokeniser = OCETokeniser()
        self.suffix_tokeniser = OCESuffixes(self.main_tokeniser)

        # Prep the DB connection
        self.engine = sqlalchemy.create_engine('sqlite:///' + self.db_file)
        sqlalchemy.event.listen(self.engine, 'connect',
                                self._setup_connection)
        self.engine.connect()

        # ... and the ORM session
        self.session = sqlalchemy.orm.sessionmaker(bind=self.engine)()
        logger.info(
            "SQLite data provider initialised. ({0})".format(self.db_file)
        )

        if debug_mode:
            self.debug()

    def shutdown(self):
        self.session.commit()
        self.session.close()
        logger.info("SQLite data provider shut down.")

    # Provider administration

    def get_config(self):
        config = [
            {
                "desc": "DB file in use:",
                "value": self.db_file,
                "read_only": True
            },
            {
                "desc": "FTS uses Enhanced Query Syntax:",
                "value": self.enhanced_query_syntax,
                "read_only": True
            },
            {
                "name": "suffix_search",
                "desc": "Is suffixer in search mode?",
                "value": self.suffix_tokeniser.search_mode,
                "read_only": False
            }
        ]
        return config

    def set_config(self, option, value):
        if option == "suffix_search":
            if value.lower() == "false":
                self.suffix_tokeniser.search_mode = False
                return [option, False]
            elif value.lower() == "true":
                self.suffix_tokeniser.search_mode = True
                return [option, True]
            else:
                return option, "invalid_value"
        else:
            return option, "invalid_option"

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

    def fetch_records(self, first=None, last=None):
        """
        Fetches records from the Records table, with optional start/end rowids.
        """
        query = self.session.query(Records)
        if first is None and last is not None:
            query = query.filter(Records.rowid <= last)
        elif first is not None and last is None:
            query = query.filter(Records.rowid >= first)
        elif first is not None and last is not None:
            query = query.filter(Records.rowid.between(first, last))
        return [row.dictionary for row in query.order_by(Records.rowid)]

    def fetch_search_results(self, query, offset=0, limit=0):
        start_time = timeit.default_timer()

        # Pre-process the query.
        # We will return the query to the client, including canonical forms of
        # special commands.
        return_query, fts_query, suffixes_query, suffixes_full_terms = \
            self._process_query(query)

        logger.info(
            "Searching -- FTS:'{}', Suffixes:'{}'.".format(fts_query,
                                                           suffixes_query)
        )

        try:
            # Get the results for the query, hitting the memoisation caches
            # if we can.
            count = self._cached_search_results_count(fts_query,
                                                      suffixes_query,
                                                      suffixes_full_terms)
            results = self._cached_search_results(fts_query,
                                                  suffixes_query,
                                                  suffixes_full_terms,
                                                  offset,
                                                  limit)
            elapsed = "{:.3f}".format(timeit.default_timer() - start_time)
            return {'total': count, 'results': results, 'query': return_query,
                    'elapsed': elapsed, 'offset': offset}
        except (sqlalchemy.exc.SQLAlchemyError,
                oce.exceptions.CustomError) as e:
            # Whoops.
            logger.error(e)
            return {'total': 0, 'results': 'error'}

    # Modification
    # TODO: This doesn't conform to the API spec yet.
    def update_record(self, row_id, field, value):
        try:
            for row in self.session.query(Records) \
                    .filter(Records.rowid == row_id):

                if not hasattr(row, field):
                    logger.warning(
                        "Invalid field name given by client: '{}'".format(
                            field
                        )
                    )
                    return 'invalid_field'

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

    def execute_retag(self, old_tag, new_tag):
        """
        Replaces the old tag with the new one on all applicable records.
        """
        if re.search(r',', "{}{}".format(old_tag, new_tag)):
            logger.error("Asked to create a tag that contains a comma.  "
                         "Aborting.")
            return 'error'
        search = self.fetch_search_results("tag:{}".format(old_tag))
        records = [(x['rowid'], x['tag']) for x in search['results']]
        for rowid, tag in records:
            new_tags = tag.split(",")
            new_tags[new_tags.index(old_tag)] = new_tag
            new_tags = ','.join(new_tags)
            self.update_record(rowid, 'tag', new_tags)
        return 'success'

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
        """
        Reads in a user-provided search query string, and prepares the
        corresponding FTS MATCH terms.  Gets a bit messy because we're
        accounting for both Standard Query Syntax and Enhanced Query Syntax
        at the same time.
        """

        # [Illegal characters and other invalid queries]
        # If there's an odd number of double inverted commas, drop the last one
        commas = re.findall('"', query)
        if len(commas) % 2 == 1:
            query = ''.join(query.rsplit(sep="\"", maxsplit=1))
        # Replace consecutive asterisks with a single asterisk
        query = re.sub(r'[*][*]', "*", query)

        # Begin processing the query proper.
        query_words = query.split()

        return_query = ''
        fts_query = ''
        suffixes_query = ''
        suffixes_full_terms = ''

        # If all the search terms are negative, we'll force a full table scan
        # (SQLite FTS does not support searching for only negative terms)
        suffixes_found_positive = False
        fts_found_positive = False
        suffixes_full_found_positive = False
        prev_was_not = False

        for word in query_words:
            # The FTS engine doesn't care about case, except where the word is
            # one of the query syntax keywords, which should always be in
            # uppercase
            query_operators = {"OR", "AND", "NOT", "NEAR"}
            if True not in {word.startswith(x) for x in query_operators}:
                word = word.lower()

            # ===================
            #   Suffix Handling
            # ===================
            # If the word is NOT, we have to watch what comes next; if the
            # next term is a suffix query, the NOT should stick with it.
            if word == "NOT":
                prev_was_not = True
                continue

            # Intercept terms that should be queried against the suffixes table.
            # We also run the full term against the FTS table; if not,
            # queries like "*copula" will not match the word 'copula'
            # (because the asterisk _needs_ to match something for the
            # suffixes table.)
            suffix_re = r'^([a-zA-Z0-9]+[:])?(-)?([*][a-zA-Z0-9]+[*]?)$'
            suffixes = re.findall(suffix_re, word)
            if len(suffixes) > 0:
                # https://blog.kapeli.com/sqlite-fts-contains-and-suffix-matches
                # ^^^ has a good description of how the suffix table queries
                # look
                field = suffixes[0][0]
                neg = suffixes[0][1]
                term = suffixes[0][2]

                if neg == '-' or prev_was_not:
                    if self.enhanced_query_syntax:
                        return_query += "NOT {}{} ".format(field, term)
                        suffixes_query += "NOT {}{} ".format(field, term[1:])
                        suffixes_full_terms += "NOT {}{}".format(field,
                                                                 term[1:])
                    else:
                        return_query += "{}-{} ".format(field, term)
                        suffixes_query += "{}-{} ".format(field, term[1:])
                        suffixes_full_terms += "{}-{}".format(field, term[1:])
                else:
                    return_query += "{}{} ".format(field, term)
                    suffixes_query += "{}{} ".format(field, term[1:])
                    suffixes_found_positive = True
                    suffixes_full_terms += "{}{} ".format(field, term[1:])
                    suffixes_full_found_positive = True

                prev_was_not = False
                continue
            # ===================

            # Now we know the NOT goes in the FTS query.  Make sure we don't
            # have a double negative in our query.

            # This will be inserted into every term; if using Enhanced
            # syntax, it will remain empty (and have no effect).  If using
            # Standard syntax, it will be set to '-'.
            standard_not = ""

            parts = re.findall(r'^([a-zA-Z0-9]+:)?(-)?(.+)$', word)
            field = parts[0][0]
            neg = parts[0][1]
            term = parts[0][2]

            if neg == '-' or prev_was_not:
                if self.enhanced_query_syntax:
                    return_query += "NOT "
                    fts_query += "NOT "
                    word = "{}{}".format(field, term)
                else:
                    standard_not = "-"
                    word = "{}{}".format(field, term)
            else:
                fts_found_positive = True

            # As a final step, special keywords are processed.
            if word == 'is:commented' or word == 'has:comment':
                return_query += 'has:{}comment '.format(standard_not)
                fts_query += 'comment:{}cmt '.format(standard_not)
            elif word == 'is:flagged' or word == 'has:flag':
                return_query += 'is:{}flagged '.format(standard_not)
                fts_query += 'flag:{}1 '.format(standard_not)
            elif word == 'is:tagged' or word == 'has:tag':
                return_query += 'has:{}tag '.format(standard_not)
                fts_query += 'tag:{}tags '.format(standard_not)
            elif word == 'has:language' or word == 'has:lang':
                return_query += 'has:{}language '.format(standard_not)
                fts_query += 'language:{}lang '.format(standard_not)
            elif word.startswith("lang:"):
                language = word.split("lang:", 1)[1]
                return_query += "language:{}{} ".format(standard_not, language)
                fts_query += "language:{}{} ".format(standard_not, language)
            elif word == '&':
                # Not needed, and FTS does not search for literal &s anyway
                continue
            else:
                return_query += "{} ".format(word)
                fts_query += "{} ".format(word)

            prev_was_not = False
            continue

        # ***************************************************************
        # Finished looking at all search terms.  See if we need to invoke
        # 'fullscan:1'
        if self.enhanced_query_syntax:
            if fts_query.startswith("NOT "):
                fts_query = "fullscan:1 {}".format(fts_query)
            if suffixes_query.startswith("NOT "):
                suffixes_query = "fullscan:1 {}".format(suffixes_query)
            if suffixes_full_terms.startswith("NOT "):
                suffixes_full_terms = "fullscan:1 {}".format(
                    suffixes_full_terms
                )
        else:
            if not fts_found_positive:
                fts_query += 'fullscan:1'
            if not suffixes_found_positive:
                suffixes_query += 'fullscan:1'
            if not suffixes_full_found_positive:
                suffixes_full_terms += 'fullscan:1'
        # ***************************************************************

        return (return_query.strip(), fts_query.strip(),
                suffixes_query.strip(), suffixes_full_terms.strip())

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
        """
        Runs arbitrary debug commands on the open DB
        """
        pass

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

    @functools.lru_cache(maxsize=128)
    def _cached_search_results_count(self, fts_query, suffixes_query,
                                     suffixes_full_terms):
        """
        Memoise the relatively expensive count() function on search results
        """
        # Make sure suffixer is in search_mode, just in case we need to use it
        prev_mode = self.suffix_tokeniser.search_mode
        self.suffix_tokeniser.search_mode = True

        # Prepare and join up the fts/suffix queries as appropriate
        search = None
        fts = None
        suffixes = None

        if fts_query != '':
            fts = self.session.query(RecordsFTS.docid)
            fts_filter = "{} MATCH :fts".format(
                RecordsFTS.__tablename__
            )
            fts = fts.filter(
                sqlalchemy.sql.expression.text(fts_filter)
            ).params(
                fts=fts_query
            ).order_by(RecordsFTS.docid)

        if suffixes_query != '':
            if suffixes_full_terms == '':
                # This shouldn't be happening; the full suffix terms should
                # always be passed along with a suffix query.
                raise oce.exceptions.CustomError("Suffix query requested, "
                                                 "but full suffix term not "
                                                 "given.")

            suffixes = self.session.query(RecordsSuffixes.docid)
            suffixes_filter = "{} MATCH :suffixes".format(
                RecordsSuffixes.__tablename__
            )
            suffixes = suffixes.filter(
                sqlalchemy.sql.expression.text(suffixes_filter)
            ).params(
                suffixes=suffixes_query
            )

            suffixes_full = self.session.query(RecordsFTS.docid)
            suffixes_full_filter = "{} MATCH :suffixes_full".format(
                RecordsFTS.__tablename__
            )
            suffixes_full = suffixes_full.filter(
                sqlalchemy.sql.expression.text(suffixes_full_filter)
            ).params(
                suffixes_full=suffixes_full_terms
            )

            suffixes = suffixes.union(
                suffixes_full
            ).order_by(
                sqlalchemy.sql.expression.text("1")
            )

        if fts is not None and suffixes is None:
            search = fts
        elif fts is not None and suffixes is not None:
            suffixes = suffixes.subquery()
            search = fts.join(suffixes, RecordsFTS.docid == suffixes)
        elif fts is None and suffixes is not None:
            search = suffixes
        elif fts is None and suffixes is None:
            # Uh-oh, this shouldn't be happening -- Even if the user passes
            # an empty string, the pre-processor should have given us an
            # fts_query of 'fullscan:1'
            raise oce.exceptions.CustomError("FTS requested on empty string "
                                             "without specifying 'fullscan:1'.")

        count = search.count()
        self.suffix_tokeniser.search_mode = prev_mode
        return count

    @functools.lru_cache(maxsize=128)
    def _cached_search_results(self, fts_query, suffixes_query,
                               suffixes_full_terms, offset, limit):
        """
        Memoised call to get the results of a search query; useful when the
        user is thumbing through the results pages without making modifications.
        """
        # For the various FTS subqueries, we'll only select docid to prevent
        # loading everything to memory (docid can be taken straight from
        # the FTS index)
        # Rough benchmarking -- Search times for query "a*"
        # 1) Ordering on `rowid` instead of `docid`: 21.986s
        # 2) Ordering on `docid` but without limiting subquery: 7.049s
        # 3) Ordering on `docid` with limited subquery: 3.538s

        # Make sure suffixer is in search_mode, just in case we need to use it
        prev_mode = self.suffix_tokeniser.search_mode
        self.suffix_tokeniser.search_mode = True

        # Prepare and join up the fts/suffix queries as appropriate
        search = None
        fts = None
        suffixes = None

        if fts_query != '':
            fts = self.session.query(RecordsFTS.docid)
            fts_filter = "{} MATCH :fts".format(
                RecordsFTS.__tablename__
            )
            fts = fts.filter(
                sqlalchemy.sql.expression.text(fts_filter)
            ).params(
                fts=fts_query
            ).order_by(RecordsFTS.docid)

        if suffixes_query != '':
            if suffixes_full_terms == '':
                # This shouldn't be happening; the full suffix terms should
                # always be passed along with a suffix query.
                raise oce.exceptions.CustomError("Suffix query requested, "
                                                 "but full suffix term not "
                                                 "given.")

            suffixes = self.session.query(RecordsSuffixes.docid)
            suffixes_filter = "{} MATCH :suffixes".format(
                RecordsSuffixes.__tablename__
            )
            suffixes = suffixes.filter(
                sqlalchemy.sql.expression.text(suffixes_filter)
            ).params(
                suffixes=suffixes_query
            )

            suffixes_full = self.session.query(RecordsFTS.docid)
            suffixes_full_filter = "{} MATCH :suffixes_full".format(
                RecordsFTS.__tablename__
            )
            suffixes_full = suffixes_full.filter(
                sqlalchemy.sql.expression.text(suffixes_full_filter)
            ).params(
                suffixes_full=suffixes_full_terms
            )

            suffixes = suffixes.union(
                suffixes_full
            ).order_by(
                sqlalchemy.sql.expression.text("1")
            )

        if fts is not None and suffixes is None:
            search = fts
        elif fts is not None and suffixes is not None:
            suffixes = suffixes.subquery()
            search = fts.join(suffixes, RecordsFTS.docid == suffixes)
        elif fts is None and suffixes is not None:
            search = suffixes
        elif fts is None and suffixes is None:
            # Uh-oh, this shouldn't be happening -- Even if the user passes
            # an empty string, the pre-processor should have given us an
            # fts_query of 'fullscan:1'
            raise oce.exceptions.CustomError("FTS requested on empty string "
                                             "without specifying 'fullscan:1'.")

        if offset > 0:
            search = search.offset(offset)
        if limit > 0:
            search = search.limit(limit)

        search = search.subquery()
        # Some hacky bits here to perform the join properly on the columns
        # (The exact column name varies based on whether or not a suffix
        # search was performed, and SQLAlchemy doesn't seem to support
        # joining by column order)
        column_id = list(search.c.keys())[0]

        # And now the main query
        main = self.session.query(Records) \
            .join(search, Records.rowid == search.c[column_id]) \
            .order_by(Records.rowid)

        results = [row.dictionary for row in main]
        print(len(results))
        self.suffix_tokeniser.search_mode = prev_mode
        return results

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
        Run multiple times by the engine.
        """
        # Register the instance's tokenisers with the DB connection.
        register_tokenizer(db_connection, 'oce',
                           make_tokenizer_module(self.main_tokeniser))
        register_tokenizer(db_connection, 'oce_suffixes',
                           make_tokenizer_module(self.suffix_tokeniser))
