#!/usr/bin/env python3
"""
Analyze World War I and World War II draft registration records in RootsMagic database.

This script provides comprehensive analysis of draft registration events (EventTypes 1021, 1024, 1025),
including breakdowns by images, notes, and citations attached to each event.

Usage:
    uv run python scripts/analyze_draft_registrations.py
    uv run python scripts/analyze_draft_registrations.py --html output.html
    uv run python scripts/analyze_draft_registrations.py --html output.html --detailed
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from rich.layout import Layout
from rich.text import Text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rmcitecraft.database.connection import connect_rmtree


# Draft registration reference data
DRAFT_PREAMBLE_MD = """
# World War I & II Draft Registrations

## World War I Draft Registrations

| Registration | Date | Ages | Birth Year Range | Men Registered |
|---|---|---|---|---|
| **First** | June 5, 1917 | 21–31 | June 1886 – June 1896 | 10.3M |
| **Second** | June 5, 1918 | 21 (new since 1st) | June 1896 – June 1897 | 1.00M |
| **Supplemental** | August 24, 1918 | 21 (new since 2nd) | June 1897 – Aug 1897 | (incl. in 2nd) |
| **Third** | September 12, 1918 | 18–45 (not previously registered) | Sept 1872 – Sept 1900 | 13.0M |
| | | | **TOTAL** | **24.0M** |

## World War II Draft Registrations

| Registration | Date | Ages | Birth Year Range | Men Registered |
|---|---|---|---|---|
| **First** | October 16, 1940 | 21–35 | Oct 1904 – Oct 1919 | 16.4M |
| **Second** | July 1, 1941 | 21 (new since 1st) | Oct 1919 – July 1920 | 1.00M |
| **Third** | February 16, 1942 | 20–44 (not previously registered) | Feb 1897 – Feb 1922 | 9.00M |
| **Fourth** ("Old Man's Draft") | April 27, 1942 | 45–64 | Apr 1877 – Feb 1897 | 13.0M |
| **Fifth** | June 30, 1942 | 18–20 | July 1921 – June 1924 | 5.00M |
| **Sixth** | December 10–31, 1942 | 18 (new since 5th) | July 1924 – Dec 1924 | 1.00M |
| **Extra** | November 16 – December 31, 1943 | 18–44 (Americans abroad) | Dec 1899 – Dec 1925 | Unknown |
| | | | **TOTAL** | **~49.0M** |

## Important Notes

- During World War I there were three registrations. The first, on June 5, 1917, was for all men between
  the ages of 21 and 31. The second, on June 5, 1918, registered those who attained age 21 after June 5, 1917.
  A supplemental registration was held on August 24, 1918, for those becoming 21 years old after June 5, 1918.
  The third registration was held on September 12, 1918, for men age 18 through 45.

- **As there is overlap in the WWI and WWII Selective Service registration birth years (1877 to 1900),
  some men may have registered twice and have both WWI and WWII draft records.**

- The Extra Registration was for American men ages 18–44 who were living abroad.

- The Fourth WWII Registration ("Old Man's Draft") was not for military service but to inventory
  manpower and skills for the war effort.
"""

EVENT_TYPES = {
    1021: "World War I - Draft Registration",
    1024: "World War II - Old Man's Draft Registration",
    1025: "World War II - Primary Draft Registration"
}


def get_event_analysis(cursor, event_type: int) -> Dict[str, Any]:
    """Get comprehensive analysis for a specific event type."""

    # Total count of events
    cursor.execute("""
        SELECT COUNT(DISTINCT e.EventID)
        FROM EventTable e
        WHERE e.EventType = ?
    """, (event_type,))
    total_events = cursor.fetchone()[0]

    # Count of unique people
    cursor.execute("""
        SELECT COUNT(DISTINCT e.OwnerID)
        FROM EventTable e
        WHERE e.EventType = ? AND e.OwnerType = 0
    """, (event_type,))
    total_people = cursor.fetchone()[0]

    # Events with images (OwnerType = 2 for EventTable)
    cursor.execute("""
        SELECT COUNT(DISTINCT e.EventID)
        FROM EventTable e
        WHERE e.EventType = ?
          AND EXISTS (
              SELECT 1 FROM MediaLinkTable ml
              WHERE ml.OwnerID = e.EventID AND ml.OwnerType = 2
          )
    """, (event_type,))
    with_images = cursor.fetchone()[0]

    # Events with notes
    cursor.execute("""
        SELECT COUNT(DISTINCT e.EventID)
        FROM EventTable e
        WHERE e.EventType = ?
          AND e.Note IS NOT NULL
          AND CAST(e.Note AS TEXT) != ''
    """, (event_type,))
    with_notes = cursor.fetchone()[0]

    # Events with citations (OwnerType = 2 for EventTable)
    cursor.execute("""
        SELECT COUNT(DISTINCT e.EventID)
        FROM EventTable e
        WHERE e.EventType = ?
          AND EXISTS (
              SELECT 1 FROM CitationLinkTable cl
              WHERE cl.OwnerID = e.EventID AND cl.OwnerType = 2
          )
    """, (event_type,))
    with_citations = cursor.fetchone()[0]

    return {
        'total_events': total_events,
        'total_people': total_people,
        'with_images': with_images,
        'with_notes': with_notes,
        'with_citations': with_citations
    }


def get_all_records(cursor) -> List[Tuple]:
    """Get all draft registration records with details."""
    cursor.execute("""
        SELECT
            p.PersonID as RIN,
            n.Given,
            n.Surname,
            e.EventType,
            e.EventID,
            (SELECT e2.Date FROM EventTable e2 WHERE e2.OwnerID = p.PersonID AND e2.EventType = 1) as BirthDate,
            (SELECT COUNT(*) FROM MediaLinkTable ml
             WHERE ml.OwnerID = e.EventID AND ml.OwnerType = 2) as img_count,
            CASE WHEN e.Note IS NOT NULL AND CAST(e.Note AS TEXT) != '' THEN 1 ELSE 0 END as has_note,
            (SELECT COUNT(*) FROM CitationLinkTable cl
             WHERE cl.OwnerID = e.EventID AND cl.OwnerType = 2) as cit_count
        FROM EventTable e
        JOIN PersonTable p ON p.PersonID = e.OwnerID AND e.OwnerType = 0
        JOIN NameTable n ON n.OwnerID = p.PersonID AND n.IsPrimary = 1
        WHERE e.EventType IN (1021, 1024, 1025)
        ORDER BY e.EventType, n.Surname, n.Given
    """)

    return cursor.fetchall()


def get_completeness_stats(cursor) -> Dict[str, int]:
    """Get completeness statistics across all draft types."""
    cursor.execute("""
        SELECT
            SUM(CASE WHEN has_img = 1 AND has_cit = 1 AND has_note = 1 THEN 1 ELSE 0 END) as complete_all,
            SUM(CASE WHEN has_img = 1 AND has_cit = 1 THEN 1 ELSE 0 END) as has_img_and_cit,
            SUM(CASE WHEN has_img = 1 THEN 1 ELSE 0 END) as has_img_only,
            SUM(CASE WHEN has_cit = 1 THEN 1 ELSE 0 END) as has_cit_only,
            SUM(CASE WHEN has_note = 1 THEN 1 ELSE 0 END) as has_note_only,
            SUM(CASE WHEN has_img = 0 AND has_cit = 0 AND has_note = 0 THEN 1 ELSE 0 END) as empty,
            COUNT(*) as total
        FROM (
            SELECT e.EventID,
                   CASE WHEN EXISTS (SELECT 1 FROM MediaLinkTable ml
                                    WHERE ml.OwnerID = e.EventID AND ml.OwnerType = 2)
                        THEN 1 ELSE 0 END as has_img,
                   CASE WHEN EXISTS (SELECT 1 FROM CitationLinkTable cl
                                    WHERE cl.OwnerID = e.EventID AND cl.OwnerType = 2)
                        THEN 1 ELSE 0 END as has_cit,
                   CASE WHEN e.Note IS NOT NULL AND CAST(e.Note AS TEXT) != ''
                        THEN 1 ELSE 0 END as has_note
            FROM EventTable e
            WHERE e.EventType IN (1021, 1024, 1025)
        )
    """)

    result = cursor.fetchone()
    return {
        'complete_all': result[0],
        'img_and_cit': result[1],
        'img_only': result[2],
        'cit_only': result[3],
        'note_only': result[4],
        'empty': result[5],
        'total': result[6]
    }


def display_terminal_output(console: Console, conn, detailed: bool = False):
    """Display analysis in terminal using Rich."""

    cursor = conn.cursor()

    # Display preamble
    console.print()
    console.print(Markdown(DRAFT_PREAMBLE_MD))
    console.print()

    # Analysis header
    console.print(Panel.fit(
        "[bold cyan]Draft Registration Events Analysis[/bold cyan]",
        border_style="cyan"
    ))
    console.print()

    # Analyze each event type
    for event_type, event_name in EVENT_TYPES.items():
        stats = get_event_analysis(cursor, event_type)

        # Create summary table
        table = Table(title=f"[bold]{event_name}[/bold] (EventType {event_type})",
                     show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", justify="right", style="green")
        table.add_column("Percentage", justify="right", style="yellow")

        total = stats['total_events']

        table.add_row("Total Events", str(total), "100.0%")
        table.add_row("Total People", str(stats['total_people']), "—")
        table.add_row(
            "With Images",
            str(stats['with_images']),
            f"{stats['with_images']/total*100:.1f}%" if total > 0 else "—"
        )
        table.add_row(
            "With Notes",
            str(stats['with_notes']),
            f"{stats['with_notes']/total*100:.1f}%" if total > 0 else "—"
        )
        table.add_row(
            "With Citations",
            str(stats['with_citations']),
            f"{stats['with_citations']/total*100:.1f}%" if total > 0 else "—"
        )

        console.print(table)
        console.print()

    # Overall summary
    cursor.execute("""
        SELECT COUNT(DISTINCT e.OwnerID)
        FROM EventTable e
        WHERE e.EventType IN (1021, 1024, 1025) AND e.OwnerType = 0
    """)
    total_unique_people = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT e.OwnerID
            FROM EventTable e
            WHERE e.EventType IN (1021, 1024, 1025) AND e.OwnerType = 0
            GROUP BY e.OwnerID
            HAVING COUNT(DISTINCT e.EventType) > 1
        )
    """)
    people_with_multiple = cursor.fetchone()[0]

    summary_table = Table(title="[bold]Overall Summary[/bold]", show_header=False)
    summary_table.add_column("Label", style="cyan")
    summary_table.add_column("Value", justify="right", style="green")

    summary_table.add_row("Total unique people with any draft registration", str(total_unique_people))
    summary_table.add_row("People with multiple draft registration types", str(people_with_multiple))

    console.print(summary_table)
    console.print()

    # Completeness analysis
    completeness = get_completeness_stats(cursor)
    total = completeness['total']

    comp_table = Table(title="[bold]Completeness Analysis[/bold] (All Draft Types Combined)",
                       show_header=True, header_style="bold magenta")
    comp_table.add_column("Category", style="cyan")
    comp_table.add_column("Count", justify="right", style="green")
    comp_table.add_column("Percentage", justify="right", style="yellow")

    comp_table.add_row(
        "Image + Citation + Note (Complete)",
        str(completeness['complete_all']),
        f"{completeness['complete_all']/total*100:.1f}%"
    )
    comp_table.add_row(
        "Image + Citation",
        str(completeness['img_and_cit']),
        f"{completeness['img_and_cit']/total*100:.1f}%"
    )
    comp_table.add_row(
        "Image Only",
        str(completeness['img_only']),
        f"{completeness['img_only']/total*100:.1f}%"
    )
    comp_table.add_row(
        "Citation Only",
        str(completeness['cit_only']),
        f"{completeness['cit_only']/total*100:.1f}%"
    )
    comp_table.add_row(
        "Note Only",
        str(completeness['note_only']),
        f"{completeness['note_only']/total*100:.1f}%"
    )
    comp_table.add_row(
        "Nothing Attached",
        str(completeness['empty']),
        f"{completeness['empty']/total*100:.1f}%",
        style="red"
    )

    console.print(comp_table)
    console.print()

    # Detailed records table
    if detailed:
        records = get_all_records(cursor)

        detail_table = Table(title="[bold]All Draft Registration Records[/bold]",
                           show_header=True, header_style="bold magenta")
        detail_table.add_column("RIN", justify="right", style="cyan")
        detail_table.add_column("Name", style="white")
        detail_table.add_column("Birth Year", justify="center", style="yellow")
        detail_table.add_column("Draft Type", style="blue")
        detail_table.add_column("Images", justify="center", style="green")
        detail_table.add_column("Note", justify="center", style="magenta")
        detail_table.add_column("Citations", justify="center", style="green")

        for record in records:
            rin, given, surname, event_type, event_id, birth_date, img_count, has_note, cit_count = record

            # Extract birth year
            birth_year = birth_date[3:7] if birth_date and len(birth_date) >= 7 else "?"

            # Format event type
            if event_type == 1021:
                draft_type = "WWI"
            elif event_type == 1024:
                draft_type = "WWII-Old"
            else:
                draft_type = "WWII-Primary"

            # Status indicators
            img_status = "✓" if img_count > 0 else "✗"
            note_status = "✓" if has_note else "✗"
            cit_status = "✓" if cit_count > 0 else "✗"

            detail_table.add_row(
                str(rin),
                f"{given} {surname}",
                birth_year,
                draft_type,
                img_status,
                note_status,
                cit_status
            )

        console.print(detail_table)
        console.print()


def generate_html_output(conn, output_file: str, detailed: bool = False):
    """Generate HTML output with DataTables."""

    cursor = conn.cursor()

    # Gather all data
    event_stats = {et: get_event_analysis(cursor, et) for et in EVENT_TYPES.keys()}
    completeness = get_completeness_stats(cursor)

    cursor.execute("""
        SELECT COUNT(DISTINCT e.OwnerID)
        FROM EventTable e
        WHERE e.EventType IN (1021, 1024, 1025) AND e.OwnerType = 0
    """)
    total_unique_people = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM (
            SELECT e.OwnerID
            FROM EventTable e
            WHERE e.EventType IN (1021, 1024, 1025) AND e.OwnerType = 0
            GROUP BY e.OwnerID
            HAVING COUNT(DISTINCT e.EventType) > 1
        )
    """)
    people_with_multiple = cursor.fetchone()[0]

    # Build HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Draft Registration Analysis - {datetime.now().strftime('%Y-%m-%d')}</title>
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.7/css/jquery.dataTables.min.css">
    <script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
    <script src="https://cdn.datatables.net/1.13.7/js/jquery.dataTables.min.js"></script>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
        .preamble {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat-card h3 {{
            margin-top: 0;
            color: #2980b9;
            font-size: 1em;
        }}
        .stat-table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .stat-table td {{
            padding: 8px 0;
            border-bottom: 1px solid #ecf0f1;
        }}
        .stat-table td:first-child {{
            color: #7f8c8d;
        }}
        .stat-table td:last-child {{
            text-align: right;
            font-weight: bold;
            color: #27ae60;
        }}
        .summary-box {{
            background: #e8f4f8;
            border-left: 4px solid #3498db;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }}
        .completeness-table {{
            width: 100%;
            background: white;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .completeness-table th {{
            background: #34495e;
            color: white;
            padding: 12px;
            text-align: left;
        }}
        .completeness-table td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ecf0f1;
        }}
        .completeness-table tr:hover {{
            background: #f8f9fa;
        }}
        .pct {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .reference-table {{
            background: white;
            margin: 20px 0;
        }}
        .reference-table table {{
            width: 100%;
            border-collapse: collapse;
        }}
        .reference-table th {{
            background: #34495e;
            color: white;
            padding: 10px;
            text-align: left;
        }}
        .reference-table td {{
            padding: 8px 10px;
            border-bottom: 1px solid #ecf0f1;
        }}
        .notes {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        .notes ul {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .checkmark {{
            color: #27ae60;
        }}
        .cross {{
            color: #e74c3c;
        }}
    </style>
</head>
<body>
    <h1>Draft Registration Records Analysis</h1>
    <p style="color: #7f8c8d;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <div class="preamble">
        <h2>World War I Draft Registrations</h2>
        <div class="reference-table">
            <table>
                <thead>
                    <tr>
                        <th>Registration</th>
                        <th>Date</th>
                        <th>Ages</th>
                        <th>Birth Year Range</th>
                        <th>Men Registered</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>First</strong></td>
                        <td>June 5, 1917</td>
                        <td>21–31</td>
                        <td>June 1886 – June 1896</td>
                        <td>10.3M</td>
                    </tr>
                    <tr>
                        <td><strong>Second</strong></td>
                        <td>June 5, 1918</td>
                        <td>21 (new since 1st)</td>
                        <td>June 1896 – June 1897</td>
                        <td>1.00M</td>
                    </tr>
                    <tr>
                        <td><strong>Supplemental</strong></td>
                        <td>August 24, 1918</td>
                        <td>21 (new since 2nd)</td>
                        <td>June 1897 – Aug 1897</td>
                        <td>(incl. in 2nd)</td>
                    </tr>
                    <tr>
                        <td><strong>Third</strong></td>
                        <td>September 12, 1918</td>
                        <td>18–45 (not previously registered)</td>
                        <td>Sept 1872 – Sept 1900</td>
                        <td>13.0M</td>
                    </tr>
                    <tr style="background: #f0f8ff; font-weight: bold;">
                        <td colspan="4" style="text-align: right;">TOTAL</td>
                        <td>24.0M</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <h2>World War II Draft Registrations</h2>
        <div class="reference-table">
            <table>
                <thead>
                    <tr>
                        <th>Registration</th>
                        <th>Date</th>
                        <th>Ages</th>
                        <th>Birth Year Range</th>
                        <th>Men Registered</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td><strong>First</strong></td>
                        <td>October 16, 1940</td>
                        <td>21–35</td>
                        <td>Oct 1904 – Oct 1919</td>
                        <td>16.4M</td>
                    </tr>
                    <tr>
                        <td><strong>Second</strong></td>
                        <td>July 1, 1941</td>
                        <td>21 (new since 1st)</td>
                        <td>Oct 1919 – July 1920</td>
                        <td>1.00M</td>
                    </tr>
                    <tr>
                        <td><strong>Third</strong></td>
                        <td>February 16, 1942</td>
                        <td>20–44 (not previously registered)</td>
                        <td>Feb 1897 – Feb 1922</td>
                        <td>9.00M</td>
                    </tr>
                    <tr>
                        <td><strong>Fourth ("Old Man's Draft")</strong></td>
                        <td>April 27, 1942</td>
                        <td>45–64</td>
                        <td>Apr 1877 – Feb 1897</td>
                        <td>13.0M</td>
                    </tr>
                    <tr>
                        <td><strong>Fifth</strong></td>
                        <td>June 30, 1942</td>
                        <td>18–20</td>
                        <td>July 1921 – June 1924</td>
                        <td>5.00M</td>
                    </tr>
                    <tr>
                        <td><strong>Sixth</strong></td>
                        <td>December 10–31, 1942</td>
                        <td>18 (new since 5th)</td>
                        <td>July 1924 – Dec 1924</td>
                        <td>1.00M</td>
                    </tr>
                    <tr>
                        <td><strong>Extra</strong></td>
                        <td>November 16 – December 31, 1943</td>
                        <td>18–44 (Americans abroad)</td>
                        <td>Dec 1899 – Dec 1925</td>
                        <td>Unknown</td>
                    </tr>
                    <tr style="background: #f0f8ff; font-weight: bold;">
                        <td colspan="4" style="text-align: right;">TOTAL</td>
                        <td>~49.0M</td>
                    </tr>
                </tbody>
            </table>
        </div>

        <div class="notes">
            <h3>Important Notes</h3>
            <ul>
                <li>During World War I there were three registrations. The first, on June 5, 1917, was for all men between
                    the ages of 21 and 31. The second, on June 5, 1918, registered those who attained age 21 after June 5, 1917.
                    A supplemental registration was held on August 24, 1918, for those becoming 21 years old after June 5, 1918.
                    The third registration was held on September 12, 1918, for men age 18 through 45.</li>
                <li><strong>As there is overlap in the WWI and WWII Selective Service registration birth years (1877 to 1900),
                    some men may have registered twice and have both WWI and WWII draft records.</strong></li>
                <li>The Extra Registration was for American men ages 18–44 who were living abroad.</li>
                <li>The Fourth WWII Registration ("Old Man's Draft") was not for military service but to inventory
                    manpower and skills for the war effort.</li>
            </ul>
        </div>
    </div>

    <h2>Analysis by Event Type</h2>
    <div class="stats-grid">
"""

    # Add event type cards
    for event_type, event_name in EVENT_TYPES.items():
        stats = event_stats[event_type]
        total = stats['total_events']

        html += f"""
        <div class="stat-card">
            <h3>{event_name}</h3>
            <table class="stat-table">
                <tr>
                    <td>Event Type</td>
                    <td>{event_type}</td>
                </tr>
                <tr>
                    <td>Total Events</td>
                    <td>{total}</td>
                </tr>
                <tr>
                    <td>Total People</td>
                    <td>{stats['total_people']}</td>
                </tr>
                <tr>
                    <td>With Images</td>
                    <td>{stats['with_images']} <span class="pct">({stats['with_images']/total*100:.1f}%)</span></td>
                </tr>
                <tr>
                    <td>With Notes</td>
                    <td>{stats['with_notes']} <span class="pct">({stats['with_notes']/total*100:.1f}%)</span></td>
                </tr>
                <tr>
                    <td>With Citations</td>
                    <td>{stats['with_citations']} <span class="pct">({stats['with_citations']/total*100:.1f}%)</span></td>
                </tr>
            </table>
        </div>
"""

    html += """
    </div>

    <div class="summary-box">
        <h2 style="margin-top: 0;">Overall Summary</h2>
"""

    html += f"""
        <p><strong>Total unique people with any draft registration:</strong> {total_unique_people}</p>
        <p><strong>People with multiple draft registration types:</strong> {people_with_multiple}</p>
    </div>

    <h2>Completeness Analysis</h2>
    <p>Analysis of all draft types combined, showing the quality of documentation:</p>
    <table class="completeness-table">
        <thead>
            <tr>
                <th>Category</th>
                <th>Count</th>
                <th>Percentage</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Image + Citation + Note (Complete)</td>
                <td>{completeness['complete_all']}</td>
                <td>{completeness['complete_all']/completeness['total']*100:.1f}%</td>
            </tr>
            <tr>
                <td>Image + Citation</td>
                <td>{completeness['img_and_cit']}</td>
                <td>{completeness['img_and_cit']/completeness['total']*100:.1f}%</td>
            </tr>
            <tr>
                <td>Image Only</td>
                <td>{completeness['img_only']}</td>
                <td>{completeness['img_only']/completeness['total']*100:.1f}%</td>
            </tr>
            <tr>
                <td>Citation Only</td>
                <td>{completeness['cit_only']}</td>
                <td>{completeness['cit_only']/completeness['total']*100:.1f}%</td>
            </tr>
            <tr>
                <td>Note Only</td>
                <td>{completeness['note_only']}</td>
                <td>{completeness['note_only']/completeness['total']*100:.1f}%</td>
            </tr>
            <tr style="background: #fee;">
                <td>Nothing Attached</td>
                <td>{completeness['empty']}</td>
                <td>{completeness['empty']/completeness['total']*100:.1f}%</td>
            </tr>
        </tbody>
    </table>
"""

    # Add detailed records table if requested
    if detailed:
        records = get_all_records(cursor)

        html += """
    <h2>All Draft Registration Records</h2>
    <p>Interactive table of all draft registration records. Click column headers to sort, use the search box to filter.</p>
    <table id="recordsTable" class="display" style="width:100%">
        <thead>
            <tr>
                <th>RIN</th>
                <th>Given Name</th>
                <th>Surname</th>
                <th>Birth Year</th>
                <th>Draft Type</th>
                <th>Images</th>
                <th>Note</th>
                <th>Citations</th>
            </tr>
        </thead>
        <tbody>
"""

        for record in records:
            rin, given, surname, event_type, event_id, birth_date, img_count, has_note, cit_count = record

            birth_year = birth_date[3:7] if birth_date and len(birth_date) >= 7 else "?"

            if event_type == 1021:
                draft_type = "WWI"
            elif event_type == 1024:
                draft_type = "WWII-Old"
            else:
                draft_type = "WWII-Primary"

            img_status = '<span class="checkmark">✓</span>' if img_count > 0 else '<span class="cross">✗</span>'
            note_status = '<span class="checkmark">✓</span>' if has_note else '<span class="cross">✗</span>'
            cit_status = '<span class="checkmark">✓</span>' if cit_count > 0 else '<span class="cross">✗</span>'

            html += f"""
            <tr>
                <td>{rin}</td>
                <td>{given}</td>
                <td>{surname}</td>
                <td>{birth_year}</td>
                <td>{draft_type}</td>
                <td>{img_status}</td>
                <td>{note_status}</td>
                <td>{cit_status}</td>
            </tr>
"""

        html += """
        </tbody>
    </table>

    <script>
        $(document).ready(function() {
            $('#recordsTable').DataTable({
                pageLength: 50,
                order: [[1, 'asc'], [2, 'asc']],
                columnDefs: [
                    { targets: [5, 6, 7], orderable: true, searchable: false }
                ]
            });
        });
    </script>
"""

    html += """
</body>
</html>
"""

    # Write HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze World War I and II draft registration records in RootsMagic database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output Options:
  --html               Interactive HTML with sortable/searchable DataTables
  --save-terminal      Archive terminal output with all Rich formatting preserved
                       (supports .html and .svg extensions)

Examples:
  # Terminal output (live display)
  %(prog)s
  %(prog)s --detailed

  # Interactive HTML report (DataTables for sorting/filtering)
  %(prog)s --html report.html
  %(prog)s --html report.html --detailed

  # Archive terminal output (preserves colors, tables, formatting)
  %(prog)s --save-terminal terminal.html
  %(prog)s --save-terminal terminal.svg
  %(prog)s --detailed --save-terminal detailed.html

Note: --html and --save-terminal produce different output formats:
  - --html: Interactive DataTables report (good for data exploration)
  - --save-terminal: Static snapshot of terminal (good for archiving)
        """
    )

    parser.add_argument(
        '--html',
        metavar='FILE',
        help='generate interactive HTML report with sortable DataTables'
    )

    parser.add_argument(
        '--save-terminal',
        metavar='FILE',
        help='save terminal output with Rich formatting (HTML/SVG)'
    )

    parser.add_argument(
        '--detailed',
        action='store_true',
        help='Include detailed table of all records'
    )

    parser.add_argument(
        '--database',
        default='data/Iiams.rmtree',
        help='Path to RootsMagic database (default: data/Iiams.rmtree)'
    )

    args = parser.parse_args()

    # Connect to database
    try:
        conn = connect_rmtree(args.database)
    except Exception as e:
        print(f"Error connecting to database: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.html:
            # Generate HTML output with DataTables
            generate_html_output(conn, args.html, args.detailed)
            console = Console()
            console.print(f"[green]✓[/green] HTML report generated: [cyan]{args.html}[/cyan]")
        elif args.save_terminal:
            # Terminal output with recording for export
            console = Console(record=True)
            display_terminal_output(console, conn, args.detailed)

            # Export based on file extension
            output_path = args.save_terminal
            if output_path.lower().endswith('.svg'):
                console.save_svg(output_path, title="Draft Registration Analysis")
                print(f"✓ Terminal output saved as SVG: {output_path}")
            else:
                # Default to HTML
                if not output_path.lower().endswith('.html'):
                    output_path += '.html'
                console.save_html(output_path)
                print(f"✓ Terminal output saved as HTML: {output_path}")
        else:
            # Terminal output only
            console = Console()
            display_terminal_output(console, conn, args.detailed)
    finally:
        conn.close()


if __name__ == '__main__':
    main()
