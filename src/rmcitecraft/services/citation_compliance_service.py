"""Citation compliance service for orchestrating compliance checks and fixes.

This service provides the business logic for:
- Running compliance analysis across sources
- Generating transformation proposals
- Applying fixes with audit trail
- Tracking compliance sessions
"""

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from rmcitecraft.services.citation_transformer import CitationTransformer, TransformationResult


@dataclass
class ComplianceIssue:
    """A compliance issue found in a source."""
    issue_type: str
    description: str
    field: str
    severity: str = 'warning'


@dataclass
class SourceComplianceResult:
    """Compliance check result for a single source."""
    source_id: int
    source_name: str
    source_type: str
    footnote: str
    short_footnote: str
    bibliography: str
    issues: list[ComplianceIssue] = field(default_factory=list)

    @property
    def is_compliant(self) -> bool:
        return len(self.issues) == 0

    @property
    def issue_types(self) -> set[str]:
        return {i.issue_type for i in self.issues}


@dataclass
class ComplianceSession:
    """A compliance fix session."""
    session_id: str
    created_at: datetime
    status: str = 'active'
    description: str = ''
    source_type_filter: Optional[str] = None
    issue_type_filter: Optional[str] = None
    total_sources: int = 0
    sources_fixed: int = 0
    sources_skipped: int = 0
    sources_errored: int = 0


class CitationComplianceService:
    """Service for managing citation compliance checks and fixes.

    This service coordinates between:
    - The RootsMagic database (SourceTable)
    - The compliance batch state database
    - The CitationTransformer for generating proposals
    """

    def __init__(self, state_db_path: str = None):
        """Initialize the compliance service.

        Args:
            state_db_path: Path to the compliance state database.
                          Defaults to ~/.rmcitecraft/compliance_state.db
        """
        if state_db_path is None:
            state_db_path = Path.home() / '.rmcitecraft' / 'compliance_state.db'

        self.state_db_path = Path(state_db_path)
        self.state_db_path.parent.mkdir(parents=True, exist_ok=True)

        self.transformer = CitationTransformer()
        self._init_state_db()

    def _init_state_db(self):
        """Initialize the state database with required tables."""
        conn = sqlite3.connect(self.state_db_path)

        # Read migration file
        migration_file = Path(__file__).parent.parent.parent.parent / 'migrations' / '006_create_compliance_batch_tables.sql'

        if migration_file.exists():
            with open(migration_file) as f:
                conn.executescript(f.read())
        else:
            # Inline minimal schema if migration file not found
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS compliance_sessions (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    status TEXT NOT NULL DEFAULT 'active',
                    description TEXT,
                    source_type_filter TEXT,
                    issue_type_filter TEXT,
                    total_sources INTEGER DEFAULT 0,
                    sources_fixed INTEGER DEFAULT 0,
                    sources_skipped INTEGER DEFAULT 0,
                    sources_errored INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS compliance_batch_items (
                    id INTEGER PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    source_id INTEGER NOT NULL,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    original_footnote TEXT,
                    original_short_footnote TEXT,
                    original_bibliography TEXT,
                    proposed_footnote TEXT,
                    proposed_short_footnote TEXT,
                    proposed_bibliography TEXT,
                    confidence_score REAL,
                    transformation_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    applied_at TIMESTAMP,
                    error_message TEXT,
                    review_notes TEXT,
                    UNIQUE(session_id, source_id)
                );
            """)

        conn.commit()
        conn.close()

    def _extract_field(self, fields_text: str, field_name: str) -> str:
        """Extract a field from SourceTable.Fields XML."""
        if not fields_text:
            return ""
        pattern = rf'<Name>{field_name}</Name>\s*<Value>(.*?)</Value>'
        match = re.search(pattern, fields_text, re.DOTALL)
        return match.group(1).strip() if match else ""

    def _extract_source_type(self, source_name: str) -> str:
        """Extract source type from source name."""
        if ':' in source_name:
            return source_name.split(':')[0].strip()
        return "Other"

    def check_source_compliance(self, source_id: int, source_name: str,
                                 fields_text: str) -> SourceComplianceResult:
        """Check a single source for compliance issues.

        Args:
            source_id: RootsMagic SourceID
            source_name: Source name
            fields_text: Decoded SourceTable.Fields XML

        Returns:
            SourceComplianceResult with all detected issues
        """
        fn = self._extract_field(fields_text, 'Footnote')
        sf = self._extract_field(fields_text, 'ShortFootnote')
        bib = self._extract_field(fields_text, 'Bibliography')

        # Decode entities for comparison
        fn_decoded = fn.replace('&lt;', '<').replace('&gt;', '>')
        sf_decoded = sf.replace('&lt;', '<').replace('&gt;', '>')
        bib_decoded = bib.replace('&lt;', '<').replace('&gt;', '>')

        result = SourceComplianceResult(
            source_id=source_id,
            source_name=source_name,
            source_type=self._extract_source_type(source_name),
            footnote=fn,
            short_footnote=sf,
            bibliography=bib
        )

        # P1: Double spaces
        for field_name, text in [('footnote', fn_decoded), ('short_footnote', sf_decoded),
                                  ('bibliography', bib_decoded)]:
            if re.search(r'  +', text):
                result.issues.append(ComplianceIssue(
                    issue_type='P1_DOUBLE_SPACES',
                    description=f'Double spaces in {field_name}',
                    field=field_name
                ))

        # P2: Missing period
        for field_name, text in [('footnote', fn_decoded), ('bibliography', bib_decoded)]:
            text = text.strip()
            if text and not text.endswith('.'):
                if text[-1] in ')"\'' or text[-1].isalnum():
                    result.issues.append(ComplianceIssue(
                        issue_type='P2_MISSING_PERIOD',
                        description=f'Missing period in {field_name}',
                        field=field_name
                    ))

        # P3: FN = SF
        if fn_decoded and sf_decoded and fn_decoded.strip() == sf_decoded.strip():
            result.issues.append(ComplianceIssue(
                issue_type='P3_FN_EQUALS_SF',
                description='Footnote identical to short footnote',
                field='all',
                severity='error'
            ))

        # P4: FN = BIB
        if fn_decoded and bib_decoded and fn_decoded.strip() == bib_decoded.strip():
            result.issues.append(ComplianceIssue(
                issue_type='P4_FN_EQUALS_BIB',
                description='Footnote identical to bibliography',
                field='all',
                severity='error'
            ))

        # P5: Missing access date
        has_url = 'http' in fn_decoded.lower() or 'familysearch' in fn_decoded.lower()
        has_accessed = bool(re.search(r'accessed\s+\d{1,2}\s+\w+\s+\d{4}', fn_decoded, re.IGNORECASE))
        if has_url and not has_accessed:
            result.issues.append(ComplianceIssue(
                issue_type='P5_MISSING_ACCESS_DATE',
                description='Missing access date for URL',
                field='footnote'
            ))

        # P6: Empty citations
        if not fn_decoded.strip():
            result.issues.append(ComplianceIssue(
                issue_type='P6_EMPTY_CITATION',
                description='Empty footnote',
                field='footnote',
                severity='error'
            ))
        if not sf_decoded.strip():
            result.issues.append(ComplianceIssue(
                issue_type='P6_EMPTY_CITATION',
                description='Empty short footnote',
                field='short_footnote',
                severity='error'
            ))
        if not bib_decoded.strip():
            result.issues.append(ComplianceIssue(
                issue_type='P6_EMPTY_CITATION',
                description='Empty bibliography',
                field='bibliography',
                severity='error'
            ))

        return result

    def create_session(self, description: str = '',
                       source_type_filter: str = None,
                       issue_type_filter: str = None) -> ComplianceSession:
        """Create a new compliance session.

        Args:
            description: Session description
            source_type_filter: Optional filter for source type
            issue_type_filter: Optional filter for issue type

        Returns:
            New ComplianceSession
        """
        session = ComplianceSession(
            session_id=str(uuid.uuid4()),
            created_at=datetime.now(),
            description=description,
            source_type_filter=source_type_filter,
            issue_type_filter=issue_type_filter
        )

        conn = sqlite3.connect(self.state_db_path)
        conn.execute("""
            INSERT INTO compliance_sessions
            (session_id, created_at, status, description, source_type_filter, issue_type_filter)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            session.session_id,
            session.created_at.isoformat(),
            session.status,
            session.description,
            session.source_type_filter,
            session.issue_type_filter
        ))
        conn.commit()
        conn.close()

        return session

    def add_batch_item(self, session_id: str, result: SourceComplianceResult,
                       proposed_sf: str = None, proposed_bib: str = None,
                       confidence: float = 0.0, notes: list[str] = None):
        """Add a batch item to a session.

        Args:
            session_id: Session ID
            result: Compliance check result
            proposed_sf: Proposed short footnote
            proposed_bib: Proposed bibliography
            confidence: Transformation confidence score
            notes: Transformation notes
        """
        conn = sqlite3.connect(self.state_db_path)
        conn.execute("""
            INSERT OR REPLACE INTO compliance_batch_items
            (session_id, source_id, source_name, source_type, issue_type,
             original_footnote, original_short_footnote, original_bibliography,
             proposed_short_footnote, proposed_bibliography,
             confidence_score, transformation_notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            result.source_id,
            result.source_name,
            result.source_type,
            list(result.issue_types)[0] if result.issue_types else 'UNKNOWN',
            result.footnote,
            result.short_footnote,
            result.bibliography,
            proposed_sf,
            proposed_bib,
            confidence,
            json.dumps(notes or [])
        ))
        conn.commit()
        conn.close()

    def generate_proposals_for_source(self, result: SourceComplianceResult) -> dict[str, Any]:
        """Generate transformation proposals for a source.

        Args:
            result: Compliance check result

        Returns:
            Dictionary with 'short_footnote' and 'bibliography' TransformationResults
        """
        proposals = {}

        # Generate short footnote if FN = SF
        if 'P3_FN_EQUALS_SF' in result.issue_types:
            sf_result = self.transformer.generate_short_footnote(
                result.footnote,
                result.source_type.lower() if result.source_type == 'Fed Census' else 'auto'
            )
            proposals['short_footnote'] = {
                'text': sf_result.transformed,
                'confidence': sf_result.confidence,
                'notes': sf_result.notes
            }

        # Generate bibliography if FN = BIB
        if 'P4_FN_EQUALS_BIB' in result.issue_types:
            bib_result = self.transformer.generate_bibliography(
                result.footnote,
                result.source_type.lower() if result.source_type == 'Fed Census' else 'auto'
            )
            proposals['bibliography'] = {
                'text': bib_result.transformed,
                'confidence': bib_result.confidence,
                'notes': bib_result.notes
            }

        return proposals

    def get_session_items(self, session_id: str,
                          status_filter: str = None) -> list[dict]:
        """Get batch items for a session.

        Args:
            session_id: Session ID
            status_filter: Optional status filter

        Returns:
            List of batch item dictionaries
        """
        conn = sqlite3.connect(self.state_db_path)
        conn.row_factory = sqlite3.Row

        query = "SELECT * FROM compliance_batch_items WHERE session_id = ?"
        params = [session_id]

        if status_filter:
            query += " AND status = ?"
            params.append(status_filter)

        cursor = conn.execute(query, params)
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return items

    def update_item_status(self, session_id: str, source_id: int,
                           status: str, review_notes: str = ''):
        """Update the status of a batch item.

        Args:
            session_id: Session ID
            source_id: Source ID
            status: New status
            review_notes: Optional review notes
        """
        conn = sqlite3.connect(self.state_db_path)
        conn.execute("""
            UPDATE compliance_batch_items
            SET status = ?, review_notes = ?, updated_at = ?
            WHERE session_id = ? AND source_id = ?
        """, (status, review_notes, datetime.now().isoformat(), session_id, source_id))
        conn.commit()
        conn.close()

    def complete_session(self, session_id: str, stats: dict[str, int]):
        """Mark a session as completed.

        Args:
            session_id: Session ID
            stats: Statistics dictionary with counts
        """
        conn = sqlite3.connect(self.state_db_path)
        conn.execute("""
            UPDATE compliance_sessions
            SET status = 'completed',
                completed_at = ?,
                total_sources = ?,
                sources_fixed = ?,
                sources_skipped = ?,
                sources_errored = ?
            WHERE session_id = ?
        """, (
            datetime.now().isoformat(),
            stats.get('total', 0),
            stats.get('fixed', 0),
            stats.get('skipped', 0),
            stats.get('errored', 0),
            session_id
        ))
        conn.commit()
        conn.close()

    def save_snapshot(self, total: int, compliant: int, issue_counts: dict[str, int],
                      details: dict = None):
        """Save a compliance snapshot for progress tracking.

        Args:
            total: Total source count
            compliant: Compliant source count
            issue_counts: Dictionary of issue type -> count
            details: Optional detailed breakdown
        """
        conn = sqlite3.connect(self.state_db_path)
        conn.execute("""
            INSERT INTO compliance_snapshots
            (total_sources, compliant_sources, sources_with_issues,
             p1_double_spaces, p2_missing_period, p3_fn_equals_sf,
             p4_fn_equals_bib, p5_missing_access_date, p6_empty_citations,
             details_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            total,
            compliant,
            total - compliant,
            issue_counts.get('P1_DOUBLE_SPACES', 0),
            issue_counts.get('P2_MISSING_PERIOD', 0),
            issue_counts.get('P3_FN_EQUALS_SF', 0),
            issue_counts.get('P4_FN_EQUALS_BIB', 0),
            issue_counts.get('P5_MISSING_ACCESS_DATE', 0),
            issue_counts.get('P6_EMPTY_CITATION', 0) + issue_counts.get('P6_EMPTY_FN', 0) +
            issue_counts.get('P6_EMPTY_SF', 0) + issue_counts.get('P6_EMPTY_BIB', 0),
            json.dumps(details) if details else None
        ))
        conn.commit()
        conn.close()

    def get_snapshots(self, limit: int = 10) -> list[dict]:
        """Get recent compliance snapshots.

        Args:
            limit: Maximum number of snapshots to return

        Returns:
            List of snapshot dictionaries
        """
        conn = sqlite3.connect(self.state_db_path)
        conn.row_factory = sqlite3.Row

        cursor = conn.execute("""
            SELECT * FROM compliance_snapshots
            ORDER BY snapshot_date DESC
            LIMIT ?
        """, (limit,))

        snapshots = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return snapshots
