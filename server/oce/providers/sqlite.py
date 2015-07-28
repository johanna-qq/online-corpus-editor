"""
A data provider that interacts with an SQLite database using SQLAlchemy's ORM
functionality
"""
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.sql.expression
import sqlalchemy.exc

import re
import timeit

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


class SQLiteProvider(DataProvider):
    # Startup/Shutdown
    def __init__(self, address):
        self.db_file = address
        self.engine = sqlalchemy.create_engine('sqlite:///' + self.db_file)
        self.session = sqlalchemy.orm.sessionmaker(bind=self.engine)()
        logger.info("SQLite data provider initialised -- No connections made "
                    "yet. ({0})".format(self.db_file))

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

    def fetch_search_results(self, query, offset, limit):
        start_time = timeit.default_timer()

        search = self.session.query(RecordsFTS)

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

        # Bind the FTS search
        # TODO: Use only docid for subquery with LIMIT -- Prevents loading
        # everything to memory
        filter_string = RecordsFTS.__tablename__ + " MATCH :text"
        search = search.filter(sqlalchemy.sql.expression.text(
            filter_string)).params(
            text=query) \
            .order_by(RecordsFTS.docid)

        logger.info("Searching for '{0}'.".format(query))

        # Try the actual search
        try:
            count = search.count()
            if limit > 0:
                sliced = search.slice(offset,
                                      offset + limit)
                results = [row.dictionary for row in sliced]
            else:
                results = [row.dictionary for row in search]
            elapsed = "{:.3f}".format(timeit.default_timer() - start_time)
            return {'total': count, 'results': results, 'query': return_query,
                    'elapsed': elapsed, 'offset': offset}
        except sqlalchemy.exc.SQLAlchemyError as e:
            # Whoops.
            print(e)
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
            return 'success'
        except sqlalchemy.exc.SQLAlchemyError as e:
            # Uh oh.
            print(e)
            return 'error'

    # ===============
    # Private helpers
    # ===============
    @staticmethod
    def _process_query(query):
        query_words = query.split()
        query = ''
        return_query = ''

        # If all the search terms are negative, we'll force a full table scan
        found_positive = False

        for word in query_words:
            # The FTS engine doesn't care about case, except where the word is
            # one of the query syntax keywords
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
