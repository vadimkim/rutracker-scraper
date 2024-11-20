def insert_tracker(conn, page):
    """ Inserts tracker into sqlite database """
    sql = 'INSERT INTO trackers (id, hash, magnet, title, size, body) VALUES (?, ?, ?, ?, ?, ?)'
    cur = conn.cursor()
    cur.execute(sql, (page.id, page.hash(), page.link, page.title, page.size, page.body))
    conn.commit()

def last_record(conn):
    """ Returns last record from trackers table """
    sql = 'SELECT IFNULL(max(id),0) AS MAXID FROM trackers'
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchone()[0]

def check_empties(conn, start, stop):
    """ Returns missing id's from the range between start and stop from trackers table """
    sql = 'WITH RECURSIVE IDS AS (SELECT ? AS id UNION ALL select id + 1 FROM IDS WHERE id < ?) SELECT id FROM IDS WHERE id NOT IN (SELECT id FROM trackers)'
    cur = conn.cursor()
    cur.execute(sql, (start, stop))
    empties = [row[0] for row in cur.fetchall()]
    return empties