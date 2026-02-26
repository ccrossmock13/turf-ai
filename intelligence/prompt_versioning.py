"""
Intelligence Engine — Subsystem 13: Prompt Versioning & Optimization
======================================================================
Version control for system prompts with performance tracking.
"""

import hashlib
import json
import logging
from typing import List, Dict, Optional

from intelligence.db import _get_conn, log_event

logger = logging.getLogger(__name__)


class PromptVersioning:
    """Version control for system prompts with performance tracking."""

    @staticmethod
    def create_version(template_text: str, description: str = '',
                       changes: str = '', created_by: str = 'admin') -> int:
        """Create a new prompt version."""
        try:
            conn = _get_conn()
            template_hash = hashlib.sha256(template_text.encode()).hexdigest()[:16]

            # Get next version number
            max_v = conn.execute('SELECT MAX(version) FROM prompt_templates').fetchone()[0]
            version = (max_v or 0) + 1

            cursor = conn.execute('''
                INSERT INTO prompt_templates
                (version, template_hash, template_text, description, changes, created_by)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (version, template_hash, template_text, description, changes, created_by))
            version_id = cursor.lastrowid
            conn.commit()
            conn.close()
            log_event('prompt_versioning', 'version_created',
                      json.dumps({'id': version_id, 'version': version}))
            return version_id
        except Exception as e:
            logger.error(f"Create prompt version error: {e}")
            return 0

    @staticmethod
    def activate_version(version_id: int) -> bool:
        """Activate a prompt version (deactivate all others)."""
        try:
            conn = _get_conn()
            conn.execute('UPDATE prompt_templates SET is_active = 0, deactivated_at = CURRENT_TIMESTAMP WHERE is_active = 1')
            conn.execute('''
                UPDATE prompt_templates SET is_active = 1, activated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (version_id,))
            conn.commit()
            conn.close()
            log_event('prompt_versioning', 'version_activated',
                      json.dumps({'id': version_id}))
            return True
        except Exception as e:
            logger.error(f"Activate version error: {e}")
            return False

    @staticmethod
    def get_active_version() -> Optional[Dict]:
        """Get the currently active prompt version."""
        try:
            conn = _get_conn()
            row = conn.execute(
                'SELECT * FROM prompt_templates WHERE is_active = 1 LIMIT 1'
            ).fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Get active version error: {e}")
            return None

    @staticmethod
    def rollback(version_id: int) -> bool:
        """Rollback to a specific prompt version."""
        return PromptVersioning.activate_version(version_id)

    @staticmethod
    def log_usage(version_id: int, query_id: int, confidence: float = None,
                  satisfaction: str = None):
        """Log usage of a prompt version for performance tracking."""
        try:
            conn = _get_conn()
            conn.execute('''
                INSERT INTO prompt_usage_log (version_id, query_id, confidence, satisfaction_rating)
                VALUES (?, ?, ?, ?)
            ''', (version_id, query_id, confidence, satisfaction))
            conn.execute('''
                UPDATE prompt_templates SET total_queries = total_queries + 1 WHERE id = ?
            ''', (version_id,))
            if confidence is not None:
                conn.execute('''
                    UPDATE prompt_templates
                    SET avg_confidence = (COALESCE(avg_confidence, 0) * (total_queries - 1) + ?) / total_queries
                    WHERE id = ?
                ''', (confidence, version_id))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Log prompt usage error: {e}")

    @staticmethod
    def get_all_versions() -> List[Dict]:
        """Get all prompt versions with performance data."""
        try:
            conn = _get_conn()
            rows = conn.execute('''
                SELECT id, version, template_hash, description, changes, is_active,
                       total_queries, avg_confidence, avg_satisfaction,
                       created_by, created_at, activated_at
                FROM prompt_templates ORDER BY version DESC
            ''').fetchall()
            conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Get all versions error: {e}")
            return []

    @staticmethod
    def compare_versions(v1_id: int, v2_id: int) -> Dict:
        """Compare two prompt versions' text and performance."""
        try:
            conn = _get_conn()
            v1 = conn.execute('SELECT * FROM prompt_templates WHERE id = ?', (v1_id,)).fetchone()
            v2 = conn.execute('SELECT * FROM prompt_templates WHERE id = ?', (v2_id,)).fetchone()
            conn.close()

            if not v1 or not v2:
                return {'error': 'Version not found'}

            v1, v2 = dict(v1), dict(v2)
            # Simple line diff
            lines1 = v1['template_text'].splitlines()
            lines2 = v2['template_text'].splitlines()
            added = [l for l in lines2 if l not in lines1]
            removed = [l for l in lines1 if l not in lines2]

            return {
                'v1': {'id': v1_id, 'version': v1['version'], 'queries': v1['total_queries'],
                       'avg_confidence': v1['avg_confidence']},
                'v2': {'id': v2_id, 'version': v2['version'], 'queries': v2['total_queries'],
                       'avg_confidence': v2['avg_confidence']},
                'lines_added': len(added),
                'lines_removed': len(removed),
                'added_sample': added[:10],
                'removed_sample': removed[:10]
            }
        except Exception as e:
            logger.error(f"Compare versions error: {e}")
            return {'error': str(e)}
