"""
Defines the SQL statements that recreate the main DBs.
Each key in db_schema is a List of single SQL statements.
"""

from oce.config import main_table

db_schema = {}

db_schema["create_fts"] = ["""
CREATE VIRTUAL TABLE {main_table}_fts USING fts4(
    content='{main_table}',
    rowid     INTEGER,
    fullscan  INTEGER,
    content   TEXT,
    flag      BOOLEAN,
    category  INTEGER,
    comment   TEXT,
    tag       TEXT,
    language  TEXT,
    tokenize=oce
);
""".format(main_table=main_table)]

db_schema["drop_fts"] = ["""
DROP TABLE IF EXISTS {main_table}_fts
""".format(main_table=main_table)]

db_schema["create_suffixes"] = ["""
CREATE VIRTUAL TABLE {main_table}_suffixes USING fts4(
    content='{main_table}',
    rowid     INTEGER,
    fullscan  INTEGER,
    content   TEXT,
    flag      BOOLEAN,
    category  INTEGER,
    comment   TEXT,
    tag       TEXT,
    language  TEXT,
    tokenize=oce_suffixes
);
""".format(main_table=main_table)]

db_schema["drop_suffixes"] = ["""
DROP TABLE IF EXISTS {main_table}_suffixes
""".format(main_table=main_table)]

db_schema["create_triggers"] = [
    """
    CREATE TRIGGER fts_after_insert AFTER INSERT ON {main_table}
    BEGIN
        INSERT INTO {main_table}_fts
            (docid, fullscan, content, flag, category, comment, tag, language)
        VALUES
            (new.rowid, new.fullscan, new.content, new.flag, new.category,
            new.comment, new.tag, new.language);
        INSERT INTO {main_table}_suffixes
            (docid, fullscan, content, flag, category, comment, tag, language)
        VALUES
            (new.rowid, new.fullscan, new.content, new.flag, new.category,
            new.comment, new.tag, new.language);
    END;
    """.format(main_table=main_table),

    """
    CREATE TRIGGER fts_before_update BEFORE UPDATE ON {main_table}
    BEGIN
        DELETE FROM {main_table}_fts WHERE docid=old.rowid;
        DELETE FROM {main_table}_suffixes WHERE docid=old.rowid;
    END;
    """.format(main_table=main_table),

    """
    CREATE TRIGGER fts_after_update AFTER UPDATE ON {main_table}
    BEGIN
        INSERT INTO {main_table}_fts
            (docid, fullscan, content, flag, category, comment, tag, language)
        VALUES
            (new.rowid, new.fullscan, new.content, new.flag, new.category,
            new.comment, new.tag, new.language);
        INSERT INTO {main_table}_suffixes
            (docid, fullscan, content, flag, category, comment, tag, language)
        VALUES
            (new.rowid, new.fullscan, new.content, new.flag, new.category,
            new.comment, new.tag, new.language);
    END;
    """.format(main_table=main_table),

    """
    CREATE TRIGGER fts_before_delete BEFORE DELETE ON {main_table}
    BEGIN
        DELETE FROM {main_table}_fts WHERE docid=old.rowid;
        DELETE FROM {main_table}_suffixes WHERE docid=old.rowid;
    END;
    """.format(main_table=main_table)
]

db_schema["drop_triggers"] = [
    """
    DROP TRIGGER IF EXISTS fts_after_insert;
    """,
    """
    DROP TRIGGER IF EXISTS fts_before_update;
    """,
    """
    DROP TRIGGER IF EXISTS fts_after_update;
    """,
    """
    DROP TRIGGER IF EXISTS fts_before_delete;
    """
]
