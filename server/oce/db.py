# Deals with DB-related operations, including high-level ones like searching,
# updating, etc.

import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.sql.expression
import sqlalchemy.exc
import sqlalchemy.ext.declarative

import re
import timeit

import oce.logger

logger = oce.logger.getLogger(__name__)


class DB:
    def __init__(self, db_file):
        self.db_file = db_file
        # Initialise the ORM session
        self.engine = sqlalchemy.create_engine('sqlite:///' + db_file)
        # sessionmaker() returns a class
        self.session = sqlalchemy.orm.sessionmaker(bind=self.engine)()
        logger.info("DB module initialised -- No connections made yet. "
                    "(" + db_file + ")")
        return

    def shutdown(self):
        self.session.commit()
        self.session.close()

    # --------
    # Commands
    # --------
    def find_pages(self, per_page=100):
        # TODO: Save pagination into a temp file, don't redo unless a record
        # is deleted.
        # print("Testing pagination...")

        # 3.277s 3.288s
        # start_time = timeit.default_timer()
        # import sqlite3
        #
        # conn = sqlite3.connect(self.db_file)
        # c = conn.cursor()
        # last_ids = []
        # last_id = 0
        # while last_id < 2406562:
        #     select_str = "SELECT rowid FROM " + Records.__tablename__ + \
        #                  " WHERE rowid > " + str(last_id) + \
        #                  " ORDER BY rowid ASC LIMIT " + str(per_page)
        #     last_id = c.execute(select_str).fetchall()[-1][0]
        #     last_ids.append(last_id)
        # print(last_ids[-1])
        # elapsed = "{:.3f}".format(timeit.default_timer() - start_time)
        # print("sqlite3: Took " + elapsed + "s.")

        # 11.931s 11.671s
        # start_time = timeit.default_timer()
        # conn = self.engine.connect()
        # last_ids = []
        # last_id = 0
        # rowid = Records.rowid
        # from sqlalchemy.sql import select
        #
        # while last_id < 2406562:
        #     s = select([rowid]).where(rowid > last_id).order_by(
        #         rowid).limit(per_page)
        #     result = conn.execute(s)
        #     last_id = result.fetchall()[-1][0]
        #     last_ids.append(last_id)
        # print(last_ids[-1])
        # elapsed = "{:.3f}".format(timeit.default_timer() - start_time)
        # print("sqlalchemy literal: Took " + elapsed + "s.")

        # 20.926s 21.148s
        # start_time = timeit.default_timer()
        # conn = self.engine.connect()
        # last_ids = []
        # last_id = 0
        # session = self.session
        # rowid = Records.rowid
        # while last_id < 2406562:
        #     last_id = session.query(rowid) \
        #         .filter(rowid > last_id) \
        #         .order_by(rowid).limit(per_page).all()[-1].rowid
        #     last_ids.append(last_id)
        # print(last_ids[-1])
        # elapsed = "{:.3f}".format(timeit.default_timer() - start_time)
        # print("sqlalchemy ORM: Took " + elapsed + "s.")

        return

    def fetch_record(self, rowid):
        """
        Gets one record from the database by ID
        :param rowid:
        :return:
        """
        return self.session.query(Records) \
            .filter(Records.rowid == rowid).one().dictionary

    def fetch_records(self, start, end):
        """
        Gets records with IDs within the range specified (as a List).
        :param start:
        :param end:
        :return:
        """
        return [row.dictionary for row in self.session.query(Records).filter(
            Records.rowid.between(start, end)).order_by(Records.rowid)]

    def fetch_meta(self):
        # Total number of records
        total = self.session.query(RecordCount.count).scalar()

        # Tags available
        tags = [x[0] for x in self.session.query(RecordTags.tag).order_by(RecordTags.tag)]

        return {
            'total': total,
            'tags': tags
        }

    def fetch_literal(self, query):
        """
        Literal SQL queries on the main Records table.
        """
        results = [row.dictionary for row in
                   self.session.query(Records).filter(sqlalchemy.sql.expression.text(query))]

        return results, len(results)

    def fetch_literal_fts(self, query):
        """
        Literal SQL queries on the Records FTS table.
        """
        results = [row.dictionary for row in
                   self.session.query(RecordsFTS).filter(sqlalchemy.sql.expression.text(query))]

        return results, len(results)

    def fetch_literal_fts_fast(self, query):
        """
        -- INSECURE --
        Literal SQL queries on the FTS table using the sqlite3 module
        """
        start_time = timeit.default_timer()
        import sqlite3

        # Notes:
        # Selecting by docid on a match query is super fast
        # selecting by rowid is super slow.
        # Our triggers ensure that docid == rowid

        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        results = c.execute(query).fetchall()
        elapsed = "{:.3f}".format(timeit.default_timer() - start_time)
        print("sqlite3: Took " + elapsed + "s.")
        print("Number of results: " + str(len(results)))
        return results

    def fetch_search_results(self, query, offset, limit):
        """
        Returns an object describing the results of a search query.s
        :param query:
        :param offset:
        :param limit: If 0, returns all results.
        :return:
        """

        start_time = timeit.default_timer()

        # Pre-process the query

        # [Illegal characters and other invalid queries]
        # If there's an odd number of double inverted commas, drop the last one
        commas = re.findall('"', query)
        if len(commas) % 2 == 1:
            query = ''.join(query.rsplit(sep="\"", maxsplit=1))

        # [Special commands]
        # Prepare the search session, and if there's a special command, parse it
        search = self.session.query(RecordsFTS)

        # We will return the query to the client, including canonical forms of
        # special commands
        query, return_query = process_query(query)

        # Bind the FTS search
        # TODO: Use only docid for subquery with LIMIT -- Prevents loading everything to memory
        filter_string = RecordsFTS.__tablename__ + " MATCH :text"
        search = search.filter(sqlalchemy.sql.expression.text(
            filter_string)).params(
            text=query) \
            .order_by(RecordsFTS.docid)

        print("Searching for '{}'.".format(
            query.encode('ascii', 'xmlcharrefreplace').decode()))

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

    def update_record(self, rowid, field, value):
        try:
            for row in self.session.query(Records) \
                    .filter(Records.rowid == rowid):

                # ====================
                # Field-specific hooks
                # ====================
                # Process record tags to update tweets_tags table
                if field == 'tag':
                    old_tags = ftsdetag('tag', row.tag)
                    self._update_tags(value, old_tags)
                elif field == 'language':
                    value = self.pre_update_language(row, value)
                # ====================

                # Add FTS tags if needed
                value = ftsaddtag(field, value)
                print(
                    ("Updating '{}' on row {}: "
                     "{} -> {}").format(field, row.rowid,
                                        str(getattr(row, field))
                                        .encode('ascii', 'xmlcharrefreplace')
                                        .decode()
                                        .replace('\n', '\\n'),
                                        str(value)
                                        .encode('ascii', 'xmlcharrefreplace')
                                        .decode()
                                        .replace('\n', '\\n')))
                setattr(row, field, value)
                self.session.commit()
            return 'success'
        except sqlalchemy.exc.SQLAlchemyError as e:
            # Uh oh.
            print(e)
            return 'error'

    def _update_tags(self, new_tags, old_tags):
        """
        Given comma-delimited lists of record tags, update the RecordTags table.
        :param new_tags:
        :param old_tags:
        :return:
        """
        # Start by preparing the lists of old and new record tags
        if new_tags == '':
            # Splitting the empty string will give us an array with one empty
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
                print(
                    ("[WARNING] Tried to remove tag that isn't in DB: {}. "
                     "Ignoring.").format(tag))
            else:
                row = rows[0]
                row.count -= 1
                if row.count == 0:
                    # Remove the row entirely.
                    self.session.delete(row)
                self.session.commit()
        return

    def pre_update_language(self, row, languages):
        if languages.strip() == '':
            return ''
        return self.normalise_language(languages)

    def normalise_language(self, languages):
        # Normalise case, sort language labels alphabetically
        languages = languages.split(",")
        languages = [y[0].upper() + y[1:].lower()
                     for y in [x.strip() for x in languages]]
        languages.sort()
        languages = ", ".join(languages)
        return languages

    def debug(self):
        self.find_pages()

        # start_time = timeit.default_timer()
        import sqlite3

        start_time = timeit.default_timer()
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        select_str = "PRAGMA compile_options"
        print(c.execute(select_str).fetchall())
        elapsed = "{:.3f}".format(timeit.default_timer() - start_time)
        print("sqlite3: Took " + elapsed + "s.")
        return


# =======================
# Module helper functions
# =======================

# --------------------
# Field pre-processing
# --------------------
# Given a field name and its contents, either add or remove a tag to it
# (For faster queries using FTS matching: "WHERE comment MATCH cmt" is much
# faster than "WHERE comment != ''")
# Possible caveat: If using the simple tokenizer in the future, 'cmt' might not
# match 'cmt:'?

# This method also appears to be faster than having a separate boolean field
# that tracks whether the record has a comment/flag/tag/etc. or not (since
# the FTS is only being run on one col?)

# Str, Str -> Str
def ftsaddtag(field, content):
    if field == 'comment' and content.strip() != '':
        return 'cmt: ' + content

    if field == 'tag' and content.strip() != '':
        return 'tags: ' + content

    if field == 'language' and content.strip() != '':
        return 'lang: ' + content

    return content


# Str, Str -> Str
def ftsdetag(field, content):
    if content is None:
        content = ''
    if field == 'comment' and content.startswith('cmt: '):
        return content.split('cmt: ', 1)[1]

    if field == 'tag' and content.startswith('tags: '):
        return content.split('tags: ', 1)[1]

    if field == 'language' and content.startswith('lang: '):
        return content.split('lang: ', 1)[1]

    return content


# Str -> Str, List
# Given some raw search query (including special commands),
# return a query string suitable for the FTS MATCH operator.
# Also returns the query to the user with the special commands in canonical form.
def process_query(query):
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
            query = query + 'comment:cmt '
            return_query = return_query + 'has:comment '
            found_positive = True
        elif word == 'is:flagged' or word == 'has:flag':
            query = query + 'flag:1 '
            return_query = return_query + 'is:flagged '
            found_positive = True
        elif word == 'is:tagged' or word == 'has:tag':
            query = query + 'tag:tags '
            return_query = return_query + 'has:tag '
            found_positive = True
        elif word == 'has:language' or word == 'has:lang':
            query = query + 'language:lang '
            return_query = return_query + 'has:language '
            found_positive = True
        elif word.startswith("lang:"):
            query = query + "language:" + word.split("lang:", 1)[1] + " "
            return_query = return_query + "language:" + word.split("lang:", 1)[1] + " "
            found_positive = True
        elif word == '&':
            # Not needed, and FTS does not search for literal &s anyway
            continue
        else:
            # Look at the start of the term or after a filter for a NOT operator
            negs = re.findall(r'(^-|:-)', word)
            if len(negs) == 0:
                found_positive = True
            query = query + word + ' '
            return_query = return_query + word + ' '

    if not found_positive:
        query = query + 'fullscan:1'

    # Final check for Enhanced Query Syntax
    if query.startswith("NOT "):
        query = 'fullscan:1 ' + query

    return [query.strip(), return_query.strip()]

# ---
# ORM
# ---
# Base table name in the DB
MAIN_TABLE = 'tweets'
# Declare ORM mappings
Base = sqlalchemy.ext.declarative.declarative_base()


class RecordsFTS(Base):
    __tablename__ = MAIN_TABLE + '_fts'

    docid = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    rowid = sqlalchemy.Column(sqlalchemy.Integer)
    content = sqlalchemy.Column(sqlalchemy.Text)
    flag = sqlalchemy.Column(sqlalchemy.Boolean)
    category = sqlalchemy.Column(sqlalchemy.Integer)
    comment = sqlalchemy.Column(sqlalchemy.Text)
    tag = sqlalchemy.Column(sqlalchemy.Text)
    language = sqlalchemy.Column(sqlalchemy.Text)

    # Represents as a standard dictionary for easy JSON-ification
    @property
    def dictionary(self):
        data = dict()
        for col in self.__table__.columns:
            # Also detags if necessary
            data[col.name] = ftsdetag(col.name, getattr(self, col.name))
        return data


class Records(Base):
    __tablename__ = MAIN_TABLE

    rowid = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    content = sqlalchemy.Column(sqlalchemy.Text)
    flag = sqlalchemy.Column(sqlalchemy.Boolean)
    category = sqlalchemy.Column(sqlalchemy.Integer)
    comment = sqlalchemy.Column(sqlalchemy.Text)
    tag = sqlalchemy.Column(sqlalchemy.Text)
    language = sqlalchemy.Column(sqlalchemy.Text)

    @property
    def dictionary(self):
        data = dict()
        for col in self.__table__.columns:
            # Also detags if necessary
            data[col.name] = ftsdetag(col.name, getattr(self, col.name))
        return data


class RecordCount(Base):
    __tablename__ = MAIN_TABLE + '_count'
    count = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)


class RecordTags(Base):
    __tablename__ = MAIN_TABLE + '_tags'
    rowid = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    tag = sqlalchemy.Column(sqlalchemy.Text)
    count = sqlalchemy.Column(sqlalchemy.Integer)
