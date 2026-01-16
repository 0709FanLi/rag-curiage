"""Dashboard cache service.

This module provides a small in-memory TTL cache for expensive dashboard
aggregations. It is designed to reduce database pressure (especially on SQLite)
and avoid intermittent slow responses caused by full table scans and lock/IO
jitter.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func

from src.models.tables import Report, Session

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CachedValue:
    """A cached value with monotonic timestamp."""

    value: Any
    cached_at_monotonic: float


class DashboardCacheService:
    """In-memory TTL cache for dashboard endpoints.

    Notes:
        - This cache is process-local. If you run multiple workers/replicas,
          each will maintain its own cache.
        - TTL caching is intentionally simple and dependency-free.
    """

    def __init__(self, *, ttl_seconds: float = 30.0) -> None:
        """Create a cache service.

        Args:
            ttl_seconds: Cache time-to-live in seconds.
        """
        self._ttl_seconds = float(ttl_seconds)
        # 注意：FastAPI 的同步 Depends 可能在 AnyIO worker thread 中执行（无 event loop）。
        # 因此不要在 __init__ 中创建 asyncio.Lock()，改为在首次协程调用时延迟创建。
        self._lock: Optional[asyncio.Lock] = None
        self._metrics_cache: Optional[CachedValue] = None
        self._funnel_cache: Optional[CachedValue] = None
        self._distribution_cache: Optional[CachedValue] = None

    def _ensure_lock(self) -> asyncio.Lock:
        """Lazily create an asyncio lock in a running event loop context."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _is_fresh(self, cached: CachedValue) -> bool:
        """Check whether cached value is still fresh."""
        return (time.monotonic() - cached.cached_at_monotonic) < self._ttl_seconds

    async def get_track_distribution(
        self,
        *,
        db: AsyncSession,
        normalize_track_name,
        get_track_color,
    ) -> List[Dict[str, Any]]:
        """Get track distribution with TTL caching.

        This endpoint can become expensive because it needs to read session
        meta-data and aggregate by track. On SQLite, full scans may be slow and
        may be affected by transient lock/IO jitter; caching reduces the chance
        of front-end timeouts.

        Args:
            db: Database session.
            normalize_track_name: Callable to normalize raw track names.
            get_track_color: Callable to map track to a color class.

        Returns:
            A list of distribution items: [{'name': str, 'value': int, 'color': str}, ...]
        """
        cached = self._distribution_cache
        if cached is not None and self._is_fresh(cached):
            return cached.value

        async with self._ensure_lock():
            cached = self._distribution_cache
            if cached is not None and self._is_fresh(cached):
                return cached.value

            started = time.monotonic()
            # Only fetch rows that have meta_data. This reduces IO a bit for
            # legacy/empty records.
            result = await db.execute(
                select(Session.meta_data).where(Session.meta_data.isnot(None))
            )
            all_meta = result.scalars().all()

            track_counts: Dict[str, int] = {}
            total_sessions = 0

            for meta in all_meta:
                if not meta or not isinstance(meta, dict):
                    continue

                raw_tracks = meta.get('track', [])
                if isinstance(raw_tracks, str):
                    raw_tracks = [raw_tracks]
                elif not isinstance(raw_tracks, list):
                    raw_tracks = ['其他']

                for raw_track in raw_tracks:
                    normalized_track = normalize_track_name(raw_track)
                    track_counts[normalized_track] = (
                        track_counts.get(normalized_track, 0) + 1
                    )

                total_sessions += 1

            distribution: List[Dict[str, Any]] = []
            if total_sessions > 0:
                sorted_tracks = sorted(
                    track_counts.items(), key=lambda x: x[1], reverse=True
                )
                for name, count in sorted_tracks:
                    distribution.append(
                        {
                            'name': name,
                            'value': int(count / total_sessions * 100),
                            'color': get_track_color(name),
                        }
                    )

            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                'dashboard_distribution computed sessions=%s tracks=%s elapsed_ms=%s ttl_seconds=%s',
                total_sessions,
                len(track_counts),
                elapsed_ms,
                self._ttl_seconds,
            )

            self._distribution_cache = CachedValue(
                value=distribution, cached_at_monotonic=time.monotonic()
            )
            return distribution

    async def get_metrics(self, *, db: AsyncSession) -> Dict[str, Any]:
        """Get dashboard metrics with TTL caching.

        Args:
            db: Database session.

        Returns:
            Dict compatible with DashboardMetricsResponse.
        """
        cached = self._metrics_cache
        if cached is not None and self._is_fresh(cached):
            return cached.value

        async with self._ensure_lock():
            cached = self._metrics_cache
            if cached is not None and self._is_fresh(cached):
                return cached.value

            started = time.monotonic()

            session_count = await db.scalar(select(func.count(Session.id))) or 0
            report_count = await db.scalar(select(func.count(Report.id))) or 0
            converting_reports = (
                await db.scalar(
                    select(func.count(Report.id)).where(
                        Report.recommended_products.isnot(None)
                    )
                )
                or 0
            )
            total_clicks = converting_reports

            consults = int(session_count)
            conversion_rate = 0.0
            if consults > 0:
                conversion_rate = float(total_clicks) / float(consults)

            payload: Dict[str, Any] = {
                'consults': consults,
                'reports': int(report_count),
                'converting_reports': int(converting_reports),
                'total_clicks': int(total_clicks),
                'conversion_rate': float(conversion_rate),
            }

            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                'dashboard_metrics computed elapsed_ms=%s ttl_seconds=%s',
                elapsed_ms,
                self._ttl_seconds,
            )

            self._metrics_cache = CachedValue(
                value=payload, cached_at_monotonic=time.monotonic()
            )
            return payload

    async def get_funnel(self, *, db: AsyncSession) -> Dict[str, Any]:
        """Get dashboard funnel data with TTL caching.

        Args:
            db: Database session.

        Returns:
            Dict compatible with DashboardFunnelResponse.
        """
        cached = self._funnel_cache
        if cached is not None and self._is_fresh(cached):
            return cached.value

        async with self._ensure_lock():
            cached = self._funnel_cache
            if cached is not None and self._is_fresh(cached):
                return cached.value

            started = time.monotonic()

            session_count = await db.scalar(select(func.count(Session.id))) or 0
            report_count = await db.scalar(select(func.count(Report.id))) or 0
            click_count = (
                await db.scalar(
                    select(func.count(Report.id)).where(
                        Report.recommended_products.isnot(None)
                    )
                )
                or 0
            )

            consults = int(session_count)

            def _pct(val: int, total: int) -> int:
                if total <= 0:
                    return 0
                return int(val / total * 100)

            payload: Dict[str, Any] = {
                'steps': [
                    {'label': '1. 会话接入', 'value': consults, 'percentage': 100},
                    {
                        'label': '2. 报告生成',
                        'value': int(report_count),
                        'percentage': _pct(int(report_count), consults),
                    },
                    {
                        'label': '3. 转化点击',
                        'value': int(click_count),
                        'percentage': _pct(int(click_count), consults),
                    },
                ]
            }

            elapsed_ms = int((time.monotonic() - started) * 1000)
            logger.info(
                'dashboard_funnel computed elapsed_ms=%s ttl_seconds=%s',
                elapsed_ms,
                self._ttl_seconds,
            )

            self._funnel_cache = CachedValue(
                value=payload, cached_at_monotonic=time.monotonic()
            )
            return payload

