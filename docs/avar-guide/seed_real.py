#!/usr/bin/env python3
"""
seed_real.py — טוען את שלושת הדוחות האמיתיים לתוך reports/sessions.json
Seeds the three parsed real reports into the local AVAR store, and rebuilds a
live "in-flight" session by replaying one real run's own search audit, so the
processing screen can be captured from genuine event data.
"""
import json, os, sys, datetime

ROOT = '/home/user/bencogpt/agentic_intel'
OUT = os.path.join(ROOT, 'reports', 'sessions.json')

sessions = json.load(open(sys.argv[1], encoding='utf-8'))

def by_title(fragment):
    return next(s for s in sessions.values() if fragment in s['title'])

# ── in-flight replay ─────────────────────────────────────────────────────────
# Built from the Qatar run's own audit trail: same agents, same queries, same
# order — stopped partway so the live processing view can be captured.
src = by_title('קטר')
agents = [a['agentName'] for a in src['agentOutputs'].values()]
audit = src['searchAudit']
t0 = audit[0]['ts'] - 90_000

events = [
    {'type': 'step', 'step': 'ANALYZE', 'message': 'מתחיל ניתוח מסמך...', 'ts': t0},
    {'type': 'analysis_done', 'claimsFound': 4, 'message': 'זוהו 4 טענות מרכזיות', 'ts': t0 + 42_000},
    {'type': 'step', 'step': 'DISPATCH',
     'message': f'נבחרו {len(agents)} סוכנים: {", ".join(agents)}', 'ts': t0 + 44_000},
    {'type': 'step', 'step': 'RESEARCH', 'message': 'סוכנים מתחילים מחקר...', 'ts': t0 + 45_000},
    {'type': 'dispatch', 'message': f'מפעיל {", ".join(agents)}', 'ts': t0 + 46_000},
]
for i, name in enumerate(agents):
    events.append({'type': 'agent_start', 'agentId': f'agent-{i+1}', 'agentName': name, 'ts': t0 + 47_000 + i * 900})

# replay the first real searches, interleaved as they actually ran
for entry in audit[:14]:
    events.append({'type': 'search', 'query': entry['query'], 'lang': entry['lang'],
                   'agent': entry['agent'], 'ts': entry['ts']})
    if entry['count']:
        events.append({'type': 'search_results', 'query': entry['query'], 'count': entry['count'],
                       'agent': entry['agent'], 'ts': entry['ts'] + 7_000})
# one agent has already finished by the captured moment
events.append({'type': 'agent_complete', 'agentId': 'agent-2', 'agentName': agents[1] if len(agents) > 1 else agents[0],
               'ts': audit[13]['ts'] + 20_000})
events.sort(key=lambda e: e['ts'])

inflight = {
    'id': 'live-' + src['id'][:8],
    'title': src['title'],
    'createdAt': src['createdAt'],
    'completedAt': None,
    'status': 'researching',
    'currentStep': 'RESEARCH',
    'language': 'he',
    'wordCount': src['wordCount'],
    'documentText': src['documentText'],
    'telemetry': {'llmCalls': 11, 'inputTokens': 284_000, 'outputTokens': 22_400, 'searchCalls': 14},
    'activeAgents': [
        {'id': f'agent-{i+1}', 'name': n, 'status': 'complete' if i == 1 else 'active'}
        for i, n in enumerate(agents)
    ],
    'searchAudit': [],
    'events': events,
}

store = dict(sessions)
# pass "--with-inflight" to add the live replay; the dashboard capture runs
# without it so the same assessment does not appear twice in the history list
if '--with-inflight' in sys.argv:
    store[inflight['id']] = inflight

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(store, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'wrote {OUT}: {len(store)} sessions')
for s in store.values():
    print(f"  {s['status']:11s} {s['title'][:58]}")
