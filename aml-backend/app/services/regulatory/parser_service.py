"""Parser Service - extracts structured content from raw regulatory documents."""
import re
import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.source import (
    Document, Provision, ProvisionType, DocumentStatus, Source, SourceVersion,
)
from app.models.base import generate_uuid

logger = logging.getLogger(__name__)


class ParsedSection:
    """A parsed section from a regulatory document."""
    def __init__(self, section_number: str, title: str, text: str,
                 provision_type: str = "article", children: list = None):
        self.section_number = section_number
        self.title = title
        self.text = text
        self.provision_type = provision_type
        self.children = children or []


class ParsedDocument:
    """A fully parsed regulatory document."""
    def __init__(self, title: str, document_type: str, sections: list[ParsedSection],
                 effective_date: datetime = None, summary: str = None,
                 language: str = "en", confidence: float = 0.8):
        self.title = title
        self.document_type = document_type
        self.sections = sections
        self.effective_date = effective_date
        self.summary = summary
        self.language = language
        self.confidence = confidence


class BaseParserAdapter:
    """Base class for parser adapters."""

    def parse(self, raw_content: str, config: dict = None) -> Optional[ParsedDocument]:
        raise NotImplementedError


class HTMLParserAdapter(BaseParserAdapter):
    """Parses HTML regulatory content."""

    def parse(self, raw_content: str, config: dict = None) -> Optional[ParsedDocument]:
        try:
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self.current_tag = None
                    self.headers = []
                    self.sections = []
                    self.current_section_text = []
                    self.current_section_title = ""
                    self.section_count = 0
                    self.in_body = False
                    self.skip_tags = {'script', 'style', 'nav', 'footer', 'header'}
                    self.skip_depth = 0

                def handle_starttag(self, tag, attrs):
                    self.current_tag = tag
                    if tag in self.skip_tags:
                        self.skip_depth += 1
                    if tag == 'body':
                        self.in_body = True
                    if tag in ('h1', 'h2', 'h3', 'h4', 'article', 'section'):
                        if self.current_section_text:
                            self._save_section()

                def handle_endtag(self, tag):
                    if tag in self.skip_tags and self.skip_depth > 0:
                        self.skip_depth -= 1
                    if tag == self.current_tag:
                        self.current_tag = None

                def handle_data(self, data):
                    if self.skip_depth > 0:
                        return
                    text = data.strip()
                    if not text:
                        return
                    if self.current_tag in ('h1', 'h2', 'h3', 'h4'):
                        self.headers.append(text)
                        if self.current_section_text:
                            self._save_section()
                        self.current_section_title = text
                    else:
                        self.current_section_text.append(text)

                def _save_section(self):
                    self.section_count += 1
                    full_text = " ".join(self.current_section_text)
                    if len(full_text.strip()) > 10:
                        self.sections.append(ParsedSection(
                            section_number=str(self.section_count),
                            title=self.current_section_title or f"Section {self.section_count}",
                            text=full_text.strip(),
                            provision_type="section",
                        ))
                    self.current_section_text = []
                    self.current_section_title = ""

            extractor = TextExtractor()
            extractor.feed(raw_content)
            if extractor.current_section_text:
                extractor._save_section()

            title = extractor.headers[0] if extractor.headers else "Untitled Document"

            # If no sections found, create one from all text
            if not extractor.sections:
                all_text = " ".join(extractor.text_parts)
                if all_text.strip():
                    extractor.sections.append(ParsedSection(
                        section_number="1",
                        title=title,
                        text=all_text.strip(),
                        provision_type="section",
                    ))

            return ParsedDocument(
                title=title,
                document_type="regulation",
                sections=extractor.sections,
                confidence=0.7,
                language=config.get("language", "en") if config else "en",
            )
        except Exception as e:
            logger.error(f"HTML parsing error: {e}")
            return None


class PlainTextParserAdapter(BaseParserAdapter):
    """Parses plain text regulatory content (articles, clauses)."""

    ARTICLE_PATTERNS = [
        r'(?:Article|المادة)\s+(\d+[\.\d]*)\s*[:\.\-–]\s*(.*?)(?=(?:Article|المادة)\s+\d|$)',
        r'(?:Section|القسم)\s+(\d+[\.\d]*)\s*[:\.\-–]\s*(.*?)(?=(?:Section|القسم)\s+\d|$)',
        r'(?:Rule|القاعدة)\s+(\d+[\.\d]*)\s*[:\.\-–]\s*(.*?)(?=(?:Rule|القاعدة)\s+\d|$)',
    ]

    def parse(self, raw_content: str, config: dict = None) -> Optional[ParsedDocument]:
        try:
            sections = []
            lang = config.get("language", "en") if config else "en"

            for pattern in self.ARTICLE_PATTERNS:
                matches = re.finditer(pattern, raw_content, re.DOTALL | re.MULTILINE)
                for match in matches:
                    num = match.group(1)
                    text = match.group(2).strip()
                    if text:
                        # Extract title from first line
                        lines = text.split('\n', 1)
                        title = lines[0].strip()[:200]
                        sections.append(ParsedSection(
                            section_number=num,
                            title=title,
                            text=text,
                            provision_type="article",
                        ))

            if not sections:
                # Split by paragraphs
                paragraphs = [p.strip() for p in raw_content.split('\n\n') if p.strip()]
                for i, para in enumerate(paragraphs, 1):
                    if len(para) > 20:
                        sections.append(ParsedSection(
                            section_number=str(i),
                            title=para[:100],
                            text=para,
                            provision_type="section",
                        ))

            return ParsedDocument(
                title=sections[0].title if sections else "Untitled",
                document_type="regulation",
                sections=sections,
                confidence=0.6,
                language=lang,
            )
        except Exception as e:
            logger.error(f"Text parsing error: {e}")
            return None


class XMLParserAdapter(BaseParserAdapter):
    """Parses XML regulatory content."""

    def parse(self, raw_content: str, config: dict = None) -> Optional[ParsedDocument]:
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(raw_content)
            sections = []
            count = 0

            def extract_text(element):
                texts = []
                if element.text:
                    texts.append(element.text.strip())
                for child in element:
                    texts.extend(extract_text(child))
                    if child.tail:
                        texts.append(child.tail.strip())
                return texts

            for elem in root.iter():
                tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
                if tag.lower() in ('article', 'section', 'provision', 'rule', 'item', 'entry'):
                    count += 1
                    text = " ".join(extract_text(elem))
                    if text.strip():
                        sections.append(ParsedSection(
                            section_number=elem.get('number', str(count)),
                            title=elem.get('title', f"Entry {count}"),
                            text=text.strip(),
                            provision_type="article",
                        ))

            return ParsedDocument(
                title=root.get('title', root.tag),
                document_type="regulation",
                sections=sections,
                confidence=0.75,
            )
        except Exception as e:
            logger.error(f"XML parsing error: {e}")
            return None


class ParserService:
    """Manages parsing of regulatory content."""

    ADAPTERS = {
        "html": HTMLParserAdapter(),
        "text": PlainTextParserAdapter(),
        "xml": XMLParserAdapter(),
    }

    @staticmethod
    def detect_format(content: str) -> str:
        """Auto-detect content format."""
        content_lower = content.strip()[:500].lower()
        if content_lower.startswith('<?xml') or content_lower.startswith('<xml'):
            return "xml"
        if '<html' in content_lower or '<body' in content_lower or '<div' in content_lower:
            return "html"
        return "text"

    @staticmethod
    def parse_content(raw_content: str, config: dict = None) -> Optional[ParsedDocument]:
        """Parse raw content using the appropriate adapter."""
        fmt = ParserService.detect_format(raw_content)
        if config and config.get("parser_type"):
            fmt = config["parser_type"]

        adapter = ParserService.ADAPTERS.get(fmt, ParserService.ADAPTERS["text"])
        return adapter.parse(raw_content, config)

    @staticmethod
    async def parse_and_store(
        db: AsyncSession,
        source_version_id: str,
        regulator_id: str,
        jurisdiction_id: str,
        config: dict = None,
    ) -> Optional[Document]:
        """Parse a source version and store as structured document with provisions."""
        version = await db.get(SourceVersion, source_version_id)
        if not version or not version.raw_content:
            return None

        parsed = ParserService.parse_content(version.raw_content, config)
        if not parsed:
            return None

        # Create document
        doc = Document(
            source_version_id=source_version_id,
            title=parsed.title,
            document_type=parsed.document_type,
            effective_date=parsed.effective_date,
            regulator_id=regulator_id,
            jurisdiction_id=jurisdiction_id,
            language=parsed.language,
            status=DocumentStatus.ACTIVE,
            summary=parsed.summary,
        )
        db.add(doc)
        await db.flush()

        # Create provisions
        for i, section in enumerate(parsed.sections):
            prov_type = ProvisionType.ARTICLE
            try:
                prov_type = ProvisionType(section.provision_type)
            except (ValueError, KeyError):
                pass

            prov = Provision(
                document_id=doc.id,
                section_number=section.section_number,
                title=section.title,
                text=section.text,
                provision_type=prov_type,
                order_index=i,
            )
            db.add(prov)

        # Update version with parsed content
        version.parsed_content = str({"title": parsed.title, "sections": len(parsed.sections)})
        version.parser_confidence = parsed.confidence

        await db.flush()
        return doc
