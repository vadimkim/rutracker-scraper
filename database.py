def insert_tracker(conn, page):
    """ insert tracker into sqlite database """
    sql = 'INSERT INTO trackers (id, hash, magnet, title, size, body) VALUES (?, ?, ?, ?, ?, ?)'
    cur = conn.cursor()
    cur.execute(sql, (page.id, page.hash(), page.link, page.title, page.size, page.body))
    conn.commit()

def last_record(conn):
    sql = 'SELECT IFNULL(max(id),0) AS MAXID FROM trackers'
    cur = conn.cursor()
    cur.execute(sql)
    return cur.fetchone()[0]
