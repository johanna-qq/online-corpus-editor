SQLite Snippets
===============

Corpus DB schema
----------------

```sql
CREATE TABLE tweets(
    rowid     INTEGER PRIMARY KEY,
    fullscan  INTEGER DEFAULT 1,
    content   TEXT,
    flag      BOOLEAN,
    category  INTEGER,
    comment   TEXT,
    tag       TEXT,
    language  TEXT
)
```

Full-text Search
----------------

### FTS Table

This is an "external content" table (https://sqlite.org/fts3.html#section_6_2_2), so the triggers below are also needed.

```sql
CREATE VIRTUAL TABLE tweets_fts USING fts4(
    content="tweets",
    rowid     INTEGER,
    fullscan  INTEGER,
    content   TEXT,
    flag      BOOLEAN,
    category  INTEGER,
    comment   TEXT,
    tag       TEXT,
    language  TEXT,
    tokenize=porter
)
```

When the FTS table is created for the first time, its index also needs to be initialised:

```sql
INSERT INTO tweets_fts(tweets_fts) VALUES('rebuild')
```

### Trigger: After insert

```sql
CREATE TRIGGER fts_ai AFTER INSERT ON tweets
BEGIN
    INSERT INTO tweets_fts
        (docid, fullscan, content, flag, category, comment, tag, language)
    VALUES
        (new.rowid, new.fullscan, new.content, new.flag, new.category, new.comment, new.tag, new.language);
END

```

### Trigger: Before update

```sql
CREATE TRIGGER fts_bu BEFORE UPDATE ON tweets
BEGIN
    DELETE FROM tweets_fts WHERE docid=old.rowid;
END
```

### Trigger: After update

```sql
CREATE TRIGGER fts_au AFTER UPDATE ON tweets
BEGIN
    INSERT INTO tweets_fts
        (docid, fullscan, content, flag, category, comment, tag, language)
    VALUES
        (new.rowid, new.fullscan, new.content, new.flag, new.category, new.comment, new.tag, new.language);
END
```

### Trigger: Before delete

```sql
CREATE TRIGGER fts_bd BEFORE DELETE ON tweets
BEGIN
    DELETE FROM tweets_fts WHERE docid=old.rowid;
END
```

Total record counts
-------------------

### Record count table

```sql
CREATE TABLE tweets_count(
    count   INTEGER PRIMARY KEY
)
```

### Trigger: After insert

```sql
CREATE TRIGGER tweet_add AFTER INSERT ON tweets
BEGIN
  UPDATE tweets_count SET
    count = count + 1;
END
```

### Trigger: After delete

```sql
CREATE TRIGGER tweet_subtract AFTER DELETE ON tweets
BEGIN
  UPDATE tweets_count SET
    count = count - 1;
END
```