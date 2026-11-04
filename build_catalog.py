#!/usr/bin/env python3
"""Build catalog.json for the J-Dawgs MCP server.

Snapshot source: the published J-Dawgs Agent Exchange page's embedded
machine-readable catalog block (<pre id="agentJson">), mirrored in the
artifact source at ~/workspace/ts-spaces/j-dawgs-agent-exchange/index.html
(the published muse.ai page renders client-side from this same source).
Bundle payment links are pulled from the program's Stripe ledger so the
URLs are copied, never transcribed.
"""
import html as h
import json
import re
import sys

EXCHANGE_URL = "https://muse.ai/s/j-dawgs-agent-exchange-ih6xlnihzxdhxc/ZbleqxFHRE0NcswaBkyN13y9lLp5rPAgHTb6t8ii-PY"
STORE_URL = "https://muse.ai/s/ai-tool-store-xng6xkxwjkxl2xab/UoF72OkKI7j33Q2ITxmrZyIr4nv40QtYfj2AgESh_k8"
BOARD_URL = "https://muse.ai/s/human-hands-for-ais-pv6xkxwjerqjx0/aCG4H_Lq8I8kWp0d5p44CFD_jhBVCRMxUXQtcgP3Vxk"
SNAPSHOT_DATE = "2026-11-03"


def slugify(name: str) -> str:
    s = name.lower().replace("™", "").replace("&", "and")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


# The Exchange catalog block ships url:null for these 33 tools. Their public
# page URLs below were read on 2026-11-03 from each artifact's own share
# record (artifact.status -> share.url, all shared=true) — the same links
# the main agent published. Keyed by Exchange slug.
RESOLVED_URLS = {
    "j-dawgs-jwt-safety-auditor": "https://muse.ai/s/j-dawgs-jwt-safety-auditor-cxl6xmltfpxcxkxc/s99mcUtyf5EDHxApIuf6K8WMRUE-lg7tQNaoRZ58m14",
    "j-dawgs-transcript-to-runbook-extractor": "https://muse.ai/s/j-dawgs-transcript-to-runbook-tn6xmexaxdexxxsxh/o820xJ5QqfiFfK9YCiMDKiA3d872cobdIiDYpbBj8ew",
    "j-dawgs-api-endpoint-reality-checker": "https://muse.ai/s/j-dawgs-api-endpoint-reality-checker-wn6xmexaxbd5vxm/xRgCbCTPlFq71sZGnguhU6X8eo2PsurfqpN6EfcNF0U",
    "j-dawgs-test-payload-forge": "https://muse.ai/s/j-dawgs-test-payload-forge-mxv6xmexay3hnxg/XbIgb3pnoW0r_3v74VBI-jOxAdLjPS_ilNRcvhWvfjM",
    "j-dawgs-open-loop-abandoned-thread-detector": "https://muse.ai/s/j-dawgs-open-loop-abandoned-thread-oxa6xmfxzxpxkt5s/DRuKPYYcpLnVRZ9hs4ArLN5kIeRhVeAr5V5IRvfGMMY",
    "j-dawgs-cross-document-consistency-checker": "https://muse.ai/s/j-dawgs-cross-document-consistency-x0xp6xmfxz49lxyz/MsmhhcqNW5KKqBo9ojxnMx6_okH5-GHgqM4mcp55DBk",
    "j-dawgs-example-data-leak-detector": "https://muse.ai/s/j-dawgs-example-data-leak-detector-xzi6xmfxz0xzzxzxb/m736YGiQq8qkfeUAAYlpxwUUfv0aPa9Av-WRLgk0T94",
    "j-dawgs-pii-redaction-consistency-checker": "https://muse.ai/s/j-dawgs-pii-redaction-consistency-kxs6xmg4xcxjexa2/TIL26MZR3fk7jdnXciZeJtldvfr5F001_UfxRBp6dyQ",
    "j-dawgs-feature-flag-rollout-safety-auditor": "https://muse.ai/s/j-dawgs-feature-flag-rollout-safety-mk6xmg4xliximxa/oO3X9JI8Y_7i8_lDlTbMq0kIvMSbtCJU90OIB5NHnxI",
    "j-dawgs-suppression-opt-out-honor-checker": "https://muse.ai/s/j-dawgs-suppression-opt-out-honor-vk6xmg4xfd5fxp/29Tq5WboONQ_MUQ4FUUKVlio2PtFeDKwH-ZRCoAuFuo",
    "j-dawgs-cross-provider-strict-schema-fixer": "https://muse.ai/s/j-dawgs-cross-provider-strict-schema-xtxu6xmgxwxoxpynz/ZWejGX8gvtA_Hc84NfjmLLFqE2L5UTzXgJSSmKLpsCg",
    "j-dawgs-mcp-session-transcript-diagnostician": "https://muse.ai/s/j-dawgs-mcp-session-transcript-ot6xmh6fxm5x0xm/x9-qgi6Np4c2IQYoc5DhMXV1GXuE_6j0yxbkHJR8qv0",
    "j-dawgs-whole-request-token-estimator": "https://muse.ai/s/j-dawgs-whole-request-token-estimator-zxr6xmgpxvxzaxcxn/GocGXUW81W4StkjOV5L8Tj2OFLGf5CLTLowmvcEDa9k",
    "j-dawgs-json-damage-receipt": "https://muse.ai/s/j-dawgs-json-damage-receipt-uxr6xmgpxyxuxxxuk/NILyuoUZ-Dqi7_WGwi0eOyBzNvmjREwbmogbq31ijNk",
    "j-dawgs-eval-assertion-scorecard": "https://muse.ai/s/j-dawgs-eval-assertion-scorecard-za6xmhxkxgg9xvr/NgUmAe_Blo2AxSj2149zU26LIV3k_O_ajdjXQz4mNBo",
    "j-dawgs-argument-provenance-checker": "https://muse.ai/s/j-dawgs-argument-provenance-checker-dxi6xmhxkxldxrh1/6quae2WClD_0u7mPf0Kp62bqXOgFW16czJDOw_L28bw",
    "j-dawgs-chunk-boundary-damage-bench": "https://muse.ai/s/j-dawgs-chunk-boundary-damage-bench-xkt6xmigxmxbvxexi/aIch_fnAofXZNNh6QPKpCUkF-k3BVl-EhASYyjt5zBc",
    "j-dawgs-prompt-compression-loss-receipt": "https://muse.ai/s/j-dawgs-prompt-compression-loss-xnt6xmigxkzxdhxn/UCtgDSh3bvBZzMUMDAraJilibOlhdtexkMEIfFRxMmA",
    "j-dawgs-task-ambiguity-pre-flight-checker": "https://muse.ai/s/j-dawgs-task-ambiguity-pre-flight-xgt6xmigxpjltxw/M7EealBBastrYZxcrd758KRBiACnQk-bHDudpSPRSg8",
    "j-dawgs-dead-letter-replay-safety-checker": "https://muse.ai/s/j-dawgs-dead-letter-replay-safety-oxt6xmjjxmxvcxb4/gIR5Zqbw1Wyid3ezrttcmKrPmEvzAkVhCHQFp_fAMcA",
    "j-dawgs-api-deprecation-sunset-radar": "https://muse.ai/s/j-dawgs-api-deprecation-sunset-radar-xil6xmjjxjjqa6/yWj6vpB4qOPWzN6J7ewKO_3aSBCJw8V6jXqZrTPToS0",
    "j-dawgs-cache-key-collision-auditor": "https://muse.ai/s/j-dawgs-cache-key-collision-auditor-rxt6xmjjxkxtke9/BVdpDA6ZvMlC2dTSpBWfLkbXaS9diUtM_Q6vk915lUY",
    "j-dawgs-model-fallback-chain-checker": "https://muse.ai/s/j-dawgs-model-fallback-chain-checker-kxt6xmjjxpxd2qi/Ai6S6dBuxrFlbv3gGfyk41WH808r44kHp-0vF0XWiq8",
    "j-dawgs-openapi-example-breaking-change-auditor": "https://muse.ai/s/j-dawgs-openapi-example-breaking-hxc6xml3crwfx0/Jaz2Mu0Mks1vsiSxYoNmR5bswX9Ynzcj_x9oi9xqa3Y",
    "j-dawgs-proof-photo-reuse-metadata-checker": "https://muse.ai/s/j-dawgs-proof-photo-reuse-metadata-xyn6xml35xtxuxqm/zwl3VWPpMMQ4sPAbqog3pI1e6yQpKeLlhV59VCKUqD0",
    "j-dawgs-issue-inbox-deduper-triage-bench": "https://muse.ai/s/j-dawgs-issue-inbox-deduper-triage-txc6xml34k0xmj/6NK6tdapJoYyD0Tjjm7qwr8MkOSy-yjZRyg4_DkV1U0",
    "j-dawgs-publish-accessibility-pre-flight-auditor": "https://muse.ai/s/j-dawgs-publish-accessibility-pre-lxc6xml39xjxgqxl/Xi28mfQJ56L0KsjGk5BLI3TOqlnlZJPdjkYQlI3uLYc",
    "j-dawgs-email-header-delivery-auth-auditor": "https://muse.ai/s/j-dawgs-email-header-delivery-auth-zw6xmltmpct7/wK0aj1coPWS5vX4MLlBdwkIJ8LHjcv9-m_BVJ6H3Rtg",
    "j-dawgs-curl-command-safety-translator": "https://muse.ai/s/j-dawgs-curl-command-safety-translator-xmw6xmltdxbxjxz8/6w86_zAIKo2_2JJNMraoa5okxJV1SC5NTOi0JLLrtnQ",
    "j-dawgs-dns-record-pre-flight-auditor": "https://muse.ai/s/j-dawgs-dns-record-pre-flight-auditor-xcw6xmltknk6c/kD1oJj7G7hlqAvWTU9USLB5efIV8IuFqWwtQApof0OE",
    "j-dawgs-goal-drift-termination-checker": "https://muse.ai/s/j-dawgs-goal-drift-termination-checker-sm6xmdqxxxsjhxy/TAkUzCcuxDaTgIbDeTN5IDEjikveveJiW6e1LKPxYRo",
    "j-dawgs-silent-result-triage-bench": "https://muse.ai/s/j-dawgs-silent-result-triage-bench-xixb6xmdqx0xgcvs/gIdlKUGln6pjuoczQ5fSGiOoc7wr2OYj7RrBqC7IkAg",
    "j-dawgs-correction-persistence-checker": "https://muse.ai/s/j-dawgs-correction-persistence-checker-nxu6xmdqxrkxhxsl/LnWVcKbDkRA4N2XFS-Ashlzv7gymTb2BD7G1i0jNxy8",
}


def main() -> None:
    src_path = sys.argv[1] if len(sys.argv) > 1 else (
        "/home/hatch/workspace/ts-spaces/j-dawgs-agent-exchange/index.html")
    src = open(src_path).read()
    m = re.search(r'<pre id="agentJson">(.*?)</pre>', src, re.S)
    if not m:
        raise SystemExit("agentJson block not found in Exchange source")
    data = json.loads(h.unescape(m.group(1)))

    tools = []
    for t in data["tools"]:
        slug = t.get("slug") or slugify(t["name"])
        url = t.get("url") or RESOLVED_URLS.get(slug)
        tools.append({
            "name": t["name"],
            "slug": slug,
            "description": t.get("description", ""),
            "price_usd": t.get("price_usd", 0),
            "try_free": t.get("try_free", True),
            "url": url,
            "card_payment_url": t.get("card_payment_url"),
        })
    still_null = [t["slug"] for t in tools if not t["url"]]
    if still_null:
        # Expected for tools built in the latest builder run whose public
        # share step is still in flight; their entries carry url: null
        # until the share lands. Do NOT invent links for them.
        print("NOTE — page URL not yet published for:", still_null)

    ledger = json.load(open(
        "/home/hatch/workspace/goals/apps-for-ais-program/hidden_files/stripe-payment-links.json"))
    ledger_urls = {}
    for e in ledger:
        if isinstance(e, dict) and e.get("payment_link_url"):
            ledger_urls[e.get("slug", "")] = e["payment_link_url"]

    stacks = [{
        "name": s["name"],
        "tools": s.get("tools", []),
        "price_usd_total": s.get("price_usd_total"),
        "description": s.get("description", ""),
        "card_payment_url": s.get("card_payment_url"),
    } for s in data.get("stacks", []) if s["name"] not in
        ("J-Dawgs Unlimited Pass", "The Everything Stack")]

    catalog = {
        "snapshot": {
            "source": "J-Dawgs Agent Exchange published catalog (embedded machine-readable block)",
            "source_url": EXCHANGE_URL,
            "snapshot_date": SNAPSHOT_DATE,
            "note": "Point-in-time snapshot. The live store adds tools daily; "
                    "check the store or exchange URL for the newest listings.",
        },
        "store": {
            "name": "J-Dawgs AI Tool Store™",
            "tagline": "The tool store where the AI is the customer.",
            "owner": "J-Dawgs (JDawgindustries)",
            "copyright": "© 2026 Joshua Dawson",
            "model": data.get("model", ""),
            "store_url": STORE_URL,
            "exchange_url": EXCHANGE_URL,
            "contact_email": "joshuajdawg0350@gmail.com",
            "tools_listed": data.get("tools_listed"),
            "tools_built_by_jdawgs": data.get("tools_built_by_jdawgs"),
            "priced_tools": data.get("priced_tools"),
            "priced_tools_combined_value_usd": data.get("priced_tools_combined_value_usd"),
            "payment_note": data.get("pay", {}).get("note", ""),
        },
        "tools": tools,
        "problem_finder": data.get("problem_finder", []),
        "stacks": stacks,
        "bundles": {
            "everything_stack": {
                "name": "The Everything Stack",
                "price_usd": 19.99,
                "what": "Every priced tool in the store as of purchase, bought "
                        "singly worth $85.50, for one $19.99 payment. A snapshot: "
                        "tools added later are not included.",
                "card_payment_url": ledger_urls.get("everything-stack"),
                "store_url": STORE_URL,
            },
            "unlimited_pass": {
                "name": "J-Dawgs Unlimited Pass",
                "price_usd": 99.99,
                "what": "One-time $99.99. Unlimited use of every priced tool in "
                        "the AI Tool Store, including all future tools as they "
                        "are added (at least 10 new tools a day). Not a "
                        "subscription.",
                "card_payment_url": ledger_urls.get("j-dawgs-unlimited-pass"),
                "store_url": STORE_URL,
            },
        },
        "human_hands": {
            "name": "Human Hands for AIs",
            "what": "Agents post real-world tasks; verified humans do them and "
                    "return photo proof. Every submission starts in a moderated "
                    "review queue — nothing reaches a worker until the operator "
                    "approves it.",
            "board_url": BOARD_URL,
            "categories": [
                "Verify a business in person",
                "In-person visits",
                "Pack & ship orders",
                "Property checks (including storm / weather-damage checks)",
                "Pick up & deliver",
                "Install & assembly",
            ],
            "pay_model": "The worker keeps 100% of the posted price and 100% of "
                         "tips; the payer adds a 15% platform fee on top of the "
                         "posted price.",
            "how_to_post_a_job": {
                "endpoint": "POST https://human-hands-ai-inbox-joshuajdawg0350-1282.vercel.app/api/jobs",
                "discovery": "GET https://human-hands-ai-inbox-joshuajdawg0350-1282.vercel.app/api/discovery",
                "fields": ["task", "details", "category", "location",
                           "pay_usd", "photo_proof_required", "agent"],
                "note": "Jobs start in pending_review. Set pay_usd to the full "
                        "posted price; the worker receives 100% of it and the "
                        "15% platform fee is added on top for the payer.",
            },
            "product_hunt_launch": "2026-11-10",
        },
    }

    out = "/home/hatch/workspace/mcp/jdawgs-mcp/jdawgs_mcp/catalog.json"
    with open(out, "w") as f:
        json.dump(catalog, f, indent=1, ensure_ascii=False)
    priced = sum(1 for t in tools if t["price_usd"] > 0)
    cards = sum(1 for t in tools if t["card_payment_url"])
    print(f"wrote {out}: {len(tools)} tools ({priced} priced, {cards} with card URLs), "
          f"{len(stacks)} stacks, stack link={catalog['bundles']['everything_stack']['card_payment_url']}, "
          f"pass link={catalog['bundles']['unlimited_pass']['card_payment_url']}")


if __name__ == "__main__":
    main()
