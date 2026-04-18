"""Crawler Service - fetches content from regulatory sources."""
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.regulatory.source import Source, SourceVersion, SourceStatus

logger = logging.getLogger(__name__)


class CrawlerResult:
    """Result of a crawl operation."""
    def __init__(self, content: str, content_hash: str, status: str = "success", error: str = None):
        self.content = content
        self.content_hash = content_hash
        self.status = status
        self.error = error
        self.fetched_at = datetime.now(timezone.utc)


class BaseCrawlerAdapter:
    """Base class for crawler adapters."""

    async def fetch(self, url: str, config: dict = None) -> CrawlerResult:
        raise NotImplementedError


class HTTPCrawlerAdapter(BaseCrawlerAdapter):
    """Crawls HTTP/HTTPS sources."""

    async def fetch(self, url: str, config: dict = None) -> CrawlerResult:
        import aiohttp
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {"User-Agent": "AML-ComplianceOS/1.0 RegulatoryIntelligence"}
                if config and config.get("headers"):
                    headers.update(config["headers"])

                async with session.get(url, headers=headers, ssl=False) as response:
                    if response.status == 200:
                        content = await response.text()
                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                        return CrawlerResult(content=content, content_hash=content_hash)
                    else:
                        return CrawlerResult(
                            content="",
                            content_hash="",
                            status="error",
                            error=f"HTTP {response.status}"
                        )
        except Exception as e:
            logger.error(f"Crawl error for {url}: {e}")
            return CrawlerResult(content="", content_hash="", status="error", error=str(e))


class XMLCrawlerAdapter(BaseCrawlerAdapter):
    """Crawls XML sources (e.g., UN Sanctions)."""

    async def fetch(self, url: str, config: dict = None) -> CrawlerResult:
        import aiohttp
        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, ssl=False) as response:
                    if response.status == 200:
                        content = await response.text()
                        content_hash = hashlib.sha256(content.encode()).hexdigest()
                        return CrawlerResult(content=content, content_hash=content_hash)
                    else:
                        return CrawlerResult(
                            content="", content_hash="",
                            status="error", error=f"HTTP {response.status}"
                        )
        except Exception as e:
            logger.error(f"XML crawl error for {url}: {e}")
            return CrawlerResult(content="", content_hash="", status="error", error=str(e))


class CrawlerService:
    """Manages crawling of regulatory sources."""

    ADAPTERS = {
        "http": HTTPCrawlerAdapter(),
        "xml": XMLCrawlerAdapter(),
    }

    @staticmethod
    def get_adapter(source: Source) -> BaseCrawlerAdapter:
        """Select the appropriate crawler adapter for a source."""
        config = source.parser_config or {}
        adapter_type = config.get("crawler_type", "http")
        return CrawlerService.ADAPTERS.get(adapter_type, CrawlerService.ADAPTERS["http"])

    @staticmethod
    async def crawl_source(db: AsyncSession, source_id: str) -> Optional[CrawlerResult]:
        """Crawl a single source and return the result."""
        source = await db.get(Source, source_id)
        if not source or not source.url:
            return None

        adapter = CrawlerService.get_adapter(source)
        result = await adapter.fetch(source.url, source.parser_config)

        # Update source status
        source.last_crawled = datetime.now(timezone.utc)
        source.last_crawl_status = result.status

        if result.status == "error":
            source.status = SourceStatus.ERROR
        else:
            source.status = SourceStatus.ACTIVE

        await db.flush()
        return result

    @staticmethod
    async def crawl_and_store(db: AsyncSession, source_id: str) -> Optional[SourceVersion]:
        """Crawl a source and store the version if content changed."""
        result = await CrawlerService.crawl_source(db, source_id)
        if not result or result.status == "error":
            return None

        # Check if content changed
        existing = await db.execute(
            select(SourceVersion)
            .where(SourceVersion.source_id == source_id, SourceVersion.is_current == True)
        )
        current_version = existing.scalar_one_or_none()

        if current_version and current_version.content_hash == result.content_hash:
            # No change
            return current_version

        # Content changed - create new version
        from app.services.regulatory.source_registry_service import SourceRegistryService
        new_version = await SourceRegistryService.create_source_version(
            db, source_id, result.content
        )

        return new_version

    @staticmethod
    async def crawl_all_monitored(db: AsyncSession) -> dict:
        """Crawl all monitored sources."""
        sources_result = await db.execute(
            select(Source).where(Source.is_monitored == True, Source.status != SourceStatus.ARCHIVED)
        )
        sources = sources_result.scalars().all()

        results = {"total": len(sources), "success": 0, "errors": 0, "unchanged": 0, "changed": 0}

        for source in sources:
            try:
                result = await CrawlerService.crawl_source(db, source.id)
                if result and result.status == "success":
                    results["success"] += 1

                    # Check for changes
                    existing = await db.execute(
                        select(SourceVersion)
                        .where(SourceVersion.source_id == source.id, SourceVersion.is_current == True)
                    )
                    current = existing.scalar_one_or_none()
                    if current and current.content_hash == result.content_hash:
                        results["unchanged"] += 1
                    else:
                        results["changed"] += 1
                else:
                    results["errors"] += 1
            except Exception as e:
                logger.error(f"Error crawling source {source.id}: {e}")
                results["errors"] += 1

        return results
