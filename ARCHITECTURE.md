# Maxi AI Lab — Architecture and engineering decisions

Browser (GitHub Pages) -> FastAPI (Render) -> Gemini API

Existing research endpoint: asynchronous Gemini Interactions API, tokenized task IDs, polling.

Enterprise demo endpoint: synchronous HTTP request that orchestrates three sequential Gemini model calls:
1. Researcher: creates a draft.
2. Reviewer: critiques unsupported claims and technical gaps.
3. Coordinator: synthesizes a final answer.

The agents are role-based LLM stages, not a CrewAI framework deployment. No real web browsing is implemented in the enterprise pipeline. The reviewer is not an independent factual verifier. Do not describe it as one.

## Observability
Optional OpenTelemetry spans: HTTP request, researcher, reviewer, coordinator. Stage durations and provider-reported tokens (when available). No fabricated token counts or pricing. Configure `OTEL_EXPORTER_OTLP_ENDPOINT` to an authorized OTLP collector. Do not log prompts, secrets or responses to telemetry. Logs contain run IDs and elapsed times.

## Security and limitations
- Enterprise demo is gated by `AGENT_DEMO_TOKEN` in a request header, which MUST NOT be put in public GitHub Pages JavaScript.
- In-memory per-IP rate limiting is only a defense-in-depth demo control; it is not robust across restarts/replicas or shared IPs. Use managed auth + Redis rate limiting + provider spending limits before production.
- The existing public `/api/research` endpoint remains unprotected by this addition. Restrict it separately before wide sharing.
- All three stages consume paid/limited model requests; control quotas.
- API call timeout does not guarantee provider billing stops.
- OpenTelemetry export is optional and only enabled when configured.
- CrewAI, Amazon Bedrock, Datadog, CloudWatch, real-time websocket monitoring, and live cost calculation are NOT implemented here.

## Interview talking points
Explain asynchronous vs synchronous execution, background task polling, failure propagation, API key isolation, latency (sum of sequential calls), how parallel review would work, why traces use stage spans, and what changes are needed for a production system.
