"""Write the demo workspace used for the README's recordings and screenshots.

    uv run python docs/demo/workspace.py <dir>

Creates <dir> with planboard.toml and a few example plans. The plans are fictional.
"""

import json
import subprocess
import sys
from pathlib import Path


def text(value: str) -> dict[str, object]:
    return {"type": "text", "text": value}


def table(columns: list[str], *rows: list[str]) -> dict[str, object]:
    return {"type": "table", "columns": columns, "rows": [list(r) for r in rows]}


def diagram(ref: str, caption: str) -> dict[str, object]:
    return {"type": "diagram", "ref": ref, "caption": caption}


def bullets(*items: str) -> dict[str, object]:
    return {"type": "list", "items": list(items)}


def callout(tone: str, title: str, body: str) -> dict[str, object]:
    return {"type": "callout", "tone": tone, "title": title, "text": body}


def code(language: str, source: str, caption: str) -> dict[str, object]:
    return {"type": "code", "language": language, "code": source, "caption": caption}


PLANS: dict[str, dict[str, object]] = {
    "api/rate-limiting": {
        "title": "Rate limiting",
        "summary": "Per-key request limits on the public API, enforced in middleware "
        "with a Redis token bucket, so one noisy client cannot slow down the rest.",
        "status": "approved",
        "branch": "feat/rate-limits",
        "tags": ["api", "redis"],
        "diagrams": {
            "request-flow": {
                "alt": "How a request passes the limiter before reaching a handler.",
                "source": "flowchart LR\n"
                "  client([Client]) --> mw[Rate limit middleware]\n"
                "  mw -->|take token| redis[(Redis)]\n"
                "  mw -->|allowed| handler[Route handler]\n"
                "  mw -->|empty bucket| reject[429 Too Many Requests]\n"
                "  handler --> db[(Postgres)]",
            },
            "bucket-refill": {
                "alt": "The sequence of a token take and refill in Redis.",
                "source": "sequenceDiagram\n"
                "  participant M as Middleware\n"
                "  participant R as Redis\n"
                "  M->>R: EVALSHA take(key, rate, burst)\n"
                "  R-->>M: tokens left, retry after\n"
                "  alt tokens left >= 0\n"
                "    M->>M: set RateLimit-* headers\n"
                "  else bucket empty\n"
                "    M-->>M: 429 with Retry-After\n"
                "  end",
            },
        },
        "sections": {
            "context": (
                "Context",
                [
                    text(
                        "The public API has no limits today. Last month a single "
                        "integration retried in a tight loop and pushed p99 latency "
                        "past **2 s** for every tenant."
                    ),
                    text(
                        "This plan adds a limit per API key, applied before any route "
                        "handler runs. It builds on [API keys](auth/api-keys)."
                    ),
                ],
            ),
            "decisions": (
                "Decisions",
                [
                    table(
                        ["Topic", "Decision"],
                        [
                            "Algorithm",
                            "Token bucket: allows short bursts, smooth over time.",
                        ],
                        ["Store", "Redis, one hash per key, updated by a Lua script."],
                        [
                            "Scope",
                            "Per API key; anonymous requests share a per-IP bucket.",
                        ],
                        ["Headers", "IETF `RateLimit-*` draft plus `Retry-After`."],
                    ),
                ],
            ),
            "design": (
                "Design",
                [
                    text(
                        "Every request takes one token. The middleware sits in front "
                        "of the router, so handlers never see a limited request. See "
                        "[the refill sequence](#bucket-refill) for the Redis side."
                    ),
                    diagram("#request-flow", "Where the limiter sits."),
                    diagram("#bucket-refill", "One atomic round trip per request."),
                    code(
                        "python",
                        "@app.middleware('http')\n"
                        "async def limit(request, call_next):\n"
                        "    result = await bucket.take(request.state.key)\n"
                        "    if result.empty:\n"
                        "        return too_many(result.retry_after)\n"
                        "    return with_headers(await call_next(request), result)",
                        "The middleware, in outline.",
                    ),
                ],
            ),
            "risks": (
                "Risks and mitigations",
                [
                    table(
                        ["Risk", "Mitigation"],
                        [
                            "Redis is down",
                            "Fail open and log; limits are a guard, not a gate.",
                        ],
                        [
                            "Clock skew between nodes",
                            "Refill uses Redis `TIME`, never the app clock.",
                        ],
                    ),
                    callout(
                        "warning",
                        "Shared egress IPs",
                        "Anonymous clients behind one NAT share a bucket. Keep the "
                        "anonymous limit generous until keys are required.",
                    ),
                ],
            ),
            "tests": (
                "Tests",
                [
                    bullets(
                        "Unit: refill maths at the boundaries of rate and burst.",
                        "Integration: 429 and headers against a real Redis.",
                        "Load: 5k req/s from 50 keys keeps p99 under 150 ms.",
                    )
                ],
            ),
        },
        "tasks": [
            {
                "id": "token-bucket",
                "title": "Token bucket script",
                "status": "done",
                "summary": "Lua script: take a token, refill by elapsed time.",
                "sections": ["design"],
                "diagrams": ["bucket-refill"],
            },
            {
                "id": "redis-store",
                "title": "Redis bucket store",
                "status": "done",
                "dependsOn": ["#token-bucket"],
            },
            {
                "id": "middleware",
                "title": "Limit middleware",
                "status": "doing",
                "summary": "Reject with 429 before routing.",
                "dependsOn": ["#redis-store", "auth/api-keys#key-lookup"],
                "sections": ["design"],
                "diagrams": ["request-flow"],
            },
            {
                "id": "response-headers",
                "title": "RateLimit headers",
                "dependsOn": ["#middleware"],
                "sections": ["decisions"],
            },
            {
                "id": "plan-quotas",
                "title": "Limits per billing plan",
                "status": "blocked",
                "note": "The free tier's limit is not decided yet.",
                "dependsOn": ["#middleware", "billing/plans#plan-catalog"],
            },
            {
                "id": "limits-docs",
                "title": "Document the limits",
                "dependsOn": ["#redis-store"],
            },
            {
                "id": "load-test",
                "title": "Load test",
                "dependsOn": ["#response-headers"],
                "sections": ["tests"],
            },
        ],
    },
    "auth/api-keys": {
        "title": "API keys",
        "summary": "Hashed, scoped API keys that tenants create and revoke from the "
        "dashboard, replacing the shared secret per tenant.",
        "status": "approved",
        "branch": "feat/api-keys",
        "tags": ["auth", "security"],
        "diagrams": {
            "data-model": {
                "alt": "How API keys relate to tenants and scopes.",
                "source": "erDiagram\n"
                "  tenants ||--o{ api_keys : owns\n"
                "  api_keys ||--o{ key_scopes : grants\n"
                "  api_keys {\n"
                "    uuid id PK\n"
                "    uuid tenant_id FK\n"
                "    text prefix\n"
                "    text hash\n"
                "    timestamp revoked_at\n"
                "  }",
            },
        },
        "sections": {
            "context": (
                "Context",
                [
                    text(
                        "Each tenant has one shared secret. Rotating it breaks every "
                        "integration at once, and a leak cannot be traced to a client."
                    )
                ],
            ),
            "model": (
                "Data model",
                [
                    text(
                        "Keys are stored as an Argon2 hash and a short public prefix "
                        "for lookup. The raw key is shown once, at creation."
                    ),
                    diagram("#data-model", "Keys belong to a tenant and carry scopes."),
                ],
            ),
        },
        "tasks": [
            {"id": "key-table", "title": "Keys table", "status": "done"},
            {
                "id": "key-lookup",
                "title": "Key lookup by prefix",
                "status": "done",
                "dependsOn": ["#key-table"],
                "sections": ["model"],
                "diagrams": ["data-model"],
            },
            {
                "id": "dashboard",
                "title": "Create and revoke in the dashboard",
                "status": "doing",
                "dependsOn": ["#key-lookup"],
            },
            {
                "id": "retire-secret",
                "title": "Retire the shared secret",
                "status": "blocked",
                "note": "Waiting for the two largest tenants to move to keys.",
                "dependsOn": ["#dashboard"],
            },
        ],
    },
    "billing/plans": {
        "title": "Billing plans",
        "summary": "A plan catalog synced with Stripe, so limits and features follow "
        "what each tenant pays for.",
        "status": "draft",
        "tags": ["billing"],
        "diagrams": {
            "sync": {
                "alt": "How plan changes flow from Stripe to the catalog.",
                "source": "flowchart LR\n"
                "  stripe[Stripe] -->|webhook| sync[Sync worker]\n"
                "  sync --> catalog[(plans)]\n"
                "  catalog --> limits[Rate limits]\n"
                "  catalog --> flags[Feature flags]",
            },
        },
        "sections": {
            "context": (
                "Context",
                [
                    text(
                        "Plans are hard-coded in three services today. This plan "
                        "makes one catalog the source of truth."
                    ),
                    diagram("#sync", "Stripe stays the source for prices."),
                ],
            ),
        },
        "tasks": [
            {"id": "plan-catalog", "title": "Plan catalog table"},
            {
                "id": "stripe-sync",
                "title": "Stripe webhook sync",
                "dependsOn": ["#plan-catalog"],
                "diagrams": ["sync"],
            },
            {
                "id": "upgrade-flow",
                "title": "Upgrade flow in the dashboard",
                "dependsOn": ["#stripe-sync"],
            },
        ],
    },
}


def write(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def main(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["planboard", "-q", "init"], cwd=root, check=True)
    for plan_id, spec in PLANS.items():
        folder = root / "plans" / plan_id
        depth = "../" * (plan_id.count("/") + 1)
        sections = spec.pop("sections")
        assert isinstance(sections, dict)
        for section_id, (title, blocks) in sections.items():
            write(
                folder / "sections" / f"{section_id}.json",
                {
                    "$schema": f"{depth}../.schema/section.schema.json",
                    "title": title,
                    "blocks": blocks,
                },
            )
        write(
            folder / "plan.json",
            {
                "$schema": f"{depth}.schema/plan.schema.json",
                **spec,
                "sections": list(sections),
                "updated": "2026-10-24",
            },
        )
    subprocess.run(["planboard", "validate"], cwd=root, check=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
