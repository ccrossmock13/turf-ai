"""
Community and Benchmarking Module for Greenside AI.
Provides anonymous benchmarking, regional alerts, shared programs, and discussion forums
for turfgrass management professionals.
"""

import json
import re
import logging
from datetime import datetime

from db import get_db, get_integrity_error

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Valid enum values
# ---------------------------------------------------------------------------

VALID_METRIC_TYPES = [
    'n_rate', 'spray_count', 'green_speed', 'mowing_hoc',
    'water_usage', 'labor_hours', 'budget_per_acre'
]
VALID_COURSE_TYPES = ['private', 'public', 'resort', 'municipal']
VALID_ALERT_TYPES = ['disease', 'pest', 'weather', 'regulatory']
VALID_SEVERITIES = ['low', 'medium', 'high', 'critical']
VALID_PROGRAM_TYPES = ['spray', 'fertility', 'pgr', 'cultural']
VALID_CATEGORIES = [
    'disease', 'pest', 'cultural', 'equipment', 'irrigation', 'general'
]
VALID_VOTE_TYPES = ['up', 'down']


# ---------------------------------------------------------------------------
# Content sanitization
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r'<[^>]+>')


def _sanitize(text):
    """Strip HTML tags from user-supplied text and trim whitespace."""
    if not text:
        return text
    return _HTML_TAG_RE.sub('', str(text)).strip()


def _validate_enum(value, allowed, field_name):
    """Raise ValueError if *value* is not in *allowed*."""
    if value not in allowed:
        raise ValueError(
            f"Invalid {field_name}: '{value}'. Must be one of {allowed}"
        )


# ---------------------------------------------------------------------------
# Table initialisation
# ---------------------------------------------------------------------------

def init_community_tables():
    """Create all community tables if they do not exist."""
    with get_db() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS benchmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                area TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                region TEXT,
                grass_type TEXT,
                course_type TEXT,
                anonymous INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS regional_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                region TEXT,
                state TEXT,
                severity TEXT DEFAULT 'medium',
                start_date TEXT,
                end_date TEXT,
                verified INTEGER DEFAULT 0,
                upvotes INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alert_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                vote_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (alert_id) REFERENCES regional_alerts (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS shared_programs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                program_type TEXT NOT NULL,
                season TEXT,
                region TEXT,
                grass_type TEXT,
                program_json TEXT NOT NULL,
                is_public INTEGER DEFAULT 0,
                downloads INTEGER DEFAULT 0,
                rating_sum REAL DEFAULT 0,
                rating_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS program_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                program_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (program_id) REFERENCES shared_programs (id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discussion_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                tags TEXT,
                upvotes INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                is_pinned INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS discussion_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                upvotes INTEGER DEFAULT 0,
                is_accepted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES discussion_posts (id)
            )
        ''')

    logger.info("Community tables initialised")


# =========================================================================
# Benchmarking
# =========================================================================

def submit_benchmark(user_id, data):
    """Submit an anonymous benchmark metric.

    Args:
        user_id: The submitting user's ID.
        data: dict with keys year, month, area, metric_type, value,
              and optional region, grass_type, course_type, anonymous.
    Returns:
        The new benchmark row ID.
    """
    metric_type = data.get('metric_type', '')
    _validate_enum(metric_type, VALID_METRIC_TYPES, 'metric_type')

    course_type = data.get('course_type')
    if course_type:
        _validate_enum(course_type, VALID_COURSE_TYPES, 'course_type')

    year = int(data['year'])
    month = int(data['month'])
    if not (1 <= month <= 12):
        raise ValueError("month must be between 1 and 12")

    value = float(data['value'])
    area = _sanitize(data.get('area', ''))
    region = _sanitize(data.get('region'))
    grass_type = _sanitize(data.get('grass_type'))
    anonymous = 1 if data.get('anonymous', True) else 0

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO benchmarks
                (user_id, year, month, area, metric_type, value,
                 region, grass_type, course_type, anonymous)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, year, month, area, metric_type, value,
              region, grass_type, course_type, anonymous))
        benchmark_id = cursor.lastrowid

    logger.info("Benchmark %s submitted by user %s (%s=%s)",
                benchmark_id, user_id, metric_type, value)
    return benchmark_id


def get_benchmarks(region=None, grass_type=None, course_type=None,
                   metric_type=None, year=None):
    """Return aggregated benchmark statistics.

    All filters are optional.  Returns a list of dicts, one per
    (metric_type, area) combination, each with min/max/avg/count.
    """
    clauses = []
    params = []

    if region:
        clauses.append("region = ?")
        params.append(region)
    if grass_type:
        clauses.append("grass_type = ?")
        params.append(grass_type)
    if course_type:
        _validate_enum(course_type, VALID_COURSE_TYPES, 'course_type')
        clauses.append("course_type = ?")
        params.append(course_type)
    if metric_type:
        _validate_enum(metric_type, VALID_METRIC_TYPES, 'metric_type')
        clauses.append("metric_type = ?")
        params.append(metric_type)
    if year:
        clauses.append("year = ?")
        params.append(int(year))

    where = "WHERE " + " AND ".join(clauses) if clauses else ""

    sql = f'''
        SELECT metric_type, area,
               COUNT(*) as cnt,
               AVG(value) as avg_val,
               MIN(value) as min_val,
               MAX(value) as max_val
        FROM benchmarks
        {where}
        GROUP BY metric_type, area
        ORDER BY metric_type, area
    '''

    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    return [
        {
            'metric_type': r['metric_type'],
            'area': r['area'],
            'count': r['cnt'],
            'average': round(float(r['avg_val']), 2) if r['avg_val'] else 0,
            'min': round(float(r['min_val']), 2) if r['min_val'] else 0,
            'max': round(float(r['max_val']), 2) if r['max_val'] else 0,
        }
        for r in rows
    ]


def get_my_vs_peers(user_id, metric_type, year=None):
    """Compare a user's metrics against their regional average.

    Returns a dict with the user's average, the peer average, and the
    difference.
    """
    _validate_enum(metric_type, VALID_METRIC_TYPES, 'metric_type')

    year_clause = "AND b.year = ?" if year else ""
    base_params_user = [user_id, metric_type]
    base_params_peer = [user_id, metric_type]
    if year:
        base_params_user.append(int(year))
        base_params_peer.append(int(year))

    with get_db() as conn:
        # User's average
        user_sql = f'''
            SELECT AVG(value) as avg_val, COUNT(*) as cnt
            FROM benchmarks
            WHERE user_id = ? AND metric_type = ? {year_clause}
        '''
        user_row = conn.execute(user_sql, tuple(base_params_user)).fetchone()
        # Peer average (same region, excluding user)
        peer_sql = f'''
            SELECT AVG(b2.value) as avg_val, COUNT(*) as cnt
            FROM benchmarks b2
            WHERE b2.user_id != ?
              AND b2.metric_type = ?
              {year_clause}
              AND b2.region IN (
                  SELECT DISTINCT region FROM benchmarks
                  WHERE user_id = ? AND region IS NOT NULL
              )
        '''
        peer_params = list(base_params_peer) + [user_id]
        peer_row = conn.execute(peer_sql, tuple(peer_params)).fetchone()

    user_avg = round(float(user_row['avg_val']), 2) if user_row and user_row['avg_val'] else None
    peer_avg = round(float(peer_row['avg_val']), 2) if peer_row and peer_row['avg_val'] else None

    diff = None
    if user_avg is not None and peer_avg is not None and peer_avg != 0:
        diff = round(user_avg - peer_avg, 2)

    return {
        'metric_type': metric_type,
        'user_average': user_avg,
        'user_count': int(user_row['cnt']) if user_row else 0,
        'peer_average': peer_avg,
        'peer_count': int(peer_row['cnt']) if peer_row else 0,
        'difference': diff,
    }


def get_percentile_ranking(user_id, metric_type, year=None):
    """Return the user's percentile ranking for a given metric.

    Percentile is computed as the fraction of peer values that are less
    than or equal to the user's average.
    """
    _validate_enum(metric_type, VALID_METRIC_TYPES, 'metric_type')

    year_clause = "AND year = ?" if year else ""
    params_user = [user_id, metric_type]
    if year:
        params_user.append(int(year))

    with get_db() as conn:
        # User average
        user_sql = f'''
            SELECT AVG(value) as avg_val
            FROM benchmarks
            WHERE user_id = ? AND metric_type = ? {year_clause}
        '''
        user_row = conn.execute(user_sql, tuple(params_user)).fetchone()
        if not user_row or user_row['avg_val'] is None:
            return {
                'metric_type': metric_type,
                'percentile': None,
                'message': 'No data submitted for this metric',
            }
        user_avg = float(user_row['avg_val'])

        # Count all values and values <= user_avg (same region)
        total_sql = f'''
            SELECT COUNT(*) as total
            FROM benchmarks
            WHERE metric_type = ? {year_clause}
              AND region IN (
                  SELECT DISTINCT region FROM benchmarks
                  WHERE user_id = ? AND region IS NOT NULL
              )
        '''
        below_sql = f'''
            SELECT COUNT(*) as below
            FROM benchmarks
            WHERE metric_type = ? AND value <= ? {year_clause}
              AND region IN (
                  SELECT DISTINCT region FROM benchmarks
                  WHERE user_id = ? AND region IS NOT NULL
              )
        '''

        total_params = [metric_type]
        if year:
            total_params.append(int(year))
        total_params.append(user_id)

        below_params = [metric_type, user_avg]
        if year:
            below_params.append(int(year))
        below_params.append(user_id)

        total_row = conn.execute(total_sql, tuple(total_params)).fetchone()
        below_row = conn.execute(below_sql, tuple(below_params)).fetchone()

    total = int(total_row['total']) if total_row else 0
    below = int(below_row['below']) if below_row else 0

    percentile = round((below / total) * 100, 1) if total > 0 else None

    return {
        'metric_type': metric_type,
        'user_average': round(user_avg, 2),
        'percentile': percentile,
        'total_entries': total,
    }


# =========================================================================
# Regional Alerts
# =========================================================================

def create_alert(user_id, data):
    """Create a new regional alert.

    Args:
        user_id: Creator's user ID.
        data: dict with alert_type, title, description, region, state,
              severity, start_date, end_date.
    Returns:
        The new alert row ID.
    """
    alert_type = data.get('alert_type', '')
    _validate_enum(alert_type, VALID_ALERT_TYPES, 'alert_type')

    severity = data.get('severity', 'medium')
    _validate_enum(severity, VALID_SEVERITIES, 'severity')

    title = _sanitize(data.get('title', ''))
    if not title:
        raise ValueError("Alert title is required")

    description = _sanitize(data.get('description', ''))
    region = _sanitize(data.get('region'))
    state = _sanitize(data.get('state'))
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO regional_alerts
                (user_id, alert_type, title, description, region, state,
                 severity, start_date, end_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, alert_type, title, description, region, state,
              severity, start_date, end_date))
        alert_id = cursor.lastrowid
    logger.info("Alert %s created by user %s: %s", alert_id, user_id, title)
    return alert_id


def get_alerts(region=None, state=None, alert_type=None, active_only=True):
    """Retrieve regional alerts with optional filters.

    When *active_only* is True, only alerts whose end_date is NULL or in
    the future are returned.
    """
    clauses = []
    params = []

    if region:
        clauses.append("region = ?")
        params.append(region)
    if state:
        clauses.append("state = ?")
        params.append(state)
    if alert_type:
        _validate_enum(alert_type, VALID_ALERT_TYPES, 'alert_type')
        clauses.append("alert_type = ?")
        params.append(alert_type)
    if active_only:
        clauses.append("(end_date IS NULL OR end_date >= DATE('now'))")

    where = "WHERE " + " AND ".join(clauses) if clauses else ""
    sql = f'''
        SELECT * FROM regional_alerts
        {where}
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 0
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
            END,
            created_at DESC
    '''

    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    return [dict(r) for r in rows]


def vote_alert(alert_id, user_id, vote_type):
    """Upvote or downvote a regional alert.

    Each user can only have one active vote per alert.  Changing the vote
    type updates the existing record.

    Returns:
        The new upvote total for the alert.
    """
    _validate_enum(vote_type, VALID_VOTE_TYPES, 'vote_type')
    with get_db() as conn:
        # Check for an existing vote
        existing = conn.execute(
            'SELECT id, vote_type FROM alert_votes WHERE alert_id = ? AND user_id = ?',
            (alert_id, user_id)
        ).fetchone()

        if existing:
            old_type = existing['vote_type']
            if old_type == vote_type:
                # Same vote -- nothing to change
                row = conn.execute(
                    'SELECT upvotes FROM regional_alerts WHERE id = ?',
                    (alert_id,)
                ).fetchone()
                return int(row['upvotes']) if row else 0

            # Flip the vote
            conn.execute(
                'UPDATE alert_votes SET vote_type = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?',
                (vote_type, existing['id'])
            )
            # Adjust upvotes: flipping up->down = -2, down->up = +2
            delta = 2 if vote_type == 'up' else -2
        else:
            conn.execute(
                'INSERT INTO alert_votes (alert_id, user_id, vote_type) VALUES (?, ?, ?)',
                (alert_id, user_id, vote_type)
            )
            delta = 1 if vote_type == 'up' else -1

        conn.execute(
            'UPDATE regional_alerts SET upvotes = upvotes + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (delta, alert_id)
        )

        row = conn.execute(
            'SELECT upvotes FROM regional_alerts WHERE id = ?',
            (alert_id,)
        ).fetchone()

    return int(row['upvotes']) if row else 0


def get_trending_alerts(limit=10):
    """Return the most-upvoted recent alerts (last 30 days)."""
    sql = '''
        SELECT * FROM regional_alerts
        WHERE created_at >= DATE('now', '-30 days')
          AND (end_date IS NULL OR end_date >= DATE('now'))
        ORDER BY upvotes DESC, created_at DESC
        LIMIT ?
    '''
    with get_db() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [dict(r) for r in rows]


# =========================================================================
# Shared Programs
# =========================================================================

def share_program(user_id, data):
    """Share a management program with the community.

    Args:
        user_id: The sharing user's ID.
        data: dict with title, description, program_type, season, region,
              grass_type, program_json (dict/list), is_public.

    Returns:
        The new program row ID.
    """
    program_type = data.get('program_type', '')
    _validate_enum(program_type, VALID_PROGRAM_TYPES, 'program_type')

    title = _sanitize(data.get('title', ''))
    if not title:
        raise ValueError("Program title is required")

    description = _sanitize(data.get('description', ''))
    season = _sanitize(data.get('season'))
    region = _sanitize(data.get('region'))
    grass_type = _sanitize(data.get('grass_type'))
    is_public = 1 if data.get('is_public', False) else 0
    program_json = data.get('program_json')
    if isinstance(program_json, (dict, list)):
        program_json = json.dumps(program_json)
    if not program_json:
        raise ValueError("program_json is required")

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO shared_programs
                (user_id, title, description, program_type, season,
                 region, grass_type, program_json, is_public)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, title, description, program_type, season,
              region, grass_type, program_json, is_public))
        program_id = cursor.lastrowid

    logger.info("Program %s shared by user %s: %s", program_id, user_id, title)
    return program_id


def get_shared_programs(program_type=None, region=None, grass_type=None):
    """List public shared programs with optional filters."""
    clauses = ["is_public = 1"]
    params = []

    if program_type:
        _validate_enum(program_type, VALID_PROGRAM_TYPES, 'program_type')
        clauses.append("program_type = ?")
        params.append(program_type)
    if region:
        clauses.append("region = ?")
        params.append(region)
    if grass_type:
        clauses.append("grass_type = ?")
        params.append(grass_type)

    where = "WHERE " + " AND ".join(clauses)

    sql = f'''
        SELECT id, user_id, title, description, program_type, season,
               region, grass_type, is_public, downloads,
               CASE WHEN rating_count > 0
                    THEN ROUND(rating_sum / rating_count, 1)
                    ELSE 0 END as avg_rating,
               rating_count, created_at, updated_at
        FROM shared_programs
        {where}
        ORDER BY created_at DESC
    '''

    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    return [dict(r) for r in rows]


def rate_program(program_id, user_id, rating, comment=None):
    """Rate a shared program (1-5).
    A user may only rate a program once.  Subsequent calls update the
    existing rating.

    Returns:
        The new average rating for the program.
    """
    rating = int(rating)
    if not (1 <= rating <= 5):
        raise ValueError("Rating must be between 1 and 5")

    comment = _sanitize(comment)

    with get_db() as conn:
        # Check for existing rating
        existing = conn.execute(
            'SELECT id, rating FROM program_ratings WHERE program_id = ? AND user_id = ?',
            (program_id, user_id)
        ).fetchone()

        if existing:
            old_rating = int(existing['rating'])
            conn.execute(
                'UPDATE program_ratings SET rating = ?, comment = ?, created_at = CURRENT_TIMESTAMP WHERE id = ?',
                (rating, comment, existing['id'])
            )
            # Adjust running totals
            conn.execute('''
                UPDATE shared_programs
                SET rating_sum = rating_sum + ? - ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (rating, old_rating, program_id))
        else:
            conn.execute(
                'INSERT INTO program_ratings (program_id, user_id, rating, comment) VALUES (?, ?, ?, ?)',
                (program_id, user_id, rating, comment)
            )
            conn.execute('''
                UPDATE shared_programs
                SET rating_sum = rating_sum + ?,
                    rating_count = rating_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (rating, program_id))

        row = conn.execute(
            'SELECT rating_sum, rating_count FROM shared_programs WHERE id = ?',
            (program_id,)
        ).fetchone()

    if row and int(row['rating_count']) > 0:
        avg = round(float(row['rating_sum']) / int(row['rating_count']), 1)
    else:
        avg = 0

    logger.info("Program %s rated %d by user %s", program_id, rating, user_id)
    return avg


def download_program(program_id, user_id):
    """Increment the download counter and return the full program.

    Returns:
        dict with the program data including parsed program_json, or
        None if not found.
    """
    with get_db() as conn:
        conn.execute(
            'UPDATE shared_programs SET downloads = downloads + 1 WHERE id = ?',
            (program_id,)
        )
        row = conn.execute(
            'SELECT * FROM shared_programs WHERE id = ?',
            (program_id,)
        ).fetchone()

    if not row:
        return None

    result = dict(row)
    # Parse the JSON payload for convenience
    try:
        result['program_data'] = json.loads(result.get('program_json', '{}'))
    except (json.JSONDecodeError, TypeError):
        result['program_data'] = {}

    logger.info("Program %s downloaded by user %s", program_id, user_id)
    return result


def get_top_programs(program_type=None, limit=10):
    """Return the highest-rated public programs."""
    clauses = ["is_public = 1", "rating_count > 0"]
    params = []

    if program_type:
        _validate_enum(program_type, VALID_PROGRAM_TYPES, 'program_type')
        clauses.append("program_type = ?")
        params.append(program_type)

    where = "WHERE " + " AND ".join(clauses)

    sql = f'''
        SELECT id, user_id, title, description, program_type, season,
               region, grass_type, downloads,
               CASE WHEN rating_count > 0
                    THEN ROUND(rating_sum / rating_count, 1)
                    ELSE 0 END as avg_rating,
               rating_count, created_at
        FROM shared_programs
        {where}
        ORDER BY (rating_sum / rating_count) DESC, rating_count DESC
        LIMIT ?
    '''
    params.append(limit)

    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    return [dict(r) for r in rows]


# =========================================================================
# Discussion Forum
# =========================================================================

def create_post(user_id, data):
    """Create a new discussion post.

    Args:
        user_id: The author's user ID.
        data: dict with title, content, category, tags (list of strings).

    Returns:
        The new post row ID.
    """
    title = _sanitize(data.get('title', ''))
    if not title:
        raise ValueError("Post title is required")

    content = _sanitize(data.get('content', ''))
    if not content:
        raise ValueError("Post content is required")

    category = data.get('category', 'general')
    _validate_enum(category, VALID_CATEGORIES, 'category')
    tags = data.get('tags')
    if isinstance(tags, list):
        tags = json.dumps([_sanitize(t) for t in tags])
    elif tags:
        tags = json.dumps([_sanitize(tags)])
    else:
        tags = '[]'

    with get_db() as conn:
        cursor = conn.execute('''
            INSERT INTO discussion_posts
                (user_id, title, content, category, tags)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, title, content, category, tags))
        post_id = cursor.lastrowid

    logger.info("Post %s created by user %s: %s", post_id, user_id, title)
    return post_id


def get_posts(category=None, page=1, per_page=20):
    """Return a paginated list of discussion posts.

    Pinned posts always appear first.
    """
    clauses = []
    params = []

    if category:
        _validate_enum(category, VALID_CATEGORIES, 'category')
        clauses.append("category = ?")
        params.append(category)

    where = "WHERE " + " AND ".join(clauses) if clauses else ""

    page = max(1, int(page))
    per_page = max(1, min(int(per_page), 100))
    offset = (page - 1) * per_page

    # Count total
    count_sql = f'SELECT COUNT(*) as total FROM discussion_posts {where}'
    list_sql = f'''
        SELECT * FROM discussion_posts
        {where}
        ORDER BY is_pinned DESC, created_at DESC
        LIMIT ? OFFSET ?
    '''

    with get_db() as conn:
        total_row = conn.execute(count_sql, tuple(params)).fetchone()
        total = int(total_row['total']) if total_row else 0

        list_params = list(params) + [per_page, offset]
        rows = conn.execute(list_sql, tuple(list_params)).fetchall()

    posts = []
    for r in rows:
        post = dict(r)
        # Parse tags JSON
        try:
            post['tags'] = json.loads(post.get('tags', '[]'))
        except (json.JSONDecodeError, TypeError):
            post['tags'] = []
        posts.append(post)

    return {
        'posts': posts,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': max(1, -(-total // per_page)),  # ceiling division
    }


def get_post_by_id(post_id):
    """Return a single discussion post with its replies.

    Returns:
        dict with the post data and a 'replies' list, or None if not found.
    """
    with get_db() as conn:
        post_row = conn.execute(
            'SELECT * FROM discussion_posts WHERE id = ?',
            (post_id,)
        ).fetchone()

        if not post_row:
            return None
        reply_rows = conn.execute('''
            SELECT * FROM discussion_replies
            WHERE post_id = ?
            ORDER BY is_accepted DESC, upvotes DESC, created_at ASC
        ''', (post_id,)).fetchall()

    post = dict(post_row)
    try:
        post['tags'] = json.loads(post.get('tags', '[]'))
    except (json.JSONDecodeError, TypeError):
        post['tags'] = []

    post['replies'] = [dict(r) for r in reply_rows]
    return post


def create_reply(post_id, user_id, content):
    """Add a reply to a discussion post.

    Returns:
        The new reply row ID.
    """
    content = _sanitize(content)
    if not content:
        raise ValueError("Reply content is required")

    with get_db() as conn:
        # Verify post exists
        post = conn.execute(
            'SELECT id FROM discussion_posts WHERE id = ?', (post_id,)
        ).fetchone()
        if not post:
            raise ValueError(f"Post {post_id} not found")

        cursor = conn.execute('''
            INSERT INTO discussion_replies (post_id, user_id, content)
            VALUES (?, ?, ?)
        ''', (post_id, user_id, content))
        reply_id = cursor.lastrowid

        # Increment reply count
        conn.execute(
            'UPDATE discussion_posts SET reply_count = reply_count + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (post_id,)
        )

    logger.info("Reply %s added to post %s by user %s", reply_id, post_id, user_id)
    return reply_id


def upvote_post(post_id, user_id):
    """Increment the upvote count on a discussion post.

    Note: This is a simple increment.  For production use you would
    track individual votes to prevent duplicates, similar to alert_votes.

    Returns:
        The new upvote total.
    """
    with get_db() as conn:
        conn.execute(
            'UPDATE discussion_posts SET upvotes = upvotes + 1 WHERE id = ?',
            (post_id,)
        )
        row = conn.execute(
            'SELECT upvotes FROM discussion_posts WHERE id = ?',
            (post_id,)
        ).fetchone()

    return int(row['upvotes']) if row else 0


def accept_reply(reply_id, post_id, user_id):
    """Mark a reply as the accepted answer.

    Only the original post author may accept a reply.  Any previously
    accepted reply on the same post is un-accepted first.

    Returns:
        True on success, False if the user is not the post author.
    """
    with get_db() as conn:
        # Verify post ownership
        post = conn.execute(
            'SELECT user_id FROM discussion_posts WHERE id = ?',
            (post_id,)
        ).fetchone()

        if not post or int(post['user_id']) != int(user_id):
            logger.warning(
                "User %s tried to accept reply %s on post %s but is not the author",
                user_id, reply_id, post_id
            )
            return False

        # Un-accept any previously accepted reply on this post
        conn.execute(
            'UPDATE discussion_replies SET is_accepted = 0 WHERE post_id = ? AND is_accepted = 1',
            (post_id,)
        )

        # Accept the target reply
        conn.execute(
            'UPDATE discussion_replies SET is_accepted = 1 WHERE id = ? AND post_id = ?',
            (reply_id, post_id)
        )

    logger.info("Reply %s accepted on post %s by user %s", reply_id, post_id, user_id)
    return True


def get_trending_posts(days=7, limit=10):
    """Return the most active discussion posts from the last *days* days.

    Active is determined by a combination of upvotes and reply count.
    """
    sql = '''
        SELECT * FROM discussion_posts
        WHERE created_at >= DATE('now', ? || ' days')
        ORDER BY (upvotes + reply_count) DESC, created_at DESC
        LIMIT ?
    '''

    with get_db() as conn:
        rows = conn.execute(sql, (str(-abs(days)), limit)).fetchall()

    results = []
    for r in rows:
        post = dict(r)
        try:
            post['tags'] = json.loads(post.get('tags', '[]'))
        except (json.JSONDecodeError, TypeError):
            post['tags'] = []
        results.append(post)

    return results


def delete_post(post_id, user_id):
    """Permanently delete a discussion post and its replies."""
    with get_db() as conn:
        row = conn.execute(
            'SELECT id FROM discussion_posts WHERE id = ? AND user_id = ?',
            (post_id, user_id)
        ).fetchone()
        if not row:
            return {'error': 'Post not found or access denied'}
        conn.execute('DELETE FROM discussion_replies WHERE post_id = ?', (post_id,))
        conn.execute('DELETE FROM discussion_posts WHERE id = ? AND user_id = ?', (post_id, user_id))
    logger.info(f"Deleted post {post_id} for user {user_id}")
    return {'success': True}


def delete_alert(alert_id, user_id):
    """Permanently delete a regional alert and its votes."""
    with get_db() as conn:
        row = conn.execute(
            'SELECT id FROM regional_alerts WHERE id = ? AND user_id = ?',
            (alert_id, user_id)
        ).fetchone()
        if not row:
            return {'error': 'Alert not found or access denied'}
        conn.execute('DELETE FROM alert_votes WHERE alert_id = ?', (alert_id,))
        conn.execute('DELETE FROM regional_alerts WHERE id = ? AND user_id = ?', (alert_id, user_id))
    logger.info(f"Deleted alert {alert_id} for user {user_id}")
    return {'success': True}