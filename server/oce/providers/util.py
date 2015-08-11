"""
Common utility functions and classes for data providers
"""


# ================
# Helper functions
# ================

# ------------------
# FTS pre-processing
# ------------------
# Given a field name and its contents, either add or remove a tag to it
# (For faster queries using FTS matching: "WHERE comment MATCH cmt" is much
# faster than "WHERE comment != ''")
# Possible caveat: If using a different tokeniser in the future, 'cmt' might not
# match 'cmt:'?

# This method also appears to be faster than having a separate boolean field
# that tracks whether the record has a comment/flag/tag/etc. or not (since
# the FTS is only being run on one column?)
fts_tags = {
    'comment': 'cmt: ',
    'tag': 'tags: ',
    'language': 'lang: '
}


def fts_tag(field, content):
    if field in fts_tags.keys() and content.strip() != '':
        return fts_tags[field] + content
    else:
        return content


def fts_detag(field, content):
    # If the value of the field is null in the DB, it gets passed as None here.
    # We need to catch this and return an empty string
    if content is None:
        return ''

    if field in fts_tags.keys() and content.startswith(fts_tags[field]):
        return content.split(fts_tags[field], 1)[1]
    else:
        return content


# --------------------------
# Language ID pre-processing
# --------------------------
# Normalises the language labels on corpus records so that the language
# classifiers don't see more categories than there really are
def langid_normalise_language(language_list):
    if language_list.strip() == '':
        return ''
    else:
        # Normalise case, sort language labels alphabetically
        languages = language_list.split(",")
        languages = [y[0].upper() + y[1:].lower()
                     for y in [x.strip() for x in languages]]
        languages.sort()
        languages = ", ".join(languages)
        return languages


# ============================================================
# SQLAlchemy ORM mappings for standard corpus table structures
# ============================================================

import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.sql.expression
import sqlalchemy.exc
import sqlalchemy.ext.declarative

import oce.config

MAIN_TABLE = oce.config.main_table


class SQLAlchemyORM:
    Base = sqlalchemy.ext.declarative.declarative_base()

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
                # Also fts_detags if necessary
                data[col.name] = fts_detag(col.name, getattr(self, col.name))
            return data

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
                data[col.name] = fts_detag(col.name, getattr(self, col.name))
            return data

    class RecordsSuffixes(Base):
        __tablename__ = MAIN_TABLE + '_suffixes'

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
                data[col.name] = fts_detag(col.name, getattr(self, col.name))
            return data

    class RecordCount(Base):
        __tablename__ = MAIN_TABLE + '_count'
        count = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)

    class RecordTags(Base):
        __tablename__ = MAIN_TABLE + '_tags'
        rowid = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
        tag = sqlalchemy.Column(sqlalchemy.Text)
        count = sqlalchemy.Column(sqlalchemy.Integer)
