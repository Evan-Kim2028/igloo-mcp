"""Factory functions for creating test reports with complex data.

Simplifies test data setup for integration tests and reduces boilerplate.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Tuple

from igloo_mcp.living_reports.models import Insight, Section
from igloo_mcp.living_reports.service import ReportService


class ReportFactory:
    """Factory for creating test reports with various configurations."""

    def __init__(self, report_service: ReportService):
        """Initialize factory with report service.

        Args:
            report_service: ReportService instance for creating reports
        """
        self.service = report_service

    def create_with_insights(
        self,
        count: int,
        *,
        title: str = "Test Report",
        skip_citations: bool = True,
        importance_range: Tuple[int, int] = (5, 9),
        template: str = "default",
    ) -> Tuple[str, List[str]]:
        """Generate report with N insights for testing.

        Args:
            count: Number of insights to create
            title: Report title
            skip_citations: If True, insights have no citations (use with skip_citation_validation)
            importance_range: (min, max) importance scores
            template: Report template to use

        Returns:
            Tuple of (report_id, list of insight_ids)

        Example:
            >>> factory = ReportFactory(report_service)
            >>> report_id, insight_ids = factory.create_with_insights(5)
        """
        report_id = self.service.create_report(title=title, template=template)
        outline = self.service.get_report_outline(report_id)

        insight_ids = []
        min_imp, max_imp = importance_range

        for i in range(count):
            importance = min_imp + (i % (max_imp - min_imp + 1))
            insight = Insight(
                insight_id=str(uuid.uuid4()),
                summary=f"Test insight {i + 1}: Finding from analysis",
                importance=importance,
                status="active",
                supporting_queries=[] if skip_citations else None,
                citations=[] if skip_citations else None,
            )
            outline.insights.append(insight)
            insight_ids.append(insight.insight_id)

        self.service.update_report_outline(report_id, outline, actor="test")
        return report_id, insight_ids

    def create_with_sections(
        self,
        count: int,
        *,
        title: str = "Test Report",
        with_content: bool = True,
        template: str = "default",
    ) -> Tuple[str, List[str]]:
        """Generate report with N sections for testing.

        Args:
            count: Number of sections to create
            title: Report title
            with_content: If True, sections have content filled
            template: Report template to use

        Returns:
            Tuple of (report_id, list of section_ids)

        Example:
            >>> report_id, section_ids = factory.create_with_sections(3)
        """
        report_id = self.service.create_report(title=title, template=template)
        outline = self.service.get_report_outline(report_id)

        section_ids = []
        for i in range(count):
            content = f"Section {i + 1} content with analysis details" * 10 if with_content else None
            section = Section(
                section_id=str(uuid.uuid4()),
                title=f"Section {i + 1}",
                order=i,
                insight_ids=[],
                content=content,
            )
            outline.sections.append(section)
            section_ids.append(section.section_id)

        self.service.update_report_outline(report_id, outline, actor="test")
        return report_id, section_ids

    def create_with_sections_and_insights(
        self,
        section_count: int,
        insights_per_section: int,
        *,
        title: str = "Complex Test Report",
        skip_citations: bool = True,
        template: str = "default",
    ) -> Tuple[str, List[str], List[str]]:
        """Generate report with sections and insights linked together.

        Args:
            section_count: Number of sections to create
            insights_per_section: Number of insights per section
            title: Report title
            skip_citations: If True, insights have no citations
            template: Report template to use

        Returns:
            Tuple of (report_id, section_ids, insight_ids)

        Example:
            >>> # Create report with 3 sections, 2 insights each
            >>> report_id, sections, insights = factory.create_with_sections_and_insights(3, 2)
        """
        report_id = self.service.create_report(title=title, template=template)
        outline = self.service.get_report_outline(report_id)

        section_ids = []
        all_insight_ids = []

        for i in range(section_count):
            section_insight_ids = []

            # Create insights for this section
            for j in range(insights_per_section):
                insight = Insight(
                    insight_id=str(uuid.uuid4()),
                    summary=f"Section {i + 1} insight {j + 1}",
                    importance=5 + (j % 6),  # 5-10 range
                    status="active",
                    supporting_queries=[] if skip_citations else None,
                    citations=[] if skip_citations else None,
                )
                outline.insights.append(insight)
                section_insight_ids.append(insight.insight_id)
                all_insight_ids.append(insight.insight_id)

            # Create section with linked insights
            section = Section(
                section_id=str(uuid.uuid4()),
                title=f"Section {i + 1}: Analysis",
                order=i,
                insight_ids=section_insight_ids,
                content=f"Section {i + 1} detailed analysis content",
            )
            outline.sections.append(section)
            section_ids.append(section.section_id)

        self.service.update_report_outline(report_id, outline, actor="test")
        return report_id, section_ids, all_insight_ids

    def create_large_report(
        self,
        *,
        section_count: int = 10,
        insight_count: int = 20,
        title: str = "Large Test Report",
        template: str = "default",
    ) -> Tuple[str, List[str], List[str]]:
        """Create a large report for performance and token efficiency testing.

        Args:
            section_count: Number of sections (default: 10)
            insight_count: Number of insights (default: 20)
            title: Report title
            template: Report template to use

        Returns:
            Tuple of (report_id, section_ids, insight_ids)

        Example:
            >>> # Create large report for testing progressive disclosure
            >>> report_id, sections, insights = factory.create_large_report()
        """
        report_id = self.service.create_report(title=title, template=template)
        outline = self.service.get_report_outline(report_id)

        # Create sections with substantial content
        section_ids = []
        for i in range(section_count):
            section = Section(
                section_id=str(uuid.uuid4()),
                title=f"Section {i + 1}: Analysis Topic",
                order=i,
                insight_ids=[],
                content=f"Detailed analysis content for section {i + 1}. " * 50,  # Large content
            )
            outline.sections.append(section)
            section_ids.append(section.section_id)

        # Create insights with detailed summaries
        insight_ids = []
        for i in range(insight_count):
            insight = Insight(
                insight_id=str(uuid.uuid4()),
                summary=f"Insight {i + 1}: Detailed finding with comprehensive information. " * 5,
                importance=(i % 10) + 1,
                status="active",
                supporting_queries=[],
                citations=[],
            )
            outline.insights.append(insight)
            insight_ids.append(insight.insight_id)

            # Link to sections (distribute insights across sections)
            section_idx = i % section_count
            outline.sections[section_idx].insight_ids.append(insight.insight_id)

        self.service.update_report_outline(report_id, outline, actor="test")
        return report_id, section_ids, insight_ids


def create_report_factory(tmp_path: Path) -> ReportFactory:
    """Helper to create a ReportFactory with temporary storage.

    Args:
        tmp_path: pytest tmp_path fixture

    Returns:
        Configured ReportFactory instance

    Example:
        >>> def test_something(tmp_path):
        ...     factory = create_report_factory(tmp_path)
        ...     report_id, insights = factory.create_with_insights(5)
    """
    reports_root = tmp_path / "reports"
    reports_root.mkdir(exist_ok=True)
    service = ReportService(reports_root=reports_root)
    return ReportFactory(service)
