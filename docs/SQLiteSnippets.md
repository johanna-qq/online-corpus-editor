SQLite Snippets
===============

## Total record counts

### Record count table
    
    CREATE TABLE tweets_count(
        count   INTEGER PRIMARY KEY
    )

### Insert trigger

    CREATE TRIGGER tweet_add AFTER INSERT ON tweets
    BEGIN
      UPDATE tweets_count SET
        count = count + 1;
    END

### Delete trigger

    CREATE TRIGGER tweet_subtract AFTER DELETE ON tweets
    BEGIN
      UPDATE tweets_count SET
        count = count - 1;
    END